"""
Data exporter — persists ScrapeResult objects to JSON and CSV.
"""

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

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
        if fmt not in ("json", "csv", "both"):
            raise ValueError(f"Unsupported export format: {fmt}")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = f"{result.platform}_"
        suffix = f"_{ts}_{uuid4().hex}"
        # Reserve bytes for the platform, timestamp, UUID and longest extension.
        query_budget = 255 - len(f"{prefix}{suffix}.json".encode("utf-8"))
        safe_query = (
            self._safe(result.query).encode("utf-8")[:query_budget].decode("utf-8", errors="ignore")
        )
        base_name = f"{prefix}{safe_query}{suffix}"

        if fmt in ("json", "both"):
            self.to_json(result, base_name)
        if fmt in ("csv", "both"):
            self.to_csv(result, base_name)

        logger.info("Exported %s data for '%s' as %s", result.platform, result.query, fmt)

    def to_json(self, result: ScrapeResult, base_name: str):
        path = self.output_dir / f"{base_name}.json"
        with open(path, "x", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("  → JSON saved: %s", path)

    def to_csv(self, result: ScrapeResult, base_name: str):
        """Flatten posts/videos/profiles into CSV rows."""
        rows = self._flatten(result)
        if not rows:
            return

        path = self.output_dir / f"{base_name}.csv"
        keys = list(dict.fromkeys(key for row in rows for key in row))
        with open(path, "x", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writerow({key: self._csv_value(key) for key in keys})
            writer.writerows({key: self._csv_value(value) for key, value in row.items()} for row in rows)
        logger.info("  → CSV saved: %s (%d rows)", path, len(rows))

    # ---- Helpers ----

    @staticmethod
    def _safe(name: str) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    @staticmethod
    def _csv_value(value):
        if isinstance(value, str) and re.match(r"^[\s\ufeff]*[=+\-@＝＋－＠\t\r\n]", value):
            return "'" + value
        return value

    @staticmethod
    def _flatten(result: ScrapeResult) -> list[dict]:
        rows = []
        for p in result.profiles:
            d = p.to_dict() if hasattr(p, "to_dict") else p.copy()
            d.pop("posts", None)
            rows.append(d)
        for v in result.videos:
            rows.append(v.to_dict() if hasattr(v, "to_dict") else v)
        for post in result.posts:
            d = post.to_dict() if hasattr(post, "to_dict") else post.copy()
            d.pop("comments", None)
            d["hashtags"] = ", ".join(d.get("hashtags", []))
            d["mentions"] = ", ".join(d.get("mentions", []))
            rows.append(d)
        return rows
