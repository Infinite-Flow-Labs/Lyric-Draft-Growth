from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import sys

try:
    from jsonschema import validate as jsonschema_validate
except Exception:  # pragma: no cover - optional runtime dependency
    jsonschema_validate = None

ROUTE_DIR = Path(__file__).resolve().parents[1] / "route"
if str(ROUTE_DIR) not in sys.path:
    sys.path.insert(0, str(ROUTE_DIR))

from route_framework_matches import choose_backend, dump_json, isoformat_z, load_json, preview_text, utc_now
try:
    from article_formatter import build_article_blocks, build_publishing_hints
except ImportError:  # pragma: no cover - module import path fallback
    from content.pipeline.write.article_formatter import build_article_blocks, build_publishing_hints


SCHEMA_VERSION = "0.1.0"


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


def trim_text(value: Any, max_chars: int) -> str:
    return preview_text(" ".join(str(value or "").split()).strip(), max_chars)


def trim_list(values: list[Any], *, max_items: int, max_chars: int) -> list[str]:
    out: list[str] = []
    for value in compact_list(values):
        trimmed = trim_text(value, max_chars)
        if trimmed:
            out.append(trimmed)
        if len(out) >= max_items:
            break
    return out


GENERIC_ENTITY_STOPLIST = {
    "we",
    "post",
    "video post",
    "video canonical url",
    "canonical url",
    "linked",
    "learn",
    "video",
    "this",
    "part",
    "since",
    "why",
}


def compact_named_entities(values: list[str], *, max_items: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in GENERIC_ENTITY_STOPLIST:
            continue
        if len(cleaned) <= 2 and cleaned.upper() != cleaned:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


GENERIC_FACT_ANCHOR_STOPLIST = {
    "release",
    "released",
    "introducing",
    "post",
    "linked",
    "canonical url",
    "we",
}


def compact_fact_anchors(values: list[str], *, max_items: int = 6, max_chars: int = 180) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in GENERIC_FACT_ANCHOR_STOPLIST:
            continue
        normalized = lowered.replace(" .", ".")
        if normalized in seen:
            continue
        seen.add(normalized)
        trimmed = preview_text(cleaned, max_chars)
        if not trimmed:
            continue
        out.append(trimmed)
        if len(out) >= max_items:
            break
    return out


def load_schema(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return load_json(path)


def load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.exists():
        return None
    return load_json(path)


def load_source_gate(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
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


def generation_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "title",
            "dek",
            "body_markdown",
            "preserved_fact_anchors",
            "style_observations",
            "open_questions",
        ],
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "dek": {"type": "string", "minLength": 1},
            "body_markdown": {"type": "string", "minLength": 120},
            "preserved_fact_anchors": {"type": "array", "items": {"type": "string"}},
            "style_observations": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
        },
    }


def build_source_packet(source_item: dict[str, Any]) -> dict[str, Any]:
    content = source_item["content"]
    participants = []
    for participant in source_item.get("participants", []):
        name = participant.get("name", "")
        if name.startswith("LinkedIn ") or name.startswith("X "):
            continue
        participants.append(participant)
    full_text = content.get("full_text", "")
    full_text_lower = full_text.lower()
    noise_flags: list[str] = []
    if "brought to you by" in full_text_lower or "interested in sponsoring" in full_text_lower:
        noise_flags.append("contains_sponsor_or_cta_boilerplate")
    if full_text.count("#### ") >= 4:
        noise_flags.append("contains_multi_section_or_multi_episode_page_dump")
    return {
        "source_id": source_item["source_id"],
        "platform": source_item["platform"],
        "source_kind": source_item["source_kind"],
        "canonical_url": source_item["canonical_url"],
        "title": source_item["title"],
        "author": source_item["author"],
        "published_at": source_item["published_at"],
        "participants": participants,
        "primary_text_source": content.get("primary_text_source"),
        "summary": preview_text(content.get("summary", ""), 400),
        "full_text": preview_text(full_text, 2600),
        "raw_quotes": compact_list(content.get("raw_quotes", []))[:6],
        "fact_anchors": compact_fact_anchors(source_item["extracted_signals"].get("fact_anchors", [])),
        "metric_signals": trim_list(source_item["extracted_signals"].get("metric_signals", []), max_items=6, max_chars=64),
        "named_entities": compact_named_entities(source_item["extracted_signals"].get("named_entities", []), max_items=8),
        "source_noise_flags": noise_flags,
    }


