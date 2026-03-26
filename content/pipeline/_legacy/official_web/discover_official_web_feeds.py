from __future__ import annotations

import argparse
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

SHARED_DIR = Path(__file__).resolve().parents[2] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from web_feed_utils import (
    FeedCandidate,
    common_feed_paths,
    extract_feed_candidates_from_html,
    http_get,
    looks_like_feed,
    parse_feed_payload,
)


SCHEMA_VERSION = "0.1.0"
HTML_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/feed+json, application/xml, text/xml;q=0.9, */*;q=0.8"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def load_items(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    data = load_json(path)
    items: list[dict[str, Any]] = []
    if isinstance(data.get("source_group"), dict):
        items.extend(data["source_group"].get("items", []))
    for group in data.get("source_groups", []):
        items.extend(group.get("items", []))
    return {str(item.get("site_id") or item.get("label") or item.get("homepage_url")): item for item in items}


def prioritize_candidates(
    site: dict[str, Any],
    fallback_item: dict[str, Any] | None,
    request_timeout: int,
    max_candidates: int,
) -> list[FeedCandidate]:
    candidates: list[FeedCandidate] = []
    seen: set[tuple[str, str]] = set()
    page_urls: list[str] = []
    for value in site.get("landing_urls", []):
        if value:
            page_urls.append(str(value))
    if site.get("homepage_url"):
        page_urls.append(str(site["homepage_url"]))
    for page_url in page_urls:
        try:
            payload, content_type = http_get(page_url, timeout=request_timeout, accept=HTML_ACCEPT)
            if looks_like_feed(payload, content_type):
                candidate = FeedCandidate(url=page_url, method="direct_feed_page", source_url=page_url)
                key = (candidate.url, candidate.method)
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)
                continue
            html_text = payload.decode("utf-8", "ignore")
            html_candidates = extract_feed_candidates_from_html(html_text, page_url)
            for candidate in html_candidates:
                key = (candidate.url, candidate.method)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)
            if html_candidates:
                continue
            for candidate in common_feed_paths(page_url):
                key = (candidate.url, candidate.method)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)
        except Exception:
            for candidate in common_feed_paths(page_url):
                key = (candidate.url, candidate.method)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)

    if fallback_item:
        feed_url = str(fallback_item.get("feed_url") or "")
        if feed_url:
            candidate = FeedCandidate(url=feed_url, method="fallback_registry", source_url=feed_url, notes="user_or_team_whitelist")
            key = (candidate.url, candidate.method)
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
        for extra in fallback_item.get("candidate_feed_urls", []):
            candidate = FeedCandidate(url=str(extra), method="fallback_registry", source_url=str(extra), notes="candidate_feed_urls")
            key = (candidate.url, candidate.method)
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
    return candidates[:max_candidates]


def candidate_score(candidate: FeedCandidate, feed_meta: dict[str, Any]) -> int:
    score = 0
    if candidate.method == "html_link_rel":
        score += 6
    elif candidate.method == "direct_feed_page":
        score += 5
    elif candidate.method == "anchor_hint":
        score += 4
    elif candidate.method == "fallback_registry":
        score += 3
    elif candidate.method == "html_link_href":
        score += 3
    elif candidate.method == "common_path":
        score += 1
    if feed_meta.get("item_count", 0) >= 5:
        score += 2
    elif feed_meta.get("item_count", 0) >= 1:
        score += 1
    candidate_host = urllib.parse.urlparse(candidate.url).netloc
    source_host = urllib.parse.urlparse(candidate.source_url).netloc
    if candidate_host and candidate_host == source_host:
        score += 1
    if candidate.notes:
        score += 1
    return score


def choose_best_validated(
    site: dict[str, Any],
    candidates: list[FeedCandidate],
    request_timeout: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_score = -1
    for candidate in candidates:
        row: dict[str, Any] = {
            "url": candidate.url,
            "method": candidate.method,
            "source_url": candidate.source_url,
            "notes": candidate.notes,
            "status": "pending",
        }
        try:
            payload, content_type = http_get(candidate.url, timeout=request_timeout, accept=FEED_ACCEPT)
            feed_meta = parse_feed_payload(payload, candidate.url, content_type=content_type)
            score = candidate_score(candidate, feed_meta)
            row.update(
                {
                    "status": "ok",
                    "score": score,
                    "feed_type": feed_meta.get("feed_type", ""),
                    "channel_title": feed_meta.get("channel_title", ""),
                    "item_count": feed_meta.get("item_count", 0),
                    "latest_title": feed_meta.get("latest_title", ""),
                    "latest_published_at": feed_meta.get("latest_published_at", ""),
                    "site_url": feed_meta.get("site_url", ""),
                    "content_type": feed_meta.get("content_type", ""),
                }
            )
            rows.append(row)
            if score > best_score:
                best_score = score
                best = {"candidate": candidate, "feed_meta": feed_meta, "score": score}
        except Exception as exc:
            row.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            rows.append(row)
    return best, rows


def build_registry_item(site: dict[str, Any], best: dict[str, Any]) -> dict[str, Any]:
    candidate: FeedCandidate = best["candidate"]
    meta = best["feed_meta"]
    return {
        "site_id": site["site_id"],
        "label": site["label"],
        "homepage_url": site.get("homepage_url", ""),
        "landing_urls": site.get("landing_urls", []),
        "kind_hints": site.get("kind_hints", []),
        "feed_url": candidate.url,
        "feed_type": meta.get("feed_type", ""),
        "discovery_method": candidate.method,
        "discovery_source_url": candidate.source_url,
        "language": site.get("language", "unknown"),
        "validation": {
            "status": "ok",
            "score": best["score"],
            "channel_title": meta.get("channel_title", ""),
            "item_count": meta.get("item_count", 0),
            "latest_title": meta.get("latest_title", ""),
            "latest_published_at": meta.get("latest_published_at", ""),
            "validated_at": isoformat_z(utc_now()),
        },
    }


def render_markdown(manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Official Web Feed Discovery")
    lines.append("")
    lines.append("## Overview")
    lines.append(f'- Generated at: {manifest.get("generated_at", "")}')
    lines.append(f'- Sites checked: {manifest.get("stats", {}).get("site_count", 0)}')
    lines.append(f'- Valid feeds: {manifest.get("stats", {}).get("valid_count", 0)}')
    lines.append(f'- Errors: {manifest.get("stats", {}).get("error_count", 0)}')
    lines.append("")
    for row in manifest.get("sites", []):
        lines.append(f'## {row.get("label", "")}')
        lines.append(f'- Homepage: {row.get("homepage_url", "")}')
        if row.get("status") == "ok":
            lines.append(f'- Feed: {row.get("feed_url", "")}')
            lines.append(f'- Method: {row.get("discovery_method", "")}')
            lines.append(f'- Latest: {row.get("latest_published_at", "")} | {row.get("latest_title", "")}')
        else:
            lines.append(f'- Error: {row.get("error", "no valid feed found")}')
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-registry",
        default="content/pipeline/configs/official_web_seed_registry.json",
        help="Seed registry of official AI company homepages/blog/newsletter landing pages.",
    )
    parser.add_argument(
        "--fallback-registry",
        default="",
        help="Optional whitelist/fallback registry. Used only after autodiscovery candidates.",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=8,
        help="Per-request timeout in seconds for page fetch and feed validation.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=12,
        help="Maximum feed candidates to validate per site after prioritization.",
    )
    parser.add_argument(
        "--site-ids",
        default="",
        help="Optional comma-separated site_id filter for faster scoped validation runs.",
    )
    parser.add_argument("--out-dir", required=True, help="Directory where autodiscovery outputs will be written.")
    args = parser.parse_args()

    seed_data = load_json(args.seed_registry)
    source_group = seed_data.get("source_group") or {}
    sites = [item for item in source_group.get("items", []) if item.get("site_id") and item.get("homepage_url")]
    if args.site_ids:
        wanted = {value.strip() for value in args.site_ids.split(",") if value.strip()}
        sites = [site for site in sites if site["site_id"] in wanted]
    fallback_map = load_items(args.fallback_registry) if args.fallback_registry else {}

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    registry_items: list[dict[str, Any]] = []
    manifest_sites: list[dict[str, Any]] = []

    for site in sites:
        fallback_item = fallback_map.get(str(site["site_id"]))
        candidates = prioritize_candidates(
            site,
            fallback_item,
            request_timeout=args.request_timeout,
            max_candidates=args.max_candidates,
        )
        best, candidate_rows = choose_best_validated(site, candidates, request_timeout=args.request_timeout)
        if best is None:
            manifest_sites.append(
                {
                    "site_id": site["site_id"],
                    "label": site["label"],
                    "homepage_url": site.get("homepage_url", ""),
                    "status": "error",
                    "error": "no valid feed found",
                    "candidates": candidate_rows,
                }
            )
            continue
        item = build_registry_item(site, best)
        registry_items.append(item)
        manifest_sites.append(
            {
                "site_id": site["site_id"],
                "label": site["label"],
                "homepage_url": site.get("homepage_url", ""),
                "status": "ok",
                "feed_url": item["feed_url"],
                "feed_type": item["feed_type"],
                "discovery_method": item["discovery_method"],
                "latest_title": item["validation"]["latest_title"],
                "latest_published_at": item["validation"]["latest_published_at"],
                "candidates": candidate_rows,
            }
        )

    registry = {
        "version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "description": "Autodiscovered official blog/newsletter feeds. Seed pages are discovery starting points, not a hard whitelist.",
        "source_group": {
            "group_id": "official_web_autodiscovered_v1",
            "enabled": True,
            "source_family": "official_web",
            "source_type": "blog_or_newsletter",
            "priority": "P0",
            "discovery_channel": "rss_autodiscovery_then_fallback",
            "fetch_mode": "discover_then_fulltext",
            "fetcher": "web_feed_autodiscovery",
            "items": registry_items,
        },
    }
    manifest = {
        "version": SCHEMA_VERSION,
        "generated_at": registry["generated_at"],
        "seed_registry_path": str(Path(args.seed_registry).expanduser().resolve()),
        "fallback_registry_path": str(Path(args.fallback_registry).expanduser().resolve()) if args.fallback_registry else "",
        "stats": {
            "site_count": len(sites),
            "valid_count": len(registry_items),
            "error_count": max(0, len(sites) - len(registry_items)),
        },
        "sites": manifest_sites,
    }

    (out_dir / "official_web_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "feed_discovery_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "feed_discovery_manifest.md").write_text(render_markdown(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
