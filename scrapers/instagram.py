"""
Instagram scraper — extracts profile metadata, posts, captions,
engagement metrics, and comments using the public JSON endpoint
with stealth browser fallback.
"""

import json
import logging
import re
import time
from typing import Optional

import requests_html

import config
from models.schemas import ScrapedComment, ScrapedPost, ScrapedProfile, ScrapeResult
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class InstagramScraper(BaseScraper):
    PLATFORM = "instagram"

    def scrape(self, target: str) -> ScrapeResult:
        """Scrape an Instagram profile by *target* username."""
        result = ScrapeResult(platform=self.PLATFORM, query=target)
        try:
            profile = self._fetch_profile(target)
            if profile:
                result.profiles.append(profile)
        except Exception as exc:
            logger.error("Instagram scrape failed for %s: %s", target, exc)
            result.errors.append(str(exc))
        return result

    # ---- internal helpers ----

    def _fetch_profile(self, username: str) -> Optional[ScrapedProfile]:
        url = f"https://instagram.com/{username}/?__a=1&__d=dis"
        session = requests_html.HTMLSession()

        headers = {"User-Agent": config.USER_AGENT}
        response = self.retry(lambda: session.get(url, headers=headers))

        if response.status_code != 200:
            logger.warning("HTTP %d for %s", response.status_code, username)
            return None

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning("Non-JSON response for %s – trying browser fallback", username)
            return self._browser_fallback(username)

        user_data = data.get("graphql", {}).get("user") or data.get("data", {}).get("user")
        if not user_data:
            logger.warning("No user data in JSON for %s", username)
            return None

        return self._parse_profile(username, user_data)

    def _parse_profile(self, username: str, user_data: dict) -> ScrapedProfile:
        posts = []
        edges = (
            user_data.get("edge_owner_to_timeline_media", {}).get("edges", [])
        )
        for edge in edges:
            node = edge.get("node", {})
            post = self._parse_post(node)
            posts.append(post)

        return ScrapedProfile(
            platform=self.PLATFORM,
            username=username,
            full_name=user_data.get("full_name", ""),
            bio=user_data.get("biography", ""),
            category=user_data.get("category_name", ""),
            followers=user_data.get("edge_followed_by", {}).get("count", 0),
            following=user_data.get("edge_follow", {}).get("count", 0),
            post_count=user_data.get("edge_owner_to_timeline_media", {}).get("count", 0),
            posts=posts,
        )

    def _parse_post(self, node: dict) -> ScrapedPost:
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        caption = ""
        if caption_edges:
            caption = caption_edges[0].get("node", {}).get("text", "")

        hashtags = re.findall(r"#(\w+)", caption)
        mentions = re.findall(r"@(\w+)", caption)

        comments = []
        comment_edges = node.get("edge_media_to_parent_comment", {}).get("edges", [])
        for ce in comment_edges:
            cn = ce.get("node", {})
            comments.append(
                ScrapedComment(
                    text=cn.get("text", ""),
                    author=cn.get("owner", {}).get("username", ""),
                    likes=cn.get("edge_liked_by", {}).get("count", 0),
                )
            )

        return ScrapedPost(
            platform=self.PLATFORM,
            post_id=node.get("shortcode", ""),
            caption=caption,
            likes=node.get("edge_liked_by", {}).get("count", 0),
            comments_count=node.get("edge_media_to_comment", {}).get("count", 0),
            comments=comments,
            media_url=node.get("display_url", ""),
            timestamp=str(node.get("taken_at_timestamp", "")),
            hashtags=hashtags,
            mentions=mentions,
        )

    def _browser_fallback(self, username: str) -> Optional[ScrapedProfile]:
        """Use headless Selenium as a fallback if the JSON endpoint fails."""
        try:
            driver = self.get_browser()
            driver.get(f"https://www.instagram.com/{username}/")
            time.sleep(3)

            page_source = driver.page_source
            match = re.search(r"window\._sharedData\s*=\s*({.*?});</script>", page_source)
            if not match:
                logger.warning("Could not extract sharedData for %s via browser", username)
                return None

            shared = json.loads(match.group(1))
            user_data = (
                shared.get("entry_data", {})
                .get("ProfilePage", [{}])[0]
                .get("graphql", {})
                .get("user", {})
            )
            if user_data:
                return self._parse_profile(username, user_data)
            return None
        except Exception as exc:
            logger.error("Browser fallback failed for %s: %s", username, exc)
            return None
