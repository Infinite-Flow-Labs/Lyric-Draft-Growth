from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
    except Exception:
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = HTML_TAG_RE.sub(" ", value)
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def build_source_id(handle: str, marker: str) -> str:
    digest = hashlib.sha1(marker.encode("utf-8")).hexdigest()[:12]
    return f"x-{handle.lower()}-{digest}"


def detect_post_kind(title: str) -> str:
    normalized = title.strip().lower()
    if normalized.startswith("r to @"):
        return "reply"
    if normalized.startswith("rt by @"):
        return "retweet"
    return "original"


def fetch_rss_for_handle(handle: str, timeout: int = 30) -> list[dict[str, Any]]:
    url = f"https://nitter.net/{handle}/rss"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        root = ET.fromstring(response.read())

    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        desc = item.findtext("description") or ""
        pub_raw = item.findtext("pubDate") or ""
        published = parse_datetime(pub_raw)
        guid = item.findtext("guid") or link or f"{title}|{pub_raw}"
        marker = guid or link or title
        post_kind = detect_post_kind(title)
        items.append(
            {
                "source_id": build_source_id(handle, marker),
                "source_family": "benchmark_x_account",
                "source_type": "x_post_metadata",
                "discovery_channel": "nitter_rss_guest",
                "author": handle,
                "origin_url": link,
                "published_at": isoformat_z(published),
                "title": normalize_text(title),
                "summary": normalize_text(desc),
                "fulltext_path": "",
                "language": "unknown",
                "eligibility": "trigger_until_fulltext",
                "fetch_status": "discovered",
                "account_handle": handle,
                "feed_url": url,
                "post_kind": post_kind,
            }
        )
    return items


def parse_handles(profile: dict[str, Any]) -> list[str]:
    entries = list(profile.get("benchmark_accounts") or []) + list(profile.get("manual_benchmark_accounts") or [])
    handles: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        handle = ""
        if isinstance(entry, str):
            raw = entry.strip()
            if raw.startswith("https://x.com/"):
                handle = raw.split("https://x.com/", 1)[1].split("/", 1)[0]
            elif raw.startswith("@"):
                handle = raw[1:]
            else:
                handle = raw
        elif isinstance(entry, dict):
            handle = str(
                entry.get("handle")
                or entry.get("x_handle")
                or entry.get("mention")
                or entry.get("label")
                or ""
            ).lstrip("@")
        handle = handle.strip()
        if not handle:
            continue
        key = handle.lower()
        if key in seen:
            continue
        seen.add(key)
        handles.append(handle)
    return handles


def render_markdown(catalog: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Official X Guest RSS Catalog")
    lines.append("")
    lines.append("## Overview")
    lines.append(f'- Generated at: {catalog.get("generated_at", "")}')
    lines.append(f'- Window: last {catalog.get("window", {}).get("hours", 0)} hours')
    lines.append(f'- Handles checked: {catalog.get("stats", {}).get("handle_count", 0)}')
    lines.append(f'- Posts discovered: {catalog.get("stats", {}).get("post_count", 0)}')
    lines.append(f'- Errors: {catalog.get("stats", {}).get("error_count", 0)}')
    lines.append("")
    for row in catalog.get("handles", []):
        lines.append(f'## @{row.get("handle", "")}')
        if row.get("error"):
            lines.append(f'- Error: {row.get("error", "")}')
            lines.append("")
            continue
        lines.append(f'- Posts in window: {row.get("post_count", 0)}')
        for post in row.get("posts", [])[:5]:
            lines.append(f'- {post.get("published_at", "")} | {post.get("title", "")}')
            lines.append(f'  {post.get("origin_url", "")}')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--account-profile",
        default="content/pipeline/configs/official_x_account_profile.json",
        help="Path to account profile JSON with benchmark_accounts[]",
    )
    parser.add_argument("--out-dir", required=True, help="Directory where x guest rss catalog artifacts will be written.")
    parser.add_argument("--window-hours", type=int, default=168, help="Keep posts published within this rolling window.")
    parser.add_argument("--max-per-handle", type=int, default=20, help="Maximum posts to keep per handle after filtering.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-handle RSS request timeout in seconds.")
    parser.add_argument("--include-replies", action="store_true", help="Keep reply posts in the catalog.")
    parser.add_argument("--include-retweets", action="store_true", help="Keep retweets in the catalog.")
    args = parser.parse_args()

    profile = load_json(args.account_profile)
    handles = parse_handles(profile)
    now = utc_now()
    cutoff = now - timedelta(hours=args.window_hours)

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    catalog_posts: list[dict[str, Any]] = []
    handle_rows: list[dict[str, Any]] = []
    error_count = 0

    for handle in handles:
        row: dict[str, Any] = {"handle": handle, "posts": []}
        try:
            items = fetch_rss_for_handle(handle, timeout=args.timeout)
            filtered: list[dict[str, Any]] = []
            for item in items:
                kind = item.get("post_kind", "original")
                if kind == "reply" and not args.include_replies:
                    continue
                if kind == "retweet" and not args.include_retweets:
                    continue
                published = parse_datetime(item.get("published_at", ""))
                if published is None:
                    filtered.append(item)
                    continue
                if published >= cutoff:
                    filtered.append(item)
            filtered = filtered[: args.max_per_handle]
            row["post_count"] = len(filtered)
            row["posts"] = filtered
            catalog_posts.extend(filtered)
        except Exception as exc:
            error_count += 1
            row["error"] = f"{type(exc).__name__}: {exc}"
        handle_rows.append(row)

    catalog = {
        "version": SCHEMA_VERSION,
        "generated_at": isoformat_z(now),
        "window": {"hours": args.window_hours},
        "stats": {
            "handle_count": len(handles),
            "post_count": len(catalog_posts),
            "error_count": error_count,
        },
        "handles": handle_rows,
        "posts": catalog_posts,
    }

    (out_dir / "guest_rss_catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "guest_rss_catalog.md").write_text(render_markdown(catalog), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
