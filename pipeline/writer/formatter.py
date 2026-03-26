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


BOLD_MARKER_RE = re.compile(r"\*\*([^*]+)\*\*")


def strip_bold_markers(text: str) -> str:
    """Remove **bold** markdown markers, keep the text inside."""
    return BOLD_MARKER_RE.sub(r"\1", text)


def normalize_article_blocks(raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for block in raw_blocks:
        block_type = str(block.get("type", "")).strip()
        text = strip_bold_markers(" ".join(str(block.get("text", "")).split()).strip())
        items = compact_list([strip_bold_markers(item) for item in block.get("items", [])])
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

    # Deduplicate: if the first quote block is identical to the dek, skip it
    # (title and dek are handled separately by the publish tool, not as blocks)
    dek_normalized = " ".join(str(dek or "").split()).strip()
    blocks: list[dict[str, Any]] = []
    skipped_dek_quote = False

    for block in parsed:
        text_normalized = " ".join(str(block.get("text", "")).split()).strip()
        # Skip the first quote that duplicates the dek
        if not skipped_dek_quote and block.get("type") == "quote" and text_normalized == dek_normalized:
            skipped_dek_quote = True
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


# === Merged from content/pipeline/write/article_formatter.py (wrapper) ===

ALLOWED_BLOCK_TYPES = {
    "hero_heading",
    "section_heading",
    "paragraph",
    "bullet_list",
    "quote",
    "link_cta",
    "closing_slogan",
    "source_embed",
}


def _trim_text(value: str, max_len: int = 140) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _first_paragraph_text(blocks: list[dict[str, Any]]) -> str:
    for block in blocks:
        if str(block.get("type", "")).strip() == "paragraph":
            text = str(block.get("text", "")).strip()
            if text:
                return text
    return ""


def _derive_bullet_items_from_blocks(blocks: list[dict[str, Any]]) -> list[str]:
    paragraph_texts = [
        str(block.get("text", "")).strip()
        for block in blocks
        if str(block.get("type", "")).strip() == "paragraph" and str(block.get("text", "")).strip()
    ]
    for text in reversed(paragraph_texts):
        tail = text.split("：", 1)[1] if "：" in text else text
        parts = [part.strip(" ，。；：,.!?！？") for part in re.split(r"[，；。]", tail) if part.strip()]
        candidates = [_trim_text(item, 42) for item in parts if len(item) >= 6]
        dedup: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            dedup.append(item)
        if len(dedup) >= 2:
            return dedup[:3]

    fallback = [_trim_text(text, 42) for text in paragraph_texts[:3] if len(text) >= 8]
    if fallback:
        return fallback[:3]
    return [
        "先用轻任务跑通链路，再决定是否扩到主流程",
        "把权限边界和执行范围先写清楚",
        "观察一周稳定性再扩大使用范围",
    ]


def _ensure_required_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = list(blocks)
    hero_index = next((idx for idx, block in enumerate(out) if str(block.get("type", "")).strip() == "hero_heading"), -1)
    desired_quote_index = (hero_index + 1) if hero_index >= 0 else 0
    quote_indices = [idx for idx, block in enumerate(out) if str(block.get("type", "")).strip() == "quote"]
    has_quote = bool(quote_indices)
    has_bullet = any(str(block.get("type", "")).strip() == "bullet_list" for block in out)

    if not has_quote:
        quote_seed = _trim_text(_first_paragraph_text(out), 150)
        if quote_seed:
            out.insert(desired_quote_index, {"type": "quote", "text": quote_seed})
    else:
        first_quote_index = quote_indices[0]
        if first_quote_index != desired_quote_index:
            quote_block = out.pop(first_quote_index)
            if first_quote_index < desired_quote_index:
                desired_quote_index -= 1
            out.insert(desired_quote_index, quote_block)

    if not has_bullet:
        items = _derive_bullet_items_from_blocks(out)
        bullet_block = {
            "type": "bullet_list",
            "text": "你可以先按这三步执行：",
            "items": items[:3],
        }
        # Put bullets before link_cta / closing_slogan to keep reading flow stable.
        insert_at = len(out)
        for index, block in enumerate(out):
            block_type = str(block.get("type", "")).strip()
            if block_type in {"link_cta", "closing_slogan"}:
                insert_at = index
                break
        out.insert(insert_at, bullet_block)

    return out


# build_publishing_hints: defined above (original, not wrapper)


# build_article_blocks: defined above (original, not wrapper)


def sanitize_article_blocks(raw_blocks: list[dict[str, Any]], *, keep_hero_first: bool = False) -> list[dict[str, Any]]:
    normalized = normalize_article_blocks(raw_blocks or [])
    if not normalized:
        return []

    filtered: list[dict[str, Any]] = []
    for block in normalized:
        block_type = str(block.get("type", "")).strip()
        if block_type not in ALLOWED_BLOCK_TYPES:
            continue
        filtered.append(block)

    if not keep_hero_first:
        return _ensure_required_blocks(filtered)

    hero_blocks = [block for block in filtered if str(block.get("type", "")).strip() == "hero_heading"]
    other_blocks = [block for block in filtered if str(block.get("type", "")).strip() != "hero_heading"]
    if not hero_blocks:
        return _ensure_required_blocks(other_blocks)
    return _ensure_required_blocks([hero_blocks[0], *other_blocks])


def validate_article_publish_contract(
    *,
    article_blocks: list[dict[str, Any]],
    inline_insertions: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    blocks = sanitize_article_blocks(article_blocks or [], keep_hero_first=True)
    if not blocks:
        errors.append("article_blocks_empty")
        return errors, warnings

    if str(blocks[0].get("type", "")).strip() != "hero_heading":
        warnings.append("first_block_not_hero_heading")

    for index, block in enumerate(blocks, start=1):
        block_type = str(block.get("type", "")).strip()
        text = str(block.get("text", "")).strip()

        if block_type not in ALLOWED_BLOCK_TYPES:
            errors.append(f"block_{index}_unsupported_type:{block_type}")
            continue

        if block_type == "bullet_list":
            items = [str(item).strip() for item in block.get("items", []) if str(item).strip()]
            if not items:
                errors.append(f"block_{index}_bullet_items_empty")
            if len(items) > 12:
                warnings.append(f"block_{index}_bullet_items_too_many")
            continue

        if block_type == "link_cta":
            url = str(block.get("url", "")).strip()
            if not url:
                errors.append(f"block_{index}_link_cta_missing_url")
            if not text:
                warnings.append(f"block_{index}_link_cta_missing_text")
            continue

        if block_type == "source_embed":
            url = str(block.get("url", "")).strip()
            if not url:
                errors.append(f"block_{index}_source_embed_missing_url")
            continue

        if not text:
            errors.append(f"block_{index}_missing_text")

    if not any(str(block.get("type", "")).strip() == "section_heading" for block in blocks):
        warnings.append("section_heading_missing")

    if not any(str(block.get("type", "")).strip() == "link_cta" for block in blocks):
        warnings.append("link_cta_missing")
    if not any(str(block.get("type", "")).strip() == "quote" for block in blocks):
        errors.append("quote_block_required")
    if not any(str(block.get("type", "")).strip() == "bullet_list" for block in blocks):
        errors.append("bullet_list_block_required")

    seen_image_ids: set[str] = set()
    max_ordinal = len(blocks)
    for idx, insertion in enumerate(inline_insertions or [], start=1):
        image_id = str(insertion.get("image_id", "")).strip()
        image_path = str(insertion.get("image_path", "")).strip()
        after_ordinal_raw = insertion.get("after_block_ordinal", 0)
        try:
            after_ordinal = int(after_ordinal_raw)
        except Exception:
            after_ordinal = 0

        if not image_id:
            errors.append(f"inline_{idx}_missing_image_id")
        elif image_id in seen_image_ids:
            warnings.append(f"inline_{idx}_duplicate_image_id:{image_id}")
        else:
            seen_image_ids.add(image_id)

        if not image_path:
            errors.append(f"inline_{idx}_missing_image_path")
        else:
            suffix = Path(image_path).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                warnings.append(f"inline_{idx}_nonstandard_image_suffix:{suffix or 'none'}")

        if after_ordinal <= 0:
            errors.append(f"inline_{idx}_invalid_after_block_ordinal:{after_ordinal_raw}")
        elif after_ordinal > max_ordinal:
            errors.append(f"inline_{idx}_after_block_ordinal_out_of_range:{after_ordinal}")

    return errors, warnings

