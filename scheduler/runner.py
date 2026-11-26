"""
Scheduler — runs scraping jobs on a configurable interval,
exports results, and triggers analytics after each cycle.
"""

import logging
import time

import schedule

import config
import scrapers
from analytics.analyzer import SocialAnalyzer
from scrapers.errors import safe_error_message
from storage.exporter import DataExporter

logger = logging.getLogger(__name__)


class ScrapeScheduler:
    """Orchestrates periodic scraping across all configured platforms."""

    def __init__(self):
        self.exporter = DataExporter()
        self.analyzer = SocialAnalyzer()

    def run_cycle(self) -> int:
        """Finish all configured targets, save a combined report and return status."""
        logger.info("=== Starting scrape cycle ===")
        self.analyzer = SocialAnalyzer()
        failures = []

        for platform, targets, scraper_name in (
            ("instagram", config.INSTAGRAM_TARGETS, "InstagramScraper"),
            ("twitter", config.TWITTER_SEARCH_QUERIES, "TwitterScraper"),
            ("youtube", config.YOUTUBE_SEARCH_QUERIES, "YouTubeScraper"),
        ):
            self._scrape_targets(platform, targets, scraper_name, failures)

        report = self.analyzer.generate_report(failures=failures)
        logger.info(
            "Cycle complete — %d successful, %d failed, report generated.",
            report["total_scrapes"], report["failed_scrapes"],
        )
        return int(bool(failures or report.get("analytics_errors")))

    def start(self, interval_minutes: int | None = None) -> int:
        """Run immediately and repeat at the interval unless a cycle fails."""
        interval = config.SCRAPE_INTERVAL_MINUTES if interval_minutes is None else interval_minutes
        status = self.run_cycle()
        if status or interval <= 0:
            return status

        def run_scheduled_cycle():
            nonlocal status
            status = self.run_cycle()

        logger.info("Scheduler started — running every %d minute(s)", interval)
        scheduler = schedule.Scheduler()
        scheduler.every(interval).minutes.do(run_scheduled_cycle)
        while not status:
            time.sleep(1)
            scheduler.run_pending()
        return status

    # ---- Platform runners ----

    @staticmethod
    def _record_failure(failures, platform, target, errors):
        failures.append({"platform": platform, "query": target, "errors": errors})
        logger.error("%s scrape failed for '%s': %s", platform, target, "; ".join(errors))

    def _scrape_targets(self, platform, targets, scraper_name, failures):
        targets = [target.strip() for target in targets if target.strip()]
        if not targets:
            logger.info("%s not configured — skipping", platform)
            return

        try:
            scraper = getattr(scrapers, scraper_name)()
        except Exception as exc:
            for target in targets:
                self._record_failure(failures, platform, target, [safe_error_message(exc)])
            return

        try:
            for target in targets:
                logger.info("Scraping %s: '%s'", platform, target)
                try:
                    result = scraper.scrape(target)
                    if result.errors:
                        self._record_failure(failures, platform, target, result.errors)
                        continue
                    self.exporter.export(result)
                    self.analyzer.add(result)
                except Exception as exc:
                    self._record_failure(failures, platform, target, [safe_error_message(exc)])
        finally:
            try:
                scraper.close_browser()
            except Exception as exc:
                logger.warning("%s browser cleanup failed: %s", platform, safe_error_message(exc))
