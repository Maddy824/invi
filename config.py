"""
Configuration management for the social media scraping system.
Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# --- Platform API Keys (loaded from .env) ---
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
WEBSCRAPING_AI_KEY = os.getenv("WEBSCRAPING_AI_KEY", "")

# --- Instagram settings ---
INSTAGRAM_TARGETS = os.getenv("INSTAGRAM_TARGETS", "").split(",")
INSTAGRAM_PROXY = os.getenv("INSTAGRAM_PROXY", "")

# --- Twitter/X settings ---
TWITTER_SEARCH_QUERIES = os.getenv("TWITTER_SEARCH_QUERIES", "").split(",")
TWITTER_TWEET_COUNT = int(os.getenv("TWITTER_TWEET_COUNT", "100"))

# --- YouTube settings ---
YOUTUBE_SEARCH_QUERIES = os.getenv("YOUTUBE_SEARCH_QUERIES", "").split(",")
YOUTUBE_MAX_RESULTS = int(os.getenv("YOUTUBE_MAX_RESULTS", "10"))

# --- Scheduler settings ---
SCRAPE_INTERVAL_MINUTES = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))

# --- MongoDB settings (optional) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "social_scraper")

# --- Selenium / Browser settings ---
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# --- Export settings ---
EXPORT_FORMAT = os.getenv("EXPORT_FORMAT", "json")  # json | csv | both
