from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Any

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from web_feed_utils import http_get, isoformat_z, parse_datetime, parse_feed_payload


SCHEMA_VERSION = "0.1.0"
FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/feed+json, application/xml, text/xml;q=0.9, */*;q=0.8"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def build_source_id(site_id: str, marker: str) -> str:
    digest = hashlib.sha1(marker.encode("utf-8")).hexdigest()[:12]
    return f"web-{site_id}-{digest}"


def discover_items(site: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload, content_type = http_get(site["feed_url"], accept=FEED_ACCEPT)
    feed = parse_feed_payload(payload, site["feed_url"], content_type=content_type)
    items: list[dict[str, Any]] = []
    for entry in feed.get("items", []):
        marker = entry.get("origin_url", "") or f'{entry.get("title", "")}|{entry.get("published_at", "")}'
        items.append(
            {
                "source_id": build_source_id(site["site_id"], marker),
                "source_family": "official_web",
                "source_type": "official_web_article_metadata",
                "discovery_channel": "rss",
                "author": site["label"],
                "site_id": site["site_id"],
                "site_label": site["label"],
                "origin_url": entry.get("origin_url", ""),
                "published_at": entry.get("published_at", ""),
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "fulltext_path": "",
                "language": site.get("language", "unknown"),
                "eligibility": "trigger_until_fulltext",
                "fetch_status": "discovered",
                "feed_url": site["feed_url"],
                "kind_hints": site.get("kind_hints", []),
            }
        )
    meta = {
        "site_id": site["site_id"],
        "site_label": site["label"],
        "feed_url": site["feed_url"],
        "item_count": len(items),
        "latest_title": feed.get("latest_title", ""),
        "latest_published_at": feed.get("latest_published_at", ""),
    }
    return items, meta


def render_markdown(catalog: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Official Web Article Catalog")
    lines.append("")
    lines.append("## Overview")
    lines.append(f'- Generated at: {catalog.get("generated_at", "")}')
    lines.append(f'- Window: last {catalog.get("window", {}).get("hours", 0)} hours')
    lines.append(f'- Sites checked: {catalog.get("stats", {}).get("site_count", 0)}')
    lines.append(f'- Articles discovered: {catalog.get("stats", {}).get("article_count", 0)}')
    lines.append(f'- Errors: {catalog.get("stats", {}).get("error_count", 0)}')
    lines.append("")
    for site in catalog.get("sites", []):
        lines.append(f'## {site.get("site_label", "")}')
        lines.append(f'- Feed: {site.get("feed_url", "")}')
        if site.get("error"):
            lines.append(f'- Error: {site.get("error", "")}')
            lines.append("")
            continue
        lines.append(f'- Articles in window: {site.get("article_count", 0)}')
        for item in site.get("articles", []):
            lines.append(f'- {item.get("published_at", "")} | {item.get("title", "")}')
            lines.append(f'  {item.get("origin_url", "")}')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        required=True,
        help="Path to autodiscovered official_web_registry.json",
    )
    parser.add_argument("--out-dir", required=True, help="Directory where article_catalog artifacts will be written.")
    parser.add_argument("--window-hours", type=int, default=168, help="Keep items published within this rolling window.")
    parser.add_argument("--max-per-site", type=int, default=10, help="Maximum posts to keep per site after filtering.")
    args = parser.parse_args()

    registry = load_json(args.registry)
    source_group = registry.get("source_group") or {}
    sites = [item for item in source_group.get("items", []) if item.get("feed_url")]
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    cutoff = now - timedelta(hours=args.window_hours)

    catalog_items: list[dict[str, Any]] = []
    site_rows: list[dict[str, Any]] = []
    error_count = 0

    for site in sites:
        row = {
            "site_id": site["site_id"],
            "site_label": site["label"],
            "feed_url": site["feed_url"],
            "articles": [],
            "item_count": 0,
        }
        try:
            items, meta = discover_items(site)
            filtered: list[dict[str, Any]] = []
            for item in items:
                published = parse_datetime(item.get("published_at", ""))
                if published is None or published >= cutoff:
                    filtered.append(item)
            filtered = filtered[: args.max_per_site]
            row["item_count"] = meta["item_count"]
            row["article_count"] = len(filtered)
            row["latest_title"] = meta["latest_title"]
            row["latest_published_at"] = meta["latest_published_at"]
            row["articles"] = filtered
            catalog_items.extend(filtered)
        except Exception as exc:
            error_count += 1
            row["error"] = f"{type(exc).__name__}: {exc}"
        site_rows.append(row)

    catalog = {
        "version": SCHEMA_VERSION,
        "generated_at": isoformat_z(now),
        "window": {"hours": args.window_hours},
        "stats": {
            "site_count": len(sites),
            "article_count": len(catalog_items),
            "error_count": error_count,
        },
        "sites": site_rows,
        "articles": catalog_items,
    }
    (out_dir / "article_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "article_catalog.md").write_text(render_markdown(catalog), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
