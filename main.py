#!/usr/bin/env python3
"""
Social Media Scraping System — CLI Entry Point
================================================
Usage:
    python main.py                     # run one full scrape cycle
    python main.py --schedule          # run on a recurring schedule
    python main.py --platform instagram --target natgeo
    python main.py --platform youtube  --target "machine learning"
    python main.py --platform twitter  --target "python programming"
    python main.py --report            # generate analytics report from latest data
"""

import argparse
import logging
import sys

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

import config
from analytics.analyzer import SocialAnalyzer
from scrapers.instagram import InstagramScraper
from scrapers.twitter import TwitterScraper
from scrapers.youtube import YouTubeScraper
from scheduler.runner import ScrapeScheduler
from storage.exporter import DataExporter

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console)],
)
logger = logging.getLogger("scraper")

SCRAPERS = {
    "instagram": InstagramScraper,
    "twitter": TwitterScraper,
    "youtube": YouTubeScraper,
}


def single_scrape(platform: str, target: str):
    """Run a one-off scrape for a specific platform and target."""
    if platform not in SCRAPERS:
        console.print(f"[red]Unknown platform: {platform}[/red]")
        console.print(f"Available: {', '.join(SCRAPERS.keys())}")
        sys.exit(1)

    exporter = DataExporter()
    analyzer = SocialAnalyzer()

    console.print(f"\n[bold cyan]Scraping {platform}[/bold cyan] → {target}")
    scraper_cls = SCRAPERS[platform]

    if platform in ("instagram", "twitter"):
        with scraper_cls() as scraper:
            result = scraper.scrape(target)
    else:
        scraper = scraper_cls()
        result = scraper.scrape(target)

    exporter.export(result)
    analyzer.add(result)

    _print_summary(result)

    report = analyzer.generate_report(save=True)
    console.print("\n[bold green]Analytics report generated.[/bold green]")
    return report


def _print_summary(result):
    """Pretty-print a quick summary table."""
    table = Table(title=f"{result.platform.upper()} — {result.query}")

    if result.profiles:
        table.add_column("Username", style="cyan")
        table.add_column("Followers", justify="right")
        table.add_column("Posts", justify="right")
        for p in result.profiles:
            d = p.to_dict() if hasattr(p, "to_dict") else p
            table.add_row(d["username"], str(d["followers"]), str(len(d.get("posts", []))))

    if result.videos:
        table.add_column("Title", style="cyan")
        table.add_column("Views", justify="right")
        table.add_column("Likes", justify="right")
        for v in result.videos:
            d = v.to_dict() if hasattr(v, "to_dict") else v
            table.add_row(d["title"][:60], str(d["views"]), str(d["likes"]))

    if result.posts:
        table.add_column("Post ID", style="cyan")
        table.add_column("Likes", justify="right")
        table.add_column("Text", max_width=50)
        for p in result.posts[:15]:
            d = p.to_dict() if hasattr(p, "to_dict") else p
            table.add_row(d["post_id"][:16], str(d["likes"]), d["caption"][:50])

    if result.errors:
        console.print(f"[red]Errors: {result.errors}[/red]")

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Automated Social Media Scraping System"
    )
    parser.add_argument(
        "--platform", "-p",
        choices=["instagram", "twitter", "youtube"],
        help="Target a single platform",
    )
    parser.add_argument("--target", "-t", help="Username or search query")
    parser.add_argument(
        "--schedule", "-s",
        action="store_true",
        help="Run on a recurring schedule (uses SCRAPE_INTERVAL_MINUTES from .env)",
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Only generate an analytics report from existing data",
    )

    args = parser.parse_args()

    console.print(
        "\n[bold magenta]Social Media Scraping System[/bold magenta] v1.0\n"
    )

    if args.platform and args.target:
        single_scrape(args.platform, args.target)
    elif args.schedule:
        scheduler = ScrapeScheduler()
        scheduler.start()
    elif args.report:
        console.print("[yellow]Report-only mode not yet connected to stored data.[/yellow]")
        console.print("Run a scrape first, then the report is auto-generated.")
    else:
        console.print("[cyan]Running one full scrape cycle across all configured platforms...[/cyan]\n")
        scheduler = ScrapeScheduler()
        scheduler.run_cycle()


if __name__ == "__main__":
    main()
