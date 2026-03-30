"""
Analytics engine — computes engagement metrics, sentiment analysis,
trend detection, and generates summary reports from scraped data.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from models.schemas import ScrapeResult

logger = logging.getLogger(__name__)


class SocialAnalyzer:
    """Runs analytics on one or more ScrapeResult objects."""

    def __init__(self):
        self._results: list[ScrapeResult] = []

    def add(self, result: ScrapeResult):
        self._results.append(result)
        return self

    # ---- High-level report ----

    def generate_report(self, save: bool = True) -> dict:
        """Produce a combined analytics report across all added results."""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "platforms_analysed": list({r.platform for r in self._results}),
            "total_scrapes": len(self._results),
            "instagram": self._instagram_insights(),
            "twitter": self._twitter_insights(),
            "youtube": self._youtube_insights(),
            "top_hashtags": self._top_hashtags(20),
            "sentiment_summary": self._sentiment_summary(),
        }

        if save:
            path = config.DATA_DIR / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Analytics report saved to %s", path)

        return report

    # ---- Platform-specific insights ----

    def _instagram_insights(self) -> dict:
        profiles = []
        for r in self._results:
            if r.platform != "instagram":
                continue
            for p in r.profiles:
                d = p.to_dict() if hasattr(p, "to_dict") else p
                total_likes = sum(
                    post.get("likes", 0) for post in d.get("posts", [])
                )
                post_count = len(d.get("posts", []))
                profiles.append({
                    "username": d.get("username"),
                    "followers": d.get("followers", 0),
                    "post_count": post_count,
                    "total_likes": total_likes,
                    "avg_likes_per_post": round(total_likes / max(post_count, 1), 1),
                    "engagement_rate": self._engagement_rate(
                        total_likes, d.get("followers", 0), post_count
                    ),
                })
        return {"profiles_scraped": len(profiles), "profiles": profiles}

    def _twitter_insights(self) -> dict:
        all_posts = []
        for r in self._results:
            if r.platform != "twitter":
                continue
            for p in r.posts:
                all_posts.append(p.to_dict() if hasattr(p, "to_dict") else p)

        if not all_posts:
            return {"tweets_collected": 0}

        total_likes = sum(p.get("likes", 0) for p in all_posts)
        total_shares = sum(p.get("shares", 0) for p in all_posts)
        return {
            "tweets_collected": len(all_posts),
            "total_likes": total_likes,
            "total_retweets": total_shares,
            "avg_likes": round(total_likes / len(all_posts), 1),
            "avg_retweets": round(total_shares / len(all_posts), 1),
        }

    def _youtube_insights(self) -> dict:
        all_videos = []
        for r in self._results:
            if r.platform != "youtube":
                continue
            for v in r.videos:
                all_videos.append(v.to_dict() if hasattr(v, "to_dict") else v)

        if not all_videos:
            return {"videos_collected": 0}

        total_views = sum(v.get("views", 0) for v in all_videos)
        total_likes = sum(v.get("likes", 0) for v in all_videos)
        top_video = max(all_videos, key=lambda v: v.get("views", 0))
        return {
            "videos_collected": len(all_videos),
            "total_views": total_views,
            "total_likes": total_likes,
            "avg_views": round(total_views / len(all_videos)),
            "top_video": {
                "title": top_video.get("title"),
                "views": top_video.get("views"),
                "video_id": top_video.get("video_id"),
            },
        }

    # ---- Cross-platform analytics ----

    def _top_hashtags(self, n: int = 20) -> list[dict]:
        counter: Counter = Counter()
        for r in self._results:
            for p in r.posts:
                d = p.to_dict() if hasattr(p, "to_dict") else p
                for tag in d.get("hashtags", []):
                    counter[tag.lower()] += 1
            for prof in r.profiles:
                d = prof.to_dict() if hasattr(prof, "to_dict") else prof
                for post in d.get("posts", []):
                    for tag in post.get("hashtags", []):
                        counter[tag.lower()] += 1
        return [{"tag": t, "count": c} for t, c in counter.most_common(n)]

    def _sentiment_summary(self) -> dict:
        """Basic sentiment analysis using TextBlob (optional dependency)."""
        try:
            from textblob import TextBlob
        except ImportError:
            return {"available": False, "note": "Install textblob for sentiment analysis"}

        polarities = []
        for r in self._results:
            for p in r.posts:
                text = p.caption if hasattr(p, "caption") else p.get("caption", "")
                if text:
                    polarities.append(TextBlob(text).sentiment.polarity)
            for prof in r.profiles:
                posts = prof.posts if hasattr(prof, "posts") else prof.get("posts", [])
                for post in posts:
                    text = post.caption if hasattr(post, "caption") else post.get("caption", "")
                    if text:
                        polarities.append(TextBlob(text).sentiment.polarity)

        if not polarities:
            return {"available": True, "samples": 0}

        avg = sum(polarities) / len(polarities)
        positive = sum(1 for p in polarities if p > 0.1)
        negative = sum(1 for p in polarities if p < -0.1)
        neutral = len(polarities) - positive - negative

        return {
            "available": True,
            "samples": len(polarities),
            "avg_polarity": round(avg, 3),
            "positive_pct": round(positive / len(polarities) * 100, 1),
            "negative_pct": round(negative / len(polarities) * 100, 1),
            "neutral_pct": round(neutral / len(polarities) * 100, 1),
        }

    # ---- Utilities ----

    @staticmethod
    def _engagement_rate(total_likes: int, followers: int, post_count: int) -> str:
        if followers == 0 or post_count == 0:
            return "N/A"
        rate = (total_likes / post_count) / followers * 100
        return f"{rate:.2f}%"
