from __future__ import annotations

import argparse
import hashlib
import html
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
ATOM_NS = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = html.unescape(HTML_TAG_RE.sub(" ", value))
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def find_channel(root: ET.Element) -> ET.Element | None:
    channel = root.find("channel")
    if channel is not None:
        return channel
    atom_channel = root.find(f"{ATOM_NS}channel")
    if atom_channel is not None:
        return atom_channel
    return root


def find_items(channel: ET.Element) -> list[ET.Element]:
    items = channel.findall("item")
    if items:
        return items
    return channel.findall(f"{ATOM_NS}entry")


def element_text(element: ET.Element, *names: str) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def atom_link_href(element: ET.Element) -> str:
    link = element.find(f"{ATOM_NS}link")
    if link is not None:
        href = (link.get("href") or "").strip()
        if href:
            return href
    return ""


def enclosure_url(element: ET.Element) -> str:
    enclosure = element.find("enclosure")
    if enclosure is not None:
        return (enclosure.get("url") or "").strip()
    return ""


def clean_summary(element: ET.Element) -> str:
    return normalize_text(
        element_text(
            element,
            "description",
            f"{CONTENT_NS}encoded",
            f"{ITUNES_NS}summary",
            "summary",
            f"{ATOM_NS}summary",
            f"{ATOM_NS}content",
        )
    )


def build_source_id(show_id: str, marker: str) -> str:
    digest = hashlib.sha1(marker.encode("utf-8")).hexdigest()[:12]
    return f"podcast-{show_id}-{digest}"


def parse_feed_item(show: dict[str, Any], item: ET.Element) -> dict[str, Any]:
    title = element_text(item, "title", f"{ATOM_NS}title")
    guid = element_text(item, "guid", "id", f"{ATOM_NS}id")
    link = element_text(item, "link")
    if not link:
        link = atom_link_href(item)
    published_at_raw = element_text(
        item,
        "pubDate",
        "published",
        "updated",
        f"{ATOM_NS}published",
        f"{ATOM_NS}updated",
    )
    published_at = parse_datetime(published_at_raw)
    marker = guid or link or f"{title}|{published_at_raw}"
    audio_url = enclosure_url(item)
    summary = clean_summary(item)
    return {
        "source_id": build_source_id(show["show_id"], marker),
        "source_family": "podcast_show",
        "source_type": "podcast_episode_metadata",
        "discovery_channel": "rss",
        "author": show["label"],
        "show_id": show["show_id"],
        "show_label": show["label"],
        "origin_url": link,
        "published_at": isoformat_z(published_at) if published_at else "",
        "title": normalize_text(title),
        "summary": summary,
        "fulltext_path": "",
        "language": show.get("language", "unknown"),
        "eligibility": "trigger_until_transcript",
        "fetch_status": "discovered",
        "feed_url": show["feed_url"],
        "audio_url": audio_url,
        "guid": guid,
        "transcript_mode": show.get("transcript_mode", "manual_or_show_notes"),
    }