def writer_system_prompt(output_language: str) -> str:
    return (
        "You are the framework-controlled article writer in a rewrite pipeline. "
        "Write one publishable article, not a thread, not an outline, not interview notes. "
        "Use the raw source as the primary fact base. "
        "Use the rewrite_context exactly as provided; do not summarize or reinterpret the framework into looser rules. "
        "Preserve the hidden structure invisibly. Do not expose template headings just because they exist in the framework. "
        "At the same time, remove AI-writing traces during first-pass generation rather than as a second editing stage. "
        "Your draft must sound authored, specific, and human without becoming sloppy or losing structure. "
        f"Write in {output_language}. "
        "If a claim is not supported by the source, omit it. "
        "Silently self-check before returning: if the draft reads like a smooth summary, a briefing recap, or a transcript digest, rewrite it once more before finalizing. "
        "Do not mention framework IDs, sample IDs, or that this was generated from a transcript. "
        "Return valid JSON only."
    )


def build_submode_instruction(source_packet: dict[str, Any], rewrite_context: dict[str, Any]) -> list[str]:
    submode_id = rewrite_context["selected_framework"]["submode_id"]
    instructions: list[str] = []
    if submode_id == "conversation_distillation":
        instructions.extend(
            [
                "Within the first 3 paragraphs, make the central person legible: who they are, why they matter, and why this conversation is worth reading now.",
                "Keep one person, one turn, or one conflict as the spine. Side ideas should strengthen that spine, not compete with it.",
                "If the middle starts reading like method notes, re-anchor with a scene beat, a turning point, or a sharper author judgment.",
                "Do not let the piece become a clean concept explainer. Keep it anchored to the person's turn, one concrete moment, or one decisive shift from the source.",
            ]
        )
        if source_packet["participants"]:
            instructions.append("Use names selectively. The main guest should feel present, but avoid cluttering paragraphs with unnecessary name repetition.")
    elif submode_id == "signal_decode":
        instructions.extend(
            [
                "Choose one dominant question or thesis early, then make the rest of the draft serve it.",
                "Do not stack parallel signals like a newsletter recap. Compress weaker signals so the piece feels like one argument, not a pile of headlines.",
                "If the source is noisy, aggressively discard sponsor text, CTA clutter, and side headlines unless they support the core thesis.",
                "Make at least one clear prioritization move: tell the reader which signal matters most and why the others matter less.",
            ]
        )
    return instructions


def build_global_quality_instructions(source_packet: dict[str, Any]) -> list[str]:
    instructions = [
        "Write a full-length article, not an extended note. Default to roughly 12-18 substantive paragraphs with varied paragraph lengths.",
        "Unless the source is genuinely thin, the body should usually feel materially longer than a one-screen read on desktop.",
        "Do not compress a multi-step argument into one paragraph if the source can support expansion.",
        "The title must carry a concrete conflict, reversal, or stake. Do not use a generic industry-summary title.",
        "The dek must sharpen the angle rather than repeating the title in softer words.",
        "Open with tension, paradox, surprise, or a concrete high-stakes question within the first 2 sentences.",
        "Within the first paragraph, introduce at least one source-specific detail so the hook is not generic.",
        "Do not spend the first paragraph on neutral context-setting.",
        "The middle must keep changing mode. Do not allow 4 straight paragraphs of abstract explanation without a scene, example, contrast, or author judgment reset.",
        "If you use section headings, each major heading should usually earn at least one substantial paragraph beneath it, and key sections should often have two.",
        "Use bullet lists sparingly. Lists should compress evidence, not replace development.",
        "End with a real judgment, risk, or unresolved forward-looking question. Do not end by merely restating the thesis.",
        "The final paragraph should echo or answer the opening tension, so the article feels carried through rather than simply stopped.",
        "Use names, orgs, and products only when they carry authority or causal weight. Avoid dense name chains that make the prose feel report-like.",
        "Do not invent authority, biography, or background details that are not explicit in the source text.",
        "Prefer fewer, weightier points over broad coverage. Cutting a weaker point is better than flattening the whole article into a recap.",
        "Before finalizing, silently check five things: hook strength, middle cohesion, identity clarity, source fidelity, and whether the piece still feels like authored writing rather than a summary.",
        "Write body_markdown as clean markdown prose. When useful, include 2-4 '##' section headings across the middle, short markdown bullet lists for compact evidence, and one blockquote using '>' only when the source clearly supports it.",
        "Do not return separate publishing metadata. The formatter will derive publishing structure from your markdown body.",
    ]
    if source_packet.get("source_noise_flags"):
        instructions.append("The source contains boilerplate or page-dump noise. Treat sponsor blocks, subscription prompts, and unrelated episode fragments as non-core unless they clearly matter.")
    return instructions


