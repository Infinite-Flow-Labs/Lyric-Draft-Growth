from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


URL_RE = re.compile(r"https?://\S+")


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def normalize_publishing_hints(raw_hints: dict[str, Any]) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    for key in ["source_label", "source_url", "closing_slogan", "primary_link_url", "primary_link_label"]:
        value = raw_hints.get(key)
        if value:
            hints[key] = " ".join(str(value).split()).strip()
    return hints


def pick_primary_link(source_item: dict[str, Any]) -> tuple[str, str]:
    canonical_url = str(source_item.get("canonical_url") or "").strip()
    source_assets = source_item.get("source_assets") or []

    for asset in source_assets:
        asset_kind = str(asset.get("asset_kind") or "").strip()
        asset_url = str(asset.get("url") or "").strip()
        if not asset_url:
            continue
        if asset_kind in {"linked_article", "linked_report", "linked_post", "linked_page"}:
            return asset_url, "原文链接"

    return canonical_url, "来源链接"


def derive_source_label(source_item: dict[str, Any]) -> str:
    author = source_item.get("author") or {}
    display_name = " ".join(str(author.get("display_name") or "").split()).strip()
    title = " ".join(str(source_item.get("title") or "").split()).strip()
    platform = str(source_item.get("platform") or "").strip()
    source_kind = str(source_item.get("source_kind") or "").strip()

    if platform == "podcast":
        if display_name and title:
            return f"{display_name} · {title}"
        return display_name or title

    if source_kind == "x_thread" and display_name:
        return display_name

    return display_name or title


