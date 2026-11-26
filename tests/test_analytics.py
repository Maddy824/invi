import json
from datetime import datetime, timezone
from unittest.mock import Mock

import config
from analytics import analyzer as analyzer_module
from analytics.analyzer import SocialAnalyzer
from models.schemas import ScrapeResult, ScrapedPost, ScrapedProfile, ScrapedVideo


def test_platform_metrics_and_caption_sentiment():
    analyzer = SocialAnalyzer()
    analyzer.add(ScrapeResult(
        platform="instagram", query="demo",
        profiles=[ScrapedProfile(
            platform="instagram", username="demo", followers=100,
            posts=[
                ScrapedPost(platform="instagram", post_id="1", likes=12,
                            caption="Wonderful.", hashtags=["Demo", "plants"]),
                ScrapedPost(platform="instagram", post_id="2", likes=8,
                            caption="Terrible.", hashtags=["demo"]),
            ],
        )],
    ))
    analyzer.add(ScrapeResult(
        platform="twitter", query="demo",
        posts=[
            ScrapedPost(platform="twitter", post_id="3", likes=5, shares=1,
                        caption="Good.", hashtags=["demo"]),
            ScrapedPost(platform="twitter", post_id="4", likes=15, shares=3,
                        caption="Bad.", hashtags=["plants"]),
        ],
    ))
    analyzer.add(ScrapeResult(
        platform="youtube", query="demo",
        videos=[
            ScrapedVideo(platform="youtube", video_id="5", views=120, likes=10),
            ScrapedVideo(platform="youtube", video_id="6", views=80, likes=6),
        ],
    ))

    report = analyzer.generate_report(save=False)
    assert report["platforms_analysed"] == ["instagram", "twitter", "youtube"]
    assert report["total_scrapes"] == 3
    assert report["instagram"]["profiles"][0] == {
        "username": "demo", "followers": 100, "post_count": 2, "total_likes": 20,
        "avg_likes_per_post": 10.0, "engagement_rate": "10.00%",
    }
    assert report["twitter"] == {
        "tweets_collected": 2, "total_likes": 20, "total_retweets": 4,
        "avg_likes": 10.0, "avg_retweets": 2.0,
    }
    assert report["youtube"]["videos_collected"] == 2
    assert report["youtube"]["total_views"] == 200
    assert report["youtube"]["total_likes"] == 16
    assert report["youtube"]["avg_views"] == 100
    assert report["youtube"]["top_video"]["video_id"] == "5"
    assert report["top_hashtags"] == [
        {"tag": "demo", "count": 3}, {"tag": "plants", "count": 2},
    ]
    assert report["sentiment_summary"]["samples"] == 4
    assert report["sentiment_summary"]["positive_pct"] == 50.0
    assert report["sentiment_summary"]["negative_pct"] == 50.0


def test_empty_report_and_zero_followers():
    analyzer = SocialAnalyzer()
    report = analyzer.generate_report(save=False)
    assert report["total_scrapes"] == 0
    assert report["instagram"]["profiles_scraped"] == 0
    assert report["twitter"]["tweets_collected"] == 0
    assert report["youtube"]["videos_collected"] == 0
    assert report["top_hashtags"] == []
    assert report["sentiment_summary"]["samples"] == 0
    assert SocialAnalyzer._engagement_rate(10, 0, 1) == "N/A"
    assert SocialAnalyzer._engagement_rate(10, 10, 0) == "N/A"


def test_missing_and_null_numeric_fields():
    analyzer = SocialAnalyzer()
    analyzer.add(ScrapeResult(
        platform="instagram", query="sample",
        profiles=[
            {"username": "null", "followers": None, "posts": [{"likes": None}, {}, {"likes": 9}]},
            {"username": "missing", "posts": [{"likes": 3}]},
        ],
    ))
    analyzer.add(ScrapeResult(
        platform="twitter", query="sample",
        posts=[{"likes": None, "shares": None}, {}, {"likes": 12, "shares": 6}],
    ))
    analyzer.add(ScrapeResult(
        platform="youtube", query="sample",
        videos=[
            {"video_id": "null", "views": None, "likes": None},
            {"video_id": "missing"},
            {"video_id": "top", "title": "Sample", "views": 90, "likes": 15},
        ],
    ))
    report = analyzer.generate_report(save=False)
    assert report["instagram"]["profiles"] == [
        {"username": "null", "followers": 0, "post_count": 3, "total_likes": 9,
         "avg_likes_per_post": 3.0, "engagement_rate": "N/A"},
        {"username": "missing", "followers": 0, "post_count": 1, "total_likes": 3,
         "avg_likes_per_post": 3.0, "engagement_rate": "N/A"},
    ]
    assert report["twitter"] == {
        "tweets_collected": 3, "total_likes": 12, "total_retweets": 6,
        "avg_likes": 4.0, "avg_retweets": 2.0,
    }
    assert report["youtube"] == {
        "videos_collected": 3, "total_views": 90, "total_likes": 15,
        "avg_views": 30, "top_video": {"video_id": "top", "title": "Sample", "views": 90},
    }
    only_null_video = SocialAnalyzer().add(ScrapeResult(
        platform="youtube", query="sample", videos=[{"video_id": "null", "views": None}],
    )).generate_report(save=False)
    assert only_null_video["youtube"]["top_video"]["views"] == 0


def test_save_demo_report(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    report = SocialAnalyzer().generate_report(demo=True)
    assert report["synthetic_demo"] is True
    path, = tmp_path.glob("report_demo_*.json")
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_repeated_reports_at_same_timestamp_preserve_both(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(analyzer_module, "datetime", Mock(now=Mock(return_value=fixed)))
    analyzer = SocialAnalyzer()
    first = analyzer.generate_report()
    analyzer.add(ScrapeResult(platform="youtube", query="sample"))
    second = analyzer.generate_report()
    reports = [json.loads(path.read_text()) for path in tmp_path.glob("report_20260101_000000_*.json")]
    assert len(reports) == 2
    assert first in reports
    assert second in reports
    assert first != second
