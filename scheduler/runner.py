"""
Scheduler — runs scraping jobs on a configurable interval,
exports results, and triggers analytics after each cycle.
"""

import logging
import time

import schedule

import config
from analytics.analyzer import SocialAnalyzer
from scrapers.instagram import InstagramScraper
from scrapers.twitter import TwitterScraper
from scrapers.youtube import YouTubeScraper
from storage.exporter import DataExporter

logger = logging.getLogger(__name__)


class ScrapeScheduler:
    """Orchestrates periodic scraping across all configured platforms."""

    def __init__(self):
        self.exporter = DataExporter()
        self.analyzer = SocialAnalyzer()

    def run_cycle(self):
        """Execute one full scraping + analytics cycle."""
        logger.info("=== Starting scrape cycle ===")
        self.analyzer = SocialAnalyzer()

        self._scrape_instagram()
        self._scrape_twitter()
        self._scrape_youtube()

        report = self.analyzer.generate_report()
        logger.info(
            "Cycle complete — %d platforms, report generated.",
            len(report.get("platforms_analysed", [])),
        )

    def start(self, interval_minutes: int = 0):
        """Start the scheduler loop.  If interval is 0, run once and exit."""
        interval = interval_minutes or config.SCRAPE_INTERVAL_MINUTES

        if interval <= 0:
            self.run_cycle()
            return

        logger.info("Scheduler started — running every %d minute(s)", interval)
        schedule.every(interval).minutes.do(self.run_cycle)

        self.run_cycle()  # run immediately on start
        while True:
            schedule.run_pending()
            time.sleep(1)

    # ---- Platform runners ----

    def _scrape_instagram(self):
        targets = [t.strip() for t in config.INSTAGRAM_TARGETS if t.strip()]
        if not targets:
            logger.info("No Instagram targets configured — skipping")
            return

        with InstagramScraper() as scraper:
            for username in targets:
                logger.info("Scraping Instagram: %s", username)
                result = scraper.scrape(username)
                self.exporter.export(result)
                self.analyzer.add(result)

    def _scrape_twitter(self):
        queries = [q.strip() for q in config.TWITTER_SEARCH_QUERIES if q.strip()]
        if not queries or not config.TWITTER_BEARER_TOKEN:
            logger.info("Twitter not configured — skipping")
            return

        with TwitterScraper() as scraper:
            for query in queries:
                logger.info("Scraping Twitter: '%s'", query)
                result = scraper.scrape(query)
                self.exporter.export(result)
                self.analyzer.add(result)

    def _scrape_youtube(self):
        queries = [q.strip() for q in config.YOUTUBE_SEARCH_QUERIES if q.strip()]
        if not queries or not config.YOUTUBE_API_KEY:
            logger.info("YouTube not configured — skipping")
            return

        scraper = YouTubeScraper()
        for query in queries:
            logger.info("Scraping YouTube: '%s'", query)
            result = scraper.scrape(query)
            self.exporter.export(result)
            self.analyzer.add(result)