def slim_structure_packet(structure_packet: dict[str, Any]) -> dict[str, Any]:
    selected = structure_packet.get("selected_submode_spec", {})
    out = {
        "hidden_skeleton": trim_list(structure_packet.get("hidden_skeleton", []), max_items=6, max_chars=90),
        "visible_template_bans": trim_list(structure_packet.get("visible_template_bans", []), max_items=4, max_chars=80),
        "allowed_surface_moves": trim_list(structure_packet.get("allowed_surface_moves", []), max_items=4, max_chars=80),
        "forbidden_surface_moves": trim_list(structure_packet.get("forbidden_surface_moves", []), max_items=4, max_chars=72),
        "selected_submode_spec": {
            "summary": trim_text(selected.get("summary", ""), 160),
            "use_when": trim_list(selected.get("use_when", []), max_items=3, max_chars=70),
            "avoid_when": trim_list(selected.get("avoid_when", []), max_items=3, max_chars=70),
            "hidden_flow": trim_list(selected.get("hidden_flow", []), max_items=6, max_chars=70),
            "hook_patterns": trim_list(selected.get("hook_patterns", []), max_items=4, max_chars=40),
            "evidence_mix": trim_list(selected.get("evidence_mix", []), max_items=5, max_chars=40),
            "reasoning_moves": trim_list(selected.get("reasoning_moves", []), max_items=4, max_chars=70),
            "rewrite_formula": trim_text(selected.get("rewrite_formula", ""), 160),
            "surface_forms": trim_list(selected.get("surface_forms", []), max_items=5, max_chars=28),
            "anti_patterns": trim_list(selected.get("anti_patterns", []), max_items=4, max_chars=60),
        },
    }
    return out


def slim_style_packet(style_packet: dict[str, Any]) -> dict[str, Any]:
    selected = style_packet.get("selected_style_profile", {})
    return {
        "global_style_principles": trim_list(style_packet.get("global_style_principles", []), max_items=4, max_chars=70),
        "global_anti_ai_rules": trim_list(style_packet.get("global_anti_ai_rules", []), max_items=4, max_chars=70),
        "selected_style_profile": {
            "tone_core": trim_text(selected.get("tone_core", ""), 180),
            "opening_moves": trim_list(selected.get("opening_moves", []), max_items=4, max_chars=40),
            "sentence_rhythm": trim_list(selected.get("sentence_rhythm", []), max_items=4, max_chars=40),
            "surface_forms": trim_list(selected.get("surface_forms", []), max_items=5, max_chars=28),
            "language_moves": trim_list(selected.get("language_moves", []), max_items=5, max_chars=40),
            "keep": trim_list(selected.get("keep", []), max_items=4, max_chars=32),
            "avoid": trim_list(selected.get("avoid", []), max_items=4, max_chars=40),
            "ai_smells": trim_list(selected.get("ai_smells", []), max_items=4, max_chars=48),
            "one_sentence_portrait": trim_text(selected.get("one_sentence_portrait", ""), 140),
        },
    }


