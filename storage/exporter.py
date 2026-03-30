"""
Data exporter — persists ScrapeResult objects to JSON, CSV,
and optionally MongoDB for downstream analytics pipelines.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from models.schemas import ScrapeResult

logger = logging.getLogger(__name__)


class DataExporter:
    """Unified exporter that writes structured scrape data to multiple sinks."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or config.DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Public API ----

    def export(self, result: ScrapeResult, fmt: Optional[str] = None):
        """Export a ScrapeResult in the configured format(s)."""
        fmt = fmt or config.EXPORT_FORMAT
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base_name = f"{result.platform}_{self._safe(result.query)}_{ts}"

        if fmt in ("json", "both"):
            self.to_json(result, base_name)
        if fmt in ("csv", "both"):
            self.to_csv(result, base_name)

        logger.info("Exported %s data for '%s' as %s", result.platform, result.query, fmt)

    def to_json(self, result: ScrapeResult, base_name: str):
        path = self.output_dir / f"{base_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("  → JSON saved: %s", path)

    def to_csv(self, result: ScrapeResult, base_name: str):
        """Flatten posts/videos/profiles into CSV rows."""
        rows = self._flatten(result)
        if not rows:
            return

        path = self.output_dir / f"{base_name}.csv"
        keys = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        logger.info("  → CSV saved: %s (%d rows)", path, len(rows))

    def to_mongo(self, result: ScrapeResult, collection_name: Optional[str] = None):
        """Insert scrape result into MongoDB (requires pymongo)."""
        try:
            from pymongo import MongoClient

            client = MongoClient(config.MONGO_URI)
            db = client[config.MONGO_DB_NAME]
            col = db[collection_name or result.platform]
            doc = result.to_dict()
            col.insert_one(doc)
            logger.info("  → MongoDB: inserted into %s.%s", config.MONGO_DB_NAME, col.name)
        except ImportError:
            logger.warning("pymongo not installed — skipping MongoDB export")
        except Exception as exc:
            logger.error("MongoDB export failed: %s", exc)

    # ---- Helpers ----

    @staticmethod
    def _safe(name: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    @staticmethod
    def _flatten(result: ScrapeResult) -> list[dict]:
        rows = []
        for p in result.profiles:
            d = p.to_dict() if hasattr(p, "to_dict") else p
            d.pop("posts", None)
            rows.append(d)
        for v in result.videos:
            rows.append(v.to_dict() if hasattr(v, "to_dict") else v)
        for post in result.posts:
            d = post.to_dict() if hasattr(post, "to_dict") else post
            d.pop("comments", None)
            d["hashtags"] = ", ".join(d.get("hashtags", []))
            d["mentions"] = ", ".join(d.get("mentions", []))
            rows.append(d)
        return rows
