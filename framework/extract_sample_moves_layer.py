from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


KEY_ALIASES = {
    "标题": "title",
    "作者": "author",
    "子模式": "submode_id",
    "source_type": "source_type",
    "source_signal": "source_signal",
    "release_signal": "release_signal",
    "reader_problem": "reader_problem",
    "core_decode": "core_decode",
    "core_promise": "core_promise",
    "hook_move": "hook_move",
    "hook_sentence": "hook_sentence",
    "hook_trigger": "hook_trigger",
    "hook_type": "hook_type",
    "proof_mode": "proof_mode",
    "reusable_parts": "reusable_parts",
    "non_reusable_parts": "non_reusable_parts",
    "style_cue": "style_cue",
    "why_standard": "why_standard",
    "target_reader": "target_reader",
    "core_problem": "core_problem",
    "section_flow_summary": "section_flow_summary",
    "section_flow": "section_flow",
    "evidence_types": "evidence_types",
    "language_markers": "language_markers",
    "framework_signals": "framework_signals",
    "one_sentence_abstraction": "one_sentence_abstraction",
    "opportunity_object": "opportunity_object",
    "signal_source": "signal_source",
    "stance": "stance",
}

CLOSING_KEYWORDS = (
    "结尾",
    "收束",
    "收口",
    "最后",
    "Close",
    "风险",
    "边界",
    "下一步",
    "行动",
    "适合",
    "不适合",
    "判断",
    "出口",
    "adoption judgment",
)