def slim_sample_packet(sample_packet: dict[str, Any]) -> dict[str, Any]:
    refs = []
    for sample in sample_packet.get("selected_sample_refs", [])[:2]:
        refs.append(
            {
                "title": trim_text(sample.get("title", ""), 60),
                "why_it_matters": trim_text(sample.get("why_it_matters", ""), 140),
                "hook_move": trim_text(sample.get("hook_move", ""), 120),
                "proof_mode": trim_list(sample.get("proof_mode", []), max_items=4, max_chars=28),
                "reusable_parts": trim_list(sample.get("reusable_parts", []), max_items=3, max_chars=60),
                "style_cue": trim_text(sample.get("style_cue", ""), 120),
            }
        )
    return {"selected_sample_refs": refs}


def slim_execution_packet(execution_packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "must_keep": trim_list(execution_packet.get("must_keep", []), max_items=5, max_chars=60),
        "must_avoid": trim_list(execution_packet.get("must_avoid", []), max_items=5, max_chars=60),
        "rewrite_failure_modes": trim_list(execution_packet.get("rewrite_failure_modes", []), max_items=4, max_chars=72),
        "quality_checks": trim_list(execution_packet.get("quality_checks", []), max_items=5, max_chars=72),
    }


def slim_capability_packets(capability_packets: dict[str, Any]) -> dict[str, Any]:
    def trim_moves(moves: list[dict[str, Any]], *, max_items: int = 3) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for move in moves[:max_items]:
            out.append(
                {
                    "move_id": str(move.get("move_id", "")).strip(),
                    "label": trim_text(move.get("label", ""), 48),
                    "when_to_use": trim_text(move.get("when_to_use", ""), 110),
                }
            )
        return out

    if not capability_packets:
        return {}
    return {
        "global_anti_patterns": trim_list(capability_packets.get("global_anti_patterns", []), max_items=6, max_chars=70),
        "title_attack_packet": {
            "job": trim_text(capability_packets.get("title_attack_packet", {}).get("job", ""), 160),
            "recommended_moves": trim_moves(capability_packets.get("title_attack_packet", {}).get("recommended_moves", []), max_items=2),
            "sample_hook_moves": trim_list(capability_packets.get("title_attack_packet", {}).get("sample_hook_moves", []), max_items=2, max_chars=110),
            "stakes_signals": trim_list(capability_packets.get("title_attack_packet", {}).get("stakes_signals", []), max_items=6, max_chars=80),
            "forbidden_moves": trim_list(capability_packets.get("title_attack_packet", {}).get("forbidden_moves", []), max_items=3, max_chars=70),
        },
        "dek_value_packet": {
            "job": trim_text(capability_packets.get("dek_value_packet", {}).get("job", ""), 160),
            "stable_moves": trim_list(capability_packets.get("dek_value_packet", {}).get("stable_moves", []), max_items=3, max_chars=70),
            "sample_why_it_matters": trim_list(capability_packets.get("dek_value_packet", {}).get("sample_why_it_matters", []), max_items=2, max_chars=120),
            "reader_payoff_signals": trim_list(capability_packets.get("dek_value_packet", {}).get("reader_payoff_signals", []), max_items=6, max_chars=70),
        },
        "opening_value_packet": {
            "job": trim_text(capability_packets.get("opening_value_packet", {}).get("job", ""), 160),
            "stable_sequence": trim_list(capability_packets.get("opening_value_packet", {}).get("stable_sequence", []), max_items=4, max_chars=70),
            "identity_anchor": capability_packets.get("opening_value_packet", {}).get("identity_anchor", {}),
            "sample_hook_moves": trim_list(capability_packets.get("opening_value_packet", {}).get("sample_hook_moves", []), max_items=2, max_chars=110),
            "opening_moves": trim_list(capability_packets.get("opening_value_packet", {}).get("opening_moves", []), max_items=4, max_chars=50),
            "why_now_signals": trim_list(capability_packets.get("opening_value_packet", {}).get("why_now_signals", []), max_items=5, max_chars=60),
        },
        "mid_reset_plan": {
            "job": trim_text(capability_packets.get("mid_reset_plan", {}).get("job", ""), 160),
            "reset_frequency": trim_text(capability_packets.get("mid_reset_plan", {}).get("reset_frequency", ""), 60),
            "allowed_reset_moves": trim_list(capability_packets.get("mid_reset_plan", {}).get("allowed_reset_moves", []), max_items=6, max_chars=50),
            "section_turn_targets": trim_list(capability_packets.get("mid_reset_plan", {}).get("section_turn_targets", []), max_items=8, max_chars=70),
            "forbidden_moves": trim_list(capability_packets.get("mid_reset_plan", {}).get("forbidden_moves", []), max_items=3, max_chars=70),
        },
        "closing_carry_packet": {
            "job": trim_text(capability_packets.get("closing_carry_packet", {}).get("job", ""), 160),
            "recommended_moves": trim_moves(capability_packets.get("closing_carry_packet", {}).get("recommended_moves", []), max_items=2),
            "closing_targets": trim_list(capability_packets.get("closing_carry_packet", {}).get("closing_targets", []), max_items=6, max_chars=70),
            "forbidden_endings": trim_list(capability_packets.get("closing_carry_packet", {}).get("forbidden_endings", []), max_items=4, max_chars=70),
        },
    }


