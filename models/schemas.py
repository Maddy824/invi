"""
Structured data models for scraped social media content.
All scrapers normalize their output into these schemas.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class ScrapedComment:
    text: str
    author: str = ""
    likes: int = 0
    timestamp: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class ScrapedPost:
    platform: str
    post_id: str
    caption: str = ""
    likes: int = 0
    views: int = 0
    shares: int = 0
    comments_count: int = 0
    comments: list = field(default_factory=list)
    media_url: str = ""
    timestamp: Optional[str] = None
    hashtags: list = field(default_factory=list)
    mentions: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["comments"] = [c if isinstance(c, dict) else c for c in d["comments"]]
        return d


@dataclass
class ScrapedProfile:
    platform: str
    username: str
    full_name: str = ""
    bio: str = ""
    category: str = ""
    followers: int = 0
    following: int = 0
    post_count: int = 0
    posts: list = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self):
        d = asdict(self)
        d["posts"] = [p if isinstance(p, dict) else p for p in d["posts"]]
        return d


@dataclass
class ScrapedVideo:
    platform: str
    video_id: str
    title: str = ""
    channel: str = ""
    views: int = 0
    likes: int = 0
    comments_count: int = 0
    description: str = ""
    published_at: str = ""
    tags: list = field(default_factory=list)
    duration: str = ""
    thumbnail_url: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class ScrapeResult:
    platform: str
    query: str
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    profiles: list = field(default_factory=list)
    videos: list = field(default_factory=list)
    posts: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def to_dict(self):
        return {
            "platform": self.platform,
            "query": self.query,
            "scraped_at": self.scraped_at,
            "profiles": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.profiles],
            "videos": [v.to_dict() if hasattr(v, "to_dict") else v for v in self.videos],
            "posts": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.posts],
            "errors": self.errors,
        }
