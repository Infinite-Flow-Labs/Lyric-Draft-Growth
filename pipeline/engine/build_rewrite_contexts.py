from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from jsonschema import validate as jsonschema_validate
except Exception:  # pragma: no cover - optional runtime dependency
    jsonschema_validate = None


SCHEMA_VERSION = "0.1.0"
ASSEMBLY_MODE = "deterministic_selection"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def load_schema(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return load_json(path)


def load_capability_playbook(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return load_json(path)


def validate_payload(payload: dict[str, Any], schema: dict[str, Any] | None) -> str | None:
    if schema is None or jsonschema_validate is None:
        return None
    try:
        jsonschema_validate(payload, schema)
    except Exception as exc:  # pragma: no cover - surfacing validation details
        return f"{type(exc).__name__}: {exc}"
    return None


def read_framework_specs(specs_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    specs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for spec_path in sorted(specs_dir.glob("*/FRAMEWORK_SPEC.json")):
        spec = load_json(spec_path)
        framework_id = spec["metadata"]["framework_id"]
        specs[framework_id] = (spec_path.resolve(), spec)
    return specs


def find_submode(spec: dict[str, Any], submode_id: str) -> dict[str, Any]:
    for submode in spec["structure"]["submodes"]:
        if submode["submode_id"] == submode_id:
            return submode
    raise KeyError(f"Unable to find submode_id={submode_id}")


def find_style_profile(spec: dict[str, Any], style_profile_id: str) -> dict[str, Any]:
    for profile in spec["style"]["submode_profiles"]:
        if profile["style_profile_id"] == style_profile_id:
            return profile
    raise KeyError(f"Unable to find style_profile_id={style_profile_id}")


def build_sample_ref_map(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {sample["sample_id"]: sample for sample in spec["samples"]["sample_refs"]}


def choose_sample_ids(final_decision: dict[str, Any], submode: dict[str, Any]) -> tuple[list[str], str]:
    matched_sample_ids = compact_list(final_decision.get("matched_sample_ids", []))
    if matched_sample_ids:
        return matched_sample_ids, "Used matched_sample_ids from framework_match final_decision."
    fallback_sample_ids = compact_list(submode.get("sample_ids", []))[:2]
    return fallback_sample_ids, "framework_match did not provide matched_sample_ids, so the assembler deterministically fell back to the first submode sample_ids."


def build_selected_spec_paths(submode_id: str, style_profile_id: str, sample_ids: list[str]) -> list[str]:
    paths = [
        "metadata.framework_id",
        "metadata.framework_label",
        "structure.hidden_skeleton",
        "structure.visible_template_bans",
        "structure.allowed_surface_moves",
        "structure.forbidden_surface_moves",
        f"structure.submodes[submode_id={submode_id}]",
        "style.global_style_principles",
        "style.global_anti_ai_rules",
        f"style.submode_profiles[style_profile_id={style_profile_id}]",
        "execution_controls.must_keep",
        "execution_controls.must_avoid",
        "execution_controls.rewrite_failure_modes",
        "execution_controls.quality_checks",
        "execution_controls.human_review_triggers",
    ]
    paths.extend(f"samples.sample_refs[sample_id={sample_id}]" for sample_id in sample_ids)
    return paths


def compact_optional_list(values: list[str], max_items: int) -> list[str]:
    return compact_list(values)[:max_items]


GENERIC_FACT_ANCHOR_STOPLIST = {
    "release",
    "released",
    "introducing",
    "post",
    "linked",
    "canonical url",
    "we",
}


def compact_fact_anchor_values(values: list[str], max_items: int = 4, max_chars: int = 140) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in GENERIC_FACT_ANCHOR_STOPLIST:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        if len(cleaned) > max_chars:
            cleaned = cleaned[: max_chars - 1].rstrip() + "…"
        out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


def trim_value(value: Any, max_chars: int) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    if not cleaned:
        return None
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def build_identity_anchor(source_item: dict[str, Any]) -> dict[str, Any]:
    participants = source_item.get("participants", [])
    hosts = [item["name"] for item in participants if item.get("role") == "host" and item.get("name")]
    guests = [item["name"] for item in participants if item.get("role") == "guest" and item.get("name")]
    other_roles = [
        f"{item.get('role')}: {item.get('name')}"
        for item in participants
        if item.get("role") not in {"host", "guest"} and item.get("name")
    ]
    return {
        "author_handle": source_item.get("author", {}).get("handle"),
        "author_display_name": source_item.get("author", {}).get("display_name"),
        "source_title": trim_value(source_item.get("title"), 180),
        "published_at": source_item.get("published_at"),
        "hosts": compact_optional_list(hosts, 2),
        "guests": compact_optional_list(guests, 2),
        "other_participants": compact_optional_list(other_roles, 4),
    }


def select_title_move_ids(playbook: dict[str, Any], framework_id: str) -> list[str]:
    defaults = playbook.get("framework_defaults", {}).get(framework_id, {})
    move_ids = defaults.get("title_moves", [])
    if move_ids:
        return move_ids
    return ["old_frame_invalidated"]


def select_closing_move_ids(playbook: dict[str, Any], framework_id: str, source_kind: str) -> list[str]:
    by_framework = playbook.get("framework_defaults", {}).get(framework_id, {}).get("closing_moves", [])
    by_source_kind = playbook.get("source_kind_closing_overrides", {}).get(source_kind, [])
    ordered: list[str] = []
    for move_id in [*by_source_kind, *by_framework]:
        if move_id and move_id not in ordered:
            ordered.append(move_id)
    return ordered[:2]


def pick_capability_moves(move_map: dict[str, Any], move_ids: list[str]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for move_id in move_ids:
        move = move_map.get(move_id)
        if not move:
            continue
        selected.append({"move_id": move_id, **move})
    return selected


def build_capability_packets(
    *,
    playbook: dict[str, Any],
    source_item: dict[str, Any],
    selected_sample_refs: list[dict[str, Any]],
    submode: dict[str, Any],
    style_profile: dict[str, Any],
    framework_spec: dict[str, Any],
) -> dict[str, Any]:
    framework_id = framework_spec["metadata"]["framework_id"]
    source_kind = source_item.get("source_kind", "")
    extracted = source_item.get("extracted_signals", {})
    title_moves = pick_capability_moves(
        playbook.get("title_hook", {}).get("stable_moves", {}),
        select_title_move_ids(playbook, framework_id),
    )
    closing_moves = pick_capability_moves(
        playbook.get("closing_carry", {}).get("stable_moves", {}),
        select_closing_move_ids(playbook, framework_id, source_kind),
    )
    sample_hook_moves = compact_list([sample.get("hook_move", "") for sample in selected_sample_refs])[:2]
    sample_why_it_matters = compact_list([sample.get("why_it_matters", "") for sample in selected_sample_refs])[:2]
    proof_modes: list[str] = []
    for sample in selected_sample_refs:
        proof_modes.extend(sample.get("proof_mode", []))

    return {
        "playbook_version": playbook.get("version"),
        "playbook_ref": playbook.get("research_ref"),
        "global_anti_patterns": playbook.get("global_anti_patterns", []),
        "sample_quality_gate": playbook.get("sample_quality_gate", {}),
        "title_attack_packet": {
            "job": playbook.get("title_hook", {}).get("job"),
            "recommended_moves": title_moves,
            "sample_hook_moves": sample_hook_moves,
            "submode_hook_patterns": submode.get("hook_patterns", []),
            "stakes_signals": compact_list(
                [
                    *extracted.get("release_signals", []),
                    *extracted.get("metric_signals", []),
                    *compact_fact_anchor_values(extracted.get("fact_anchors", [])),
                ]
            )[:8],
            "forbidden_moves": playbook.get("title_hook", {}).get("forbidden_moves", []),
        },
        "dek_value_packet": {
            "job": playbook.get("dek_function", {}).get("job"),
            "stable_moves": playbook.get("dek_function", {}).get("stable_moves", []),
            "sample_why_it_matters": sample_why_it_matters,
            "reader_payoff_signals": compact_list(
                [
                    submode.get("summary", ""),
                    *submode.get("use_when", []),
                    *proof_modes,
                ]
            )[:8],
            "forbidden_moves": playbook.get("dek_function", {}).get("forbidden_moves", []),
        },
        "opening_value_packet": {
            "job": playbook.get("opening_move", {}).get("job"),
            "stable_sequence": playbook.get("opening_move", {}).get("stable_sequence", []),
            "identity_anchor": build_identity_anchor(source_item),
            "sample_hook_moves": sample_hook_moves,
            "opening_moves": style_profile.get("opening_moves", []),
            "why_now_signals": compact_list(
                [
                    source_item.get("published_at", ""),
                    *extracted.get("release_signals", []),
                    *extracted.get("task_hints", []),
                ]
            )[:6],
            "forbidden_moves": playbook.get("opening_move", {}).get("forbidden_moves", []),
        },
        "mid_reset_plan": {
            "job": playbook.get("mid_article_attention_reset", {}).get("job"),
            "reset_frequency": playbook.get("mid_article_attention_reset", {}).get("reset_frequency"),
            "allowed_reset_moves": playbook.get("mid_article_attention_reset", {}).get("stable_moves", []),
            "format_helpers": playbook.get("mid_article_attention_reset", {}).get("format_helpers", []),
            "section_turn_targets": compact_list(
                [
                    *submode.get("reasoning_moves", []),
                    *submode.get("evidence_mix", []),
                    *framework_spec.get("execution_controls", {}).get("quality_checks", []),
                ]
            )[:10],
            "forbidden_moves": playbook.get("mid_article_attention_reset", {}).get("forbidden_moves", []),
        },
        "closing_carry_packet": {
            "job": playbook.get("closing_carry", {}).get("job"),
            "recommended_moves": closing_moves,
            "closing_targets": compact_list(
                [
                    *framework_spec.get("execution_controls", {}).get("quality_checks", []),
                    *framework_spec.get("execution_controls", {}).get("rewrite_failure_modes", []),
                ]
            )[:8],
            "forbidden_endings": playbook.get("closing_carry", {}).get("forbidden_moves", []),
        },
    }


def build_rewrite_context(
    *,
    source_path: Path,
    source_item: dict[str, Any],
    framework_match_path: Path,
    framework_match: dict[str, Any],
    framework_spec_path: Path,
    framework_spec: dict[str, Any],
    capability_playbook: dict[str, Any] | None,
) -> dict[str, Any]:
    final_decision = framework_match["final_decision"]
    framework_id = final_decision["framework_id"]
    submode_id = final_decision["submode_id"]
    submode = find_submode(framework_spec, submode_id)
    style_profile = find_style_profile(framework_spec, submode["style_profile_id"])
    sample_ids, sample_note = choose_sample_ids(final_decision, submode)
    sample_ref_map = build_sample_ref_map(framework_spec)
    missing_sample_ids = [sample_id for sample_id in sample_ids if sample_id not in sample_ref_map]
    if missing_sample_ids:
        raise KeyError(f"{framework_id}/{submode_id} missing sample refs for: {missing_sample_ids}")
    selected_sample_refs = [sample_ref_map[sample_id] for sample_id in sample_ids]
    selected_paths = build_selected_spec_paths(submode_id, style_profile["style_profile_id"], sample_ids)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "assembly_mode": ASSEMBLY_MODE,
        "assembled_at": isoformat_z(utc_now()),
        "source_ref": str(source_path.resolve()),
        "framework_match_ref": str(framework_match_path.resolve()),
        "framework_spec_ref": str(framework_spec_path.resolve()),
        "selected_framework": {
            "framework_id": framework_id,
            "framework_label": framework_spec["metadata"]["framework_label"],
            "submode_id": submode_id,
            "confidence": final_decision["confidence"],
        },
        "assembly_manifest": {
            "no_summarization": True,
            "selected_spec_paths": selected_paths,
            "selected_sample_ids": sample_ids,
            "selection_rationale": (
                "Deterministically selected the exact framework slices required by the chosen route: shared structure constraints, "
                "the matched submode spec, its mapped style profile, explicitly selected sample refs, and execution controls. "
                "No LLM summarization was used."
            ),
        },
        "structure_packet": {
            "hidden_skeleton": framework_spec["structure"]["hidden_skeleton"],
            "visible_template_bans": framework_spec["structure"]["visible_template_bans"],
            "allowed_surface_moves": framework_spec["structure"]["allowed_surface_moves"],
            "forbidden_surface_moves": framework_spec["structure"]["forbidden_surface_moves"],
            "selected_submode_spec": submode,
        },
        "style_packet": {
            "global_style_principles": framework_spec["style"]["global_style_principles"],
            "global_anti_ai_rules": framework_spec["style"]["global_anti_ai_rules"],
            "selected_style_profile": style_profile,
        },
        "sample_packet": {
            "selected_sample_refs": selected_sample_refs,
            "sample_selection_rationale": sample_note,
        },
        "execution_packet": {
            "must_keep": framework_spec["execution_controls"]["must_keep"],
            "must_avoid": framework_spec["execution_controls"]["must_avoid"],
            "rewrite_failure_modes": framework_spec["execution_controls"]["rewrite_failure_modes"],
            "quality_checks": framework_spec["execution_controls"]["quality_checks"],
            "human_review_triggers": framework_spec["execution_controls"]["human_review_triggers"],
        },
        "writer_guardrails": {
            "use_raw_source_as_primary_fact_base": True,
            "do_not_summarize_framework_spec": True,
            "preserve_hidden_structure_as_invisible": True,
            "prefer_sample_voice_over_template_surface": True,
        },
    }
    if capability_playbook:
        payload["capability_packets"] = build_capability_packets(
            playbook=capability_playbook,
            source_item=source_item,
            selected_sample_refs=selected_sample_refs,
            submode=submode,
            style_profile=style_profile,
            framework_spec=framework_spec,
        )
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Rewrite Context {Path(payload['source_ref']).parent.name}",
        "",
        f"- Source Ref: {payload['source_ref']}",
        f"- Framework Match Ref: {payload['framework_match_ref']}",
        f"- Framework Spec Ref: {payload['framework_spec_ref']}",
        f"- Selected Framework: {payload['selected_framework']['framework_id']}",
        f"- Selected Submode: {payload['selected_framework']['submode_id']}",
        f"- Confidence: {payload['selected_framework']['confidence']}",
        f"- Selected Samples: {', '.join(payload['assembly_manifest']['selected_sample_ids'])}",
        "",
        "## Hidden Skeleton",
    ]
    for item in payload["structure_packet"]["hidden_skeleton"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Sample Selection", payload["sample_packet"]["sample_selection_rationale"]])
    capability_packets = payload.get("capability_packets")
    if capability_packets:
        lines.extend(
            [
                "",
                "## Capability Packets",
                f"- Title Moves: {', '.join(move['move_id'] for move in capability_packets['title_attack_packet']['recommended_moves'])}",
                f"- Mid Reset Frequency: {capability_packets['mid_reset_plan']['reset_frequency']}",
                f"- Closing Moves: {', '.join(move['move_id'] for move in capability_packets['closing_carry_packet']['recommended_moves'])}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-match-root", required=True, help="Directory containing framework_match.json artifacts")
    parser.add_argument("--out-root", required=True, help="Directory where rewrite_context artifacts will be written")
    parser.add_argument(
        "--framework-specs-dir",
        default="framework",
        help="Framework specs directory",
    )
    parser.add_argument(
        "--rewrite-context-schema",
        default="framework/REWRITE_CONTEXT_SCHEMA.json",
        help="Path to REWRITE_CONTEXT_SCHEMA.json for validation",
    )
    parser.add_argument(
        "--capability-playbook",
        default="content/pipeline/configs/ARTICLE_CAPABILITY_PLAYBOOK.json",
        help="Path to the stable article capability playbook JSON",
    )
    args = parser.parse_args()

    framework_match_root = Path(args.framework_match_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    framework_specs = read_framework_specs(Path(args.framework_specs_dir).expanduser().resolve())
    schema = load_schema(Path(args.rewrite_context_schema).expanduser().resolve() if args.rewrite_context_schema else None)
    capability_playbook = load_capability_playbook(Path(args.capability_playbook).expanduser().resolve() if args.capability_playbook else None)

    results: list[dict[str, Any]] = []
    for framework_match_path in sorted(framework_match_root.glob("**/framework_match.json")):
        framework_match = load_json(framework_match_path)
        source_path = Path(framework_match["source_ref"]).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source_item.json referenced by framework_match: {source_path}")
        source_item = load_json(source_path)

        framework_id = framework_match["final_decision"]["framework_id"]
        if framework_id not in framework_specs:
            raise KeyError(f"Unknown framework_id in framework_match: {framework_id}")
        framework_spec_path, framework_spec = framework_specs[framework_id]

        payload = build_rewrite_context(
            source_path=source_path,
            source_item=source_item,
            framework_match_path=framework_match_path,
            framework_match=framework_match,
            framework_spec_path=framework_spec_path,
            framework_spec=framework_spec,
            capability_playbook=capability_playbook,
        )
        validation_error = validate_payload(payload, schema)
        source_id = Path(framework_match["source_ref"]).parent.name
        target_dir = out_root / source_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_json = target_dir / "rewrite_context.json"
        out_md = target_dir / "rewrite_context.md"
        dump_json(out_json, payload)
        out_md.write_text(render_markdown(payload), encoding="utf-8")

        row = {
            "source_id": source_id,
            "status": "ok" if validation_error is None else "schema_error",
            "framework_id": payload["selected_framework"]["framework_id"],
            "submode_id": payload["selected_framework"]["submode_id"],
            "output_json": str(out_json),
            "output_md": str(out_md),
            "validation_error": validation_error,
        }
        results.append(row)
        print(f"{source_id} -> {row['status']}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "framework_match_root": str(framework_match_root),
        "out_root": str(out_root),
        "count": len(results),
        "ok_count": sum(1 for row in results if row["status"] == "ok"),
        "schema_error_count": sum(1 for row in results if row["status"] == "schema_error"),
        "results": results,
    }
    manifest_path = out_root / "rewrite_context_manifest.json"
    dump_json(manifest_path, manifest)
    print(manifest_path)
    print(f"ok={manifest['ok_count']} schema_errors={manifest['schema_error_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