def slim_humanizer_packet(humanizer_packet: dict[str, Any] | None) -> dict[str, Any]:
    if not humanizer_packet:
        return {}
    return {
        "core_principles": trim_list(humanizer_packet.get("core_principles", []), max_items=5, max_chars=90),
        "voice_rules": trim_list(humanizer_packet.get("voice_rules", []), max_items=5, max_chars=95),
        "ai_smells_to_avoid": trim_list(humanizer_packet.get("ai_smells_to_avoid", []), max_items=10, max_chars=80),
        "preferred_rewrites": trim_list(humanizer_packet.get("preferred_rewrites", []), max_items=5, max_chars=90),
        "writer_guardrails": trim_list(humanizer_packet.get("writer_guardrails", []), max_items=5, max_chars=100),
        "self_check": trim_list(humanizer_packet.get("self_check", []), max_items=5, max_chars=95),
    }


def build_writer_context_packet(rewrite_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_framework": rewrite_context["selected_framework"],
        "structure_packet": slim_structure_packet(rewrite_context.get("structure_packet", {})),
        "style_packet": slim_style_packet(rewrite_context.get("style_packet", {})),
        "sample_packet": slim_sample_packet(rewrite_context.get("sample_packet", {})),
        "execution_packet": slim_execution_packet(rewrite_context.get("execution_packet", {})),
        "capability_packets": slim_capability_packets(rewrite_context.get("capability_packets", {})),
        "writer_guardrails": rewrite_context.get("writer_guardrails", {}),
    }


