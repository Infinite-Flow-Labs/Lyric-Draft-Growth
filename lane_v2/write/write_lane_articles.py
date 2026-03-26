from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

try:
    from jsonschema import validate as jsonschema_validate
except Exception:  # pragma: no cover - optional runtime dependency
    jsonschema_validate = None

ROUTE_DIR = Path(__file__).resolve().parents[1] / "route"
if str(ROUTE_DIR) not in sys.path:
    sys.path.insert(0, str(ROUTE_DIR))

ASSEMBLE_DIR = Path(__file__).resolve().parents[1] / "assemble"
if str(ASSEMBLE_DIR) not in sys.path:
    sys.path.insert(0, str(ASSEMBLE_DIR))

try:
    from article_formatter import build_article_blocks, build_publishing_hints
except ImportError:  # pragma: no cover - module import path fallback
    from content.pipeline.write.article_formatter import build_article_blocks, build_publishing_hints

from route_framework_matches import choose_backend, dump_json, isoformat_z, load_json, preview_text, utc_now
from build_rewrite_contexts import build_capability_packets


SCHEMA_VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[2]
T01_HARD_CHECKS = [
    "标题必须包含变化判断，不能是公告标题改写。",
    "Dek 必须回答真正值得看的变化是什么。",
    "开篇前两段必须出现发布动作 + 高价值判断。",
    "中段必须写清变化前后对比 + 人群影响 + 不该用边界。",
    "结尾必须给出可执行动作（立刻试用 / 观察 / 暂缓）。",
]
AI_SMELL_PATTERNS = {
    "not_but": r"不是[^。！？\n]{0,60}而是",
    "not_but_variant": r"不是[^。！？\n]{0,60}而在于",
    "not_only_but_also": r"不仅[^。！？\n]{0,60}而且",
    "not_just_more": r"不只是[^。！？\n]{0,60}更是",
    "formula_sequence": r"(首先|其次|最后)[，,：:]",
    "defensive_negation": r"(不是噱头|不是小事|并非炒作|不是空话|并非偶然|绝非巧合|并不夸张)",
}
def count_bare_handles(text: str) -> int:
    """Count @handles not preceded by a Chinese name (>=2 consecutive Chinese chars) within 6 chars."""
    handles = list(re.finditer(r"@\w{2,}", text))
    bare = 0
    for m in handles:
        start = max(0, m.start() - 6)
        context = text[start:m.start()]
        has_name = bool(re.search(r"[\u4e00-\u9fff]{2,}", context))
        if not has_name:
            bare += 1
    return bare
# Detect article ending with a question mark (rhetorical question ending)
RHETORICAL_ENDING_PATTERN = re.compile(r"[？?]\s*$")
AI_STALE_SURFACE_PHRASES = (
    "这个判断太轻了",
    "官方说得很直接",
    "最值得看",
    "更容易看清",
    "说透",
    "很清楚",
)
MID_TURN_MARKERS = (
    "但问题在于",
    "更关键的是",
    "换个角度",
    "落到执行",
    "这意味着",
    "另一面是",
    "先看边界",
    "回到现实",
    "不过",
    "但",
)
ACTION_CUE_PATTERN = re.compile(r"(可以|建议|先|马上|立刻|优先|下一步|试试|先做|先跑|先用)")
BOUNDARY_CUE_PATTERN = re.compile(r"(边界|不适合|限制|风险|前提|不等于|仅适用于|别把)")
PROMOTIONAL_WORD_PATTERN = re.compile(
    r"(颠覆性|革命性|划时代|史诗级|炸裂|封神|王炸|神级|重磅|天花板|无敌|必看|闭眼入|YYDS|震撼|顶配|巅峰)"
)
VAGUE_ATTRIBUTION_PATTERNS = [
    re.compile(r"(专家|业内人士|观察者|一些人|很多人|有人|市场人士)(普遍)?(认为|指出|表示|提到|称)"),
    re.compile(r"(据悉|有消息称|有观点认为|普遍认为|业界普遍认为|市场普遍认为)"),
]
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
BOLD_SPAN_PATTERN = re.compile(r"\*\*([^*]{1,220})\*\*")
EM_DASH_PATTERN = re.compile(r"\s*—\s*")
SUBHEADING_LINE_PATTERN = re.compile(r"(?m)^\s*#{2,3}\s+.+$")
BULLET_LINE_PATTERN = re.compile(r"(?m)^\s*[-*•]\s+.+$")
QUOTE_LINE_PATTERN = re.compile(r"(?m)^\s*>\s+.+$")


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(cleaned)
    return out


def trim_text(value: Any, max_chars: int) -> str:
    return preview_text(" ".join(str(value or "").split()).strip(), max_chars)


def trim_list(values: list[Any], *, max_items: int, max_chars: int) -> list[str]:
    out: list[str] = []
    for value in compact_list([str(item) for item in values]):
        trimmed = trim_text(value, max_chars)
        if not trimmed:
            continue
        out.append(trimmed)
        if len(out) >= max_items:
            break
    return out


def stale_surface_phrase_report(text: str) -> tuple[int, list[str]]:
    hits: list[str] = []
    total = 0
    for phrase in AI_STALE_SURFACE_PHRASES:
        count = text.count(phrase)
        if count > 0:
            hits.append(phrase)
            total += count
    return total, hits


def load_schema(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return load_json(path)


def load_optional_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return load_json(path)


def normalize_lane_id(value: str) -> str:
    return str(value or "").strip().lower()


def is_t01_lane(lane_assignment: dict[str, Any]) -> bool:
    lane_id = normalize_lane_id(
        str(lane_assignment.get("selected_lane_id", "")) or str(lane_assignment.get("lane_id", ""))
    )
    if lane_id.startswith("t01"):
        return True
    framework_id = str(lane_assignment.get("framework_id", "")).strip()
    return framework_id == "02_launch_application"


def apply_t01_signal_boost(
    contract: dict[str, Any],
    *,
    lane_assignment: dict[str, Any],
    t01_signal_boost: dict[str, Any] | None,
) -> dict[str, Any]:
    if not t01_signal_boost or not is_t01_lane(lane_assignment):
        return contract

    opening_boost = trim_list(t01_signal_boost.get("opening_hook_boost", []), max_items=8, max_chars=120)
    mid_boost = trim_list(t01_signal_boost.get("mid_transition_boost", []), max_items=8, max_chars=120)
    closing_boost = trim_list(t01_signal_boost.get("closing_carry_boost", []), max_items=6, max_chars=120)
    forbidden_boost = trim_list(t01_signal_boost.get("forbidden_surface_boost", []), max_items=8, max_chars=90)

    opening_contract = contract.get("opening_hook_contract", {})
    opening_contract["moves"] = compact_list([*opening_boost, *(opening_contract.get("moves", []) or [])])[:14]

    mid_contract = contract.get("mid_turn_contract", {})
    mid_contract["moves"] = compact_list([*mid_boost, *(mid_contract.get("moves", []) or [])])[:16]

    closing_contract = contract.get("closing_carry_contract", {})
    closing_contract["moves"] = compact_list([*closing_boost, *(closing_contract.get("moves", []) or [])])[:12]
    closing_contract["forbidden_endings"] = compact_list(
        [*(closing_contract.get("forbidden_endings", []) or []), *forbidden_boost]
    )[:12]

    anti_ai = contract.get("anti_ai_contract", {})
    anti_ai["must_avoid"] = compact_list([*(anti_ai.get("must_avoid", []) or []), *forbidden_boost])[:20]

    contract["opening_hook_contract"] = opening_contract
    contract["mid_turn_contract"] = mid_contract
    contract["closing_carry_contract"] = closing_contract
    contract["anti_ai_contract"] = anti_ai
    contract["t01_signal_boost_ref"] = t01_signal_boost.get("source_sample_refs", [])
    return contract


def observe_self_improving_original(
    *,
    observe_script: Path,
    skill_dir: Path,
    article_md: Path,
    lane_id: str,
    log_dir: str,
) -> dict[str, Any]:
    if not observe_script.exists():
        return {"status": "skipped_missing_observe_script", "detail": str(observe_script)}
    cmd = [
        "python3",
        str(observe_script),
        "record-original",
        str(article_md),
        "--skill",
        str(skill_dir),
        "--account",
        lane_id or "lane_v2",
        "--content-type",
        "article",
    ]
    if log_dir.strip():
        cmd.extend(["--log-dir", log_dir.strip()])
    completed = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=40)
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return {
            "status": "error",
            "exit_code": completed.returncode,
            "stdout": preview_text(stdout, 300),
            "stderr": preview_text(stderr, 300),
        }
    hash_match = re.search(r"记录原稿:\s*([a-f0-9]{8})", stdout)
    return {
        "status": "ok",
        "content_hash": hash_match.group(1) if hash_match else "",
        "stdout": preview_text(stdout, 300),
    }


def validate_payload(payload: dict[str, Any], schema: dict[str, Any] | None) -> str | None:
    if schema is None or jsonschema_validate is None:
        return None
    try:
        jsonschema_validate(payload, schema)
    except Exception as exc:  # pragma: no cover - surfacing validation details
        return f"{type(exc).__name__}: {exc}"
    return None


def extract_reader_pain_point(
    backend: Any,
    model: str,
    topic_statement: str,
    primary_source_excerpt: str,
    output_language: str,
) -> dict[str, Any]:
    """Lightweight LLM call to extract the reader's concrete pain point from source material."""
    prompt = json.dumps(
        {
            "task": "Extract the single most concrete reader pain point this topic addresses.",
            "instructions": [
                "You are identifying what specific frustration, inefficiency, or blocked workflow a reader experiences BEFORE this topic's solution exists.",
                "The pain point must be a concrete situation the reader personally encounters, not an abstract industry trend.",
                "Bad example: 'AI coding tools are evolving rapidly' (abstract, not a pain point).",
                "Good example: 'Your Codex task ran overnight and failed, but you only found out the next morning when you opened your laptop' (concrete personal situation).",
                "The hook_sentence should open the article by putting the reader inside this pain point.",
                f"Output language: {output_language}.",
            ],
            "topic_statement": topic_statement,
            "primary_source_excerpt": primary_source_excerpt[:1200],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["pain_point", "hook_sentence", "who_feels_it"],
        "properties": {
            "pain_point": {"type": "string", "description": "One sentence: the concrete frustration/blocked workflow."},
            "hook_sentence": {"type": "string", "description": "One sentence that opens the article by placing the reader inside the pain."},
            "who_feels_it": {"type": "string", "description": "The specific type of person who feels this pain most acutely."},
        },
    }
    try:
        return backend.complete_json(
            model=model,
            system_prompt="You extract reader pain points from source material. Return JSON only.",
            user_prompt=prompt,
            output_schema=schema,
        )
    except Exception:
        return {"pain_point": "", "hook_sentence": "", "who_feels_it": ""}


GITHUB_URL_PATTERN = re.compile(r"https?://github\.com/([\w\-\.]+)/([\w\-\.]+)")


def enrich_from_github(source_text: str, *, timeout_s: int = 15) -> dict[str, Any]:
    """Extract GitHub repo URLs from source text and fetch basic repo metadata."""
    matches = GITHUB_URL_PATTERN.findall(source_text)
    if not matches:
        return {}
    enrichments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for owner, repo in matches[:3]:
        repo = repo.rstrip(".git")
        key = f"{owner}/{repo}"
        if key in seen:
            continue
        seen.add(key)
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            request = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "growth-engine-enrichment"})
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
            enrichments.append({
                "repo": key,
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "language": data.get("language", ""),
                "description": (data.get("description") or "")[:200],
                "updated_at": data.get("pushed_at", ""),
                "license": (data.get("license") or {}).get("spdx_id", ""),
            })
        except Exception:
            continue
    return {"github_repos": enrichments} if enrichments else {}