def build_publishing_hints(source_item: dict[str, Any], raw_hints: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_hints = raw_hints or {}
    primary_link_url, default_link_label = pick_primary_link(source_item)
    parsed = urlparse(primary_link_url) if primary_link_url else None
    source_url = str(raw_hints.get("source_url") or source_item.get("canonical_url") or primary_link_url or "").strip()
    primary_link_label = str(raw_hints.get("primary_link_label") or "").strip()
    if not primary_link_label and primary_link_url:
        primary_link_label = default_link_label
        if parsed and parsed.netloc:
            primary_link_label = f"{default_link_label} · {parsed.netloc}"

    hints = {
        "source_label": str(raw_hints.get("source_label") or derive_source_label(source_item) or "").strip(),
        "source_url": source_url,
        "closing_slogan": str(raw_hints.get("closing_slogan") or "").strip(),
        "primary_link_url": primary_link_url,
        "primary_link_label": primary_link_label,
    }
    return normalize_publishing_hints(hints)


def split_markdown_chunks(body_markdown: str) -> list[str]:
    text = str(body_markdown or "").replace("\r\n", "\n").strip()
    return [chunk.strip() for chunk in re.split(r"\n\s*\n+", text) if chunk.strip()]


def normalize_quote(lines: list[str]) -> str:
    return " ".join(line.lstrip("> ").strip() for line in lines if line.strip()).strip()


def parse_chunk(chunk: str) -> dict[str, Any]:
    lines = [line.rstrip() for line in chunk.splitlines() if line.strip()]
    if not lines:
        return {"type": "paragraph", "text": ""}

    if len(lines) == 1 and lines[0].startswith(("## ", "### ")):
        return {"type": "section_heading", "text": lines[0].lstrip("# ").strip()}

    if all(line.lstrip().startswith(">") for line in lines):
        return {"type": "quote", "text": normalize_quote(lines)}

    bullet_prefixes = ("- ", "* ", "• ")
    bullet_lines = [line for line in lines if line.lstrip().startswith(bullet_prefixes)]
    if bullet_lines and len(bullet_lines) == len(lines):
        return {
            "type": "bullet_list",
            "text": "",
            "items": compact_list([line.lstrip()[2:].strip() for line in lines]),
        }
    if bullet_lines and len(lines) >= 2 and not lines[0].lstrip().startswith(bullet_prefixes):
        return {
            "type": "bullet_list",
            "text": " ".join(lines[:1]).strip(),
            "items": compact_list([line.lstrip()[2:].strip() for line in lines[1:]]),
        }

    if URL_RE.search(chunk) and len(lines) <= 3:
        url_match = URL_RE.search(chunk)
        if url_match:
            url = url_match.group(0).strip()
            before = chunk[: url_match.start()].strip()
            after = chunk[url_match.end() :].strip()
            label = ""
            text = before
            if after:
                label = after
            elif before and len(lines) == 2:
                label = lines[0].strip()
            if text or label:
                return {
                    "type": "link_cta",
                    "text": text,
                    "url": url,
                    "label": label,
                }

    text = " ".join(line.strip() for line in lines).strip()
    if 12 <= len(text) <= 44 and "。" not in text and "，" not in text and not URL_RE.search(text):
        return {"type": "section_heading", "text": text}

    return {"type": "paragraph", "text": text}


def choose_hero_heading(dek: str, first_block: dict[str, Any] | None) -> str:
    if first_block and first_block.get("type") == "paragraph":
        text = str(first_block.get("text") or "").strip()
        if 24 <= len(text) <= 90 and not URL_RE.search(text):
            return text
    return " ".join(str(dek or "").split()).strip()


X_POST_URL_RE = re.compile(r"https?://(?:x\.com|twitter\.com)/\w+/status/\d+")


def normalize_article_blocks(raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for block in raw_blocks:
        block_type = str(block.get("type", "")).strip()
        text = " ".join(str(block.get("text", "")).split()).strip()
        items = compact_list(block.get("items", []))
        payload: dict[str, Any] = {"type": block_type, "text": text}
        if items:
            payload["items"] = items
        if block.get("url"):
            payload["url"] = str(block["url"]).strip()
        if block.get("label"):
            payload["label"] = " ".join(str(block["label"]).split()).strip()
        # source_embed blocks only need url
        if block_type == "source_embed":
            if block.get("url"):
                normalized.append({"type": "source_embed", "text": text, "url": block["url"]})
            continue
        if block_type == "bullet_list" and not items:
            continue
        if block_type != "bullet_list" and block_type != "link_cta" and not text:
            continue
        normalized.append(payload)
    return normalized


def build_article_blocks(*, title: str, dek: str, body_markdown: str, publishing_hints: dict[str, Any]) -> list[dict[str, Any]]:
    chunks = split_markdown_chunks(body_markdown)
    parsed = [parse_chunk(chunk) for chunk in chunks]

    hero_heading = choose_hero_heading(dek, parsed[0] if parsed else None)
    blocks: list[dict[str, Any]] = []
    if hero_heading:
        blocks.append({"type": "hero_heading", "text": hero_heading})

    for index, block in enumerate(parsed):
        if index == 0 and block.get("type") == "paragraph" and block.get("text") == hero_heading:
            continue
        blocks.append(block)

    # Auto-insert source_embed blocks for X post URLs from publishing_hints
    source_url = str(publishing_hints.get("source_url") or "").strip()
    has_embed = any(block.get("type") == "source_embed" for block in blocks)
    if not has_embed and source_url and X_POST_URL_RE.match(source_url):
        blocks.append({
            "type": "source_embed",
            "text": "",
            "url": source_url,
        })

    has_link_cta = any(block.get("type") == "link_cta" for block in blocks)
    if not has_link_cta and publishing_hints.get("primary_link_url"):
        primary_url = publishing_hints["primary_link_url"]
        # Skip link_cta if we already embedded this URL as source_embed
        if not (has_embed or (source_url and X_POST_URL_RE.match(source_url) and primary_url == source_url)):
            blocks.append(
                {
                    "type": "link_cta",
                    "text": "如果你想看原始论证链，可以直接读原文：",
                    "url": primary_url,
                    "label": publishing_hints.get("primary_link_label") or primary_url,
                }
            )

    if publishing_hints.get("closing_slogan"):
        blocks.append({"type": "closing_slogan", "text": publishing_hints["closing_slogan"]})

    return normalize_article_blocks(blocks)
