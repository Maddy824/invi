import copy
import csv
import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from models.schemas import ScrapeResult, ScrapedPost, ScrapedProfile, ScrapedVideo
from storage import exporter as exporter_module
from storage.exporter import DataExporter


def test_export_both_preserves_original_records_and_csv_fields(tmp_path):
    result = ScrapeResult(
        platform="twitter",
        query="demo/example",
        profiles=[{"username": "demo", "posts": [{"likes": 3}]}],
        posts=[{
            "post_id": "demo-1", "caption": "A fictional café", "likes": 3,
            "comments": [{"text": "fictional"}], "hashtags": ["demo", "test"],
            "mentions": ["fictional"],
        }],
    )
    original = copy.deepcopy(result.to_dict())
    DataExporter(tmp_path).export(result, fmt="both")

    json_path, = tmp_path.glob("twitter_demo_example_*.json")
    csv_path, = tmp_path.glob("twitter_demo_example_*.csv")
    assert json.loads(json_path.read_text(encoding="utf-8")) == original
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert rows[0]["username"] == "demo"
    assert rows[1]["caption"] == "A fictional café"
    assert rows[1]["hashtags"] == "demo, test"
    assert rows[1]["mentions"] == "fictional"
    assert "comments" not in rows[1]
    assert result.to_dict() == original


def test_export_json_only_and_empty_csv(tmp_path):
    result = ScrapeResult(platform="youtube", query="empty")
    exporter = DataExporter(tmp_path)
    exporter.export(result, fmt="json")
    assert len(list(tmp_path.glob("*.json"))) == 1
    exporter.export(result, fmt="csv")
    assert not list(tmp_path.glob("*.csv"))


def test_unsupported_format_fails(tmp_path):
    with pytest.raises(ValueError, match="Unsupported export format"):
        DataExporter(tmp_path).export(
            ScrapeResult(platform="twitter", query="demo"), fmt="unsupported"
        )


@pytest.mark.parametrize("text", [
    "=1+1", "+text", "-text", "@name", " =1+1", "\ttext", "\rtext", "\ntext",
    " \ttext", "\ufeff=1+1", "\u00a0\ufeff=1+1", "＝text", "＋text", "－text", "＠text", '=1+1,"text"',
])
def test_csv_neutralizes_formula_like_text_without_changing_json(tmp_path, text):
    result = ScrapeResult(
        platform="twitter", query="sample",
        profiles=[ScrapedProfile(platform="instagram", username="normal", bio=text)],
        posts=[ScrapedPost(platform="twitter", post_id="1", caption=text, likes=-7, mentions=[text])],
        videos=[ScrapedVideo(platform="youtube", video_id="2", title=text)],
    )
    original = copy.deepcopy(result.to_dict())
    DataExporter(tmp_path).export(result, fmt="both")

    json_path, = tmp_path.glob("*.json")
    csv_path, = tmp_path.glob("*.csv")
    assert json.loads(json_path.read_text()) == original
    with csv_path.open(newline="", encoding="utf-8") as stream:
        profile, video, post = csv.DictReader(stream)
    assert profile["bio"] == "'" + text
    assert video["title"] == "'" + text
    assert post["caption"] == "'" + text
    assert post["mentions"] == "'" + text
    assert profile["username"] == "normal"
    assert post["likes"] == "-7"
    assert result.to_dict() == original


def test_repeated_exports_at_same_timestamp_preserve_both(tmp_path, monkeypatch):
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(exporter_module, "datetime", Mock(now=Mock(return_value=fixed)))
    exporter = DataExporter(tmp_path)
    for caption in ("first", "second"):
        exporter.export(ScrapeResult(
            platform="twitter", query="sample",
            posts=[ScrapedPost(platform="twitter", post_id="1", caption=caption)],
        ), fmt="both")

    json_paths = list(tmp_path.glob("twitter_sample_20260101_000000_*.json"))
    csv_paths = list(tmp_path.glob("twitter_sample_20260101_000000_*.csv"))
    assert len(json_paths) == len(csv_paths) == 2
    assert {path.stem for path in json_paths} == {path.stem for path in csv_paths}
    assert {json.loads(path.read_text())["posts"][0]["caption"] for path in json_paths} == {"first", "second"}
    captions = set()
    for path in csv_paths:
        with path.open(newline="", encoding="utf-8") as stream:
            captions.add(next(csv.DictReader(stream))["caption"])
    assert captions == {"first", "second"}


@pytest.mark.parametrize("query", [
    pytest.param("search " + "x" * 202, id="ascii-209"),
    pytest.param("search x" + "界" * 200, id="unicode"),
])
def test_long_queries_export_to_unique_bounded_filenames(tmp_path, monkeypatch, query):
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(exporter_module, "datetime", Mock(now=Mock(return_value=fixed)))
    exporter = DataExporter(tmp_path)
    for index, target in enumerate((query, query + "different", query)):
        exporter.export(ScrapeResult(
            platform="youtube", query=target,
            videos=[ScrapedVideo(platform="youtube", video_id=str(index), title=f"Sample {index}")],
        ), fmt="both")

    json_paths = list(tmp_path.glob("youtube_search_*.json"))
    csv_paths = list(tmp_path.glob("youtube_search_*.csv"))
    assert len(json_paths) == len(csv_paths) == 3
    assert {path.stem for path in json_paths} == {path.stem for path in csv_paths}
    for path in json_paths + csv_paths:
        assert len(path.name.encode("utf-8")) <= 255
        assert path.name.startswith(f"youtube_search_{query[7:17]}")
        assert "_20260101_000000_" in path.stem
        assert len(path.stem.rsplit("_", 1)[1]) == 32
    assert {
        json.loads(path.read_text())["videos"][0]["video_id"]: json.loads(path.read_text())["query"]
        for path in json_paths
    } == {"0": query, "1": query + "different", "2": query}
    ids = set()
    for path in csv_paths:
        with path.open(newline="", encoding="utf-8") as stream:
            ids.add(next(csv.DictReader(stream))["video_id"])
    assert ids == {"0", "1", "2"}