def enrich_source_materials(
    primary_source_item: dict[str, Any],
    source_materials: list[dict[str, Any]],
) -> dict[str, Any]:
    """Collect enrichment data from URLs found in source materials."""
    # Gather all text to search for URLs
    texts = []
    full_text = primary_source_item.get("content", {}).get("full_text", "")
    if full_text:
        texts.append(full_text)
    for mat in source_materials[:4]:
        for anchor in mat.get("fact_anchors", []):
            texts.append(str(anchor))
        url = mat.get("canonical_url", "")
        if url:
            texts.append(url)
    combined = "\n".join(texts)

    enrichment: dict[str, Any] = {}
    github_data = enrich_from_github(combined)
    if github_data:
        enrichment.update(github_data)
    return enrichment


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


def compact_named_entities(values: list[str], *, max_items: int = 8) -> list[str]:
    stoplist = {"we", "post", "video post", "video canonical url", "canonical url", "linked", "video"}
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in stoplist:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(cleaned)
        if len(out) >= max_items:
            break
    return out


def compact_fact_anchors(values: list[str], *, max_items: int = 8, max_chars: int = 180) -> list[str]:
    stoplist = {"release", "released", "introducing", "post", "linked", "canonical url", "we"}
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in stoplist:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(trim_text(cleaned, max_chars))
        if len(out) >= max_items:
            break
    return out


def build_primary_source_packet(source_item: dict[str, Any]) -> dict[str, Any]:
    content = source_item.get("content", {})
    participants = []
    for participant in source_item.get("participants", []):
        name = participant.get("name", "")
        if name.startswith("LinkedIn ") or name.startswith("X "):
            continue
        participants.append(participant)
    full_text = content.get("full_text", "")
    return {
        "source_id": source_item.get("source_id", ""),
        "platform": source_item.get("platform", ""),
        "source_kind": source_item.get("source_kind", ""),
        "canonical_url": source_item.get("canonical_url", ""),
        "title": source_item.get("title", ""),
        "author": source_item.get("author", {}),
        "published_at": source_item.get("published_at", ""),
        "participants": participants,
        "primary_text_source": content.get("primary_text_source", ""),
        "summary": trim_text(content.get("summary", ""), 500),
        "full_text": trim_text(full_text, 3200),
        "raw_quotes": trim_list(content.get("raw_quotes", []), max_items=6, max_chars=180),
        "fact_anchors": compact_fact_anchors(source_item.get("extracted_signals", {}).get("fact_anchors", []), max_items=8),
        "metric_signals": trim_list(source_item.get("extracted_signals", {}).get("metric_signals", []), max_items=8, max_chars=64),
        "named_entities": compact_named_entities(source_item.get("extracted_signals", {}).get("named_entities", []), max_items=10),
    }


def find_submode(spec: dict[str, Any], submode_id: str) -> dict[str, Any]:
    for submode in spec.get("structure", {}).get("submodes", []):
        if submode.get("submode_id") == submode_id:
            return submode
    raise KeyError(f"Unable to find submode_id={submode_id}")


def find_style_profile(spec: dict[str, Any], style_profile_id: str) -> dict[str, Any]:
    for profile in spec.get("style", {}).get("submode_profiles", []):
        if profile.get("style_profile_id") == style_profile_id:
            return profile
    raise KeyError(f"Unable to find style_profile_id={style_profile_id}")


