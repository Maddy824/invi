#!/usr/bin/env python3
"""
Social Media Scraping System — CLI Entry Point
================================================
Usage:
    python main.py                     # run one full scrape cycle
    python main.py --demo              # analyse bundled synthetic data offline
    python main.py --schedule          # run on a recurring schedule
    python main.py --platform instagram --target natgeo
    python main.py --platform youtube  --target "machine learning"
    python main.py --platform twitter  --target "python programming"
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

import scrapers
from analytics.analyzer import SocialAnalyzer
from models.schemas import ScrapeResult
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
    "instagram": "InstagramScraper",
    "twitter": "TwitterScraper",
    "youtube": "YouTubeScraper",
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
    scraper_cls = getattr(scrapers, SCRAPERS[platform])

    if platform in ("instagram", "twitter"):
        with scraper_cls() as scraper:
            result = scraper.scrape(target)
    else:
        scraper = scraper_cls()
        result = scraper.scrape(target)

    if result.errors:
        raise RuntimeError(f"{platform} scrape failed: {'; '.join(result.errors)}")

    exporter.export(result)
    analyzer.add(result)

    _print_summary(result)

    report = analyzer.generate_report(save=True)
    console.print("\n[bold green]Analytics report generated.[/bold green]")
    return report


def run_demo():
    """Run the real export and analytics pipeline on fictional records."""
    fixture = Path(__file__).resolve().parent / "fixtures" / "demo_posts.json"
    results = json.loads(fixture.read_text(encoding="utf-8"))
    exporter = DataExporter()
    analyzer = SocialAnalyzer()

    console.print("[bold cyan]Offline demo: synthetic data only[/bold cyan]")
    for record in results:
        result = ScrapeResult(**record)
        exporter.export(result, fmt="both")
        analyzer.add(result)

    report = analyzer.generate_report(save=True, demo=True)
    console.print("[bold]Synthetic analytics report[/bold]")
    console.print_json(data=report)


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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--platform", "-p",
        choices=SCRAPERS,
        help="Target a single platform",
    )
    parser.add_argument("--target", "-t", help="Username or search query")
    mode.add_argument(
        "--schedule", "-s",
        action="store_true",
        help="Run on a recurring schedule (uses SCRAPE_INTERVAL_MINUTES from .env)",
    )
    mode.add_argument(
        "--demo",
        action="store_true",
        help="Analyse bundled synthetic data and export JSON/CSV offline",
    )

    args = parser.parse_args()
    if bool(args.platform) != bool(args.target):
        parser.error("--platform and --target must be used together")

    console.print(
        "\n[bold magenta]Social Media Scraping System[/bold magenta] v1.0\n"
    )

    try:
        if args.demo:
            run_demo()
        elif args.platform:
            single_scrape(args.platform, args.target)
        else:
            from scheduler.runner import ScrapeScheduler

            scheduler = ScrapeScheduler()
            if args.schedule:
                return scheduler.start()
            else:
                console.print("[cyan]Running one full scrape cycle across all configured platforms...[/cyan]\n")
                return scheduler.run_cycle()
    except Exception as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
