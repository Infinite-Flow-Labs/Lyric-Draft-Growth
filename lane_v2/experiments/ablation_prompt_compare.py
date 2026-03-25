"""
Ablation experiment: compare full prompt vs P0-slim prompt.
Does NOT call LLM — only builds prompts and measures sizes.

Usage:
    python3 lane_v2/experiments/ablation_prompt_compare.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lane_v2" / "write"))
sys.path.insert(0, str(REPO_ROOT / "lane_v2" / "route"))
sys.path.insert(0, str(REPO_ROOT / "lane_v2" / "assemble"))

from write_lane_articles import (
    build_article_quality_contract,
    build_framework_context,
    build_primary_source_packet,
    build_source_bundle_packet,
    build_source_material_packet,
    build_writer_context_packet,
    lane_writer_user_prompt,
    load_json,
    trim_text,
)

PACKET_PATH = REPO_ROOT / "lane_v2/runs/20260325_t01_wechat_rerun_fmt_v2/02_t01_topic_engine/06_writer_packets/topic-x-op7418-b9e09e039182/writer_packet.json"


def load_everything():
    packet = load_json(PACKET_PATH)

    framework_specs = {}
    for spec_dir in sorted((REPO_ROOT / "framework").iterdir()):
        sf = spec_dir / "FRAMEWORK_SPEC.json"
        if sf.exists():
            framework_specs[spec_dir.name] = (sf, load_json(sf))

    loaded_sources = {}
    source_rows = [
        *(packet.get("source_bundle", {}).get("primary_sources", []) or []),
        *(packet.get("source_bundle", {}).get("supporting_sources", []) or []),
        *(packet.get("source_materials", []) or []),
    ]
    for row in source_rows:
        p = str(row.get("source_item_path", "")).strip()
        if p:
            pp = Path(p).expanduser().resolve()
            if pp.exists() and str(pp) not in loaded_sources:
                loaded_sources[str(pp)] = load_json(pp)

    primary_path = None
    for row in packet.get("source_bundle", {}).get("primary_sources", []):
        pp = Path(str(row.get("source_item_path", ""))).expanduser().resolve()
        if str(pp) in loaded_sources:
            primary_path = pp
            break
    if not primary_path and loaded_sources:
        primary_path = Path(next(iter(loaded_sources.keys())))

    primary_source_item = loaded_sources[str(primary_path)]

    cap_path = REPO_ROOT / "lane_v2/configs/ARTICLE_CAPABILITY_PLAYBOOK.json"
    capability_playbook = load_json(cap_path) if cap_path.exists() else None

    hum_path = REPO_ROOT / "lane_v2/configs/HUMANIZER_ZH_PACKET.json"
    humanizer_packet = load_json(hum_path) if hum_path.exists() else None

    t01_path = REPO_ROOT / "lane_v2/configs/T01_SIGNAL_BOOST_FROM_DOTEY.json"
    t01_signal_boost = load_json(t01_path) if t01_path.exists() else None

    lc_path = REPO_ROOT / "lane_v2/docs/lane_pilot/T01_single_lane_contract_v1.md"
    lane_contract_excerpt = lc_path.read_text(encoding="utf-8") if lc_path.exists() else ""

    return (
        packet, framework_specs, loaded_sources, primary_source_item,
        capability_playbook, humanizer_packet, t01_signal_boost, lane_contract_excerpt,
    )


def build_full_prompt(packet, framework_specs, loaded_sources, primary_source_item,
                      capability_playbook, humanizer_packet, t01_signal_boost, lane_contract_excerpt):
    """Current production prompt — unchanged."""
    framework_context, _ = build_framework_context(
        framework_specs=framework_specs,
        framework_id=packet["framework_id"],
        submode_id=packet["submode_id"],
        source_item=primary_source_item,
        capability_playbook=capability_playbook,
    )

    primary_source_packet = build_primary_source_packet(primary_source_item)
    source_bundle_packet = build_source_bundle_packet(packet.get("source_bundle", {}))

    primary_paths = {
        str(Path(str(row.get("source_item_path", ""))).expanduser().resolve())
        for row in packet.get("source_bundle", {}).get("primary_sources", [])
        if str(row.get("source_item_path", "")).strip()
    }
    source_family_map = {}
    for row in packet.get("source_materials", []) or []:
        rp = Path(str(row.get("source_item_path", ""))).expanduser().resolve()
        source_family_map[str(rp)] = str(row.get("source_family", "unknown"))
    source_materials_packet = []
    for pt, si in loaded_sources.items():
        sf = source_family_map.get(pt, "unknown")
        sr = "primary" if pt in primary_paths else "supporting"
        source_materials_packet.append(build_source_material_packet(si, sf, source_role=sr))
    source_materials_packet = source_materials_packet[:8]

    article_quality_contract = build_article_quality_contract(
        framework_context=framework_context,
        primary_source_packet=primary_source_packet,
        humanizer_packet=humanizer_packet,
        lane_assignment=packet.get("lane_assignment", {}),
        t01_signal_boost=t01_signal_boost,
    )

    prompt = lane_writer_user_prompt(
        packet=packet,
        primary_source_packet=primary_source_packet,
        source_bundle_packet=source_bundle_packet,
        source_materials_packet=source_materials_packet,
        framework_context=framework_context,
        lane_contract_excerpt=lane_contract_excerpt,
        output_language="zh-CN",
        humanizer_packet=humanizer_packet,
        article_quality_contract=article_quality_contract,
    )
    return prompt


def slim_framework_spec(spec: dict) -> dict:
    """P0: strip routing, metadata, samples, schema_version, full_fidelity from spec."""
    return {
        "intent": spec.get("intent", {}),
        "structure": spec.get("structure", {}),
        "style": spec.get("style", {}),
        "execution_controls": spec.get("execution_controls", {}),
    }


def build_slim_prompt(packet, framework_specs, loaded_sources, primary_source_item,
                      capability_playbook, humanizer_packet, t01_signal_boost, lane_contract_excerpt):
    """P0-slim: remove routing/metadata/samples from framework_spec_full,
       remove lane_candidates from writer_packet."""
    framework_context, _ = build_framework_context(
        framework_specs=framework_specs,
        framework_id=packet["framework_id"],
        submode_id=packet["submode_id"],
        source_item=primary_source_item,
        capability_playbook=capability_playbook,
    )

    # P0: slim the framework_spec_full
    framework_context["framework_spec_full"] = slim_framework_spec(
        framework_context["framework_spec_full"]
    )

    primary_source_packet = build_primary_source_packet(primary_source_item)
    source_bundle_packet = build_source_bundle_packet(packet.get("source_bundle", {}))

    primary_paths = {
        str(Path(str(row.get("source_item_path", ""))).expanduser().resolve())
        for row in packet.get("source_bundle", {}).get("primary_sources", [])
        if str(row.get("source_item_path", "")).strip()
    }
    source_family_map = {}
    for row in packet.get("source_materials", []) or []:
        rp = Path(str(row.get("source_item_path", ""))).expanduser().resolve()
        source_family_map[str(rp)] = str(row.get("source_family", "unknown"))
    source_materials_packet = []
    for pt, si in loaded_sources.items():
        sf = source_family_map.get(pt, "unknown")
        sr = "primary" if pt in primary_paths else "supporting"
        source_materials_packet.append(build_source_material_packet(si, sf, source_role=sr))
    source_materials_packet = source_materials_packet[:8]

    article_quality_contract = build_article_quality_contract(
        framework_context=framework_context,
        primary_source_packet=primary_source_packet,
        humanizer_packet=humanizer_packet,
        lane_assignment=packet.get("lane_assignment", {}),
        t01_signal_boost=t01_signal_boost,
    )

    # P0: strip lane_candidates from packet before prompt assembly
    slim_packet = {k: v for k, v in packet.items() if k not in ("lane_candidates", "lane_candidates_all")}
    if "lane_assignment" in slim_packet:
        la = dict(slim_packet["lane_assignment"])
        la.pop("lane_candidates", None)
        la.pop("lane_candidates_all", None)
        slim_packet["lane_assignment"] = la

    prompt = lane_writer_user_prompt(
        packet=slim_packet,
        primary_source_packet=primary_source_packet,
        source_bundle_packet=source_bundle_packet,
        source_materials_packet=source_materials_packet,
        framework_context=framework_context,
        lane_contract_excerpt=lane_contract_excerpt,
        output_language="zh-CN",
        humanizer_packet=humanizer_packet,
        article_quality_contract=article_quality_contract,
    )
    return prompt


def component_breakdown(prompt_json_str: str) -> dict[str, int]:
    obj = json.loads(prompt_json_str)
    return {k: len(json.dumps(v, ensure_ascii=False, separators=(",", ":"))) for k, v in obj.items()}


def main():
    data = load_everything()
    full = build_full_prompt(*data)
    slim = build_slim_prompt(*data)

    print("=" * 70)
    print("ABLATION PROMPT COMPARISON")
    print("=" * 70)
    print(f"\nFull prompt:  {len(full):>6,} chars")
    print(f"Slim prompt:  {len(slim):>6,} chars")
    print(f"Saved:        {len(full) - len(slim):>6,} chars ({(len(full) - len(slim)) / len(full) * 100:.1f}%)")

    print("\n--- Full prompt component breakdown ---")
    for k, v in component_breakdown(full).items():
        print(f"  {k:40s} {v:>6,} chars")

    print("\n--- Slim prompt component breakdown ---")
    for k, v in component_breakdown(slim).items():
        print(f"  {k:40s} {v:>6,} chars")

    # Show what was removed from framework_spec_full
    full_obj = json.loads(full)
    slim_obj = json.loads(slim)
    full_spec = full_obj.get("framework_context", {}).get("framework_spec_full", {})
    slim_spec = slim_obj.get("framework_context", {}).get("framework_spec_full", {})
    removed_keys = set(full_spec.keys()) - set(slim_spec.keys())
    print(f"\n--- Removed from framework_spec_full: {sorted(removed_keys)} ---")
    for k in sorted(removed_keys):
        sz = len(json.dumps(full_spec[k], ensure_ascii=False, separators=(",", ":")))
        print(f"  {k}: {sz:,} chars removed")

    # Save both prompts for inspection
    out_dir = Path(__file__).parent / "ablation_outputs"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "prompt_full.json").write_text(
        json.dumps(json.loads(full), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "prompt_slim.json").write_text(
        json.dumps(json.loads(slim), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nPrompts saved to {out_dir}/")


if __name__ == "__main__":
    main()
