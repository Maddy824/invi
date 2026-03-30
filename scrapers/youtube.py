"""
YouTube scraper — searches videos, extracts metadata and engagement
metrics via the official YouTube Data API v3.
"""

import logging
from typing import Optional

from googleapiclient.discovery import build

import config
from models.schemas import ScrapedVideo, ScrapeResult
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class YouTubeScraper(BaseScraper):
    PLATFORM = "youtube"

    def __init__(self):
        super().__init__()
        self._service = None

    @property
    def youtube(self):
        if self._service is None:
            if not config.YOUTUBE_API_KEY:
                raise RuntimeError("YOUTUBE_API_KEY not configured")
            self._service = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
        return self._service

    def scrape(self, target: str) -> ScrapeResult:
        """Search YouTube for *target* query and return structured video data."""
        result = ScrapeResult(platform=self.PLATFORM, query=target)

        try:
            videos = self._search_videos(target)
            result.videos = videos
        except Exception as exc:
            logger.error("YouTube scrape failed for '%s': %s", target, exc)
            result.errors.append(str(exc))

        return result

    # ---- internal helpers ----

    def _search_videos(self, query: str) -> list[ScrapedVideo]:
        search_response = (
            self.youtube.search()
            .list(q=query, type="video", part="id,snippet", maxResults=config.YOUTUBE_MAX_RESULTS)
            .execute()
        )

        video_ids = [
            item["id"]["videoId"]
            for item in search_response.get("items", [])
            if "videoId" in item.get("id", {})
        ]

        if not video_ids:
            return []

        stats_response = (
            self.youtube.videos()
            .list(part="statistics,contentDetails,snippet", id=",".join(video_ids))
            .execute()
        )

        videos: list[ScrapedVideo] = []
        for item in stats_response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            details = item.get("contentDetails", {})

            videos.append(
                ScrapedVideo(
                    platform=self.PLATFORM,
                    video_id=item["id"],
                    title=snippet.get("title", ""),
                    channel=snippet.get("channelTitle", ""),
                    description=snippet.get("description", ""),
                    published_at=snippet.get("publishedAt", ""),
                    tags=snippet.get("tags", []),
                    views=int(stats.get("viewCount", 0)),
                    likes=int(stats.get("likeCount", 0)),
                    comments_count=int(stats.get("commentCount", 0)),
                    duration=details.get("duration", ""),
                    thumbnail_url=snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", ""),
                )
            )

        logger.info("Fetched %d YouTube videos for '%s'", len(videos), query)
        return videos
