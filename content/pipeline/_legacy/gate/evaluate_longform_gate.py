from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def word_count(text: str) -> int:
    return len(str(text).split())


def evaluate_longform_gate(source_item: dict[str, Any], min_fulltext_words: int) -> dict[str, Any]:
    content = source_item.get("content", {})
    extracted = source_item.get("extracted_signals", {})
    full_text = content.get("full_text", "")
    summary = content.get("summary") or ""
    assembly_notes = content.get("assembly_notes") or ""
    source_kind = source_item.get("source_kind", "")
    primary_text_source = content.get("primary_text_source") or ""
    source_assets = source_item.get("source_assets", [])
    task_hints = extracted.get("task_hints", [])
    release_signals = extracted.get("release_signals", [])
    participant_count = len(source_item.get("participants", []))
    fact_anchor_count = len(extracted.get("fact_anchors", []))
    summary_words = word_count(summary)
    full_text_words = word_count(full_text)
    trimmed_noise = "Trimmed episode page at sponsor/footer marker." in assembly_notes
    is_interviewish = participant_count > 0 or "interview" in extracted.get("task_hints", [])
    linked_context_asset_count = sum(
        1
        for asset in source_assets
        if str(asset.get("asset_kind", "")).startswith("linked_") and bool(asset.get("selected_for_text"))
    )
    announcement_like = source_kind in {"x_thread", "x_article", "x_post"} and (
        "release" in task_hints or bool(release_signals)
    )

    longform_eligible = True
    reasons: list[str] = []

    min_words_required = min_fulltext_words
    min_fact_anchors_required = 5
    if announcement_like and linked_context_asset_count > 0:
        min_words_required = max(100, min_fulltext_words - 40)
        min_fact_anchors_required = 3
    elif announcement_like and linked_context_asset_count == 0:
        min_words_required = max(180, min_fulltext_words)

    if full_text_words < min_words_required:
        longform_eligible = False
        reasons.append(f"full_text too short for longform ({full_text_words} words < {min_words_required})")

    if fact_anchor_count < min_fact_anchors_required:
        longform_eligible = False
        reasons.append(f"too few concrete fact anchors ({fact_anchor_count} < {min_fact_anchors_required})")

    if source_kind == "podcast_transcript" and primary_text_source == "episode_page":
        if trimmed_noise:
            reasons.append("source was trimmed from a noisy episode page")
        if full_text_words < 220 and participant_count == 0:
            longform_eligible = False
            reasons.append("episode-page source looks like a briefing summary, not a full transcript")

    if announcement_like and linked_context_asset_count == 0 and full_text_words < 240:
        longform_eligible = False
        reasons.append("announcement source lacks linked context evidence and is too thin for longform")

    if is_interviewish and participant_count == 0:
        longform_eligible = False
        reasons.append("interview-like source has no reliable participants extracted")

    if not summary and not (announcement_like and linked_context_asset_count > 0) and full_text_words < max(min_fulltext_words * 2, 300):
        longform_eligible = False
        reasons.append("source lacks a usable summary and also lacks enough body text")

    if announcement_like and linked_context_asset_count > 0 and longform_eligible:
        reasons.append("announcement source has linked context support and passes longform gate")

    if longform_eligible and not reasons:
        reasons.append("enough source density and factual anchors for longform rewrite")

    return {
        "schema_version": SCHEMA_VERSION,
        "source_ref": source_item.get("_source_ref", ""),
        "source_id": source_item["source_id"],
        "longform_eligible": longform_eligible,
        "recommended_action": "write_longform" if longform_eligible else "hold_or_shortform",
        "reasons": reasons,
        "signals": {
            "source_kind": source_kind,
            "primary_text_source": primary_text_source,
            "participant_count": participant_count,
            "summary_words": summary_words,
            "full_text_words": full_text_words,
            "fact_anchor_count": fact_anchor_count,
            "trimmed_noisy_episode_page": trimmed_noise,
            "linked_context_asset_count": linked_context_asset_count,
            "announcement_like": announcement_like,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    signals = payload["signals"]
    lines = [
        f"# Source Gate {payload['source_id']}",
        "",
        f"- Longform Eligible: {payload['longform_eligible']}",
        f"- Recommended Action: {payload['recommended_action']}",
        f"- Source Kind: {signals['source_kind']}",
        f"- Primary Text Source: {signals['primary_text_source']}",
        f"- Participants: {signals['participant_count']}",
        f"- Summary Words: {signals['summary_words']}",
        f"- Full Text Words: {signals['full_text_words']}",
        f"- Fact Anchors: {signals['fact_anchor_count']}",
        "",
        "## Reasons",
    ]
    for item in payload["reasons"]:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-item-root", required=True, help="Directory containing source_item.json artifacts")
    parser.add_argument("--out-root", required=True, help="Directory where source_gate artifacts will be written")
    parser.add_argument("--min-fulltext-words", type=int, default=140, help="Minimum cleaned full_text words required for longform")
    args = parser.parse_args()

    source_item_root = Path(args.source_item_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for source_path in sorted(source_item_root.glob("**/source_item.json")):
        source_item = load_json(source_path)
        source_item["_source_ref"] = str(source_path.resolve())
        payload = evaluate_longform_gate(source_item, args.min_fulltext_words)

        target_dir = out_root / payload["source_id"]
        target_dir.mkdir(parents=True, exist_ok=True)
        out_json = target_dir / "source_gate.json"
        out_md = target_dir / "source_gate.md"
        dump_json(out_json, payload)
        out_md.write_text(render_markdown(payload), encoding="utf-8")

        row = {
            "source_id": payload["source_id"],
            "longform_eligible": payload["longform_eligible"],
            "recommended_action": payload["recommended_action"],
            "output_json": str(out_json),
            "output_md": str(out_md),
        }
        results.append(row)
        print(f"{payload['source_id']} -> {payload['recommended_action']}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "source_item_root": str(source_item_root),
        "out_root": str(out_root),
        "count": len(results),
        "longform_eligible_count": sum(1 for row in results if row["longform_eligible"]),
        "hold_or_shortform_count": sum(1 for row in results if not row["longform_eligible"]),
        "results": results,
    }
    manifest_path = out_root / "source_gate_manifest.json"
    dump_json(manifest_path, manifest)
    print(manifest_path)
    print(
        f"longform_eligible={manifest['longform_eligible_count']} hold_or_shortform={manifest['hold_or_shortform_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
