from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lane_v2.write.article_formatter import (
    build_article_blocks as lane_build_article_blocks,
    build_publishing_hints as lane_build_publishing_hints,
    normalize_article_blocks,
)


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


def build_publishing_hints(source_item: dict[str, Any], raw_hints: dict[str, Any] | None = None) -> dict[str, Any]:
    return lane_build_publishing_hints(source_item, raw_hints)


def build_article_blocks(*, title: str, dek: str, body_markdown: str, publishing_hints: dict[str, Any]) -> list[dict[str, Any]]:
    return lane_build_article_blocks(
        title=title,
        dek=dek,
        body_markdown=body_markdown,
        publishing_hints=publishing_hints,
    )


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
