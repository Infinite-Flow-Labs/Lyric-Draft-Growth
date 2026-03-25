from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content.pipeline.write.article_formatter import build_article_blocks, build_publishing_hints

DEFAULT_TEMPLATE_PATH = ROOT / "content/pipeline/configs/ARTICLE_IMAGE_BRIEF.template.json"
DEFAULT_STYLE_BRIDGE_PATH = ROOT / "content/pipeline/configs/ARTICLE_IMAGE_STYLE_BRIDGE.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def trim_sentence(value: str, max_len: int) -> str:
    text = clean_text(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def trim_hard(value: str, max_len: int) -> str:
    text = clean_text(value)
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip(" ，。；：,.!?！？…")


def merge_text(base: str, extra: str) -> str:
    base_clean = clean_text(base)
    extra_clean = clean_text(extra)
    if not extra_clean:
        return base_clean
    if not base_clean:
        return extra_clean
    if extra_clean in base_clean:
        return base_clean
    return f"{base_clean}; {extra_clean}"


def merge_prompt_seed(existing: str, additions: list[str], *, max_len: int = 560) -> str:
    parts = [clean_text(existing)] if clean_text(existing) else []
    parts.extend(clean_text(item) for item in additions if clean_text(item))
    merged = " ".join(dedupe(parts))
    return trim_sentence(merged, max_len)


def article_slug(article_path: Path, article_payload: dict[str, Any]) -> str:
    source_ref = clean_text(article_payload.get("source_ref"))
    if source_ref:
        return Path(source_ref).parent.name
    return article_path.parent.name


def get_source_item(article_payload: dict[str, Any]) -> dict[str, Any]:
    source_ref = clean_text(article_payload.get("source_ref"))
    if not source_ref:
        return {}
    path = Path(source_ref)
    if not path.exists():
        return {}
    return load_json(path)


def get_publishing_hints(article_payload: dict[str, Any], source_item: dict[str, Any]) -> dict[str, Any]:
    raw_hints = article_payload.get("publishing_hints") or {}
    if source_item:
        return build_publishing_hints(source_item, raw_hints)
    return {
        key: clean_text(value)
        for key, value in raw_hints.items()
        if clean_text(value)
    }


def get_article_blocks(article_payload: dict[str, Any], publishing_hints: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = article_payload.get("article_blocks") or []
    if blocks:
        return blocks
    return build_article_blocks(
        title=article_payload.get("title", ""),
        dek=article_payload.get("dek", ""),
        body_markdown=article_payload.get("body_markdown", ""),
        publishing_hints=publishing_hints,
    )


def split_sections(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current = {
        "section_ref": "framing",
        "heading": "",
        "blocks": [],
    }

    for block in blocks:
        block_type = clean_text(block.get("type"))
        if block_type == "section_heading":
            if current["blocks"] or current["heading"]:
                sections.append(current)
            current = {
                "section_ref": f"section_{len(sections) + 1:02d}",
                "heading": clean_text(block.get("text")),
                "blocks": [block],
            }
            continue
        if block_type in {"link_cta", "closing_slogan", "source_embed"}:
            continue
        current["blocks"].append(block)

    if current["blocks"] or current["heading"]:
        sections.append(current)
    # If writer did not emit explicit subheadings, fallback to grouped pseudo-sections
    # so inline image planning still has enough insertion points.
    if len(sections) <= 1:
        grouped = split_sections_without_headings(blocks)
        if grouped:
            return grouped
    return sections


def split_sections_without_headings(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content_blocks = [
        block
        for block in blocks
        if clean_text(block.get("type")) not in {"hero_heading", "link_cta", "closing_slogan", "source_embed"}
    ]
    if len(content_blocks) <= 3:
        return []

    group_size = 3
    grouped_sections: list[dict[str, Any]] = []
    for index in range(0, len(content_blocks), group_size):
        chunk = content_blocks[index : index + group_size]
        if not chunk:
            continue
        heading = ""
        for block in chunk:
            if clean_text(block.get("type")) in {"section_heading", "paragraph", "quote"} and clean_text(block.get("text")):
                heading = trim_sentence(clean_text(block.get("text")), 20)
                break
        grouped_sections.append(
            {
                "section_ref": f"section_{len(grouped_sections) + 1:02d}",
                "heading": heading,
                "blocks": chunk,
            }
        )
    return grouped_sections


def collect_section_text(section: dict[str, Any]) -> str:
    parts: list[str] = []
    if clean_text(section.get("heading")):
        parts.append(clean_text(section["heading"]))
    for block in section.get("blocks", []):
        block_type = clean_text(block.get("type"))
        if block_type in {"hero_heading", "section_heading"}:
            continue
        if block_type == "bullet_list":
            if clean_text(block.get("text")):
                parts.append(clean_text(block["text"]))
            parts.extend(clean_text(item) for item in block.get("items", []) if clean_text(item))
            continue
        text = clean_text(block.get("text"))
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def contains_any(text: str, patterns: list[str]) -> bool:
    haystack = clean_text(text)
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in patterns)


def extract_contrast_pair(text: str) -> tuple[str, str]:
    cleaned = clean_text(text)
    match = re.search(r"不是(.+?)，?而是(.+)", cleaned)
    if not match:
        return "", ""
    before = clean_text(match.group(1))
    after = clean_text(match.group(2))
    return before, after


def tighten_phrase(text: str, max_len: int) -> str:
    value = clean_text(text)
    replacements = [
        "真正值得盯的不是",
        "这次真正值得看的，不是",
        "真正值得看的，不是",
        "真正值得注意的，不是",
        "最关键的变化，不是",
        "这次最关键的变化，不是",
        "很多人第一次听到",
        "很多人还在把",
        "如果你还在把",
        "有人开始",
        "开始",
        "认真",
        "这次",
        "而是",
        "不是",
        "“",
        "”",
        "\"",
    ]
    for target in replacements:
        value = value.replace(target, " ")
    value = re.sub(r"\s+", " ", value).strip(" ，。；：")
    if not value:
        value = clean_text(text)
    return trim_sentence(value, max_len)


def compress_hook_target(text: str, max_len: int) -> str:
    value = clean_text(text)
    replacements = [
        "真正值得盯的不是",
        "这次真正值得看的，不是",
        "真正值得看的，不是",
        "真正值得注意的，不是",
        "最关键的变化，不是",
        "这次最关键的变化，不是",
        "不是",
        "而是",
        "开始",
        "认真",
        "有人",
        "这次",
        "“",
        "”",
        "\"",
    ]
    for target in replacements:
        value = value.replace(target, " ")
    value = re.sub(r"\s+", " ", value).strip(" ，。；：,.!?！？…")
    value = value.replace("推理时代", "推理").replace("模型账本", "账本").replace("模型架构", "架构")
    if not value:
        value = clean_text(text)
    return trim_hard(value, max_len)


VALID_DIAGRAM_TYPES = [
    "quadrant_map", "stage_evolution", "workflow_map", "comparison_board",
    "file_artifact_map", "system_stack", "timeline", "example_breakdown",
    "section_reset_diagram",
]
VALID_IMAGE_GRAMMARS = [
    "hook_cover", "skip_board", "example_comparison", "concept_cluster",
    "framework_map", "workflow_map", "evolution_map", "decision_board",
    "section_reset",
]

# LLM-based image type selector (used when backend is available)
_image_type_backend: Any = None
_image_type_model: str = ""


def configure_image_type_backend(backend: Any, model: str) -> None:
    global _image_type_backend, _image_type_model
    _image_type_backend = backend
    _image_type_model = model


def _llm_choose_image_types(text: str, heading: str, *, is_cover: bool = False) -> tuple[str, str]:
    """Use LLM to pick diagram_type and image_grammar based on content semantics."""
    if not _image_type_backend or not _image_type_model:
        return "", ""
    prompt = json.dumps({
        "task": "Choose the best diagram_type and image_grammar for an article image.",
        "is_cover": is_cover,
        "heading": clean_text(heading)[:80],
        "text_excerpt": clean_text(text)[:400],
        "diagram_type_options": VALID_DIAGRAM_TYPES,
        "image_grammar_options": VALID_IMAGE_GRAMMARS,
        "rules": [
            "For cover images, image_grammar should usually be hook_cover.",
            "Match the visual type to the content's logical structure, not just keywords.",
            "comparison_board / example_comparison: when content compares before/after or two options.",
            "workflow_map: when content describes a process or steps.",
            "decision_board / skip_board: when content helps reader decide yes/no or filter options.",
            "evolution_map / stage_evolution: when content shows change over time.",
            "section_reset: default when content is a single concept or judgment.",
        ],
    }, ensure_ascii=False, separators=(",", ":"))
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["diagram_type", "image_grammar"],
        "properties": {
            "diagram_type": {"type": "string", "enum": VALID_DIAGRAM_TYPES},
            "image_grammar": {"type": "string", "enum": VALID_IMAGE_GRAMMARS},
        },
    }
    try:
        from route_framework_matches import preview_text  # noqa: reuse utility
    except ImportError:
        pass
    try:
        result = _image_type_backend.complete_json(
            model=_image_type_model,
            system_prompt="You select visual diagram types for article images. Return JSON only.",
            user_prompt=prompt,
            output_schema=schema,
        )
        return str(result.get("diagram_type", "")), str(result.get("image_grammar", ""))
    except Exception:
        return "", ""


def choose_diagram_type(text: str, heading: str = "", *, is_cover: bool = False) -> str:
    # Try LLM first
    llm_diagram, _ = _llm_choose_image_types(text, heading, is_cover=is_cover)
    if llm_diagram and llm_diagram in VALID_DIAGRAM_TYPES:
        return llm_diagram

    # Fallback: regex matching
    haystack = f"{clean_text(heading)}\n{clean_text(text)}"
    checks = [
        ("quadrant_map", [r"四象限", r"象限"]),
        ("stage_evolution", [r"阶段", r"升级", r"演进", r"迭代", r"重构", r"三次", r"四次"]),
        ("workflow_map", [r"工作流", r"流程", r"步骤", r"并行", r"分块", r"agent"]),
        ("comparison_board", [r"区别", r"不同", r"对比", r"不是.*而是", r"误解", r"改写"]),
        ("file_artifact_map", [r"文件", r"目录", r"analysis", r"prompt", r"draft", r"revision"]),
        ("system_stack", [r"架构", r"系统", r"模块", r"上下文", r"skill", r"能力"]),
        ("timeline", [r"过去", r"后来", r"现在", r"回头看"]),
        ("example_breakdown", [r"案例", r"例子", r"原文", r"翻译成了", r"期望"]),
    ]
    for label, patterns in checks:
        if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in patterns):
            return label
    if is_cover:
        return "workflow_map"
    return "section_reset_diagram"


def choose_image_grammar(text: str, heading: str = "", *, is_cover: bool = False) -> str:
    # Try LLM first
    _, llm_grammar = _llm_choose_image_types(text, heading, is_cover=is_cover)
    if llm_grammar and llm_grammar in VALID_IMAGE_GRAMMARS:
        return llm_grammar

    # Fallback: regex matching
    haystack = f"{clean_text(heading)}\n{clean_text(text)}"
    if is_cover:
        return "hook_cover"
    if contains_any(haystack, [r"直接跳过", r"跳过", r"噪音区", r"没必要", r"别投入", r"淘汰"]):
        return "skip_board"
    if contains_any(haystack, [r"比如", r"例子", r"时代", r"几个月后", r"以前", r"后来", r"对比", r"不是.*而是"]):
        return "example_comparison"
    if contains_any(haystack, [r"地图感", r"知道就好", r"RAG", r"思维链", r"多模态", r"幻觉"]):
        return "concept_cluster"
    if contains_any(haystack, [r"四象限", r"象限", r"两根轴", r"策略"]):
        return "framework_map"
    if contains_any(haystack, [r"工作流", r"流程", r"步骤", r"并行", r"分块", r"Agent", r"agent"]):
        return "workflow_map"
    if contains_any(haystack, [r"阶段", r"升级", r"演进", r"迭代", r"重构", r"战场", r"瓶颈"]):
        return "evolution_map"
    if contains_any(haystack, [r"判断", r"值得", r"应该", r"策略", r"原则"]):
        return "decision_board"
    return "section_reset"


def diagram_scene_elements(diagram_type: str) -> list[str]:
    mapping = {
        "quadrant_map": ["quadrant grid", "4 labeled zones", "small icons", "directional emphasis"],
        "stage_evolution": ["3-4 stage panels", "left-to-right arrows", "evolution markers"],
        "workflow_map": ["pipeline blocks", "arrows", "input/output artifacts", "step modules"],
        "comparison_board": ["side-by-side columns", "contrast labels", "highlight markers"],
        "system_stack": ["layered modules", "stacked blocks", "connections", "system labels"],
        "timeline": ["timeline path", "milestones", "transition arrows"],
        "file_artifact_map": ["files and folders", "step numbers", "artifact labels", "handoff arrows"],
        "example_breakdown": ["example card", "annotated callouts", "before/after comparison"],
        "section_reset_diagram": ["one central concept", "2-3 support labels", "one relationship arrow"],
    }
    return mapping.get(diagram_type, ["one main concept diagram", "short labels", "clean arrows"])


def diagram_relationships(diagram_type: str) -> list[str]:
    mapping = {
        "quadrant_map": ["show how the framework splits into 4 decision zones"],
        "stage_evolution": ["show progression across stages", "make the shift in logic visually obvious"],
        "workflow_map": ["show sequence and handoff", "make the operating logic obvious at a glance"],
        "comparison_board": ["surface the key difference immediately", "show old frame vs new frame"],
        "system_stack": ["show layers and dependencies", "make module roles obvious"],
        "timeline": ["show movement across time", "highlight the direction of change"],
        "file_artifact_map": ["show which artifacts are created and reused", "show where persistence matters"],
        "example_breakdown": ["show the example and why it matters", "make the correction visible"],
        "section_reset_diagram": ["reset attention around one concept", "show the new mental model quickly"],
    }
    return mapping.get(diagram_type, ["show one concept clearly"])


def grammar_scene_elements(image_grammar: str) -> list[str]:
    mapping = {
        "hook_cover": ["one dominant visual idea", "2-4 large visual nodes max", "clear title area", "one obvious structure"],
        "framework_map": ["framework grid or branches", "4 zones max", "clean labels", "one system view"],
        "concept_cluster": ["one center node", "3-5 surrounding concepts", "radial links", "short concept labels"],
        "example_comparison": ["left card vs right card", "center arrow", "one bottom takeaway", "few text blocks"],
        "skip_board": ["4-6 rejection cards", "one strong top verdict", "crossed-out or muted examples"],
        "decision_board": ["3-4 decision cards", "priority contrast", "one short rule takeaway"],
        "workflow_map": ["3-4 step modules", "arrows", "artifact or action icons"],
        "evolution_map": ["3 stage panels max", "left-to-right progression", "transition arrow"],
        "section_reset": ["one focused concept", "one headline", "2-3 support labels max"],
    }
    return mapping.get(image_grammar, ["one main concept", "short labels", "clear structure"])


def grammar_relationships(image_grammar: str) -> list[str]:
    mapping = {
        "hook_cover": ["present one question and one promise", "make the article worth clicking in one glance"],
        "framework_map": ["show the full framework at a glance", "make category boundaries obvious"],
        "concept_cluster": ["show where the reader should place concepts", "build mental map rather than explain paragraphs"],
        "example_comparison": ["make the before/after or old/new contrast obvious", "show why one example proves the point"],
        "skip_board": ["make exclusion easy", "support fast scanning and strong judgment"],
        "decision_board": ["show how to decide quickly", "make priority ordering obvious"],
        "workflow_map": ["show how the system operates", "make stage handoff obvious"],
        "evolution_map": ["show how logic shifts over time", "make the transition visible"],
        "section_reset": ["reset attention with one new idea", "keep one concept visually dominant"],
    }
    return mapping.get(image_grammar, ["show one concept clearly"])


def grammar_text_budget(image_grammar: str) -> dict[str, int]:
    mapping = {
        "hook_cover": {"max_text_blocks": 2, "headline_max_chars": 16, "subheadline_max_chars": 16, "label_max_chars": 8, "max_labels": 4},
        "framework_map": {"max_text_blocks": 3, "headline_max_chars": 14, "subheadline_max_chars": 12, "label_max_chars": 6, "max_labels": 6},
        "concept_cluster": {"max_text_blocks": 2, "headline_max_chars": 14, "subheadline_max_chars": 10, "label_max_chars": 8, "max_labels": 5},
        "example_comparison": {"max_text_blocks": 4, "headline_max_chars": 12, "subheadline_max_chars": 10, "label_max_chars": 8, "max_labels": 6},
        "skip_board": {"max_text_blocks": 2, "headline_max_chars": 8, "subheadline_max_chars": 14, "label_max_chars": 6, "max_labels": 6},
        "decision_board": {"max_text_blocks": 3, "headline_max_chars": 12, "subheadline_max_chars": 12, "label_max_chars": 8, "max_labels": 5},
        "workflow_map": {"max_text_blocks": 3, "headline_max_chars": 12, "subheadline_max_chars": 12, "label_max_chars": 8, "max_labels": 4},
        "evolution_map": {"max_text_blocks": 3, "headline_max_chars": 12, "subheadline_max_chars": 12, "label_max_chars": 8, "max_labels": 4},
        "section_reset": {"max_text_blocks": 2, "headline_max_chars": 12, "subheadline_max_chars": 12, "label_max_chars": 8, "max_labels": 3},
    }
    return mapping.get(image_grammar, {"max_text_blocks": 2, "headline_max_chars": 12, "subheadline_max_chars": 12, "label_max_chars": 8, "max_labels": 4})


def choose_short_labels(section: dict[str, Any], max_items: int = 4) -> list[str]:
    labels: list[str] = []
    for block in section.get("blocks", []):
        if clean_text(block.get("type")) == "bullet_list":
            labels.extend(clean_text(item) for item in block.get("items", []) if clean_text(item))
    if labels:
        return [trim_sentence(label, 20) for label in dedupe(labels)[:max_items]]

    heading = clean_text(section.get("heading"))
    if heading:
        parts = re.split(r"[：:，、/]", heading)
        labels.extend(clean_text(part) for part in parts if clean_text(part))
    return [trim_sentence(label, 16) for label in dedupe(labels)[:max_items]]


def choose_cover_text(title: str, dek: str, lead_text: str) -> tuple[str, str]:
    contrast_before, contrast_after = extract_contrast_pair(title)
    if contrast_after:
        headline = compress_hook_target(contrast_after, 14)
        subtitle = trim_hard(f"不是{compress_hook_target(contrast_before, 10)}", 14) if contrast_before else trim_hard(dek, 14)
        return headline or trim_hard(title, 14), subtitle
    if "？" in title:
        question = clean_text(title.split("？", 1)[0] + "？")
        return trim_hard(question, 14), trim_hard(dek, 14)
    if "：" in title:
        after = clean_text(title.split("：", 1)[1])
        return compress_hook_target(after, 14), trim_hard(dek, 14)
    return trim_hard(title, 14), trim_hard(dek or lead_text, 14)


def choose_inline_text(image_grammar: str, heading: str, section_text: str, labels: list[str]) -> tuple[str, str, list[str]]:
    if image_grammar == "skip_board":
        headline = "直接跳过"
        subtitle = trim_sentence("如果它真的重要，过几个月它还会在", 14)
        return headline, subtitle, labels[:6]
    if image_grammar == "concept_cluster":
        return trim_sentence(heading, 12), "", labels[:5]
    if image_grammar == "example_comparison":
        before, after = extract_contrast_pair(section_text)
        if after:
            return tighten_phrase(after, 12), trim_sentence(f"不是{tighten_phrase(before, 8)}", 12), labels[:4]
        return trim_sentence(heading, 12), trim_sentence("一个具体例子就够了", 12), labels[:4]
    if image_grammar == "framework_map":
        return trim_sentence(heading, 12), trim_sentence("先看全图，再读细节", 12), labels[:6]
    if image_grammar == "workflow_map":
        return trim_sentence(heading, 12), "", labels[:4]
    if image_grammar == "evolution_map":
        return trim_sentence(heading, 12), trim_sentence("重点是逻辑怎么变了", 12), labels[:4]
    if image_grammar == "decision_board":
        return trim_sentence(heading, 12), trim_sentence("这张图只回答怎么判断", 12), labels[:5]
    return trim_sentence(heading, 12), trim_sentence(section_text, 12), labels[:3]


def build_cover_brief(template: dict[str, Any], article_payload: dict[str, Any], source_item: dict[str, Any], sections: list[dict[str, Any]]) -> dict[str, Any]:
    cover = copy.deepcopy(template["cover_image"])
    title = clean_text(article_payload.get("title"))
    dek = clean_text(article_payload.get("dek"))
    lead_section = sections[0] if sections else {"heading": "", "blocks": []}
    lead_text = collect_section_text(lead_section)
    full_text = "\n".join(filter(None, [title, dek, lead_text]))
    diagram_type = choose_diagram_type(full_text, title, is_cover=True)
    image_grammar = choose_image_grammar(full_text, title, is_cover=True)
    source_label = ""
    author = source_item.get("author") or {}
    display_name = clean_text(author.get("display_name"))
    if display_name:
        source_label = display_name

    cover["image_grammar"] = image_grammar
    cover["diagram_type"] = diagram_type
    cover["concept_summary"] = trim_sentence(dek or lead_text or title, 140)
    cover["scene_elements"] = grammar_scene_elements(image_grammar)
    cover["key_relationships"] = grammar_relationships(image_grammar)
    headline, subheadline = choose_cover_text(title, dek, lead_text)
    budget = grammar_text_budget(image_grammar)
    cover["text_budget"] = budget
    cover["on_canvas_text"]["headline"] = trim_sentence(headline, budget["headline_max_chars"])
    cover["on_canvas_text"]["subheadline"] = trim_sentence(subheadline, budget["subheadline_max_chars"])
    cover["on_canvas_text"]["short_labels"] = [trim_sentence(label, budget["label_max_chars"]) for label in choose_short_labels(lead_section, budget["max_labels"])]
    cover["prompt_seed"] = trim_sentence(
        f"Make this a hook-first cover. One question or tension, one promise, not a dense summary. Source context: {source_label}" if source_label else
        "Make this a hook-first cover. One question or tension, one promise, not a dense summary.",
        200,
    )
    return cover


def derive_section_heading(section: dict[str, Any], index: int) -> str:
    heading = clean_text(section.get("heading"))
    if heading:
        return heading
    for block in section.get("blocks", []):
        text = clean_text(block.get("text"))
        if clean_text(block.get("type")) in {"hero_heading", "paragraph"} and text:
            return trim_sentence(text, 28)
    return f"第 {index} 节"


def build_inline_brief(template_block: dict[str, Any], section: dict[str, Any], index: int) -> dict[str, Any]:
    brief = copy.deepcopy(template_block)
    heading = derive_section_heading(section, index)
    section_text = collect_section_text(section)
    diagram_type = choose_diagram_type(section_text, heading)
    image_grammar = choose_image_grammar(section_text, heading)
    first_paragraph = ""
    for block in section.get("blocks", []):
        if clean_text(block.get("type")) == "paragraph" and clean_text(block.get("text")):
            first_paragraph = clean_text(block.get("text"))
            break

    brief["image_id"] = f"inline_{index:02d}"
    brief["section_ref"] = clean_text(section.get("section_ref")) or f"section_{index:02d}"
    brief["image_grammar"] = image_grammar
    brief["diagram_type"] = diagram_type
    brief["concept_summary"] = trim_sentence(first_paragraph or section_text or heading, 140)
    brief["scene_elements"] = grammar_scene_elements(image_grammar)
    brief["key_relationships"] = grammar_relationships(image_grammar)
    budget = grammar_text_budget(image_grammar)
    brief["text_budget"] = budget
    labels = [trim_sentence(label, budget["label_max_chars"]) for label in choose_short_labels(section, budget["max_labels"])]
    headline, subheadline, labels = choose_inline_text(image_grammar, heading, first_paragraph or section_text, labels)
    brief["on_canvas_text"]["headline"] = trim_sentence(headline, budget["headline_max_chars"])
    brief["on_canvas_text"]["subheadline"] = trim_sentence(subheadline, budget["subheadline_max_chars"])
    brief["on_canvas_text"]["short_labels"] = labels
    brief["placement_rule"] = f"Insert near the start of {brief['section_ref']} to reset attention at this section transition."
    brief["prompt_seed"] = trim_sentence(f"Use the {image_grammar} grammar. This is one visual job, not a paragraph summary: {heading}", 200)
    return brief


def apply_style_overlay(brief: dict[str, Any], overlay: dict[str, Any]) -> None:
    if not overlay:
        return

    composition = brief.get("composition") or {}
    for field in ("layout_pattern", "diagram_focus", "text_position"):
        value = clean_text(overlay.get(field))
        if value:
            composition[field] = value
    brief["composition"] = composition

    brief["scene_elements"] = dedupe(list(brief.get("scene_elements") or []) + list(overlay.get("scene_elements_add") or []))
    brief["key_relationships"] = dedupe(list(brief.get("key_relationships") or []) + list(overlay.get("key_relationships_add") or []))
    brief["visual_constraints"] = dedupe(
        list(brief.get("visual_constraints") or []) + list(overlay.get("visual_constraints_add") or [])
    )
    brief["negative_constraints"] = dedupe(
        list(brief.get("negative_constraints") or []) + list(overlay.get("negative_constraints_add") or [])
    )

    prompt_additions: list[str] = []
    profile_label = clean_text(overlay.get("profile_label"))
    if profile_label:
        prompt_additions.append(f"Style profile: {profile_label}.")
    style_direction = clean_text(overlay.get("style_direction_add"))
    if style_direction:
        prompt_additions.append(style_direction)
    prompt_additions.extend(clean_text(item) for item in list(overlay.get("prompt_seed_lines") or []))
    brief["prompt_seed"] = merge_prompt_seed(str(brief.get("prompt_seed") or ""), prompt_additions)


def apply_style_bridge(payload: dict[str, Any], style_bridge: dict[str, Any]) -> dict[str, Any]:
    if not style_bridge:
        return payload

    style_profile_id = clean_text(style_bridge.get("style_profile_id"))
    if style_profile_id:
        payload["style_profile_id"] = style_profile_id

    global_rules = payload.get("global_visual_rules") or {}
    global_bridge = style_bridge.get("global") or {}
    global_rules["style_direction"] = merge_text(
        str(global_rules.get("style_direction") or ""),
        str(global_bridge.get("style_direction_add") or ""),
    )
    global_rules["must_have"] = dedupe(
        list(global_rules.get("must_have") or []) + list(global_bridge.get("must_have_add") or [])
    )
    global_rules["must_avoid"] = dedupe(
        list(global_rules.get("must_avoid") or []) + list(global_bridge.get("must_avoid_add") or [])
    )
    payload["global_visual_rules"] = global_rules

    cover = payload.get("cover_image") or {}
    cover_cfg = style_bridge.get("cover") or {}
    apply_style_overlay(cover, cover_cfg.get("default") or {})
    cover_overrides = cover_cfg.get("diagram_overrides") or {}
    apply_style_overlay(cover, cover_overrides.get(clean_text(cover.get("diagram_type"))) or {})
    payload["cover_image"] = cover

    inline_cfg = style_bridge.get("inline") or {}
    grammar_overrides = inline_cfg.get("grammar_overrides") or {}
    updated_inline: list[dict[str, Any]] = []
    for inline in payload.get("inline_images", []) or []:
        block = copy.deepcopy(inline)
        apply_style_overlay(block, inline_cfg.get("default") or {})
        apply_style_overlay(block, grammar_overrides.get(clean_text(block.get("image_grammar"))) or {})
        updated_inline.append(block)
    payload["inline_images"] = updated_inline
    return payload


def build_payload(
    article_path: Path,
    template_path: Path,
    *,
    max_inline: int,
    style_bridge_path: Path | None,
) -> dict[str, Any]:
    article_payload = load_json(article_path)
    source_item = get_source_item(article_payload)
    publishing_hints = get_publishing_hints(article_payload, source_item)
    blocks = get_article_blocks(article_payload, publishing_hints)
    sections = split_sections(blocks)
    template = load_json(template_path)

    payload = copy.deepcopy(template)
    payload["article_ref"] = str(article_path.resolve())
    if article_payload.get("source_ref"):
        payload["source_ref"] = clean_text(article_payload.get("source_ref"))

    payload["cover_image"] = build_cover_brief(template, article_payload, source_item, sections)

    inline_sections = sections[: max(0, max_inline)]
    payload["inline_images"] = [
        build_inline_brief(template["inline_images"][0], section, index + 1)
        for index, section in enumerate(inline_sections)
    ]

    bridge = load_optional_json(style_bridge_path or DEFAULT_STYLE_BRIDGE_PATH)
    return apply_style_bridge(payload, bridge)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", required=True, help="Path to article_draft.json")
    parser.add_argument("--out", required=True, help="Output path for ARTICLE_IMAGE_BRIEF JSON")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--style-bridge", default=str(DEFAULT_STYLE_BRIDGE_PATH))
    parser.add_argument("--max-inline", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    article_path = Path(args.article).resolve()
    out_path = Path(args.out).resolve()
    template_path = Path(args.template).resolve()
    style_bridge_path = Path(args.style_bridge).resolve() if clean_text(args.style_bridge) else None

    payload = build_payload(
        article_path,
        template_path,
        max_inline=max(0, args.max_inline),
        style_bridge_path=style_bridge_path,
    )
    dump_json(out_path, payload)
    print(
        json.dumps(
            {
                "ok": True,
                "article": str(article_path),
                "out": str(out_path),
                "inline_count": len(payload.get("inline_images", [])),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