MID_KEYWORDS = (
    "对比",
    "流程",
    "步骤",
    "解释",
    "拆解",
    "场景",
    "架构",
    "组件",
    "Comparison",
    "Architecture",
    "Capability",
    "Demo",
    "Setup",
    "Proof",
    "Pitfalls",
    "Context",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip().strip("`")
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(cleaned)
    return out


def normalize_key(raw_key: str) -> str:
    key = raw_key.strip().strip("`")
    return KEY_ALIASES.get(key, key)


def parse_heading_block(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    pattern = re.compile(r"^###\s+(.+?)\n(.*?)(?=^###\s+|\Z)", re.MULTILINE | re.DOTALL)
    for match in pattern.finditer(text):
        key = normalize_key(match.group(1))
        raw_value = match.group(2).strip()
        lines = [line.rstrip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            continue
        if all(line.lstrip().startswith("- ") for line in lines):
            result[key] = [line.lstrip()[2:].strip() for line in lines]
        else:
            result[key] = " ".join(lines).strip()
    return result


def parse_bullet_block(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        match = re.match(r"^- `([^`]+)`: ?(.*)$", line)
        if not match:
            i += 1
            continue
        key = normalize_key(match.group(1))
        value = match.group(2).strip()
        if value:
            result[key] = value
            i += 1
            continue
        i += 1
        items: list[str] = []
        while i < len(lines):
            candidate = lines[i].rstrip()
            if re.match(r"^- `([^`]+)`: ?(.*)$", candidate):
                break
            if candidate.strip().startswith("- "):
                items.append(candidate.strip()[2:].strip())
            i += 1
        if items:
            result[key] = items
    return result


def parse_sample_sections(md_text: str) -> list[dict[str, Any]]:
    sections = re.split(r"^##\s+", md_text, flags=re.MULTILINE)
    out: list[dict[str, Any]] = []
    for raw in sections[1:]:
        block = raw.strip()
        if not block:
            continue
        lines = block.splitlines()
        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        sample_id_match = re.search(r"(\d{10,})", header)
        sample_id = sample_id_match.group(1) if sample_id_match else header

        if "### " in body:
            fields = parse_heading_block(body)
        else:
            fields = parse_bullet_block(body)
        if not fields:
            continue
        fields["sample_id"] = sample_id
        out.append(fields)
    return out


def flatten_list_fields(cards: list[dict[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for card in cards:
        value = card.get(field)
        if isinstance(value, list):
            values.extend([str(item) for item in value])
        elif isinstance(value, str):
            values.append(value)
    return compact_list(values)


def top_count_rows(values: list[str], top_k: int = 20) -> list[dict[str, Any]]:
    counter = Counter([value for value in values if value])
    rows: list[dict[str, Any]] = []
    for text, count in counter.most_common(top_k):
        rows.append({"text": text, "count": count})
    return rows


def collect_mid_and_closing(cards: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    mid: list[str] = []
    closing: list[str] = []
    for card in cards:
        candidates: list[str] = []
        for key in ["reusable_parts", "proof_mode", "section_flow", "section_flow_summary", "core_promise", "one_sentence_abstraction"]:
            value = card.get(key)
            if isinstance(value, list):
                candidates.extend([str(item) for item in value])
            elif isinstance(value, str):
                candidates.append(value)
        for text in candidates:
            cleaned = " ".join(text.split()).strip()
            if not cleaned:
                continue
            if any(keyword in cleaned for keyword in CLOSING_KEYWORDS):
                closing.append(cleaned)
            elif any(keyword in cleaned for keyword in MID_KEYWORDS):
                mid.append(cleaned)
            else:
                mid.append(cleaned)
    return compact_list(mid), compact_list(closing)


def derive_title_stats(titles: list[str]) -> dict[str, Any]:
    return {
        "count": len(titles),
        "with_number": sum(1 for title in titles if re.search(r"\d", title)),
        "with_question_mark": sum(1 for title in titles if "?" in title or "？" in title),
        "with_colon_or_dash": sum(1 for title in titles if ":" in title or "：" in title or "—" in title or "-" in title),
        "avg_length": round(sum(len(title) for title in titles) / len(titles), 2) if titles else 0,
    }


def build_moves_layer(framework_dir: Path, cards: list[dict[str, Any]]) -> dict[str, Any]:
    spec = load_json(framework_dir / "FRAMEWORK_SPEC.json")
    framework_id = spec.get("metadata", {}).get("framework_id", framework_dir.name)

    titles = flatten_list_fields(cards, "title")
    opening = compact_list(
        flatten_list_fields(cards, "hook_move")
        + flatten_list_fields(cards, "hook_sentence")
        + flatten_list_fields(cards, "hook_trigger")
    )
    mid, closing = collect_mid_and_closing(cards)
    evidence = compact_list(flatten_list_fields(cards, "proof_mode") + flatten_list_fields(cards, "evidence_types"))
    language = compact_list(flatten_list_fields(cards, "language_markers") + flatten_list_fields(cards, "style_cue"))
    non_reusable = flatten_list_fields(cards, "non_reusable_parts")

    return {
        "schema_version": "0.1.0",
        "generated_at": utc_now_iso(),
        "source": {
            "framework_id": framework_id,
            "sample_decompositions_md": str((framework_dir / "SAMPLE_DECOMPOSITIONS.md").resolve()),
            "sample_count": len(cards),
        },
        "sample_cards": cards,
        "moves_layer": {
            "title_layer": {
                "title_examples": titles[:30],
                "title_feature_stats": derive_title_stats(titles),
            },
            "opening_hook_layer": {
                "moves": opening[:60],
                "top_moves": top_count_rows(opening, top_k=20),
            },
            "mid_transition_layer": {
                "moves": mid[:120],
                "top_moves": top_count_rows(mid, top_k=30),
            },
            "closing_carry_layer": {
                "moves": closing[:80],
                "top_moves": top_count_rows(closing, top_k=20),
            },
            "evidence_combo_layer": {
                "evidence_units": evidence[:100],
                "top_evidence_units": top_count_rows(evidence, top_k=25),
            },
            "language_action_layer": {
                "language_moves": language[:100],
                "top_language_moves": top_count_rows(language, top_k=25),
            },
            "rewrite_forbidden_zone_layer": {
                "non_reusable_parts": non_reusable[:120],
                "top_non_reusable_parts": top_count_rows(non_reusable, top_k=25),
            },
        },
    }


def render_moves_markdown(payload: dict[str, Any]) -> str:
    source = payload["source"]
    layer = payload["moves_layer"]
    lines = [
        f"# {source['framework_id']} Sample Moves Layer",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- sample_count: {source['sample_count']}",
        "",
        "## Opening Hook Moves",
    ]
    for row in layer["opening_hook_layer"]["top_moves"][:12]:
        lines.append(f"- ({row['count']}) {row['text']}")
    lines.extend(["", "## Mid Transition Moves"])
    for row in layer["mid_transition_layer"]["top_moves"][:15]:
        lines.append(f"- ({row['count']}) {row['text']}")
    lines.extend(["", "## Closing Carry Moves"])
    for row in layer["closing_carry_layer"]["top_moves"][:12]:
        lines.append(f"- ({row['count']}) {row['text']}")
    lines.extend(["", "## Evidence Units"])
    for row in layer["evidence_combo_layer"]["top_evidence_units"][:12]:
        lines.append(f"- ({row['count']}) {row['text']}")
    lines.extend(["", "## Language Moves"])
    for row in layer["language_action_layer"]["top_language_moves"][:12]:
        lines.append(f"- ({row['count']}) {row['text']}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-root", default="framework")
    args = parser.parse_args()

    framework_root = Path(args.framework_root).expanduser().resolve()
    framework_dirs = sorted([path for path in framework_root.iterdir() if path.is_dir() and (path / "SAMPLE_DECOMPOSITIONS.md").exists()])
    if not framework_dirs:
        raise RuntimeError(f"No framework dirs with SAMPLE_DECOMPOSITIONS.md under {framework_root}")

    manifest_rows: list[dict[str, Any]] = []
    for framework_dir in framework_dirs:
        md_path = framework_dir / "SAMPLE_DECOMPOSITIONS.md"
        cards = parse_sample_sections(md_path.read_text(encoding="utf-8"))
        if not cards:
            continue
        payload = build_moves_layer(framework_dir, cards)
        out_json = framework_dir / "SAMPLE_MOVES_LAYER.json"
        out_md = framework_dir / "SAMPLE_MOVES_LAYER.md"
        dump_json(out_json, payload)
        out_md.write_text(render_moves_markdown(payload), encoding="utf-8")
        manifest_rows.append(
            {
                "framework_dir": str(framework_dir),
                "sample_count": len(cards),
                "output_json": str(out_json),
                "output_md": str(out_md),
            }
        )
        print(f"{framework_dir.name}: samples={len(cards)} -> {out_json.name}")

    manifest = {
        "generated_at": utc_now_iso(),
        "framework_root": str(framework_root),
        "count": len(manifest_rows),
        "results": manifest_rows,
    }
    manifest_path = framework_root / "SAMPLE_MOVES_LAYER_MANIFEST.json"
    dump_json(manifest_path, manifest)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
