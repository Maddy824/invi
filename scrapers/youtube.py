"""
YouTube scraper — searches videos, extracts metadata and engagement
metrics via the official YouTube Data API v3.
"""

import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config
from models.schemas import ScrapedVideo, ScrapeResult
from scrapers.base import BaseScraper
from scrapers.errors import ScrapeError, safe_error_message

logger = logging.getLogger(__name__)


class YouTubeScraper(BaseScraper):
    PLATFORM = "youtube"

    def __init__(self):
        super().__init__()
        self._service = None
        # The client logs raw response details and request URLs (including keys)
        # before raising HttpError. Keep only our sanitized diagnostics.
        for name in ("googleapiclient.discovery", "googleapiclient.http", "googleapiclient.model"):
            logging.getLogger(name).disabled = True

    @property
    def youtube(self):
        if self._service is None:
            if not config.YOUTUBE_API_KEY:
                raise ScrapeError("YOUTUBE_API_KEY not configured")
            self._service = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
        return self._service

    def scrape(self, target: str) -> ScrapeResult:
        """Search YouTube for *target* query and return structured video data."""
        result = ScrapeResult(platform=self.PLATFORM, query=target)

        try:
            videos = self._search_videos(target)
            result.videos = videos
        except HttpError as exc:
            # The upstream message and URL may contain the API key.
            status = exc.resp.status
            message = "YouTube API request failed"
            if isinstance(status, int) and 100 <= status <= 599:
                message += f" (HTTP {status})"
            logger.error("YouTube scrape failed for '%s': %s", target, message)
            result.errors.append(message)
        except Exception as exc:
            message = safe_error_message(exc)
            logger.error("YouTube scrape failed for '%s': %s", target, message)
            result.errors.append(message)

        return result

    # ---- internal helpers ----

    def _search_videos(self, query: str) -> list[ScrapedVideo]:
        search_response = (
            self.youtube.search()
            .list(q=query, type="video", part="id,snippet", maxResults=config.YOUTUBE_MAX_RESULTS)
            .execute()
        )
        if (
            not isinstance(search_response, dict)
            or not isinstance(search_response.get("items"), list)
            or search_response.get("error")
        ):
            raise ScrapeError("YouTube search returned an error or unexpected response")

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
        if (
            not isinstance(stats_response, dict)
            or not isinstance(stats_response.get("items"), list)
            or stats_response.get("error")
        ):
            raise ScrapeError("YouTube video details returned an error or unexpected response")

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