def writer_user_prompt(
    source_packet: dict[str, Any],
    rewrite_context: dict[str, Any],
    output_language: str,
    humanizer_packet: dict[str, Any] | None,
) -> str:
    return json.dumps(
        {
            "task": "Write a framework-controlled article draft.",
            "instructions": [
                "Raw source facts outrank stylistic cleverness.",
                "The framework packets below are selected exactly from FRAMEWORK_SPEC.json. Do not paraphrase them into a weaker brief.",
                "Apply the hidden skeleton, selected submode, selected style profile, sample cues, and execution controls while keeping the result natural.",
                "Prefer the sample voice and rhythm over visible templated surface forms.",
                "Do not turn the article into a transcript recap, bullet summary, or Q&A.",
                "Keep names, products, dates, metrics, and direct claims consistent with the source.",
                "If the source has ambiguity, avoid overstating; use open_questions for any unresolved point you intentionally left out or treated cautiously.",
                "Use the strongest sample why_it_matters, hook_move, and style_cue to sharpen the title and first 2 paragraphs without copying the sample surface.",
                "Treat capability_packets as reusable jobs learned from sample study: title attack, dek value, opening break, middle attention resets, and closing carry are separate tasks that all need to be satisfied.",
                "Apply the humanizer packet during writing, not after writing. Remove AI-writing smell while keeping the article's structure, judgment, and source fidelity intact.",
                "Across the middle, keep re-earning attention. Every 2-4 paragraphs, change mode with a stronger judgment, a sharper contrast, a concrete scenario, a question, or a reader payoff reset.",
                f"Output language: {output_language}.",
            ]
            + build_global_quality_instructions(source_packet)
            + build_submode_instruction(source_packet, rewrite_context),
            "source_item": source_packet,
            "rewrite_context": build_writer_context_packet(rewrite_context),
            "humanizer_packet": slim_humanizer_packet(humanizer_packet),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def normalize_generation(raw: dict[str, Any], source_item: dict[str, Any]) -> dict[str, Any]:
    body_markdown = str(raw["body_markdown"]).strip()
    publishing_hints = build_publishing_hints(source_item, raw.get("publishing_hints") or {})
    article_blocks = build_article_blocks(
        title=" ".join(raw["title"].split()).strip(),
        dek=" ".join(raw["dek"].split()).strip(),
        body_markdown=body_markdown,
        publishing_hints=publishing_hints,
    )
    return {
        "title": " ".join(raw["title"].split()).strip(),
        "dek": " ".join(raw["dek"].split()).strip(),
        "body_markdown": body_markdown,
        "preserved_fact_anchors": compact_list(raw.get("preserved_fact_anchors", []))[:10],
        "style_observations": compact_list(raw.get("style_observations", []))[:8],
        "open_questions": compact_list(raw.get("open_questions", []))[:6],
        "article_blocks": article_blocks,
        "publishing_hints": publishing_hints,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# {payload['title']}", "", f"*{payload['dek']}*"]
    normalized_dek = " ".join(str(payload.get("dek", "")).split()).strip()
    for block in payload.get("article_blocks", []):
        lines.append("")
        block_type = block["type"]
        if block_type == "hero_heading" and " ".join(str(block.get("text", "")).split()).strip() == normalized_dek:
            continue
        if block_type in {"hero_heading", "section_heading"}:
            lines.append(f"## {block['text']}")
        elif block_type == "bullet_list":
            if block.get("text"):
                lines.append(block["text"])
            for item in block.get("items", []):
                lines.append(f"- {item}")
        elif block_type == "quote":
            lines.append(f"> {block['text']}")
        elif block_type == "link_cta":
            if block.get("text"):
                lines.append(block["text"])
            if block.get("url"):
                label = block.get("label") or block["url"]
                lines.append(f"[{label}]({block['url']})")
        else:
            lines.append(block["text"])
    return "\n".join(lines).rstrip() + "\n"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite-context-root", required=True, help="Directory containing rewrite_context.json artifacts")
    parser.add_argument("--out-root", required=True, help="Directory where article draft artifacts will be written")
    parser.add_argument(
        "--article-draft-schema",
        default="content/pipeline/configs/ARTICLE_DRAFT_SCHEMA.json",
        help="Path to ARTICLE_DRAFT_SCHEMA.json for validation",
    )
    parser.add_argument("--backend", choices=["auto", "openai_compatible", "codex_cli"], default="auto")
    parser.add_argument("--writer-model", default="", help="Writer model name")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable containing API key")
    parser.add_argument("--codex-binary", default="codex", help="Codex CLI binary name or absolute path")
    parser.add_argument("--codex-working-dir", default="/tmp", help="Working directory used by codex exec backend")
    parser.add_argument("--codex-reasoning-effort", default="medium", help="Codex reasoning effort override")
    parser.add_argument("--timeout-s", type=int, default=180, help="Backend timeout in seconds")
    parser.add_argument("--output-language", default="zh-CN", help="Output language tag or label")
    parser.add_argument("--source-gate-root", help="Optional directory containing source_gate.json artifacts")
    parser.add_argument(
        "--humanizer-packet",
        default="content/pipeline/configs/HUMANIZER_ZH_PACKET.json",
        help="Optional anti-AI-writing packet used during first-pass generation",
    )
    parser.add_argument(
        "--include-human-review-required",
        action="store_true",
        help="Also generate drafts for framework matches flagged as requiring human review",
    )
    args = parser.parse_args()

    rewrite_context_root = Path(args.rewrite_context_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    source_gate_root = Path(args.source_gate_root).expanduser().resolve() if args.source_gate_root else None
    schema = load_schema(Path(args.article_draft_schema).expanduser().resolve() if args.article_draft_schema else None)
    humanizer_packet = load_optional_json(Path(args.humanizer_packet).expanduser().resolve() if args.humanizer_packet else None)
    backend_name, backend = choose_backend(
        backend=args.backend,
        api_key_env=args.api_key_env,
        api_base=args.api_base,
        timeout_s=args.timeout_s,
        bootstrap_decisions_file=None,
        codex_binary=args.codex_binary,
        codex_working_dir=args.codex_working_dir,
        codex_reasoning_effort=args.codex_reasoning_effort,
    )
    if backend_name == "bootstrap":
        raise RuntimeError("bootstrap backend is not supported for article writing")
    writer_model = args.writer_model or ("gpt-5.4" if backend_name == "codex_cli" else "")

    results: list[dict[str, Any]] = []
    for rewrite_context_path in sorted(rewrite_context_root.glob("**/rewrite_context.json")):
        rewrite_context = load_json(rewrite_context_path)
        source_path = Path(rewrite_context["source_ref"]).expanduser().resolve()
        framework_match_path = Path(rewrite_context["framework_match_ref"]).expanduser().resolve()
        source_item = load_json(source_path)
        framework_match = load_json(framework_match_path)
        source_id = source_item["source_id"]
        source_gate = load_source_gate(source_gate_root / source_id / "source_gate.json") if source_gate_root else None
        requires_human_review = bool(framework_match["final_decision"]["requires_human_review"])
        if requires_human_review and not args.include_human_review_required:
            row = {
                "source_id": source_id,
                "status": "skipped_human_review_required",
                "output_json": "",
                "output_md": "",
                "validation_error": None,
            }
            results.append(row)
            print(f"{source_id} -> skipped_human_review_required")
            continue
        if source_gate and not source_gate["longform_eligible"]:
            row = {
                "source_id": source_id,
                "status": "skipped_source_gate",
                "output_json": "",
                "output_md": "",
                "validation_error": None,
            }
            results.append(row)
            print(f"{source_id} -> skipped_source_gate")
            continue

        raw = backend.complete_json(
            model=writer_model,
            system_prompt=writer_system_prompt(args.output_language),
            user_prompt=writer_user_prompt(build_source_packet(source_item), rewrite_context, args.output_language, humanizer_packet),
            output_schema=generation_response_schema(),
        )
        article = normalize_generation(raw, source_item)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source_ref": str(source_path),
            "framework_match_ref": str(framework_match_path),
            "rewrite_context_ref": str(rewrite_context_path.resolve()),
            "model": writer_model or "codex-default",
            "generated_at": isoformat_z(utc_now()),
            "output_language": args.output_language,
            "framework_id": rewrite_context["selected_framework"]["framework_id"],
            "submode_id": rewrite_context["selected_framework"]["submode_id"],
            "requires_human_review": requires_human_review,
            **article,
        }
        validation_error = validate_payload(payload, schema)
        target_dir = out_root / source_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_json = target_dir / "article_draft.json"
        out_md = target_dir / "article_draft.md"
        dump_json(out_json, payload)
        out_md.write_text(render_markdown(payload), encoding="utf-8")

        row = {
            "source_id": source_id,
            "status": "ok" if validation_error is None else "schema_error",
            "framework_id": payload["framework_id"],
            "submode_id": payload["submode_id"],
            "output_json": str(out_json),
            "output_md": str(out_md),
            "validation_error": validation_error,
        }
        results.append(row)
        print(f"{source_id} -> {row['status']}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "backend": backend_name,
        "rewrite_context_root": str(rewrite_context_root),
        "out_root": str(out_root),
        "output_language": args.output_language,
        "count": len(results),
        "ok_count": sum(1 for row in results if row["status"] == "ok"),
        "schema_error_count": sum(1 for row in results if row["status"] == "schema_error"),
        "skipped_human_review_count": sum(1 for row in results if row["status"] == "skipped_human_review_required"),
        "skipped_source_gate_count": sum(1 for row in results if row["status"] == "skipped_source_gate"),
        "results": results,
    }
    manifest_path = out_root / "article_draft_manifest.json"
    dump_json(manifest_path, manifest)
    print(manifest_path)
    print(
        "ok="
        f"{manifest['ok_count']} schema_errors={manifest['schema_error_count']} "
        f"skipped_human_review={manifest['skipped_human_review_count']} "
        f"skipped_source_gate={manifest['skipped_source_gate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
