"""
Abstract base class for all platform scrapers.
Provides common browser setup, retry logic, and logging.
"""

import abc
import logging
import time
from typing import Optional

from selenium import webdriver
from selenium_stealth import stealth

import config

logger = logging.getLogger(__name__)


class BaseScraper(abc.ABC):
    """Base class every platform scraper must extend."""

    PLATFORM: str = "generic"

    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None

    # ---- Browser lifecycle ----

    def get_browser(self) -> webdriver.Chrome:
        """Spin up a stealth Chrome instance."""
        if self.driver:
            return self.driver

        opts = webdriver.ChromeOptions()
        if config.HEADLESS:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("start-maximized")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)

        if config.INSTAGRAM_PROXY:
            opts.add_argument(f"--proxy-server={config.INSTAGRAM_PROXY}")

        self.driver = webdriver.Chrome(options=opts)
        stealth(
            self.driver,
            user_agent=config.USER_AGENT,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=False,
            run_on_insecure_origins=False,
        )
        return self.driver

    def close_browser(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    # ---- Retry helper ----

    @staticmethod
    def retry(fn, retries: int = 3, delay: float = 2.0):
        """Execute *fn* with exponential back-off retries."""
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                wait = delay * attempt
                logger.warning("Attempt %d failed: %s – retrying in %.1fs", attempt, exc, wait)
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    # ---- Abstract interface ----

    @abc.abstractmethod
    def scrape(self, target: str):
        """Run scraping for *target* (username, query, etc.) and return a ScrapeResult."""
        ...

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close_browser()