def build_sample_ref_map(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {sample["sample_id"]: sample for sample in spec.get("samples", {}).get("sample_refs", [])}


def slim_structure_packet(structure_packet: dict[str, Any]) -> dict[str, Any]:
    selected = structure_packet.get("selected_submode_spec", {})
    return {
        "hidden_skeleton": trim_list(structure_packet.get("hidden_skeleton", []), max_items=8, max_chars=90),
        "visible_template_bans": trim_list(structure_packet.get("visible_template_bans", []), max_items=6, max_chars=90),
        "allowed_surface_moves": trim_list(structure_packet.get("allowed_surface_moves", []), max_items=6, max_chars=90),
        "forbidden_surface_moves": trim_list(structure_packet.get("forbidden_surface_moves", []), max_items=6, max_chars=80),
        "selected_submode_spec": {
            "summary": trim_text(selected.get("summary", ""), 200),
            "use_when": trim_list(selected.get("use_when", []), max_items=4, max_chars=90),
            "avoid_when": trim_list(selected.get("avoid_when", []), max_items=4, max_chars=90),
            "hidden_flow": trim_list(selected.get("hidden_flow", []), max_items=8, max_chars=80),
            "hook_patterns": trim_list(selected.get("hook_patterns", []), max_items=5, max_chars=48),
            "evidence_mix": trim_list(selected.get("evidence_mix", []), max_items=6, max_chars=48),
            "reasoning_moves": trim_list(selected.get("reasoning_moves", []), max_items=6, max_chars=80),
            "rewrite_formula": trim_text(selected.get("rewrite_formula", ""), 180),
            "surface_forms": trim_list(selected.get("surface_forms", []), max_items=6, max_chars=40),
            "anti_patterns": trim_list(selected.get("anti_patterns", []), max_items=6, max_chars=70),
        },
    }


def slim_style_packet(style_packet: dict[str, Any]) -> dict[str, Any]:
    selected = style_packet.get("selected_style_profile", {})
    return {
        "global_style_principles": trim_list(style_packet.get("global_style_principles", []), max_items=6, max_chars=80),
        "global_anti_ai_rules": trim_list(style_packet.get("global_anti_ai_rules", []), max_items=8, max_chars=85),
        "selected_style_profile": {
            "tone_core": trim_text(selected.get("tone_core", ""), 220),
            "opening_moves": trim_list(selected.get("opening_moves", []), max_items=6, max_chars=50),
            "sentence_rhythm": trim_list(selected.get("sentence_rhythm", []), max_items=6, max_chars=60),
            "surface_forms": trim_list(selected.get("surface_forms", []), max_items=6, max_chars=40),
            "language_moves": trim_list(selected.get("language_moves", []), max_items=6, max_chars=60),
            "keep": trim_list(selected.get("keep", []), max_items=6, max_chars=44),
            "avoid": trim_list(selected.get("avoid", []), max_items=6, max_chars=55),
            "ai_smells": trim_list(selected.get("ai_smells", []), max_items=8, max_chars=70),
            "one_sentence_portrait": trim_text(selected.get("one_sentence_portrait", ""), 160),
        },
    }


def slim_sample_packet(sample_packet: dict[str, Any]) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    for sample in sample_packet.get("selected_sample_refs", [])[:2]:
        refs.append(
            {
                "title": trim_text(sample.get("title", ""), 80),
                "why_it_matters": trim_text(sample.get("why_it_matters", ""), 180),
                "hook_move": trim_text(sample.get("hook_move", ""), 140),
                "proof_mode": trim_list(sample.get("proof_mode", []), max_items=5, max_chars=40),
                "reusable_parts": trim_list(sample.get("reusable_parts", []), max_items=5, max_chars=90),
                "style_cue": trim_text(sample.get("style_cue", ""), 140),
            }
        )
    return {"selected_sample_refs": refs}


def slim_execution_packet(execution_packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "must_keep": trim_list(execution_packet.get("must_keep", []), max_items=8, max_chars=70),
        "must_avoid": trim_list(execution_packet.get("must_avoid", []), max_items=8, max_chars=70),
        "rewrite_failure_modes": trim_list(execution_packet.get("rewrite_failure_modes", []), max_items=6, max_chars=90),
        "quality_checks": trim_list(execution_packet.get("quality_checks", []), max_items=8, max_chars=90),
        "human_review_triggers": trim_list(execution_packet.get("human_review_triggers", []), max_items=6, max_chars=90),
    }


def slim_capability_packets(capability_packets: dict[str, Any]) -> dict[str, Any]:
    if not capability_packets:
        return {}

    def trim_moves(moves: list[dict[str, Any]], *, max_items: int = 3) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for move in moves[:max_items]:
            out.append(
                {
                    "move_id": str(move.get("move_id", "")).strip(),
                    "label": trim_text(move.get("label", ""), 64),
                    "when_to_use": trim_text(move.get("when_to_use", ""), 140),
                }
            )
        return out

    return {
        "global_anti_patterns": trim_list(capability_packets.get("global_anti_patterns", []), max_items=8, max_chars=85),
        "title_attack_packet": {
            "job": trim_text(capability_packets.get("title_attack_packet", {}).get("job", ""), 200),
            "recommended_moves": trim_moves(capability_packets.get("title_attack_packet", {}).get("recommended_moves", []), max_items=2),
            "sample_hook_moves": trim_list(capability_packets.get("title_attack_packet", {}).get("sample_hook_moves", []), max_items=3, max_chars=140),
            "stakes_signals": trim_list(capability_packets.get("title_attack_packet", {}).get("stakes_signals", []), max_items=10, max_chars=90),
            "forbidden_moves": trim_list(capability_packets.get("title_attack_packet", {}).get("forbidden_moves", []), max_items=5, max_chars=90),
        },
        "dek_value_packet": {
            "job": trim_text(capability_packets.get("dek_value_packet", {}).get("job", ""), 200),
            "stable_moves": trim_list(capability_packets.get("dek_value_packet", {}).get("stable_moves", []), max_items=6, max_chars=85),
            "sample_why_it_matters": trim_list(capability_packets.get("dek_value_packet", {}).get("sample_why_it_matters", []), max_items=3, max_chars=160),
            "reader_payoff_signals": trim_list(capability_packets.get("dek_value_packet", {}).get("reader_payoff_signals", []), max_items=8, max_chars=85),
        },
        "opening_value_packet": {
            "job": trim_text(capability_packets.get("opening_value_packet", {}).get("job", ""), 200),
            "stable_sequence": trim_list(capability_packets.get("opening_value_packet", {}).get("stable_sequence", []), max_items=6, max_chars=90),
            "identity_anchor": capability_packets.get("opening_value_packet", {}).get("identity_anchor", {}),
            "sample_hook_moves": trim_list(capability_packets.get("opening_value_packet", {}).get("sample_hook_moves", []), max_items=3, max_chars=140),
            "opening_moves": trim_list(capability_packets.get("opening_value_packet", {}).get("opening_moves", []), max_items=6, max_chars=80),
            "why_now_signals": trim_list(capability_packets.get("opening_value_packet", {}).get("why_now_signals", []), max_items=8, max_chars=80),
        },
        "mid_reset_plan": {
            "job": trim_text(capability_packets.get("mid_reset_plan", {}).get("job", ""), 200),
            "reset_frequency": trim_text(capability_packets.get("mid_reset_plan", {}).get("reset_frequency", ""), 80),
            "allowed_reset_moves": trim_list(capability_packets.get("mid_reset_plan", {}).get("allowed_reset_moves", []), max_items=8, max_chars=80),
            "section_turn_targets": trim_list(capability_packets.get("mid_reset_plan", {}).get("section_turn_targets", []), max_items=10, max_chars=90),
            "forbidden_moves": trim_list(capability_packets.get("mid_reset_plan", {}).get("forbidden_moves", []), max_items=5, max_chars=90),
        },
        "closing_carry_packet": {
            "job": trim_text(capability_packets.get("closing_carry_packet", {}).get("job", ""), 200),
            "recommended_moves": trim_moves(capability_packets.get("closing_carry_packet", {}).get("recommended_moves", []), max_items=2),
            "closing_targets": trim_list(capability_packets.get("closing_carry_packet", {}).get("closing_targets", []), max_items=8, max_chars=90),
            "forbidden_endings": trim_list(capability_packets.get("closing_carry_packet", {}).get("forbidden_endings", []), max_items=6, max_chars=90),
        },
    }


def slim_humanizer_packet(humanizer_packet: dict[str, Any] | None) -> dict[str, Any]:
    if not humanizer_packet:
        return {}
    return {
        "core_principles": trim_list(humanizer_packet.get("core_principles", []), max_items=8, max_chars=100),
        "voice_rules": trim_list(humanizer_packet.get("voice_rules", []), max_items=8, max_chars=105),
        "ai_smells_to_avoid": trim_list(humanizer_packet.get("ai_smells_to_avoid", []), max_items=20, max_chars=90),
        "preferred_rewrites": trim_list(humanizer_packet.get("preferred_rewrites", []), max_items=8, max_chars=100),
        "writer_guardrails": trim_list(humanizer_packet.get("writer_guardrails", []), max_items=8, max_chars=110),
        "self_check": trim_list(humanizer_packet.get("self_check", []), max_items=8, max_chars=105),
    }


def build_global_quality_instructions() -> list[str]:
    return [
        "Write a full-length article. Default to roughly 12-18 substantive paragraphs with varied paragraph lengths.",
        "The title must carry a concrete conflict, reversal, or stake. Avoid generic industry-summary titles.",
        "The dek must sharpen the angle and reader payoff, not repeat the title.",
        "Open with tension/paradox/surprise within the first 2 sentences.",
        "First paragraph must contain at least one source-specific fact.",
        "The middle must keep changing mode. Avoid 4 straight paragraphs of abstract explanation.",
        "Use bullet lists only to compress evidence, not as a substitute for argument flow.",
        "End with a concrete judgment and action guidance; do not stop at recap.",
        "Do not use the template contrast forms '不是...而是...' or '不仅...而且...'.",
        "Do not use promotional hype language (e.g., 颠覆性/炸裂/封神/王炸/天花板).",
        "Avoid vague attribution (e.g., 专家认为/有人指出/据悉). Use source-backed attribution only.",
        "Avoid emoji decoration and em-dash-heavy rhythm.",
        "Avoid bold-overuse in markdown body.",
        "Avoid stale AI-sounding bridge phrases: 这个判断太轻了 / 官方说得很直接 / 最值得看 / 更容易看清 / 说透 / 很清楚.",
        "Use colloquial, concrete, human phrasing instead of template transitions.",
        "Do not output pipeline metadata lines (Framework/Submode/Output Language/Human Review/Preserved Fact Anchors/Open Questions).",
        "Do not append writer notes or TODO comments in body_markdown.",
    ]


def build_submode_instruction(submode_id: str) -> list[str]:
    if submode_id == "release_showcase":
        return [
            "The piece must move from release signal -> practical consequence -> who should act now.",
            "At least one paragraph must explicitly explain limits/risks/trade-offs.",
            "Avoid writing as a press-release recap. The reader must get an adoption judgment.",
        ]
    if submode_id == "feature_playbook":
        return [
            "Translate feature terms into concrete user actions and boundaries.",
            "Give best-use and not-for-you boundaries explicitly.",
        ]
    if submode_id == "signal_decode":
        return [
            "Choose one dominant thesis and make the entire draft serve it.",
            "Do not pile independent signals like a newsletter digest.",
        ]
    return []


def load_source_docs_raw(spec: dict[str, Any]) -> dict[str, str]:
    source_docs = spec.get("metadata", {}).get("source_of_truth_refs", {}) or {}
    out: dict[str, str] = {}
    for doc_key, doc_path in source_docs.items():
        path_value = str(doc_path or "").strip()
        if not path_value:
            continue
        abs_path = (REPO_ROOT / path_value).resolve()
        if abs_path.exists():
            out[str(doc_key)] = abs_path.read_text(encoding="utf-8")
    return out


def load_style_profiles_packet(spec: dict[str, Any], submode_id: str) -> dict[str, Any]:
    refs = spec.get("metadata", {}).get("source_of_truth_refs", {}) or {}
    rel_path = str(refs.get("style_profiles_md", "")).strip()
    if not rel_path:
        return {"style_profiles_ref": "", "overview_section_excerpt": "", "submode_section_excerpt": ""}
    style_path = (REPO_ROOT / rel_path).resolve()
    if not style_path.exists():
        return {"style_profiles_ref": str(style_path), "overview_section_excerpt": "", "submode_section_excerpt": ""}
    raw = style_path.read_text(encoding="utf-8")
    overview_match = re.search(r"##\s+总体观察\s*(.*?)(?=\n##\s+\d+\.\s+|\Z)", raw, flags=re.S)
    submode_match = re.search(
        rf"##\s+\d+\.\s+{re.escape(submode_id)}\s*(.*?)(?=\n##\s+\d+\.\s+|\Z)",
        raw,
        flags=re.S | re.I,
    )
    overview_excerpt = trim_text((overview_match.group(1) if overview_match else "").strip(), 1800)
    submode_excerpt = trim_text((submode_match.group(1) if submode_match else "").strip(), 2600)
    return {
        "style_profiles_ref": str(style_path),
        "overview_section_excerpt": overview_excerpt,
        "submode_section_excerpt": submode_excerpt,
    }


def _top_texts(rows: list[dict[str, Any]], *, max_items: int, max_chars: int) -> list[str]:
    out: list[str] = []
    for row in rows[:max_items]:
        text = trim_text(str(row.get("text", "")).strip(), max_chars)
        if text:
            out.append(text)
    return compact_list(out)


def _normalize_submode_token(value: Any) -> str:
    return str(value or "").strip().strip("`").strip().lower()


def load_sample_moves_layer_packet(spec_path: Path, submode_id: str) -> dict[str, Any]:
    layer_path = spec_path.parent / "SAMPLE_MOVES_LAYER.json"
    if not layer_path.exists():
        return {
            "sample_moves_layer_ref": str(layer_path),
            "opening_hook_moves": [],
            "mid_transition_moves": [],
            "closing_carry_moves": [],
            "evidence_combo_units": [],
            "language_action_moves": [],
            "forbidden_rewrite_parts": [],
            "sample_cards_for_submode": [],
        }
    payload = load_json(layer_path)
    moves_layer = payload.get("moves_layer", {}) or {}
    sample_cards: list[dict[str, Any]] = []
    normalized_target = _normalize_submode_token(submode_id)
    for card in payload.get("sample_cards", []):
        if _normalize_submode_token(card.get("submode_id", "")) != normalized_target:
            continue
        sample_cards.append(
            {
                "sample_id": str(card.get("sample_id", "")),
                "title": trim_text(card.get("title", ""), 140),
                "hook_move": trim_text(card.get("hook_move", ""), 180),
                "proof_mode": trim_list(card.get("proof_mode", []), max_items=4, max_chars=80),
                "reusable_parts": trim_list(card.get("reusable_parts", []), max_items=5, max_chars=120),
                "style_cue": trim_text(card.get("style_cue", ""), 180),
            }
        )
        if len(sample_cards) >= 6:
            break
    if not sample_cards:
        for card in payload.get("sample_cards", [])[:4]:
            sample_cards.append(
                {
                    "sample_id": str(card.get("sample_id", "")),
                    "title": trim_text(card.get("title", ""), 140),
                    "hook_move": trim_text(card.get("hook_move", ""), 180),
                    "proof_mode": trim_list(card.get("proof_mode", []), max_items=4, max_chars=80),
                    "reusable_parts": trim_list(card.get("reusable_parts", []), max_items=5, max_chars=120),
                    "style_cue": trim_text(card.get("style_cue", ""), 180),
                }
            )

    return {
        "sample_moves_layer_ref": str(layer_path),
        "opening_hook_moves": _top_texts(
            moves_layer.get("opening_hook_layer", {}).get("top_moves", []),
            max_items=10,
            max_chars=160,
        ),
        "mid_transition_moves": _top_texts(
            moves_layer.get("mid_transition_layer", {}).get("top_moves", []),
            max_items=12,
            max_chars=160,
        ),
        "closing_carry_moves": _top_texts(
            moves_layer.get("closing_carry_layer", {}).get("top_moves", []),
            max_items=8,
            max_chars=160,
        ),
        "evidence_combo_units": _top_texts(
            moves_layer.get("evidence_combo_layer", {}).get("top_evidence_units", []),
            max_items=10,
            max_chars=120,
        ),
        "language_action_moves": _top_texts(
            moves_layer.get("language_action_layer", {}).get("top_language_moves", []),
            max_items=10,
            max_chars=180,
        ),
        "forbidden_rewrite_parts": _top_texts(
            moves_layer.get("rewrite_forbidden_zone_layer", {}).get("top_non_reusable_parts", []),
            max_items=10,
            max_chars=160,
        ),
        "sample_cards_for_submode": sample_cards,
    }


def build_writer_context_packet(framework_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_framework": framework_context["selected_framework"],
        "framework_spec_slim": framework_context.get("framework_spec_slim", {}),
        "style_profiles_packet": framework_context.get("style_profiles_packet", {}),
        "sample_moves_layer_packet": framework_context.get("sample_moves_layer_packet", {}),
    }


def build_source_bundle_packet(source_bundle: dict[str, Any]) -> dict[str, Any]:
    def slim_source_rows(rows: list[dict[str, Any]], max_items: int) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for row in rows[:max_items]:
            out.append(
                {
                    "signal_id": str(row.get("signal_id", "")),
                    "source_family": str(row.get("source_family", "")),
                    "canonical_url": str(row.get("canonical_url", "")),
                    "title": trim_text(row.get("title", ""), 220),
                    "published_at": str(row.get("published_at", "")),
                }
            )
        return out

    anchors: list[dict[str, str]] = []
    seen_anchors: set[tuple[str, str]] = set()
    for row in source_bundle.get("fact_anchors", [])[:24]:
        claim = trim_text(row.get("claim", ""), 180)
        source_url = str(row.get("source_url", "")).strip()
        if not claim or not source_url:
            continue
        key = (claim.lower(), source_url)
        if key in seen_anchors:
            continue
        seen_anchors.add(key)
        anchors.append({"claim": claim, "source_url": source_url, "signal_id": str(row.get("signal_id", ""))})
        if len(anchors) >= 18:
            break

    return {
        "lane_id": source_bundle.get("lane_id", ""),
        "framework_id": source_bundle.get("framework_id", ""),
        "submode_id": source_bundle.get("submode_id", ""),
        "composition_mode": source_bundle.get("composition_mode", ""),
        "primary_sources": slim_source_rows(source_bundle.get("primary_sources", []), 4),
        "supporting_sources": slim_source_rows(source_bundle.get("supporting_sources", []), 6),
        "fact_anchors": anchors,
        "forbidden_claims": trim_list(source_bundle.get("forbidden_claims", []), max_items=10, max_chars=120),
        "coverage_checks": source_bundle.get("coverage_checks", {}),
        "requirement_checks": source_bundle.get("requirement_checks", {}),
    }


def build_source_material_packet(source_item: dict[str, Any], source_family: str, source_role: str = "supporting") -> dict[str, Any]:
    content = source_item.get("content", {})
    extracted = source_item.get("extracted_signals", {})
    if source_role == "primary":
        return {
            "source_id": source_item.get("source_id", ""),
            "source_role": "primary",
            "canonical_url": source_item.get("canonical_url", ""),
            "title": trim_text(source_item.get("title", ""), 220),
            "fact_anchors": compact_fact_anchors(extracted.get("fact_anchors", []), max_items=10, max_chars=180),
            "full_text_excerpt": trim_text(content.get("full_text", ""), 2400),
        }
    # Supporting sources: only identity + fact anchors (summary duplicates source_bundle)
    return {
        "source_id": source_item.get("source_id", ""),
        "source_role": "supporting",
        "canonical_url": source_item.get("canonical_url", ""),
        "title": trim_text(source_item.get("title", ""), 220),
        "fact_anchors": compact_fact_anchors(extracted.get("fact_anchors", []), max_items=6, max_chars=180),
    }


def derive_sample_learning_signals(sample_packet: dict[str, Any]) -> dict[str, list[str]]:
    selected = sample_packet.get("selected_sample_refs", []) or []
    opening: list[str] = []
    mid: list[str] = []
    closing: list[str] = []
    for sample in selected:
        hook = trim_text(sample.get("hook_move", ""), 180)
        why = trim_text(sample.get("why_it_matters", ""), 180)
        parts = trim_list(sample.get("reusable_parts", []), max_items=5, max_chars=140)
        if hook:
            opening.append(hook)
        if why:
            opening.append(why)
        if parts:
            opening.append(parts[0])
        if len(parts) >= 2:
            mid.extend(parts[1:-1] or parts[1:2])
            closing.append(parts[-1])
    return {
        "opening_hook_cues": compact_list(opening)[:6],
        "mid_turn_cues": compact_list(mid)[:8],
        "closing_carry_cues": compact_list(closing)[:6],
    }


def build_article_quality_contract(
    *,
    framework_context: dict[str, Any],
    primary_source_packet: dict[str, Any],
    humanizer_packet: dict[str, Any] | None,
    lane_assignment: dict[str, Any],
    t01_signal_boost: dict[str, Any] | None,
) -> dict[str, Any]:
    capability = framework_context.get("capability_packets", {}) or {}
    sample_layer = framework_context.get("sample_moves_layer_packet", {}) or {}
    sample_packet = framework_context.get("sample_packet", {}) or {}
    selected_samples = sample_packet.get("selected_sample_refs", []) or []

    sample_hook_moves = compact_list([trim_text(row.get("hook_move", ""), 180) for row in selected_samples])[:8]
    sample_reusable_parts: list[str] = []
    sample_proof_modes: list[str] = []
    for row in selected_samples:
        sample_reusable_parts.extend(trim_list(row.get("reusable_parts", []), max_items=6, max_chars=120))
        sample_proof_modes.extend(trim_list(row.get("proof_mode", []), max_items=5, max_chars=90))

    opening_packet = capability.get("opening_value_packet", {}) or {}
    mid_packet = capability.get("mid_reset_plan", {}) or {}
    closing_packet = capability.get("closing_carry_packet", {}) or {}
    framework_spec = framework_context.get("framework_spec_full", {}) or {}
    style_packet = framework_context.get("style_profiles_packet", {}) or {}

    contract = {
        "source_of_truth": {
            "framework_spec_ref": framework_context.get("framework_spec_ref", ""),
            "style_profiles_ref": style_packet.get("style_profiles_ref", ""),
            "sample_moves_layer_ref": sample_layer.get("sample_moves_layer_ref", ""),
        },
        "opening_hook_contract": {
            "moves": compact_list(
                [
                    *sample_layer.get("opening_hook_moves", []),
                    *sample_hook_moves,
                    *opening_packet.get("stable_sequence", []),
                    *opening_packet.get("opening_moves", []),
                ]
            )[:10],
            "hook_cues": compact_list(sample_layer.get("language_action_moves", []))[:8],
            "must_include_primary_fact_anchor": True,
        },
        "mid_turn_contract": {
            "moves": compact_list(
                [
                    *sample_layer.get("mid_transition_moves", []),
                    *mid_packet.get("allowed_reset_moves", []),
                    *mid_packet.get("section_turn_targets", []),
                    *sample_reusable_parts,
                ]
            )[:14],
            "evidence_units": compact_list(
                [*sample_layer.get("evidence_combo_units", []), *sample_proof_modes]
            )[:12],
            "turn_markers_hint": list(MID_TURN_MARKERS),
        },
        "closing_carry_contract": {
            "moves": compact_list(
                [
                    *sample_layer.get("closing_carry_moves", []),
                    *closing_packet.get("closing_targets", []),
                ]
            )[:10],
            "forbidden_endings": compact_list(
                [*closing_packet.get("forbidden_endings", []), *sample_layer.get("forbidden_rewrite_parts", [])]
            )[:10],
        },
        "primary_fact_anchor_pool": primary_source_packet.get("fact_anchors", [])[:8],
        "anti_ai_contract": {
            "must_avoid": compact_list(
                [
                    *AI_STALE_SURFACE_PHRASES,
                    *framework_spec.get("style", {}).get("global_anti_ai_rules", []),
                    *framework_spec.get("structure", {}).get("visible_template_bans", []),
                    *sample_layer.get("forbidden_rewrite_parts", []),
                    *(humanizer_packet or {}).get("ai_smells_to_avoid", []),
                ]
            )[:24],
            "self_check": compact_list((humanizer_packet or {}).get("self_check", []))[:8],
        },
    }
    return apply_t01_signal_boost(
        contract,
        lane_assignment=lane_assignment,
        t01_signal_boost=t01_signal_boost,
    )


def structure_gate(
    *,
    body_markdown: str,
    primary_source_packet: dict[str, Any],
    quality_contract: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", str(body_markdown or "")) if p.strip()]
    opening = "\n".join(paragraphs[:2])
    mid = "\n".join(paragraphs[2:-2]) if len(paragraphs) > 4 else ""
    closing = "\n".join(paragraphs[-2:]) if paragraphs else ""
    reasons: list[str] = []

    if len(paragraphs) < 10:
        reasons.append("structure_too_short")

    anchors = [anchor for anchor in primary_source_packet.get("fact_anchors", []) if len(str(anchor).strip()) >= 4][:6]
    if anchors and not any(str(anchor) in opening for anchor in anchors):
        reasons.append("opening_missing_primary_anchor")

    mid_hits = sum(1 for marker in MID_TURN_MARKERS if marker in mid)
    if mid_hits < 2:
        reasons.append("mid_missing_turns")

    if not ACTION_CUE_PATTERN.search(closing):
        reasons.append("closing_missing_action")
    if not BOUNDARY_CUE_PATTERN.search(closing):
        reasons.append("closing_missing_boundary")

    report = {
        "paragraph_count": len(paragraphs),
        "opening_anchor_hits": sum(1 for anchor in anchors if str(anchor) in opening),
        "mid_turn_marker_hits": mid_hits,
        "closing_action_hit": bool(ACTION_CUE_PATTERN.search(closing)),
        "closing_boundary_hit": bool(BOUNDARY_CUE_PATTERN.search(closing)),
        "quality_contract": quality_contract,
    }
    return (len(reasons) == 0, reasons, report)


def ensure_opening_quote_block(body_markdown: str, dek: str) -> str:
    text = str(body_markdown or "").replace("\r\n", "\n").strip()
    if not text:
        quote_text = " ".join(str(dek or "").split()).strip()
        return f"> {quote_text}" if quote_text else ""
    # Remove leading --- separator lines (LLM artifact)
    lines = text.split("\n")
    while lines and lines[0].strip() in ("---", "***", "___", ""):
        lines.pop(0)
    text = "\n".join(lines).strip()
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    # Also strip --- chunks from between paragraphs
    chunks = [c for c in chunks if c.strip() not in ("---", "***", "___")]
    if chunks and chunks[0].startswith(">"):
        return "\n\n".join(chunks)
    # First chunk is not a quote — prepend dek as quote
    quote_text = " ".join(str(dek or "").split()).strip()
    if not quote_text:
        quote_text = chunks[0][:120].strip() if chunks else ""
    if not quote_text:
        return "\n\n".join(chunks)
    return f"> {quote_text}\n\n" + "\n\n".join(chunks)


def extract_markdown_chunks(body_markdown: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", str(body_markdown or "").strip()) if chunk.strip()]


def markdown_format_report(*, title: str, body_markdown: str) -> dict[str, Any]:
    chunks = extract_markdown_chunks(body_markdown)
    heading_count = len(SUBHEADING_LINE_PATTERN.findall(body_markdown))
    quote_line_count = len(QUOTE_LINE_PATTERN.findall(body_markdown))
    bullet_line_count = len(BULLET_LINE_PATTERN.findall(body_markdown))
    bold_span_count = len(BOLD_SPAN_PATTERN.findall(body_markdown))
    first_chunk = chunks[0] if chunks else ""
    opening_quote_ok = first_chunk.startswith(">")
    return {
        "title_chars": len(str(title or "").strip()),
        "chunk_count": len(chunks),
        "heading_count": heading_count,
        "quote_line_count": quote_line_count,
        "bullet_line_count": bullet_line_count,
        "bold_span_count": bold_span_count,
        "opening_quote_ok": opening_quote_ok,
    }


def markdown_format_gate(report: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    title_chars = int(report.get("title_chars", 0))
    if title_chars > 32:
        reasons.append("title_too_long")
    if title_chars < 12:
        reasons.append("title_too_short")
    if int(report.get("heading_count", 0)) < 2:
        reasons.append("subheading_missing")
    if int(report.get("quote_line_count", 0)) < 1:
        reasons.append("quote_block_missing")
    if not bool(report.get("opening_quote_ok", False)):
        reasons.append("subtitle_quote_not_opening")
    if int(report.get("bullet_line_count", 0)) < 3:
        reasons.append("bullet_density_low")
    bold_span_count = int(report.get("bold_span_count", 0))
    if bold_span_count < 3:
        reasons.append("bold_emphasis_low")
    if bold_span_count > 16:
        reasons.append("bold_emphasis_overuse")
    return (len(reasons) == 0, reasons)


def normalize_generation(raw: dict[str, Any], source_item: dict[str, Any]) -> dict[str, Any]:
    body_markdown = ensure_opening_quote_block(str(raw["body_markdown"]).strip(), str(raw.get("dek", "")))
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
        "preserved_fact_anchors": compact_list(raw.get("preserved_fact_anchors", []))[:12],
        "style_observations": compact_list(raw.get("style_observations", []))[:8],
        "open_questions": compact_list(raw.get("open_questions", []))[:6],
        "article_blocks": article_blocks,
        "publishing_hints": publishing_hints,
    }


def ai_smell_report(*, title: str, dek: str, body_markdown: str) -> dict[str, Any]:
    text = "\n".join([str(title or ""), str(dek or ""), str(body_markdown or "")])
    counts: dict[str, Any] = {}
    for key, pattern in AI_SMELL_PATTERNS.items():
        counts[key] = len(re.findall(pattern, text))
    connector_density = len(re.findall(r"(因此|所以|同时|另外|总之|综上)", text))
    counts["connector_density"] = connector_density
    counts["promo_lexicon"] = len(PROMOTIONAL_WORD_PATTERN.findall(text))
    counts["vague_attribution"] = sum(len(pattern.findall(text)) for pattern in VAGUE_ATTRIBUTION_PATTERNS)
    counts["emoji_count"] = len(EMOJI_PATTERN.findall(text))
    counts["em_dash_count"] = len(EM_DASH_PATTERN.findall(text))
    counts["bold_span_count"] = len(BOLD_SPAN_PATTERN.findall(str(body_markdown or "")))
    stale_count, stale_hits = stale_surface_phrase_report(text)
    counts["stale_surface_phrase_hits"] = stale_count
    counts["stale_surface_phrase_terms"] = stale_hits
    # New detections
    counts["bare_handle_count"] = count_bare_handles(str(body_markdown or ""))
    paragraphs = [p.strip() for p in str(body_markdown or "").split("\n\n") if p.strip()]
    counts["rhetorical_ending"] = bool(paragraphs and RHETORICAL_ENDING_PATTERN.search(paragraphs[-1]))
    return counts


def humanizer_gate(report: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if int(report.get("not_but", 0)) > 0:
        reasons.append("contains_pattern_not_but")
    if int(report.get("not_only_but_also", 0)) > 0:
        reasons.append("contains_pattern_not_only_but_also")
    if int(report.get("formula_sequence", 0)) > 2:
        reasons.append("formulaic_sequence_overuse")
    if int(report.get("connector_density", 0)) > 14:
        reasons.append("connector_density_too_high")
    if int(report.get("promo_lexicon", 0)) > 1:
        reasons.append("promotional_lexicon_overuse")
    if int(report.get("vague_attribution", 0)) > 0:
        reasons.append("vague_attribution_detected")
    if int(report.get("emoji_count", 0)) > 0:
        reasons.append("emoji_detected")
    if int(report.get("em_dash_count", 0)) > 2:
        reasons.append("em_dash_overuse")
    if int(report.get("bold_span_count", 0)) > 8:
        reasons.append("bold_overuse")
    if int(report.get("stale_surface_phrase_hits", 0)) > 0:
        reasons.append("stale_surface_phrase_detected")
    # New hard gates
    if int(report.get("not_but_variant", 0)) > 0:
        reasons.append("contains_pattern_not_but_variant")
    if int(report.get("not_just_more", 0)) > 0:
        reasons.append("contains_pattern_not_just_more")
    if int(report.get("defensive_negation", 0)) > 0:
        reasons.append("defensive_negation_detected")
    if bool(report.get("rhetorical_ending", False)):
        reasons.append("rhetorical_question_ending")
    if int(report.get("bare_handle_count", 0)) > 0:
        reasons.append("bare_handle_without_real_name")
    return (len(reasons) == 0, reasons)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# {payload['title']}", "", f"> {payload['dek']}"]
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


def lane_writer_system_prompt(output_language: str) -> str:
    return (
        "You are the lane-controlled article writer in a topic-to-lane pipeline. "
        "This is not free writing. Lane contract + framework context + source bundle are hard constraints. "
        "Use provided source evidence as the primary fact base and avoid unsupported claims. "
        "Keep hooks strong, middle dynamic, and closing actionable. "
        "Avoid AI-writing smell in first-pass generation without sacrificing structure. "
        "Before returning JSON, run a strict self-check and rewrite violating spans yourself. "
        "Do not ship banned patterns and do not rely on post-process cleanup. "
        "Never include pipeline metadata labels in the article body. "
        f"Write in {output_language}. "
        "Return valid JSON only."
    )


def lane_writer_user_prompt(
    *,
    packet: dict[str, Any],
    primary_source_packet: dict[str, Any],
    source_bundle_packet: dict[str, Any],
    source_materials_packet: list[dict[str, Any]],
    framework_context: dict[str, Any],
    lane_contract_excerpt: str,
    output_language: str,
    humanizer_packet: dict[str, Any] | None,
    extra_instructions: list[str] | None = None,
    previous_failed_draft: dict[str, Any] | None = None,
    article_quality_contract: dict[str, Any] | None = None,
    reader_pain_point: dict[str, Any] | None = None,
    source_enrichment: dict[str, Any] | None = None,
) -> str:
    lane_assignment = packet.get("lane_assignment", {})
    topic_card = packet.get("topic_card", {})
    composition_mode = str(lane_assignment.get("composition_mode", "mixed"))
    generation_ratio = float(lane_assignment.get("generation_ratio", packet.get("generation_ratio", 0.8)))
    rewrite_ratio = float(lane_assignment.get("rewrite_ratio", packet.get("rewrite_ratio", 0.2)))

    # --- Unified instructions: one authoritative source of rules ---
    instructions = [
        # Core writing mandate
        "Raw source facts outrank rhetorical cleverness.",
        "Do not produce a summary digest; produce a judged, usable article.",
        f"Composition: {composition_mode} (generation={generation_ratio:.0%}, rewrite={rewrite_ratio:.0%}).",
        "Rewrite portion preserves critical release facts; generated portion adds judgment + action paths.",
        "At least 5 preserved_fact_anchors from provided sources.",
        "Honor forbidden_claims strictly.",
        # Format rules
        f"Output language: {output_language}.",
        "body_markdown must use markdown structure. First chunk must be a quote block: > ...",
        "At least 2 subheadings (## ...), 1 bullet list (>=3 items), 3-10 bold spans.",
        "Title: 12-32 chars, must carry conflict/reversal/stake.",
        "Dek: a plain sentence that sharpens the angle. Do NOT prefix with labels. Do NOT repeat the title. The dek field in JSON is a plain sentence.",
        "CRITICAL FORMAT: body_markdown must start with '> ' quote block as the FIRST line. No '---' separators. No plain text before the first quote block. Structure: > hook quote\\n\\n正文段落...",
        "Do not output framework IDs, submode IDs, model names, or metadata in article text.",
        # Anti-AI smell (merged from humanizer_packet)
        "Banned: 不是...而是..., 不仅...而且..., 首先/其次/最后 template, emoji, em-dash overuse, bold overuse.",
        "Banned: promotional hype (颠覆性/炸裂/封神/王炸/天花板), vague attribution (专家认为/据悉).",
        "Banned: stale bridges (这个判断太轻了/官方说得很直接/最值得看/更容易看清/说透/很清楚).",
        "Sound like an informed human writer making judgments, not a neutral recap engine.",
        "Delete filler phrases. Vary rhythm. Trust the reader.",
    ]
    instructions.extend(T01_HARD_CHECKS)
    instructions.extend(build_submode_instruction(str(framework_context["selected_framework"]["submode_id"])))
    if (article_quality_contract or {}).get("t01_signal_boost_ref"):
        instructions.extend([
            "T01 rhythm: opening must hit conclusion + contrast + source fact within two paragraphs.",
            "T01 rhythm: middle must escalate value at least twice (signal -> judgment -> action).",
            "T01 rhythm: ending must include stance, boundary, and one concrete discussion question.",
        ])
    # Hook & pain point rules
    if reader_pain_point and reader_pain_point.get("hook_sentence"):
        instructions.extend([
            "CRITICAL: The article must open by placing the reader inside a concrete personal pain point — not by stating what happened.",
            f"Reader pain point: {reader_pain_point.get('pain_point', '')}",
            f"Use this hook as opening inspiration (adapt, don't copy verbatim): {reader_pain_point.get('hook_sentence', '')}",
            f"The person who feels this most: {reader_pain_point.get('who_feels_it', '')}",
        ])
    else:
        instructions.append(
            "The article must open by placing the reader inside a concrete personal frustration or blocked workflow, not by stating what product/feature launched."
        )
    # Information architecture
    instructions.extend([
        "First two paragraphs must complete: what is it → what changed → why it matters to YOU specifically.",
        "Related/tangential signals must not exceed 20% of the article. If removing a related signal paragraph doesn't weaken the main argument, remove it.",
        "Every external example cited must have a direct causal link to the main topic. 'Same general direction' is not enough.",
    ])
    # Source respect & anti-fabrication
    instructions.extend([
        "When mentioning a source author for the first time, use their known public name or Chinese name (e.g. '归藏' not '@op7418'). @handle can follow in parentheses.",
        "Do not make quantitative promises (time, effort, cost) not supported by source data.",
        "Audience segments must be by concrete use-case scenario, not vague identity labels like '独立开发者'.",
    ])
    # Enrichment data usage
    if source_enrichment and source_enrichment.get("github_repos"):
        instructions.append(
            "source_enrichment contains real-time GitHub data (stars, forks, last update). Use these numbers naturally in the article for credibility. Do not fabricate numbers not in enrichment."
        )
    # Ending rules
    instructions.extend([
        "The article must end with a concrete actionable next step, NOT a rhetorical question or philosophical open-ended prompt.",
        "Do not use defensive negation — do not deny accusations nobody made (e.g. '不是噱头', '不是小事').",
    ])
    if extra_instructions:
        instructions.extend(extra_instructions)

    prompt_payload = {
        "task": "Write one publishable lane-controlled article draft.",
        "instructions": instructions,
        "topic_card": {
            "topic_id": topic_card.get("topic_id", ""),
            "topic_statement": trim_text(topic_card.get("topic_statement", ""), 300),
            "why_now": trim_text(topic_card.get("why_now", ""), 220),
            "cluster_signature": topic_card.get("cluster_signature", ""),
        },
        "lane_assignment": {
            "selected_lane_id": lane_assignment.get("selected_lane_id", ""),
            "framework_id": lane_assignment.get("framework_id", ""),
            "submode_id": lane_assignment.get("submode_id", ""),
            "composition_mode": composition_mode,
            "rationale": trim_text(lane_assignment.get("rationale", ""), 240),
        },
        "primary_source_item": primary_source_packet,
        "source_bundle": source_bundle_packet,
        "source_materials": source_materials_packet,
        "framework_context": build_writer_context_packet(framework_context),
    }
    if reader_pain_point and reader_pain_point.get("hook_sentence"):
        prompt_payload["reader_pain_point"] = reader_pain_point
    if source_enrichment:
        prompt_payload["source_enrichment"] = source_enrichment
    if previous_failed_draft:
        prompt_payload["previous_failed_draft"] = previous_failed_draft
    return json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))


def lane_repair_user_prompt(
    *,
    failed_article: dict[str, Any],
    gate_reasons: list[str],
    output_language: str,
) -> str:
    payload = {
        "task": "Revise the failed article draft with minimal edits to clear hard humanizer gate.",
        "requirements": [
            "Keep factual claims unchanged unless wording itself is unsupported.",
            "Keep structure and argument flow as much as possible; avoid full rewrite.",
            "Fix only violating spans related to gate reasons.",
            "Remove these patterns if present: 不是...而是..., 不仅...而且..., 首先/其次/最后模板, 宣传腔词, 模糊归因, emoji, 破折号堆叠, 粗体滥用.",
            "Also remove stale bridge phrases: 这个判断太轻了 / 官方说得很直接 / 最值得看 / 更容易看清 / 说透 / 很清楚.",
            "If style reasons exist, you must fix markdown layout: opening quote subtitle, subheadings, bullet list, bold key terms.",
            "Do not append metadata, notes, TODO, or explanations.",
            f"Output language: {output_language}.",
        ],
        "gate_reasons": gate_reasons,
        "failed_draft": {
            "title": str(failed_article.get("title", "")),
            "dek": str(failed_article.get("dek", "")),
            "body_markdown": str(failed_article.get("body_markdown", "")),
            "preserved_fact_anchors": failed_article.get("preserved_fact_anchors", []),
            "style_observations": failed_article.get("style_observations", []),
            "open_questions": failed_article.get("open_questions", []),
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def lane_micro_repair_user_prompt(
    *,
    failed_article: dict[str, Any],
    gate_reasons: list[str],
    output_language: str,
) -> str:
    payload = {
        "task": "Do a targeted micro-repair to clear hard pattern gate while preserving meaning.",
        "requirements": [
            "Patch only spans that trigger gate reasons; keep paragraph structure and facts unchanged.",
            "Do not add new claims, names, or numbers.",
            "Eliminate all template contrasts such as 不是...而是... and 不仅...而且....",
            "Do not use 首先/其次/最后 checklist wording.",
            "Eliminate stale bridge phrases: 这个判断太轻了 / 官方说得很直接 / 最值得看 / 更容易看清 / 说透 / 很清楚.",
            "If style reasons are present, patch markdown structure minimally to satisfy them (quote subtitle / subheading / list / bold).",
            "Do not append explanations, notes, or metadata.",
            f"Output language: {output_language}.",
        ],
        "gate_reasons": gate_reasons,
        "failed_draft": {
            "title": str(failed_article.get("title", "")),
            "dek": str(failed_article.get("dek", "")),
            "body_markdown": str(failed_article.get("body_markdown", "")),
            "preserved_fact_anchors": failed_article.get("preserved_fact_anchors", []),
            "style_observations": failed_article.get("style_observations", []),
            "open_questions": failed_article.get("open_questions", []),
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def read_framework_specs(specs_dir: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    specs: dict[str, tuple[Path, dict[str, Any]]] = {}
    for spec_path in sorted(specs_dir.glob("*/FRAMEWORK_SPEC.json")):
        spec = load_json(spec_path)
        framework_id = str(spec.get("metadata", {}).get("framework_id", "")).strip()
        if not framework_id:
            continue
        specs[framework_id] = (spec_path.resolve(), spec)
    return specs


def build_framework_context(
    *,
    framework_specs: dict[str, tuple[Path, dict[str, Any]]],
    framework_id: str,
    submode_id: str,
    source_item: dict[str, Any],
    capability_playbook: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    if framework_id not in framework_specs:
        raise KeyError(f"framework_id not found: {framework_id}")
    spec_path, spec = framework_specs[framework_id]
    submode = find_submode(spec, submode_id)
    style_profile = find_style_profile(spec, str(submode.get("style_profile_id", "")))
    sample_ref_map = build_sample_ref_map(spec)
    primary_sample_ids = [sample_id for sample_id in compact_list(submode.get("sample_ids", [])) if sample_id in sample_ref_map]
    sample_ids = list(primary_sample_ids)
    target_cap = 2
    if len(sample_ids) < target_cap:
        for row in spec.get("samples", {}).get("sample_refs", []):
            sid = str(row.get("sample_id", "")).strip()
            if not sid or sid in sample_ids:
                continue
            sample_ids.append(sid)
            if len(sample_ids) >= target_cap:
                break
    sample_ids = sample_ids[:target_cap]
    selected_sample_refs = [sample_ref_map[sample_id] for sample_id in sample_ids]
    style_profiles_packet = load_style_profiles_packet(spec, submode_id)
    sample_moves_layer_packet = load_sample_moves_layer_packet(spec_path, submode_id)

    payload: dict[str, Any] = {
        "selected_framework": {
            "framework_id": framework_id,
            "framework_label": spec.get("metadata", {}).get("framework_label", ""),
            "submode_id": submode_id,
        },
        "framework_spec_ref": str(spec_path),
        "framework_spec_slim": {
            "intent": spec.get("intent", {}),
            "structure": spec.get("structure", {}),
            "style": spec.get("style", {}),
            "execution_controls": spec.get("execution_controls", {}),
        },
        "style_profiles_packet": style_profiles_packet,
        "sample_moves_layer_packet": sample_moves_layer_packet,
        "sample_packet": {
            "selected_sample_refs": selected_sample_refs,
        },
    }
    return payload, str(spec_path)


def collect_writer_packet_paths(root: Path) -> list[Path]:
    if root.is_file() and root.name == "writer_packet.json":
        return [root.resolve()]
    if root.is_file() and root.name == "writer_packet_manifest.json":
        payload = load_json(root)
        out: list[Path] = []
        for row in payload.get("writer_packets", []):
            path = Path(str(row.get("writer_packet_json", ""))).expanduser().resolve()
            if path.exists():
                out.append(path)
        return out
    if root.is_dir():
        manifest = root / "writer_packet_manifest.json"
        if manifest.exists():
            return collect_writer_packet_paths(manifest)
        return sorted(path.resolve() for path in root.glob("**/writer_packet.json"))
    return []


def load_source_items_for_packet(packet: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    sources: dict[str, dict[str, Any]] = {}
    source_rows = [
        *(packet.get("source_bundle", {}).get("primary_sources", []) or []),
        *(packet.get("source_bundle", {}).get("supporting_sources", []) or []),
        *(packet.get("source_materials", []) or []),
    ]
    for row in source_rows:
        path_value = str(row.get("source_item_path", "")).strip()
        if not path_value:
            continue
        path = Path(path_value).expanduser().resolve()
        key = str(path)
        if key in sources:
            continue
        try:
            sources[key] = load_json(path)
        except Exception as exc:  # pragma: no cover - surfaced in manifest
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
    return sources, errors


def choose_primary_source_path(packet: dict[str, Any], loaded_sources: dict[str, dict[str, Any]]) -> Path | None:
    primary_rows = packet.get("source_bundle", {}).get("primary_sources", []) or []
    for row in primary_rows:
        path_value = str(row.get("source_item_path", "")).strip()
        if not path_value:
            continue
        path = Path(path_value).expanduser().resolve()
        if str(path) in loaded_sources:
            return path
    if loaded_sources:
        return Path(next(iter(loaded_sources.keys()))).expanduser().resolve()
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--writer-packet-root", required=True, help="Path to writer_packet manifest/root/file")
    parser.add_argument("--out-root", required=True, help="Directory where article draft artifacts will be written")
    parser.add_argument(
        "--framework-specs-dir",
        default="framework",
        help="Path to framework spec root containing */FRAMEWORK_SPEC.json",
    )
    parser.add_argument(
        "--lane-contract",
        default="lane_v2/docs/lane_pilot/T01_single_lane_contract_v1.md",
        help="Optional lane contract markdown used as additional instruction context",
    )
    parser.add_argument(
        "--article-draft-schema",
        default="lane_v2/configs/ARTICLE_DRAFT_SCHEMA.json",
        help="Path to ARTICLE_DRAFT_SCHEMA.json for validation",
    )
    parser.add_argument(
        "--capability-playbook",
        default="lane_v2/configs/ARTICLE_CAPABILITY_PLAYBOOK.json",
        help="Optional capability playbook JSON",
    )
    parser.add_argument(
        "--humanizer-packet",
        default="lane_v2/configs/HUMANIZER_ZH_PACKET.json",
        help="Optional anti-AI packet",
    )
    parser.add_argument(
        "--t01-signal-boost",
        default="lane_v2/configs/T01_SIGNAL_BOOST_FROM_DOTEY.json",
        help="Optional T01 hook/escalation boost config",
    )
    parser.add_argument(
        "--self-improving-observe-script",
        default="/home/lyric/.codex/skills/writing-style-skill/scripts/observe.py",
        help="Path to self-improving observe.py",
    )
    parser.add_argument(
        "--self-improving-skill-dir",
        default="/home/lyric/.codex/skills/writing-style-skill",
        help="Self-improving skill directory path",
    )
    parser.add_argument(
        "--self-improving-log-dir",
        default="lane_v2/runs/self_improving_logs",
        help="Optional explicit log dir for self-improving observe",
    )
    parser.add_argument(
        "--enable-self-improving-observe",
        dest="enable_self_improving_observe",
        action="store_true",
        default=True,
        help="Record generated original drafts into self-improving observation log",
    )
    parser.add_argument(
        "--no-self-improving-observe",
        dest="enable_self_improving_observe",
        action="store_false",
    )
    parser.add_argument("--backend", choices=["auto", "anthropic", "openai_compatible", "codex_cli"], default="auto")
    parser.add_argument("--writer-model", default="claude-sonnet-4-6", help="Model for article generation (heavy task)")
    parser.add_argument("--light-model", default="claude-haiku-4-5-20251001", help="Model for pain point extraction and other light tasks")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable containing API key")
    parser.add_argument("--codex-binary", default="codex", help="Codex CLI binary name or absolute path")
    parser.add_argument("--codex-working-dir", default="/tmp", help="Working directory used by codex exec backend")
    parser.add_argument("--codex-reasoning-effort", default="medium", help="Codex reasoning effort override")
    parser.add_argument("--timeout-s", type=int, default=240, help="Backend timeout in seconds")
    parser.add_argument("--output-language", default="zh-CN", help="Output language tag or label")
    parser.add_argument("--limit", type=int, default=0, help="Optional max packets to generate")
    parser.add_argument("--humanizer-hard-gate", dest="humanizer_hard_gate", action="store_true", default=True)
    parser.add_argument("--no-humanizer-hard-gate", dest="humanizer_hard_gate", action="store_false")
    parser.add_argument(
        "--humanizer-rewrite-on-fail",
        dest="humanizer_rewrite_on_fail",
        action="store_true",
        default=True,
        help="On gate failure, use an LLM repair pass (minimal-edit revision, not full rewrite)",
    )
    parser.add_argument("--no-humanizer-rewrite-on-fail", dest="humanizer_rewrite_on_fail", action="store_false")
    parser.add_argument(
        "--include-human-review-required",
        action="store_true",
        help="Also generate drafts for packets flagged as requires_human_review",
    )
    parser.add_argument(
        "--include-not-ready",
        action="store_true",
        help="Also generate drafts for packets with source_bundle.ready_for_writer=false",
    )
    args = parser.parse_args()

    writer_packet_root = Path(args.writer_packet_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    self_improving_log_dir = (
        str(Path(args.self_improving_log_dir).expanduser().resolve()) if str(args.self_improving_log_dir).strip() else ""
    )

    schema = load_schema(Path(args.article_draft_schema).expanduser().resolve() if args.article_draft_schema else None)
    capability_playbook = load_optional_json(Path(args.capability_playbook).expanduser().resolve() if args.capability_playbook else None)
    humanizer_packet = load_optional_json(Path(args.humanizer_packet).expanduser().resolve() if args.humanizer_packet else None)
    t01_signal_boost = load_optional_json(Path(args.t01_signal_boost).expanduser().resolve() if args.t01_signal_boost else None)
    observe_script = Path(args.self_improving_observe_script).expanduser().resolve()
    self_improving_skill_dir = Path(args.self_improving_skill_dir).expanduser().resolve()
    lane_contract_path = Path(args.lane_contract).expanduser().resolve() if args.lane_contract else None
    lane_contract_excerpt = lane_contract_path.read_text(encoding="utf-8") if lane_contract_path and lane_contract_path.exists() else ""
    framework_specs = read_framework_specs(Path(args.framework_specs_dir).expanduser().resolve())
    if not framework_specs:
        raise RuntimeError("No framework specs found. Check --framework-specs-dir.")

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
        raise RuntimeError("bootstrap backend is not supported for lane writing")
    writer_model = args.writer_model or ("gpt-5.4" if backend_name == "codex_cli" else "")

    packet_paths = collect_writer_packet_paths(writer_packet_root)
    if args.limit and args.limit > 0:
        packet_paths = packet_paths[: args.limit]
    if not packet_paths:
        raise RuntimeError(f"No writer_packet.json found under {writer_packet_root}")

    results: list[dict[str, Any]] = []
    for packet_path in packet_paths:
        packet = load_json(packet_path)
        topic_id = str(packet.get("topic_id", packet_path.parent.name))
        lane_assignment = packet.get("lane_assignment", {})
        source_bundle = packet.get("source_bundle", {})
        requires_human_review = bool(lane_assignment.get("requires_human_review", False))
        ready_for_writer = bool(source_bundle.get("ready_for_writer", False))

        if requires_human_review and not args.include_human_review_required:
            row = {
                "topic_id": topic_id,
                "status": "skipped_human_review_required",
                "output_json": "",
                "output_md": "",
                "validation_error": None,
            }
            results.append(row)
            print(f"{topic_id} -> skipped_human_review_required")
            continue

        if not ready_for_writer and not args.include_not_ready:
            row = {
                "topic_id": topic_id,
                "status": "skipped_not_ready_for_writer",
                "output_json": "",
                "output_md": "",
                "validation_error": None,
            }
            results.append(row)
            print(f"{topic_id} -> skipped_not_ready_for_writer")
            continue

        loaded_sources, source_load_errors = load_source_items_for_packet(packet)
        primary_source_path = choose_primary_source_path(packet, loaded_sources)
        if primary_source_path is None:
            row = {
                "topic_id": topic_id,
                "status": "error_missing_primary_source",
                "output_json": "",
                "output_md": "",
                "validation_error": "; ".join(source_load_errors[:3]) if source_load_errors else "primary source missing",
            }
            results.append(row)
            print(f"{topic_id} -> error_missing_primary_source")
            continue
        primary_source_item = loaded_sources[str(primary_source_path)]

        framework_id = str(lane_assignment.get("framework_id", packet.get("framework_id", ""))).strip()
        submode_id = str(lane_assignment.get("submode_id", packet.get("submode_id", ""))).strip()
        if not framework_id or not submode_id:
            row = {
                "topic_id": topic_id,
                "status": "error_missing_framework_binding",
                "output_json": "",
                "output_md": "",
                "validation_error": "missing framework_id/submode_id in writer packet",
            }
            results.append(row)
            print(f"{topic_id} -> error_missing_framework_binding")
            continue

        try:
            framework_context, framework_spec_ref = build_framework_context(
                framework_specs=framework_specs,
                framework_id=framework_id,
                submode_id=submode_id,
                source_item=primary_source_item,
                capability_playbook=capability_playbook,
            )
        except Exception as exc:
            row = {
                "topic_id": topic_id,
                "status": "error_framework_context",
                "output_json": "",
                "output_md": "",
                "validation_error": f"{type(exc).__name__}: {exc}",
            }
            results.append(row)
            print(f"{topic_id} -> error_framework_context")
            continue

        source_materials_packet: list[dict[str, Any]] = []
        primary_paths = {
            str(Path(str(row.get("source_item_path", ""))).expanduser().resolve())
            for row in source_bundle.get("primary_sources", [])
            if str(row.get("source_item_path", "")).strip()
        }
        source_family_map: dict[str, str] = {}
        for row in packet.get("source_materials", []) or []:
            row_path = Path(str(row.get("source_item_path", ""))).expanduser().resolve()
            source_family_map[str(row_path)] = str(row.get("source_family", "unknown"))
        for path_text, source_item in loaded_sources.items():
            source_family = source_family_map.get(path_text, "unknown")
            source_role = "primary" if path_text in primary_paths else "supporting"
            source_materials_packet.append(
                build_source_material_packet(source_item, source_family, source_role=source_role)
            )
        source_materials_packet = source_materials_packet[:4]
        primary_source_packet = build_primary_source_packet(primary_source_item)
        source_bundle_packet = build_source_bundle_packet(source_bundle)
        article_quality_contract = build_article_quality_contract(
            framework_context=framework_context,
            primary_source_packet=primary_source_packet,
            humanizer_packet=humanizer_packet,
            lane_assignment=lane_assignment,
            t01_signal_boost=t01_signal_boost,
        )

        # --- Source enrichment (fetch GitHub metadata etc.) ---
        source_enrichment = enrich_source_materials(primary_source_item, source_materials_packet)

        # --- Pain point extraction (lightweight pre-writer LLM call, uses light model) ---
        light_model = args.light_model or writer_model
        reader_pain = extract_reader_pain_point(
            backend=backend,
            model=light_model,
            topic_statement=trim_text(topic_card.get("topic_statement", ""), 300),
            primary_source_excerpt=trim_text(
                primary_source_item.get("content", {}).get("full_text", ""), 1200
            ),
            output_language=args.output_language,
        )

        base_user_prompt = lane_writer_user_prompt(
            packet=packet,
            primary_source_packet=primary_source_packet,
            source_bundle_packet=source_bundle_packet,
            source_materials_packet=source_materials_packet,
            framework_context=framework_context,
            lane_contract_excerpt=lane_contract_excerpt,
            output_language=args.output_language,
            humanizer_packet=humanizer_packet,
            article_quality_contract=article_quality_contract,
            reader_pain_point=reader_pain,
            source_enrichment=source_enrichment,
        )
        prompt_metrics = {
            "user_prompt_total_chars": len(base_user_prompt),
            "framework_spec_full_json_chars": len(
                json.dumps(framework_context.get("framework_spec_full", {}), ensure_ascii=False, separators=(",", ":"))
            ),
            "topic_card_chars": len(json.dumps(packet.get("topic_card", {}), ensure_ascii=False, separators=(",", ":"))),
            "primary_source_packet_chars": len(json.dumps(primary_source_packet, ensure_ascii=False, separators=(",", ":"))),
            "source_bundle_packet_chars": len(json.dumps(source_bundle_packet, ensure_ascii=False, separators=(",", ":"))),
            "source_materials_packet_chars": len(
                json.dumps(source_materials_packet, ensure_ascii=False, separators=(",", ":"))
            ),
            "style_profiles_packet_chars": len(
                json.dumps(framework_context.get("style_profiles_packet", {}), ensure_ascii=False, separators=(",", ":"))
            ),
            "sample_moves_layer_packet_chars": len(
                json.dumps(framework_context.get("sample_moves_layer_packet", {}), ensure_ascii=False, separators=(",", ":"))
            ),
            "article_quality_contract_chars": len(
                json.dumps(article_quality_contract, ensure_ascii=False, separators=(",", ":"))
            ),
            "t01_signal_boost_applied": bool(article_quality_contract.get("t01_signal_boost_ref")),
            "selected_sample_refs_count": len(
                framework_context.get("sample_packet", {}).get("selected_sample_refs", [])
            ),
        }
        raw = backend.complete_json(
            model=writer_model,
            system_prompt=lane_writer_system_prompt(args.output_language),
            user_prompt=base_user_prompt,
            output_schema=generation_response_schema(),
        )
        article = normalize_generation(raw, primary_source_item)
        smell_report = ai_smell_report(title=article["title"], dek=article["dek"], body_markdown=article["body_markdown"])
        humanizer_passed, humanizer_reasons = humanizer_gate(smell_report) if args.humanizer_hard_gate else (True, [])
        structure_passed, structure_reasons, structure_report = structure_gate(
            body_markdown=article["body_markdown"],
            primary_source_packet=primary_source_packet,
            quality_contract=article_quality_contract,
        )
        markdown_style_report = markdown_format_report(
            title=article["title"],
            body_markdown=article["body_markdown"],
        )
        markdown_style_passed, markdown_style_reasons = markdown_format_gate(markdown_style_report)
        gate_reasons = compact_list([*humanizer_reasons, *structure_reasons, *markdown_style_reasons])
        hard_gate_passed = bool(humanizer_passed and structure_passed and markdown_style_passed)
        rewrote_for_gate = False

        # LLM repair pass on any hard gate failure (minimal-edit revision).
        if args.humanizer_hard_gate and not hard_gate_passed and args.humanizer_rewrite_on_fail:
            rewrote_for_gate = True
            max_repair_rounds = 3
            for _ in range(max_repair_rounds):
                repair_user_prompt = lane_repair_user_prompt(
                    failed_article=article,
                    gate_reasons=gate_reasons,
                    output_language=args.output_language,
                )
                raw = backend.complete_json(
                    model=writer_model,
                    system_prompt=lane_writer_system_prompt(args.output_language),
                    user_prompt=repair_user_prompt,
                    output_schema=generation_response_schema(),
                )
                article = normalize_generation(raw, primary_source_item)
                smell_report = ai_smell_report(title=article["title"], dek=article["dek"], body_markdown=article["body_markdown"])
                humanizer_passed, humanizer_reasons = humanizer_gate(smell_report)
                structure_passed, structure_reasons, structure_report = structure_gate(
                    body_markdown=article["body_markdown"],
                    primary_source_packet=primary_source_packet,
                    quality_contract=article_quality_contract,
                )
                markdown_style_report = markdown_format_report(
                    title=article["title"],
                    body_markdown=article["body_markdown"],
                )
                markdown_style_passed, markdown_style_reasons = markdown_format_gate(markdown_style_report)
                gate_reasons = compact_list([*humanizer_reasons, *structure_reasons, *markdown_style_reasons])
                hard_gate_passed = bool(humanizer_passed and structure_passed and markdown_style_passed)
                if hard_gate_passed:
                    break
            # Fallback micro-repair rounds for residual hard-pattern failures.
            if not hard_gate_passed:
                for _ in range(2):
                    micro_prompt = lane_micro_repair_user_prompt(
                        failed_article=article,
                        gate_reasons=gate_reasons,
                        output_language=args.output_language,
                    )
                    raw = backend.complete_json(
                        model=writer_model,
                        system_prompt=lane_writer_system_prompt(args.output_language),
                        user_prompt=micro_prompt,
                        output_schema=generation_response_schema(),
                    )
                    article = normalize_generation(raw, primary_source_item)
                    smell_report = ai_smell_report(title=article["title"], dek=article["dek"], body_markdown=article["body_markdown"])
                    humanizer_passed, humanizer_reasons = humanizer_gate(smell_report)
                    structure_passed, structure_reasons, structure_report = structure_gate(
                        body_markdown=article["body_markdown"],
                        primary_source_packet=primary_source_packet,
                        quality_contract=article_quality_contract,
                    )
                    markdown_style_report = markdown_format_report(
                        title=article["title"],
                        body_markdown=article["body_markdown"],
                    )
                    markdown_style_passed, markdown_style_reasons = markdown_format_gate(markdown_style_report)
                    gate_reasons = compact_list([*humanizer_reasons, *structure_reasons, *markdown_style_reasons])
                    hard_gate_passed = bool(humanizer_passed and structure_passed and markdown_style_passed)
                    if hard_gate_passed:
                        break

        target_dir = out_root / topic_id
        target_dir.mkdir(parents=True, exist_ok=True)
        if args.humanizer_hard_gate and not hard_gate_passed:
            rejected_json = target_dir / "rejected_humanizer.json"
            rejected_md = target_dir / "rejected_humanizer.md"
            dump_json(
                rejected_json,
                {
                    "topic_id": topic_id,
                    "framework_id": framework_id,
                    "submode_id": submode_id,
                    "smell_report": smell_report,
                    "structure_report": structure_report,
                    "markdown_style_report": markdown_style_report,
                    "gate_reasons": gate_reasons,
                    "rewrote_for_gate": rewrote_for_gate,
                    "draft": article,
                },
            )
            rejected_md.write_text(render_markdown({**article}), encoding="utf-8")
            row = {
                "topic_id": topic_id,
                "status": "blocked_humanizer_gate",
                "framework_id": framework_id,
                "submode_id": submode_id,
                "framework_spec_ref": framework_spec_ref,
                "output_json": "",
                "output_md": "",
                "validation_error": "; ".join(gate_reasons),
                "source_load_errors": source_load_errors[:3],
                "humanizer_smell_report": smell_report,
                "structure_report": structure_report,
                "markdown_style_report": markdown_style_report,
                "prompt_metrics": prompt_metrics,
            }
            results.append(row)
            print(f"{topic_id} -> blocked_humanizer_gate")
            continue

        payload = {
            "schema_version": SCHEMA_VERSION,
            "source_ref": str(primary_source_path),
            "framework_match_ref": f"{packet_path}#lane_assignment",
            "rewrite_context_ref": f"{packet_path}#writer_packet",
            "model": writer_model or "codex-default",
            "generated_at": isoformat_z(utc_now()),
            "output_language": args.output_language,
            "framework_id": framework_id,
            "submode_id": submode_id,
            "requires_human_review": requires_human_review,
            **article,
        }
        validation_error = validate_payload(payload, schema)

        out_json = target_dir / "article_draft.json"
        out_md = target_dir / "article_draft.md"
        dump_json(out_json, payload)
        out_md.write_text(render_markdown(payload), encoding="utf-8")
        self_improving_observe = {"status": "skipped_disabled"}
        if args.enable_self_improving_observe:
            self_improving_observe = observe_self_improving_original(
                observe_script=observe_script,
                skill_dir=self_improving_skill_dir,
                article_md=out_md,
                lane_id=str(lane_assignment.get("selected_lane_id", packet.get("lane_id", ""))),
                log_dir=self_improving_log_dir,
            )

        row = {
            "topic_id": topic_id,
            "status": "ok" if validation_error is None else "schema_error",
            "framework_id": framework_id,
            "submode_id": submode_id,
            "framework_spec_ref": framework_spec_ref,
            "output_json": str(out_json),
            "output_md": str(out_md),
            "validation_error": validation_error,
            "source_load_errors": source_load_errors[:3],
            "rewrote_for_humanizer_gate": rewrote_for_gate,
            "humanizer_smell_report": smell_report,
            "structure_report": structure_report,
            "markdown_style_report": markdown_style_report,
            "prompt_metrics": prompt_metrics,
            "self_improving_observe": self_improving_observe,
        }
        results.append(row)
        print(f"{topic_id} -> {row['status']}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "backend": backend_name,
        "writer_packet_root": str(writer_packet_root),
        "out_root": str(out_root),
        "output_language": args.output_language,
        "count": len(results),
        "ok_count": sum(1 for row in results if row["status"] == "ok"),
        "schema_error_count": sum(1 for row in results if row["status"] == "schema_error"),
        "blocked_humanizer_gate_count": sum(1 for row in results if row["status"] == "blocked_humanizer_gate"),
        "skipped_human_review_count": sum(1 for row in results if row["status"] == "skipped_human_review_required"),
        "skipped_not_ready_count": sum(1 for row in results if row["status"] == "skipped_not_ready_for_writer"),
        "self_improving_observe_ok_count": sum(
            1 for row in results if (row.get("self_improving_observe") or {}).get("status") == "ok"
        ),
        "self_improving_observe_error_count": sum(
            1 for row in results if (row.get("self_improving_observe") or {}).get("status") == "error"
        ),
        "results": results,
    }
    manifest_path = out_root / "article_draft_manifest.json"
    dump_json(manifest_path, manifest)
    print(manifest_path)
    print(
        "ok="
        f"{manifest['ok_count']} schema_errors={manifest['schema_error_count']} "
        f"blocked_humanizer_gate={manifest['blocked_humanizer_gate_count']} "
        f"skipped_human_review={manifest['skipped_human_review_count']} "
        f"skipped_not_ready={manifest['skipped_not_ready_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
