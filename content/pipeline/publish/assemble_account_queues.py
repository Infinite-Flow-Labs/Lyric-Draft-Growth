from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content.pipeline.write.article_formatter import (
    build_article_blocks,
    build_publishing_hints,
    sanitize_article_blocks,
    validate_article_publish_contract,
)


ROOT = Path(__file__).resolve().parents[3]
ACCOUNTS_RUNTIME = ROOT / "accounts_runtime"
DISTRIBUTION_RUNTIME = ROOT / "distribution_runtime"
ARTICLE_INDEX_PATH = ROOT / "content/library/articles/article_index.json"


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_body_markdown(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    return text.rstrip() + "\n"


def render_block_text(blocks: list[dict[str, Any]], fallback_markdown: str) -> str:
    if not blocks:
        return normalize_body_markdown(fallback_markdown)
    parts: list[str] = []
    for block in blocks:
        block_type = block.get("type")
        text = str(block.get("text", "")).strip()
        if block_type == "bullet_list":
            if text:
                parts.append(text)
            for item in block.get("items", []):
                parts.append(f"- {item}")
        elif block_type == "quote":
            if text:
                parts.append(f"> {text}")
        elif block_type == "link_cta":
            if text:
                parts.append(text)
            if block.get("url"):
                parts.append(str(block["url"]).strip())
        elif block_type == "source_embed":
            if block.get("url"):
                parts.append(str(block["url"]).strip())
        elif text:
            parts.append(text)
    return normalize_body_markdown("\n\n".join(part for part in parts if part.strip()))


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def build_publish_ops(
    *,
    article_blocks: list[dict[str, Any]],
    inline_insertions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    insertions_by_ordinal: dict[int, list[dict[str, Any]]] = {}
    for insertion in inline_insertions:
        ordinal = int(insertion.get("after_block_ordinal", 0) or 0)
        if ordinal <= 0:
            continue
        insertions_by_ordinal.setdefault(ordinal, []).append(insertion)

    ops: list[dict[str, Any]] = []
    for ordinal, block in enumerate(article_blocks, start=1):
        block_type = str(block.get("type", "")).strip()
        op: dict[str, Any] = {
            "op": "type_block",
            "block_type": block_type,
        }
        text = str(block.get("text", "") or "").strip()
        if text:
            op["text"] = text
        items = [str(item).strip() for item in block.get("items", []) if str(item).strip()]
        if items:
            op["items"] = items
        url = str(block.get("url", "") or "").strip()
        if url:
            op["url"] = url
        label = str(block.get("label", "") or "").strip()
        if label:
            op["label"] = label
        ops.append(op)

        for insertion in insertions_by_ordinal.get(ordinal, []):
            ops.append(
                {
                    "op": "insert_media",
                    "image_id": str(insertion.get("image_id", "")).strip(),
                    "image_path": str(insertion.get("image_path", "")).strip(),
                    "section_ref": str(insertion.get("section_ref", "")).strip(),
                }
            )
    return ops


def validate_publish_spec_payload(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    blocks = payload.get("article_blocks", []) or []
    inline_insertions = payload.get("inline_image_insertions", []) or []
    return validate_article_publish_contract(article_blocks=blocks, inline_insertions=inline_insertions)


@dataclass(frozen=True)
class AccountRuntime:
    account_id: str
    platform: str
    enabled: bool
    publisher_type: str
    publisher_account: str
    bit_port: int | None
    timezone: str
    publish_queue_dir: Path
    published_dir: Path


def load_accounts() -> list[AccountRuntime]:
    accounts: list[AccountRuntime] = []
    for account_dir in sorted(ACCOUNTS_RUNTIME.iterdir()):
        if not account_dir.is_dir() or account_dir.name.startswith("_"):
            continue
        profile_path = account_dir / "profile/account_profile.json"
        publisher_path = account_dir / "profile/publisher_config.json"
        if not profile_path.exists() or not publisher_path.exists():
            continue
        profile = load_json(profile_path)
        publisher = load_json(publisher_path)
        accounts.append(
            AccountRuntime(
                account_id=profile["account_id"],
                platform=profile.get("platform", "x"),
                enabled=bool(profile.get("enabled", True)),
                publisher_type=publisher.get("publisher_type", "x_post_bitbrowser"),
                publisher_account=publisher.get("publisher_account") or profile["account_id"],
                bit_port=publisher.get("bit_port"),
                timezone=publisher.get("timezone", "Asia/Shanghai"),
                publish_queue_dir=account_dir / "publish_queue",
                published_dir=account_dir / "published",
            )
        )
    return accounts


def content_key(item: dict[str, Any]) -> str:
    return f"{item['family']}::{item['run_id']}::{item['source_id']}"


def read_reserved_content_keys() -> set[str]:
    keys: set[str] = set()
    for root in [ACCOUNTS_RUNTIME]:
        for job_path in root.glob("*/publish_queue/*/*/publish_job.json"):
            try:
                payload = load_json(job_path)
            except Exception:
                continue
            ref = payload.get("content_ref") or {}
            if {"family", "run_id", "source_id"} <= set(ref.keys()):
                keys.add(f"{ref['family']}::{ref['run_id']}::{ref['source_id']}")
        for job_path in root.glob("*/published/*/*/publish_job.json"):
            try:
                payload = load_json(job_path)
            except Exception:
                continue
            ref = payload.get("content_ref") or {}
            if {"family", "run_id", "source_id"} <= set(ref.keys()):
                keys.add(f"{ref['family']}::{ref['run_id']}::{ref['source_id']}")
    return keys


def queued_slots_for_date(account: AccountRuntime, plan_date: str) -> int:
    date_dir = account.publish_queue_dir / plan_date
    if not date_dir.exists():
        return 0
    return len([path for path in date_dir.iterdir() if path.is_dir()])


def next_slot_dir(account: AccountRuntime, plan_date: str) -> Path:
    date_dir = account.publish_queue_dir / plan_date
    date_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(int(path.name) for path in date_dir.iterdir() if path.is_dir() and path.name.isdigit())
    next_slot = (existing[-1] + 1) if existing else 1
    return date_dir / f"{next_slot:02d}"


def choose_candidates(
    *,
    families: set[str],
    include_human_review_required: bool,
    source_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    payload = load_json(ARTICLE_INDEX_PATH)
    items = payload.get("articles", [])
    filtered = [
        item
        for item in items
        if item.get("family") in families
        and (include_human_review_required or not item.get("requires_human_review", False))
        and (not source_ids or item.get("source_id") in source_ids)
    ]
    filtered.sort(key=lambda item: (item.get("generated_at", ""), item.get("family", ""), item.get("source_id", "")), reverse=True)
    deduped: list[dict[str, Any]] = []
    seen_source_ids: set[str] = set()
    for item in filtered:
        source_id = str(item.get("source_id", "")).strip()
        if not source_id or source_id in seen_source_ids:
            continue
        seen_source_ids.add(source_id)
        deduped.append(item)
    return deduped


def build_article_queue_item(account: AccountRuntime, article: dict[str, Any], slot_dir: Path) -> dict[str, Any]:
    article_payload = load_json(Path(article["article_json"]))
    article_blocks = sanitize_article_blocks(article_payload.get("article_blocks", []) or [], keep_hero_first=True)
    publishing_hints = article_payload.get("publishing_hints", {}) or {}
    source_ref = str(article_payload.get("source_ref", "")).strip()
    if source_ref:
        source_item_path = Path(source_ref)
        if source_item_path.exists():
            source_item = load_json(source_item_path)
            publishing_hints = build_publishing_hints(source_item, publishing_hints)
            if not article_blocks:
                article_blocks = sanitize_article_blocks(
                    build_article_blocks(
                        title=article_payload.get("title", ""),
                        dek=article_payload.get("dek", ""),
                        body_markdown=article_payload.get("body_markdown", ""),
                        publishing_hints=publishing_hints,
                    ),
                    keep_hero_first=True,
                )

    title_path = slot_dir / "title.txt"
    body_path = slot_dir / "article.md"
    spec_path = slot_dir / "article_publish_spec.json"
    title_path.write_text(str(article_payload["title"]).strip() + "\n", encoding="utf-8")
    body_path.write_text(
        render_block_text(article_blocks, article_payload["body_markdown"]),
        encoding="utf-8",
    )
    assets_payload: dict[str, Any] = {
        "title_txt": str(title_path.resolve()),
        "article_md": str(body_path.resolve()),
    }

    publish_spec_payload = {
        "publish_contract_version": "article_publish_contract_v2",
        "title": article_payload["title"],
        "dek": article_payload.get("dek", ""),
        "article_blocks": article_blocks,
        "publishing_hints": publishing_hints,
        "content_ref": {
            "family": article["family"],
            "run_id": article["run_id"],
            "source_id": article["source_id"],
        },
    }

    article_dir = Path(article["article_json"]).resolve().parent
    image_brief = load_optional_json(article_dir / "article_image_brief.json")
    cover_candidates = [
        article_dir / "image_assets/cover_01/result_1.png",
        article_dir / "image_assets/cover_01/result_1.jpg",
    ]
    cover_source = next((path for path in cover_candidates if path.exists()), None)
    if cover_source is not None:
        cover_dest = slot_dir / cover_source.name.replace("result_1", "cover")
        cover_dest.write_bytes(cover_source.read_bytes())
        assets_payload["cover_image"] = str(cover_dest.resolve())
        publish_spec_payload["cover_image_path"] = str(cover_dest.resolve())

    inline_insertions: list[dict[str, Any]] = []
    blocks = article_blocks
    section_anchors: dict[str, int] = {}
    current_ref = "framing"
    current_heading_ordinal: int | None = None
    current_first_content_ordinal: int | None = None
    next_section_number = 2

    def save_anchor() -> None:
        anchor = current_first_content_ordinal or current_heading_ordinal
        if anchor:
            section_anchors[current_ref] = anchor

    for ordinal, block in enumerate(blocks, start=1):
        block_type = str(block.get("type", "")).strip()
        if block_type == "section_heading":
            save_anchor()
            current_ref = f"section_{next_section_number:02d}"
            next_section_number += 1
            current_heading_ordinal = ordinal
            current_first_content_ordinal = None
            continue
        if block_type in {"hero_heading", "link_cta", "closing_slogan", "source_embed"}:
            continue
        if current_first_content_ordinal is None:
            current_first_content_ordinal = ordinal
    save_anchor()

    if image_brief:
        for inline_brief in image_brief.get("inline_images", []):
            image_id = str(inline_brief.get("image_id", "")).strip()
            section_ref = str(inline_brief.get("section_ref", "")).strip()
            anchor_ordinal = section_anchors.get(section_ref)
            if not image_id or not anchor_ordinal:
                continue
            source_candidates = [
                article_dir / "image_assets" / image_id / "result_1.png",
                article_dir / "image_assets" / image_id / "result_1.jpg",
            ]
            source_path = next((path for path in source_candidates if path.exists()), None)
            if source_path is None:
                continue
            dest_name = f"{image_id}{source_path.suffix.lower()}"
            dest_path = slot_dir / dest_name
            dest_path.write_bytes(source_path.read_bytes())
            inline_insertions.append(
                {
                    "image_id": image_id,
                    "after_block_ordinal": anchor_ordinal,
                    "image_path": str(dest_path.resolve()),
                    "section_ref": section_ref,
                }
            )

    if inline_insertions:
        publish_spec_payload["inline_image_insertions"] = inline_insertions
        assets_payload["inline_images"] = [item["image_path"] for item in inline_insertions]

    publish_spec_payload["publish_ops"] = build_publish_ops(
        article_blocks=article_blocks,
        inline_insertions=inline_insertions,
    )

    errors, warnings = validate_publish_spec_payload(publish_spec_payload)
    publish_spec_payload["contract_validation"] = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        raise ValueError(f"publish_contract_invalid: {'; '.join(errors)}")

    dump_json(spec_path, publish_spec_payload)
    assets_payload["article_publish_spec_json"] = str(spec_path.resolve())

    job = {
        "job_id": f"{account.account_id}-{slot_dir.parent.name}-{slot_dir.name}",
        "account_id": account.account_id,
        "platform": account.platform,
        "publisher_type": account.publisher_type,
        "publish_mode": "article",
        "publisher_account": account.publisher_account,
        "status": "queued",
        "scheduled_time": "",
        "timezone": account.timezone,
        "slot_dir": str(slot_dir.resolve()),
        "content_ref": {
            "family": article["family"],
            "run_id": article["run_id"],
            "source_id": article["source_id"],
            "article_json": article["article_json"],
            "article_md": article["article_md"],
        },
        "assets": assets_payload,
        "notes": "assembled automatically from content/library/articles without duplicate cross-account assignment",
    }
    dump_json(slot_dir / "publish_job.json", job)
    return job


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Queue date in YYYY-MM-DD")
    parser.add_argument("--families", default="podcast,official_x,article_x", help="Comma-separated allowed content families")
    parser.add_argument("--source-ids", default="", help="Comma-separated exact source_id allowlist")
    parser.add_argument("--per-account-max", type=int, default=1, help="Maximum queued slots to keep per account for the target date")
    parser.add_argument("--include-human-review-required", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    families = {part.strip() for part in args.families.split(",") if part.strip()}
    source_ids = {part.strip() for part in args.source_ids.split(",") if part.strip()}
    accounts = [account for account in load_accounts() if account.enabled]
    reserved = read_reserved_content_keys()
    candidates = choose_candidates(
        families=families,
        include_human_review_required=args.include_human_review_required,
        source_ids=source_ids or None,
    )

    plan_items: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []

    for account in accounts:
        existing_count = queued_slots_for_date(account, args.date)
        if existing_count >= max(1, args.per_account_max):
            plan_items.append(
                {
                    "account_id": account.account_id,
                    "status": "skipped_existing_queue",
                    "reason": f"existing queued slots for {args.date}: {existing_count}",
                }
            )
            continue

        chosen: dict[str, Any] | None = None
        for article in candidates:
            key = content_key(article)
            if key in reserved:
                continue
            chosen = article
            reserved.add(key)
            break

        if chosen is None:
            plan_items.append(
                {
                    "account_id": account.account_id,
                    "status": "skipped_no_available_content",
                    "reason": "no unused article remained after duplicate filtering",
                }
            )
            continue

        slot_dir = next_slot_dir(account, args.date)
        plan_row = {
            "account_id": account.account_id,
            "status": "planned",
            "slot": slot_dir.name,
            "queue_dir": str(slot_dir.resolve()),
            "content_ref": {
                "family": chosen["family"],
                "run_id": chosen["run_id"],
                "source_id": chosen["source_id"],
                "article_json": chosen["article_json"],
                "article_md": chosen["article_md"],
            },
        }

        if args.dry_run:
            plan_items.append(plan_row)
            continue

        slot_dir.mkdir(parents=True, exist_ok=True)
        try:
            job = build_article_queue_item(account, chosen, slot_dir)
            plan_items.append(plan_row)
            manifest_items.append(
                {
                    "account_id": account.account_id,
                    "slot": slot_dir.name,
                    "queue_dir": str(slot_dir.resolve()),
                    "publish_job": str((slot_dir / "publish_job.json").resolve()),
                    "publish_mode": job["publish_mode"],
                    "source_id": chosen["source_id"],
                }
            )
        except Exception as exc:
            try:
                if slot_dir.exists() and not (slot_dir / "publish_job.json").exists():
                    shutil.rmtree(slot_dir, ignore_errors=True)
            except Exception:
                pass
            plan_items.append(
                {
                    "account_id": account.account_id,
                    "status": "error_build_queue_item",
                    "slot": slot_dir.name,
                    "reason": f"{type(exc).__name__}: {exc}",
                    "content_ref": {
                        "family": chosen["family"],
                        "run_id": chosen["run_id"],
                        "source_id": chosen["source_id"],
                    },
                }
            )
            continue

    generated_at = isoformat_z(datetime.now(timezone.utc))
    plan_payload = {
        "plan_date": args.date,
        "generated_at": generated_at,
        "families": sorted(families),
        "source_ids": sorted(source_ids),
        "per_account_max": args.per_account_max,
        "items": plan_items,
    }
    manifest_payload = {
        "plan_date": args.date,
        "generated_at": generated_at,
        "queued_count": len(manifest_items),
        "items": manifest_items,
    }

    plan_path = DISTRIBUTION_RUNTIME / "plans" / args.date / "distribution_plan.json"
    manifest_path = DISTRIBUTION_RUNTIME / "manifests" / args.date / "distribution_manifest.json"
    dump_json(plan_path, plan_payload)
    dump_json(manifest_path, manifest_payload)

    print(str(plan_path.resolve()))
    print(str(manifest_path.resolve()))
    print(f"planned={len([item for item in plan_items if item.get('status') == 'planned'])} queued={len(manifest_items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
