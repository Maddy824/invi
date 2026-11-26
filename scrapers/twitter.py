"""
Twitter / X scraper — searches tweets via the guest-token approach
through the webscraping.ai proxy, normalizes results into structured models.
"""

import http.client
import json
import logging
import urllib.parse
from contextlib import closing
from typing import Optional

import config
from models.schemas import ScrapedPost, ScrapeResult
from scrapers.base import BaseScraper
from scrapers.errors import ScrapeError, safe_error_message

logger = logging.getLogger(__name__)

API_HOST = "api.webscraping.ai"


class TwitterScraper(BaseScraper):
    PLATFORM = "twitter"

    def __init__(self):
        super().__init__()
        self._guest_token: Optional[str] = None

    def scrape(self, target: str) -> ScrapeResult:
        """Search Twitter for *target* query and return structured results."""
        result = ScrapeResult(platform=self.PLATFORM, query=target)

        if not config.TWITTER_BEARER_TOKEN:
            result.errors.append("TWITTER_BEARER_TOKEN not configured")
            return result
        if not config.WEBSCRAPING_AI_KEY:
            result.errors.append("WEBSCRAPING_AI_KEY not configured")
            return result

        try:
            self._acquire_guest_token()
            tweets = self._search_tweets(target)
            result.posts = tweets
        except Exception as exc:
            message = safe_error_message(exc)
            logger.error("Twitter scrape failed for '%s': %s", target, message)
            result.errors.append(message)

        return result

    # ---- internal helpers ----

    def _conn(self) -> http.client.HTTPSConnection:
        return http.client.HTTPSConnection(API_HOST, timeout=config.HTTP_TIMEOUT_SECONDS)

    def _acquire_guest_token(self):
        if self._guest_token:
            return

        params = {
            "api_key": config.WEBSCRAPING_AI_KEY,
            "js": "false",
            "timeout": 25000,
            "url": "https://api.twitter.com/1.1/guest/activate.json",
            "headers[Authorization]": f"Bearer {config.TWITTER_BEARER_TOKEN}",
        }
        data = self._request_json("POST", params, "Twitter guest token request")

        token = data.get("guest_token")
        if data.get("errors") or not isinstance(token, str) or not token.strip():
            raise ScrapeError("Failed to obtain Twitter guest token")

        self._guest_token = token
        logger.info("Acquired Twitter guest token")

    def _search_tweets(self, query: str) -> list[ScrapedPost]:
        twitter_params = {
            "q": query,
            "count": config.TWITTER_TWEET_COUNT,
            "include_want_retweets": 1,
            "include_quote_count": "true",
            "include_reply_count": 1,
            "tweet_mode": "extended",
            "include_entities": "true",
            "include_user_entities": "true",
            "simple_quoted_tweet": "true",
            "tweet_search_mode": "live",
            "query_source": "typed_query",
        }

        api_params = {
            "api_key": config.WEBSCRAPING_AI_KEY,
            "js": "false",
            "timeout": 25000,
            "url": "https://api.twitter.com/2/search/adaptive.json?"
            + urllib.parse.urlencode(twitter_params),
            "headers[Authorization]": f"Bearer {config.TWITTER_BEARER_TOKEN}",
            "headers[X-Guest-Token]": self._guest_token,
        }

        data = self._request_json("GET", api_params, "Twitter search")
        return self._parse_tweets(data)

    def _request_json(self, method: str, params: dict, operation: str) -> dict:
        with closing(self._conn()) as conn:
            conn.request(method, f"/html?{urllib.parse.urlencode(params)}")
            res = conn.getresponse()
            if res.status != 200:
                raise ScrapeError(f"{operation} failed (HTTP {res.status})")
            data = json.loads(res.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ScrapeError(f"{operation} returned an unexpected response")
        return data

    def _parse_tweets(self, data: dict) -> list[ScrapedPost]:
        objects = data.get("globalObjects")
        if (
            data.get("errors")
            or not isinstance(objects, dict)
            or not isinstance(objects.get("tweets"), dict)
        ):
            raise ScrapeError("Twitter search returned an error or unexpected response")
        tweets_map = objects["tweets"]
        posts: list[ScrapedPost] = []
        for tweet_id, tweet in tweets_map.items():
            text = tweet.get("full_text", tweet.get("text", ""))
            hashtags = [
                h["text"]
                for h in tweet.get("entities", {}).get("hashtags", [])
            ]
            mentions = [
                m["screen_name"]
                for m in tweet.get("entities", {}).get("user_mentions", [])
            ]

            posts.append(
                ScrapedPost(
                    platform=self.PLATFORM,
                    post_id=tweet_id,
                    caption=text,
                    likes=tweet.get("favorite_count", 0),
                    shares=tweet.get("retweet_count", 0),
                    views=0,
                    comments_count=tweet.get("reply_count", 0),
                    timestamp=tweet.get("created_at", ""),
                    hashtags=hashtags,
                    mentions=mentions,
                )
            )

        logger.info("Parsed %d tweets for search", len(posts))
        return posts
