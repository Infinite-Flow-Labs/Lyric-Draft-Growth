from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

SHARED_DIR = Path(__file__).resolve().parents[1] / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from linked_source_enrichment import fetch_link_context, normalize_space

try:
    from jsonschema import validate as jsonschema_validate
except Exception:  # pragma: no cover
    jsonschema_validate = None


SCHEMA_VERSION = "0.1.0"
METRIC_RE = re.compile(
    r"\$\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s?(?:k|m|b|million|billion)\b",
    re.IGNORECASE,
)
ENTITY_RE = re.compile(r"\b(?:[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9&.-]+){0,3}|[A-Z]{2,})\b")

RELEASE_TERMS = (
    "launch",
    "launched",
    "release",
    "released",
    "introducing",
    "announced",
    "now available",
    "available today",
    "rollout",
    "new model",
    "new feature",
    "new capability",
    "partnership",
)
TASK_HINT_PATTERNS = {
    "release": (r"\brelease\b", r"\blaunched\b", r"\bintroducing\b", r"\bavailable\b"),
    "workflow": (r"\bworkflow\b", r"\bpipeline\b", r"\bsteps\b"),
    "tutorial": (r"\bguide\b", r"\bhow to\b", r"\btutorial\b"),
    "comparison": (r"\bvs\b", r"\bcompare\b", r"\bbenchmark\b"),
    "opinion_decode": (r"\bwhat this means\b", r"\bwhy\b", r"\bfuture\b"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = normalize_space(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def release_signals(text: str) -> list[str]:
    lowered = text.lower()
    out = [term for term in RELEASE_TERMS if term in lowered]
    return compact_list(out)


def metric_signals(text: str) -> list[str]:
    return compact_list(METRIC_RE.findall(text))[:24]


def named_entities(text: str) -> list[str]:
    entities = []
    for match in ENTITY_RE.findall(text):
        token = normalize_space(match)
        if len(token) < 2:
            continue
        if token.lower() in {"rt", "pinned", "the", "and"}:
            continue
        entities.append(token)
    return compact_list(entities)[:28]


def task_hints(text: str, kind_hints: list[str]) -> list[str]:
    lowered = text.lower()
    hints: list[str] = []
    for hint, patterns in TASK_HINT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lowered, re.IGNORECASE):
                hints.append(hint)
                break
    for hint in kind_hints:
        normalized = normalize_space(hint).lower()
        if not normalized:
            continue
        if "research" in normalized:
            hints.append("opinion_decode")
        if "product" in normalized or "company" in normalized:
            hints.append("release")
    return compact_list(hints)


def build_fact_anchors(
    title: str,
    summary: str,
    release_hits: list[str],
    metric_hits: list[str],
    entities: list[str],
    canonical_url: str,
) -> list[str]:
    anchors: list[str] = [title]
    if summary:
        anchors.append(summary)
    anchors.extend(release_hits[:8])
    anchors.extend(metric_hits[:12])
    anchors.extend(entities[:16])
    if canonical_url:
        anchors.append(canonical_url)
    return compact_list(anchors)[:40]


def build_source_item(
    article: dict[str, Any],
    *,
    fetched_at: str,
    fetch_timeout: int,
    max_chars: int,
    min_words: int,
    allow_metadata_fallback: bool,
) -> tuple[dict[str, Any], str]:
    title = normalize_space(article.get("title", ""))
    summary = normalize_space(article.get("summary", ""))
    canonical_url = normalize_space(article.get("origin_url", ""))
    site_label = normalize_space(article.get("site_label", "")) or normalize_space(article.get("author", ""))
    site_id = normalize_space(article.get("site_id", ""))
    feed_url = normalize_space(article.get("feed_url", ""))
    kind_hints = [normalize_space(value) for value in article.get("kind_hints", []) if normalize_space(value)]

    assembly_notes: list[str] = []
    full_text = ""
    primary_text_source = "article_body"
    article_words = 0

    try:
        linked = fetch_link_context(
            canonical_url,
            timeout=max(5, fetch_timeout),
            max_chars=max(1000, max_chars),
            min_words=max(40, min_words),
        )
        full_text = linked["text"]
        article_words = int(linked.get("word_count", 0))
        assembly_notes.append(f"article_body_fetched:{canonical_url}")
        assembly_notes.append(f"article_body_words={article_words}")
    except Exception as exc:
        if not allow_metadata_fallback:
            raise RuntimeError(f"fulltext_fetch_failed:{type(exc).__name__}: {exc}") from exc
        primary_text_source = "metadata_fallback"
        full_text = "\n\n".join(
            [
                f"Article title: {title}" if title else "",
                f"Article summary: {summary}" if summary else "",
                f"Canonical URL: {canonical_url}" if canonical_url else "",
            ]
        ).strip()
        assembly_notes.append(f"fulltext_fetch_failed:{type(exc).__name__}")
        assembly_notes.append("used_metadata_fallback")

    if not full_text:
        full_text = f"Article title: {title}" if title else canonical_url

    combined_for_signals = "\n\n".join([title, summary, full_text])
    release_hits = release_signals(combined_for_signals)
    metric_hits = metric_signals(combined_for_signals)
    entity_hits = named_entities(combined_for_signals)
    hint_hits = task_hints(combined_for_signals, kind_hints)
    fact_hits = build_fact_anchors(
        title=title,
        summary=summary,
        release_hits=release_hits,
        metric_hits=metric_hits,
        entities=entity_hits,
        canonical_url=canonical_url,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_id": article["source_id"],
        "fetched_at": fetched_at,
        "platform": "web",
        "source_kind": "web_article",
        "canonical_url": canonical_url,
        "author": {
            "handle": None,
            "display_name": site_label or None,
            "account_url": article.get("homepage_url") or None,
        },
        "title": title or None,
        "language": article.get("language") or "unknown",
        "published_at": article.get("published_at") or None,
        "participants": [],
        "source_assets": [
            {
                "asset_kind": "article_page",
                "url": canonical_url,
                "selected_for_text": True,
                "notes": f"primary_text_source={primary_text_source}",
            },
            {
                "asset_kind": "rss_feed",
                "url": feed_url,
                "selected_for_text": False,
                "notes": f"site_id={site_id}" if site_id else None,
            },
        ],
        "content": {
            "primary_text_source": primary_text_source,
            "summary": summary or None,
            "full_text": full_text,
            "sections": compact_list(
                [
                    "article_body" if primary_text_source == "article_body" else "metadata_fallback",
                    "official_web_article",
                    *kind_hints[:2],
                ]
            ),
            "raw_quotes": [],
            "assembly_notes": "; ".join(assembly_notes) if assembly_notes else None,
        },
        "extracted_signals": {
            "release_signals": release_hits,
            "metric_signals": metric_hits,
            "named_entities": entity_hits,
            "task_hints": hint_hits,
            "fact_anchors": fact_hits,
            "normalization_notes": f"site_id={site_id}; article_words={article_words}" if site_id else f"article_words={article_words}",
        },
    }
    return payload, primary_text_source


def render_markdown(item: dict[str, Any]) -> str:
    lines = [
        f"# Source Item {item['source_id']}",
        "",
        f"- Platform: {item['platform']}",
        f"- Source Kind: {item['source_kind']}",
        f"- Canonical URL: {item['canonical_url']}",
        f"- Author: {item['author'].get('display_name') or item['author'].get('handle')}",
        f"- Published At: {item.get('published_at', '')}",
        f"- Primary Text Source: {item['content'].get('primary_text_source')}",
        "",
        "## Signals",
        f"- Release Signals: {', '.join(item['extracted_signals'].get('release_signals', []))}",
        f"- Task Hints: {', '.join(item['extracted_signals'].get('task_hints', []))}",
        f"- Fact Anchors: {len(item['extracted_signals'].get('fact_anchors', []))}",
        "",
        "## Content Preview",
        "",
        item["content"]["full_text"][:1500],
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-catalog", required=True, help="Path to article_catalog.json")
    parser.add_argument("--out-root", required=True, help="Directory where source_item artifacts will be written")
    parser.add_argument(
        "--schema",
        default="framework/SOURCE_ITEM_SCHEMA.json",
        help="Path to SOURCE_ITEM_SCHEMA.json",
    )
    parser.add_argument("--fetch-timeout", type=int, default=25, help="Article fulltext fetch timeout in seconds")
    parser.add_argument("--max-chars", type=int, default=12000, help="Max chars kept from fetched article body")
    parser.add_argument("--min-words", type=int, default=120, help="Minimum words required for fetched article body")
    parser.add_argument(
        "--allow-metadata-fallback",
        action="store_true",
        help="Allow fallback to title+summary when article fulltext fetch fails",
    )
    args = parser.parse_args()

    catalog = load_json(args.article_catalog)
    schema = load_json(args.schema)
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    fetched_at = isoformat_z(utc_now())
    articles = catalog.get("articles", [])
    seen_source_ids: set[str] = set()
    rows: list[dict[str, Any]] = []
    schema_errors = 0

    for article in articles:
        source_id = str(article.get("source_id") or "").strip()
        if not source_id or source_id in seen_source_ids:
            continue
        seen_source_ids.add(source_id)
        target_dir = out_root / source_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_json = target_dir / "source_item.json"
        out_md = target_dir / "source_item.md"

        try:
            payload, mode = build_source_item(
                article,
                fetched_at=fetched_at,
                fetch_timeout=args.fetch_timeout,
                max_chars=args.max_chars,
                min_words=args.min_words,
                allow_metadata_fallback=args.allow_metadata_fallback,
            )
            if jsonschema_validate is not None:
                jsonschema_validate(payload, schema)
            status = "ok"
            validation_error = None
            dump_json(out_json, payload)
            out_md.write_text(render_markdown(payload), encoding="utf-8")
            print(f"{source_id} -> ok ({mode})")
        except Exception as exc:
            status = "error"
            validation_error = f"{type(exc).__name__}: {exc}"
            schema_errors += 1
            print(f"{source_id} -> error ({validation_error})")

        rows.append(
            {
                "source_id": source_id,
                "status": status,
                "output_json": str(out_json) if status == "ok" else "",
                "output_md": str(out_md) if status == "ok" else "",
                "error": validation_error,
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": fetched_at,
        "article_catalog_ref": str(Path(args.article_catalog).expanduser().resolve()),
        "out_root": str(out_root),
        "count": len(rows),
        "ok_count": sum(1 for row in rows if row["status"] == "ok"),
        "error_count": sum(1 for row in rows if row["status"] == "error"),
        "schema_errors": schema_errors,
        "results": rows,
    }
    dump_json(out_root / "source_item_manifest.json", manifest)
    print(f"source_items={manifest['count']} ok={manifest['ok_count']} errors={manifest['error_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
