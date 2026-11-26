import csv
import json
import os
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import config
import main


ROOT = Path(__file__).resolve().parents[1]

# Exercise the CLI entry point in a fresh process. Any platform import or
# attempted network access is a test failure, even if caught by the CLI.
OFFLINE_CLI = """
import importlib.abc
import runpy
import socket
import sys
from pathlib import Path

attempts = []

def forbid(*args, **kwargs):
    attempts.append("network")
    raise AssertionError("Network access is forbidden in the demo")

socket.socket.connect = forbid
socket.socket.connect_ex = forbid
socket.create_connection = forbid
socket.getaddrinfo = forbid

class NoPlatformImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("scrapers.", "scheduler.")) or fullname.split(".")[0] in {
            "selenium", "selenium_stealth", "requests_html", "lxml_html_clean",
            "googleapiclient",
        }:
            attempts.append(fullname)
            raise ImportError(f"Unavailable platform dependency: {fullname}")

sys.meta_path.insert(0, NoPlatformImports())

import config
config.DATA_DIR = Path(sys.argv[1])
sys.argv = ["main.py", *sys.argv[2:]]
try:
    runpy.run_path("main.py", run_name="__main__")
finally:
    assert not attempts, attempts
"""


def offline_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-c", OFFLINE_CLI, str(tmp_path), *args],
        cwd=ROOT,
        env={
            **os.environ,
            "YOUTUBE_API_KEY": "",
            "TWITTER_BEARER_TOKEN": "",
            "WEBSCRAPING_AI_KEY": "",
            "EXPORT_FORMAT": "json",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_help_without_platform_dependencies(tmp_path):
    process = offline_cli(tmp_path, "--help")
    assert process.returncode == 0, process.stderr
    assert "--demo" in process.stdout
    assert "--report" not in process.stdout
    assert not list(tmp_path.iterdir())


def test_demo_is_offline_and_exports_real_report(tmp_path):
    process = offline_cli(tmp_path, "--demo")
    assert process.returncode == 0, process.stdout + process.stderr
    assert "Offline demo: synthetic data only" in process.stdout
    assert "Synthetic analytics report" in process.stdout
    report_path, = tmp_path.glob("report_demo_*.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["synthetic_demo"] is True
    assert report["total_scrapes"] == 3
    assert report["instagram"]["profiles"][0]["engagement_rate"] == "10.00%"
    assert report["youtube"]["total_views"] == 200
    assert report["sentiment_summary"]["samples"] == 4
    assert report["top_hashtags"][0] == {"tag": "demo", "count": 3}
    for platform, row_count in [("instagram", 1), ("twitter", 2), ("youtube", 2)]:
        json_path, = tmp_path.glob(f"{platform}_demo_synthetic_*.json")
        assert json.loads(json_path.read_text(encoding="utf-8"))["query"] == "demo_synthetic"
        csv_path, = tmp_path.glob(f"{platform}_demo_synthetic_*.csv")
        with csv_path.open(encoding="utf-8", newline="") as stream:
            assert len(list(csv.DictReader(stream))) == row_count


@pytest.mark.parametrize("platform,missing", [
    ("youtube", "YOUTUBE_API_KEY"),
    ("twitter", "TWITTER_BEARER_TOKEN"),
    ("twitter", "WEBSCRAPING_AI_KEY"),
])
def test_missing_credentials_returns_nonzero(live_config, tmp_path, monkeypatch, caplog, platform, missing):
    monkeypatch.setattr(config, missing, "")
    monkeypatch.setattr(sys, "argv", ["main.py", "--platform", platform, "--target", "sample"])
    assert main.main() == 1
    assert f"{missing} not configured" in caplog.text
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("platform,key,count", [
    ("instagram", "profiles", "profiles_scraped"),
    ("twitter", "posts", "tweets_collected"),
    ("youtube", "videos", "videos_collected"),
])
def test_successful_live_dispatch(live_config, tmp_path, monkeypatch, mock_instagram, mock_twitter,
                                  mock_youtube, platform, key, count):
    connect, _ = mock_twitter(
        (200, {"guest_token": "fictional-guest"}),
        (200, {"globalObjects": {"tweets": {"sample": {"text": "Fictional post"}}}}),
    )
    build, _ = mock_youtube
    monkeypatch.setattr(sys, "argv", ["main.py", "--platform", platform, "--target", "sample"])
    assert main.main() == 0
    result_path, = tmp_path.glob(f"{platform}_sample_*.json")
    result = json.loads(result_path.read_text())
    assert result["platform"] == platform
    assert len(result[key]) == 1
    assert not result["errors"]
    report_path, = tmp_path.glob("report_*.json")
    report = json.loads(report_path.read_text())
    assert report["platforms_analysed"] == [platform]
    assert report[platform][count] == 1
    assert mock_instagram.call_count == (1 if platform == "instagram" else 0)
    assert connect.call_count == (2 if platform == "twitter" else 0)
    assert build.call_count == (1 if platform == "youtube" else 0)


def test_failed_single_response_returns_nonzero(live_config, tmp_path, monkeypatch, mock_instagram):
    mock_instagram.return_value.json.return_value = {"data": {}}
    monkeypatch.setattr(sys, "argv", ["main.py", "--platform", "instagram", "--target", "sample"])
    assert main.main() == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [[], ["--schedule"]])
def test_partial_cycle_finishes_all_targets(live_config, tmp_path, monkeypatch, caplog, mock_instagram,
                                           mock_twitter, mock_youtube, args):
    monkeypatch.setattr(config, "INSTAGRAM_TARGETS", ["bad", "good"])
    monkeypatch.setattr(config, "TWITTER_SEARCH_QUERIES", ["bad", "good"])
    monkeypatch.setattr(config, "YOUTUBE_SEARCH_QUERIES", ["bad", "good"])
    monkeypatch.setattr(config, "SCRAPE_INTERVAL_MINUTES", 1)
    mock_instagram.side_effect = [Mock(status_code=503), mock_instagram.return_value]
    connect, _ = mock_twitter(
        (200, {"guest_token": "fictional-guest"}),
        (200, {"errors": [{"message": "unavailable"}]}),
        (200, {"globalObjects": {"tweets": {"sample": {"text": "Fictional post"}}}}),
    )
    _, service = mock_youtube
    search = service.search.return_value.list.return_value.execute
    secret = config.YOUTUBE_API_KEY
    encoded = urllib.parse.quote_plus(secret)
    search.side_effect = [RuntimeError(f"Upstream failure: {secret} {encoded}"), search.return_value]
    monkeypatch.setattr(sys, "argv", ["main.py", *args])

    assert main.main() == 1
    assert mock_instagram.call_count == 2
    assert connect.call_count == 3
    assert search.call_count == 2
    for platform in ("instagram", "twitter", "youtube"):
        assert len(list(tmp_path.glob(f"{platform}_good_*.json"))) == 1
        assert not list(tmp_path.glob(f"{platform}_bad_*.json"))
    report_path, = tmp_path.glob("report_*.json")
    report_text = report_path.read_text()
    assert secret not in report_text + caplog.text
    assert encoded not in report_text + caplog.text
    report = json.loads(report_text)
    assert report["attempted_scrapes"] == 6
    assert report["total_scrapes"] == 3
    assert report["failed_scrapes"] == 3
    assert report["platforms_analysed"] == ["instagram", "twitter", "youtube"]
    assert [(failure["platform"], failure["query"]) for failure in report["failures"]] == [
        ("instagram", "bad"), ("twitter", "bad"), ("youtube", "bad"),
    ]
    assert all(failure["errors"] for failure in report["failures"])
    assert report["instagram"]["profiles_scraped"] == 1
    assert report["twitter"]["tweets_collected"] == 1
    assert report["youtube"]["videos_collected"] == 1


def test_cycle_saves_failure_report_with_null_followers(live_config, tmp_path, monkeypatch,
                                                        mock_instagram, mock_youtube):
    monkeypatch.setattr(config, "INSTAGRAM_TARGETS", ["sample"])
    monkeypatch.setattr(config, "TWITTER_SEARCH_QUERIES", ["bad"])
    monkeypatch.setattr(config, "TWITTER_BEARER_TOKEN", "")
    monkeypatch.setattr(config, "YOUTUBE_SEARCH_QUERIES", ["good"])
    user = mock_instagram.return_value.json.return_value["graphql"]["user"]
    user["edge_followed_by"]["count"] = None
    monkeypatch.setattr(sys, "argv", ["main.py"])

    assert main.main() == 1
    instagram_path, = tmp_path.glob("instagram_sample_*.json")
    assert json.loads(instagram_path.read_text())["profiles"][0]["followers"] is None
    youtube_path, = tmp_path.glob("youtube_good_*.json")
    assert json.loads(youtube_path.read_text())["videos"][0]["views"] == 200
    report_path, = tmp_path.glob("report_*.json")
    report = json.loads(report_path.read_text())
    assert report["attempted_scrapes"] == 3
    assert report["total_scrapes"] == 2
    assert report["failed_scrapes"] == 1
    assert report["failures"] == [
        {"platform": "twitter", "query": "bad", "errors": ["TWITTER_BEARER_TOKEN not configured"]},
    ]
    assert report["instagram"]["profiles"][0] == {
        "username": "sample", "followers": 0, "post_count": 1,
        "total_likes": 10, "avg_likes_per_post": 10.0, "engagement_rate": "N/A",
    }
    assert report["youtube"]["total_views"] == 200
    assert not report.get("analytics_errors")


@pytest.mark.parametrize("failed_scrape", [False, True])
def test_cycle_preserves_report_if_analytics_section_fails(live_config, tmp_path, monkeypatch,
                                                          mock_instagram, mock_youtube, failed_scrape):
    monkeypatch.setattr(config, "INSTAGRAM_TARGETS", ["sample"])
    monkeypatch.setattr(config, "YOUTUBE_SEARCH_QUERIES", ["good"])
    if failed_scrape:
        monkeypatch.setattr(config, "TWITTER_SEARCH_QUERIES", ["bad"])
        monkeypatch.setattr(config, "TWITTER_BEARER_TOKEN", "")
    user = mock_instagram.return_value.json.return_value["graphql"]["user"]
    user["edge_followed_by"]["count"] = "invalid count"
    monkeypatch.setattr(sys, "argv", ["main.py"])

    assert main.main() == 1
    assert len(list(tmp_path.glob("youtube_good_*.json"))) == 1
    report_path, = tmp_path.glob("report_*.json")
    report = json.loads(report_path.read_text())
    assert report["attempted_scrapes"] == 2 + int(failed_scrape)
    assert report["total_scrapes"] == 2
    assert report["failed_scrapes"] == len(report["failures"]) == int(failed_scrape)
    if failed_scrape:
        assert report["failures"][0]["query"] == "bad"
    assert report["instagram"] is None
    assert report["analytics_errors"] == {"instagram": "Unexpected error (TypeError)"}
    assert report["youtube"]["total_views"] == 200


def test_successful_cycle_returns_zero(live_config, tmp_path, monkeypatch, mock_instagram,
                                       mock_twitter, mock_youtube):
    monkeypatch.setattr(config, "INSTAGRAM_TARGETS", ["sample"])
    monkeypatch.setattr(config, "TWITTER_SEARCH_QUERIES", ["sample"])
    monkeypatch.setattr(config, "YOUTUBE_SEARCH_QUERIES", ["sample"])
    mock_twitter(
        (200, {"guest_token": "fictional-guest"}),
        (200, {"globalObjects": {"tweets": {"sample": {"text": "Fictional post"}}}}),
    )
    monkeypatch.setattr(sys, "argv", ["main.py"])

    assert main.main() == 0
    report_path, = tmp_path.glob("report_*.json")
    report = json.loads(report_path.read_text())
    assert report["attempted_scrapes"] == report["total_scrapes"] == 3
    assert report["failed_scrapes"] == 0
    assert report["failures"] == []
    assert report["platforms_analysed"] == ["instagram", "twitter", "youtube"]


def test_cycle_continues_after_missing_credentials(live_config, tmp_path, monkeypatch, mock_youtube):
    monkeypatch.setattr(config, "TWITTER_SEARCH_QUERIES", ["bad1", "bad2"])
    monkeypatch.setattr(config, "TWITTER_BEARER_TOKEN", "")
    monkeypatch.setattr(config, "YOUTUBE_SEARCH_QUERIES", ["good"])
    monkeypatch.setattr(sys, "argv", ["main.py"])

    assert main.main() == 1
    report_path, = tmp_path.glob("report_*.json")
    report = json.loads(report_path.read_text())
    assert report["total_scrapes"] == 1
    assert report["failed_scrapes"] == 2
    assert report["attempted_scrapes"] == 3
    assert report["platforms_analysed"] == ["youtube"]
    assert report["failures"] == [
        {"platform": "twitter", "query": target, "errors": ["TWITTER_BEARER_TOKEN not configured"]}
        for target in ("bad1", "bad2")
    ]


def test_schedule_runs_due_jobs_at_positive_interval(live_config, tmp_path, monkeypatch, mock_youtube):
    from scheduler import runner

    class Clock:
        now_value = datetime(2026, 1, 1)

        @classmethod
        def now(cls):
            return cls.now_value

    start = Clock.now()
    run_times = []

    def advance(seconds):
        Clock.now_value += timedelta(seconds=seconds)
        assert Clock.now() <= start + timedelta(minutes=2)

    _, service = mock_youtube
    search = service.search.return_value.list.return_value.execute

    def respond():
        run_times.append(Clock.now())
        if len(run_times) == 3:
            return {"error": {"message": "unavailable"}}
        return search.return_value

    search.side_effect = respond
    monkeypatch.setattr(runner.schedule, "datetime", SimpleNamespace(datetime=Clock, timedelta=timedelta))
    monkeypatch.setattr(runner.time, "sleep", advance)
    monkeypatch.setattr(config, "YOUTUBE_SEARCH_QUERIES", ["sample"])
    monkeypatch.setattr(config, "SCRAPE_INTERVAL_MINUTES", 1)
    monkeypatch.setattr(sys, "argv", ["main.py", "--schedule"])

    assert main.main() == 1
    assert run_times == [start, start + timedelta(minutes=1), start + timedelta(minutes=2)]
    reports = [json.loads(path.read_text()) for path in tmp_path.glob("report_*.json")]
    assert len(reports) == 3
    assert sorted(report["total_scrapes"] for report in reports) == [0, 1, 1]
    assert sorted(report["failed_scrapes"] for report in reports) == [0, 0, 1]
    assert len(list(tmp_path.glob("youtube_sample_*.json"))) == 2


def test_incomplete_platform_argument_does_not_start_cycle(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--platform", "youtube"])
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert exc.value.code == 2
