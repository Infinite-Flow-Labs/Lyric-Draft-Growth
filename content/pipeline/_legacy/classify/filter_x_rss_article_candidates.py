from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

SHARED_DIR = Path(__file__).resolve().parents[1] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from linked_source_enrichment import extract_urls


SCHEMA_VERSION = "0.1.0"
DEFAULT_ARTICLE_PATTERNS = [
    "/article/",
    "/articles/",
    "x.com/i/articles/",
    "substack.com",
    "beehiiv.com",
    "medium.com",
    "/blog/",
    "/news/",
    "newsletter",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_patterns(raw: str) -> list[str]:
    if not raw.strip():
        return DEFAULT_ARTICLE_PATTERNS
    values = [item.strip().lower() for item in raw.split(",")]
    return [item for item in values if item]


def collect_signals(post: dict[str, Any], patterns: list[str]) -> list[str]:
    title = str(post.get("title") or "")
    summary = str(post.get("summary") or "")
    origin_url = str(post.get("origin_url") or "")
    blob = "\n".join([title, summary, origin_url]).lower()
    urls = extract_urls("\n".join([title, summary, origin_url]))

    hits: list[str] = []
    for pattern in patterns:
        if pattern in blob:
            hits.append(f"pattern:{pattern}")

    for url in urls:
        lowered = url.lower()
        for pattern in patterns:
            if pattern in lowered:
                hits.append(f"url:{url}")
                break

    deduped: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        if hit in seen:
            continue
        seen.add(hit)
        deduped.append(hit)
    return deduped


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# X RSS Article Candidates",
        "",
        "## Overview",
        f"- Generated at: {payload.get('generated_at', '')}",
        f"- Input posts: {payload.get('stats', {}).get('input_post_count', 0)}",
        f"- Article-like posts: {payload.get('stats', {}).get('article_like_post_count', 0)}",
        f"- Handles with article-like posts: {payload.get('stats', {}).get('handle_count', 0)}",
        "",
    ]
    for row in payload.get("handles", []):
        lines.append(f"## @{row.get('handle', '')}")
        lines.append(f"- Article-like posts: {row.get('post_count', 0)}")
        for post in row.get("posts", [])[:5]:
            lines.append(f"- {post.get('published_at', '')} | {post.get('title', '')}")
            lines.append(f"  {post.get('origin_url', '')}")
            signals = post.get("article_signals", [])
            if signals:
                lines.append(f"  signals: {', '.join(signals[:3])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-catalog", required=True, help="Path to guest_rss_catalog.json")
    parser.add_argument("--out-dir", required=True, help="Directory for filtered article-like RSS catalog")
    parser.add_argument(
        "--article-patterns",
        default="",
        help="Comma-separated patterns. Default keeps article/blog/newsletter-like signals.",
    )
    parser.add_argument("--max-per-handle", type=int, default=20, help="Max article-like posts per handle")
    args = parser.parse_args()

    in_catalog = load_json(args.in_catalog)
    patterns = normalize_patterns(args.article_patterns)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    posts_by_handle: dict[str, list[dict[str, Any]]] = {}
    input_post_count = 0
    for post in in_catalog.get("posts", []):
        input_post_count += 1
        signals = collect_signals(post, patterns)
        if not signals:
            continue
        handle = str(post.get("account_handle") or post.get("author") or "")
        if not handle:
            continue
        enriched = dict(post)
        enriched["article_signals"] = signals
        posts_by_handle.setdefault(handle, []).append(enriched)

    handle_rows: list[dict[str, Any]] = []
    article_posts: list[dict[str, Any]] = []
    for handle in sorted(posts_by_handle.keys(), key=lambda x: x.lower()):
        rows = posts_by_handle[handle][: max(1, args.max_per_handle)]
        handle_rows.append(
            {
                "handle": handle,
                "post_count": len(rows),
                "posts": rows,
            }
        )
        article_posts.extend(rows)

    catalog = {
        "version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "source_catalog_ref": str(Path(args.in_catalog).expanduser().resolve()),
        "article_patterns": patterns,
        "stats": {
            "input_post_count": input_post_count,
            "article_like_post_count": len(article_posts),
            "handle_count": len(handle_rows),
        },
        "handles": handle_rows,
        "posts": article_posts,
    }

    dump_json(out_dir / "guest_rss_catalog.json", catalog)
    (out_dir / "guest_rss_catalog.md").write_text(render_markdown(catalog), encoding="utf-8")
    print(f"input_posts={input_post_count} article_like_posts={len(article_posts)} handles={len(handle_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