def fetch_feed(show: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = http_get(show["feed_url"])
    root = ET.fromstring(payload)
    channel = find_channel(root)
    if channel is None:
        raise ValueError("missing feed channel")
    channel_title = element_text(channel, "title", f"{ATOM_NS}title")
    items = find_items(channel)
    parsed_items = [parse_feed_item(show, item) for item in items]
    meta = {
        "show_id": show["show_id"],
        "show_label": show["label"],
        "channel_title": channel_title or show["label"],
        "feed_url": show["feed_url"],
        "item_count": len(parsed_items),
    }
    return parsed_items, meta


def render_catalog_markdown(catalog: dict[str, Any]) -> str:
    lines: list[str] = []
    stats = catalog.get("stats", {})
    window = catalog.get("window", {})
    lines.append("# Episode Catalog")
    lines.append("")
    lines.append("## Overview")
    lines.append(f'- Generated at: {catalog.get("generated_at", "")}')
    lines.append(f'- Window: last {window.get("hours", 0)} hours')
    lines.append(f'- Shows checked: {stats.get("show_count", 0)}')
    lines.append(f'- Episodes discovered: {stats.get("episode_count", 0)}')
    lines.append(f'- Errors: {stats.get("error_count", 0)}')
    lines.append("")

    for show in catalog.get("shows", []):
        lines.append(f'## {show.get("show_label", "")}')
        lines.append(f'- Feed: {show.get("feed_url", "")}')
        if show.get("error"):
            lines.append(f'- Error: {show["error"]}')
            lines.append("")
            continue
        lines.append(f'- Episodes in window: {show.get("episode_count", 0)}')
        lines.append(f'- Total feed items seen: {show.get("feed_item_count", 0)}')
        for episode in show.get("episodes", []):
            lines.append(f'- {episode.get("published_at", "")} | {episode.get("title", "")}')
            lines.append(f'  {episode.get("origin_url", "")}')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        default="content/pipeline/configs/podcast_discovery_registry.json",
        help="Path to the validated podcast discovery registry JSON.",
    )
    parser.add_argument("--out-dir", required=True, help="Directory where episode_catalog artifacts will be written.")
    parser.add_argument("--window-hours", type=int, default=72, help="Keep episodes published within this rolling window.")
    parser.add_argument("--max-per-show", type=int, default=5, help="Maximum episodes to keep per show after filtering.")
    args = parser.parse_args()

    registry_path = Path(args.registry).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    registry = load_json(registry_path)
    source_group = registry.get("source_group") or {}
    shows = [item for item in source_group.get("items", []) if item.get("feed_url")]

    now = utc_now()
    cutoff = now - timedelta(hours=args.window_hours)
    catalog_episodes: list[dict[str, Any]] = []
    show_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for show in shows:
        row = {
            "show_id": show["show_id"],
            "show_label": show["label"],
            "feed_url": show["feed_url"],
            "transcript_mode": show.get("transcript_mode", "manual_or_show_notes"),
            "episodes": [],
            "feed_item_count": 0,
        }
        try:
            episodes, meta = fetch_feed(show)
            row["feed_item_count"] = meta["item_count"]
            filtered: list[dict[str, Any]] = []
            for episode in episodes:
                published_at = parse_datetime(episode.get("published_at"))
                if published_at and published_at < cutoff:
                    continue
                filtered.append(episode)
            filtered.sort(key=lambda episode: episode.get("published_at", ""), reverse=True)
            filtered = filtered[: args.max_per_show]
            row["episodes"] = filtered
            row["episode_count"] = len(filtered)
            catalog_episodes.extend(filtered)
        except Exception as exc:
            row["episode_count"] = 0
            row["error"] = f"{type(exc).__name__}: {exc}"
            errors.append({"show_id": show["show_id"], "error": row["error"]})
        show_rows.append(row)

    catalog = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(now),
        "registry_ref": {
            "path": str(registry_path),
            "group_id": source_group.get("group_id", ""),
            "validated_at": registry.get("validated_at", ""),
        },
        "window": {
            "hours": args.window_hours,
            "started_at": isoformat_z(cutoff),
            "ended_at": isoformat_z(now),
        },
        "stats": {
            "show_count": len(shows),
            "episode_count": len(catalog_episodes),
            "error_count": len(errors),
        },
        "shows": show_rows,
        "episodes": sorted(catalog_episodes, key=lambda episode: episode.get("published_at", ""), reverse=True),
        "errors": errors,
    }

    catalog_json = out_dir / "episode_catalog.json"
    catalog_md = out_dir / "episode_catalog.md"
    catalog_json.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    catalog_md.write_text(render_catalog_markdown(catalog), encoding="utf-8")

    print(catalog_json)
    print(catalog_md)
    print(f"episodes={catalog['stats']['episode_count']} errors={catalog['stats']['error_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
