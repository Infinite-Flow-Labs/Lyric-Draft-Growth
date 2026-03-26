from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


SCHEMA_VERSION = "0.1.0"
ROUTING_MODE = "llm_router_plus_reviewer"
LOW_CONFIDENCE_FRAMEWORKS = {"05_ab_benchmark", "08_signal_to_action"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_source_gate(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return load_json(path)


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


def preview_text(value: str, limit: int) -> str:
    cleaned = " ".join(str(value).split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


@dataclass
class FrameworkSpecView:
    framework_id: str
    framework_label: str
    confidence: str
    path: str
    routing: dict[str, Any]
    submodes: dict[str, dict[str, Any]]
    sample_refs: dict[str, dict[str, Any]]


def read_framework_specs(specs_dir: Path) -> dict[str, FrameworkSpecView]:
    specs: dict[str, FrameworkSpecView] = {}
    for spec_path in sorted(specs_dir.glob("*/FRAMEWORK_SPEC.json")):
        spec = load_json(spec_path)
        framework_id = spec["metadata"]["framework_id"]
        specs[framework_id] = FrameworkSpecView(
            framework_id=framework_id,
            framework_label=spec["metadata"]["framework_label"],
            confidence=spec["metadata"]["confidence"],
            path=str(spec_path.resolve()),
            routing=spec["routing"],
            submodes={submode["submode_id"]: submode for submode in spec["structure"]["submodes"]},
            sample_refs={sample["sample_id"]: sample for sample in spec["samples"]["sample_refs"]},
        )
    return specs


def build_candidate_packet(spec: FrameworkSpecView) -> dict[str, Any]:
    return {
        "framework_id": spec.framework_id,
        "framework_label": spec.framework_label,
        "framework_confidence": spec.confidence,
        "routing": {
            "source_fit": spec.routing["source_fit"][:3],
            "source_unfit": spec.routing["source_unfit"][:4],
            "strong_signals": spec.routing["strong_signals"][:4],
            "disqualifiers": spec.routing["disqualifiers"][:4],
        },
        "submodes": [
            {
                "submode_id": submode["submode_id"],
                "label": submode["label"],
                "summary": submode["summary"],
                "use_when": submode["use_when"][:3],
                "avoid_when": submode["avoid_when"][:3],
                "source_fit": submode["source_fit"][:3],
                "source_unfit": submode["source_unfit"][:3],
                "sample_ids": submode["sample_ids"],
            }
            for submode in spec.submodes.values()
        ],
    }


def build_source_packet(source_item: dict[str, Any]) -> dict[str, Any]:
    title = source_item["title"]
    summary = source_item.get("content", {}).get("summary", "")
    summary_lower = f"{title}\n{summary}".lower()
    explicit_guest_markers = [
        "we talk with",
        "interview with",
        "joined by",
        "featuring:",
        "cohost",
        "guest",
    ]
    narrated_briefing_markers = [
        "in the headlines",
        "essay:",
        "scouting report",
        "this episode explains",
        "current ai landscape",
        "race to",
    ]
    return {
        "source_id": source_item["source_id"],
        "platform": source_item["platform"],
        "source_kind": source_item["source_kind"],
        "title": title,
        "canonical_url": source_item.get("canonical_url"),
        "author": source_item.get("author"),
        "participants": source_item.get("participants", []),
        "participant_count": len(source_item.get("participants", [])),
        "has_explicit_guest_language": any(marker in summary_lower for marker in explicit_guest_markers),
        "looks_like_narrated_briefing": any(marker in summary_lower for marker in narrated_briefing_markers),
        "published_at": source_item.get("published_at"),
        "summary": preview_text(summary, 1200),
        "full_text_excerpt": preview_text(source_item.get("content", {}).get("full_text", ""), 1600),
        "sections": source_item.get("content", {}).get("sections", [])[:8],
        "task_hints": source_item.get("extracted_signals", {}).get("task_hints", []),
        "fact_anchors": source_item.get("extracted_signals", {}).get("fact_anchors", [])[:6],
        "release_signals": source_item.get("extracted_signals", {}).get("release_signals", []),
        "metric_signals": source_item.get("extracted_signals", {}).get("metric_signals", [])[:6],
    }


def router_system_prompt() -> str:
    return (
        "You are the framework router for a rewrite pipeline. "
        "Your job is to select the best framework and submode for a source item. "
        "You must not summarize loosely. Use the provided framework routing criteria exactly. "
        "Choose the framework whose routing fit and submode fit best match the source. "
        "Return valid JSON only. Keep supporting_source_quotes short, each <= 20 words."
    )


def router_user_prompt(source_packet: dict[str, Any], prefilter: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "task": "Route this source item to the best framework and submode.",
            "instructions": [
                "Treat prefilter candidates as narrowing only, not as the final answer.",
                "Use raw source evidence and routing criteria to decide.",
                "Prefer the submode that best matches source type and reader payoff.",
                "Alternative choices should be realistic competitors, not filler, and max 2.",
                "Only use sample IDs that belong to the selected submode.",
                "Do not default to conversation_distillation just because source_kind is podcast_transcript.",
                "Use conversation_distillation only when there is clear guest/dialogue structure,人物弧线, or conversation-led payoff.",
                "If the source behaves more like a narrated briefing, scouting report, essay decode, or multi-headline market interpretation, prefer signal_decode.",
                "Schema is enforced separately; do not add any extra keys.",
            ],
            "source_item": source_packet,
            "prefilter": prefilter,
            "candidate_frameworks": candidates,
        },
        ensure_ascii=False,
        indent=2,
    )


def reviewer_system_prompt() -> str:
    return (
        "You are the routing reviewer. "
        "Review the router decision critically against the source item and framework criteria. "
        "You may agree or override. "
        "Return valid JSON only. If you override, provide a complete replacement choice."
    )


def reviewer_user_prompt(
    source_packet: dict[str, Any],
    prefilter: dict[str, Any],
    candidates: list[dict[str, Any]],
    router_result: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "task": "Review the router decision.",
            "instructions": [
                "Check whether the router confused source type, reader payoff, or submode fit.",
                "Use override only if there is a clearly better framework/submode.",
                "Mark requires_human_review for low-confidence cases or unresolved ambiguity.",
                "For podcast sources, challenge any conversation_distillation route that lacks explicit guest/dialogue evidence.",
                "For narrated briefings, scouting reports, or essay-style audio explainers, prefer signal_decode over conversation_distillation.",
                "Schema is enforced separately; do not add any extra keys.",
            ],
            "source_item": source_packet,
            "prefilter": prefilter,
            "candidate_frameworks": candidates,
            "router_result": router_result,
        },
        ensure_ascii=False,
        indent=2,
    )


class OpenAICompatibleClient:
    def __init__(self, api_key: str, api_base: str, timeout_s: int) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout_s = timeout_s

    def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not model:
            raise RuntimeError("openai_compatible backend requires --router-model / --reviewer-model")
        url = f"{self.api_base}/chat/completions"
        payload = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        content = raw["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return json.loads(content)


class CodexExecClient:
    def __init__(self, codex_binary: str, working_dir: str, timeout_s: int, reasoning_effort: str = "") -> None:
        self.codex_binary = codex_binary
        self.working_dir = Path(working_dir).expanduser().resolve()
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        self.reasoning_effort = reasoning_effort

    def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if output_schema is None:
            raise RuntimeError("codex_cli backend requires an output schema")

        with tempfile.TemporaryDirectory(prefix="codex-route-", dir="/tmp") as temp_dir:
            schema_path = Path(temp_dir) / "output_schema.json"
            output_path = Path(temp_dir) / "last_message.json"
            dump_json(schema_path, output_schema)

            prompt = "\n\n".join(
                [
                    system_prompt,
                    user_prompt,
                    "Execution constraints:",
                    "- Do not run shell commands.",
                    "- Do not inspect local files.",
                    "- Use only the JSON material included in this prompt.",
                    "- Return only JSON that matches the provided schema.",
                ]
            )

            command = [
                self.codex_binary,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "-C",
                str(self.working_dir),
                "-s",
                "read-only",
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "-",
            ]
            if model:
                command[2:2] = ["-m", model]
            if self.reasoning_effort:
                command[2:2] = ["-c", f'model_reasoning_effort="{self.reasoning_effort}"']

            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
            )
            if completed.returncode != 0:
                stderr = preview_text(completed.stderr, 1800)
                stdout = preview_text(completed.stdout, 1800)
                raise RuntimeError(f"codex exec failed with code {completed.returncode}. stderr={stderr} stdout={stdout}")

            raw_text = output_path.read_text(encoding="utf-8").strip()
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                if raw_text.startswith("```") and raw_text.endswith("```"):
                    lines = raw_text.splitlines()
                    stripped = "\n".join(lines[1:-1]).strip()
                    return json.loads(stripped)
                raise


def normalize_choice(choice: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "framework_id": choice["framework_id"],
        "submode_id": choice["submode_id"],
        "confidence": choice["confidence"],
        "rationale": preview_text(choice["rationale"], 900),
        "triggered_routing_signals": compact_list(choice.get("triggered_routing_signals", []))[:8],
        "supporting_source_quotes": compact_list(choice.get("supporting_source_quotes", []))[:5],
        "matched_sample_ids": compact_list(choice.get("matched_sample_ids", []))[:3],
    }
    ambiguity_notes = compact_list(choice.get("ambiguity_notes", []))[:4]
    if ambiguity_notes:
        payload["ambiguity_notes"] = ambiguity_notes
    return payload


def validate_choice(choice: dict[str, Any], framework_specs: dict[str, FrameworkSpecView]) -> None:
    framework_id = choice["framework_id"]
    submode_id = choice["submode_id"]
    if framework_id not in framework_specs:
        raise ValueError(f"Unknown framework_id: {framework_id}")
    spec = framework_specs[framework_id]
    if submode_id not in spec.submodes:
        raise ValueError(f"{framework_id} does not contain submode_id={submode_id}")
    valid_sample_ids = set(spec.submodes[submode_id]["sample_ids"])
    for sample_id in choice["matched_sample_ids"]:
        if sample_id not in valid_sample_ids:
            raise ValueError(f"{framework_id}/{submode_id} does not contain sample_id={sample_id}")


def load_bootstrap_decisions(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    return {entry["source_id"]: entry for entry in payload["decisions"]}


def choice_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "framework_id",
            "submode_id",
            "confidence",
            "rationale",
            "triggered_routing_signals",
            "supporting_source_quotes",
            "matched_sample_ids",
            "ambiguity_notes",
        ],
        "properties": {
            "framework_id": {"type": "string", "minLength": 1},
            "submode_id": {"type": "string", "minLength": 1},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "rationale": {"type": "string", "minLength": 1},
            "triggered_routing_signals": {"type": "array", "items": {"type": "string"}},
            "supporting_source_quotes": {"type": "array", "items": {"type": "string"}},
            "matched_sample_ids": {"type": "array", "items": {"type": "string"}},
            "ambiguity_notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def router_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["top_choice", "alternative_choices"],
        "properties": {
            "top_choice": choice_output_schema(),
            "alternative_choices": {"type": "array", "items": choice_output_schema()},
        },
    }


def reviewer_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["agrees_with_router", "override_choice", "concerns", "requires_human_review"],
        "properties": {
            "agrees_with_router": {"type": "boolean"},
            "override_choice": {
                "type": ["object", "null"],
                "additionalProperties": False,
                "required": [
                    "framework_id",
                    "submode_id",
                "confidence",
                "rationale",
                "triggered_routing_signals",
                "supporting_source_quotes",
                "matched_sample_ids",
                "ambiguity_notes",
                ],
                "properties": choice_output_schema()["properties"],
            },
            "concerns": {"type": "array", "items": {"type": "string"}},
            "requires_human_review": {"type": "boolean"},
        },
    }


def choose_backend(
    *,
    backend: str,
    api_key_env: str,
    api_base: str,
    timeout_s: int,
    bootstrap_decisions_file: str | None,
    codex_binary: str,
    codex_working_dir: str,
    codex_reasoning_effort: str,
) -> tuple[str, Any]:
    if backend == "bootstrap":
        if not bootstrap_decisions_file:
            raise RuntimeError("--backend bootstrap requires --bootstrap-decisions-file")
        return "bootstrap", load_bootstrap_decisions(Path(bootstrap_decisions_file))

    if backend == "openai_compatible":
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"--backend openai_compatible requires env {api_key_env}")
        return "openai_compatible", OpenAICompatibleClient(api_key=api_key, api_base=api_base, timeout_s=timeout_s)

    if backend == "codex_cli":
        binary_path = shutil.which(codex_binary)
        if not binary_path:
            raise RuntimeError(f"Unable to find codex binary: {codex_binary}")
        return "codex_cli", CodexExecClient(
            codex_binary=binary_path,
            working_dir=codex_working_dir,
            timeout_s=timeout_s,
            reasoning_effort=codex_reasoning_effort,
        )

    if bootstrap_decisions_file:
        return "bootstrap", load_bootstrap_decisions(Path(bootstrap_decisions_file))

    api_key = os.environ.get(api_key_env)
    if api_key:
        return "openai_compatible", OpenAICompatibleClient(api_key=api_key, api_base=api_base, timeout_s=timeout_s)

    binary_path = shutil.which(codex_binary)
    if binary_path:
        return "codex_cli", CodexExecClient(
            codex_binary=binary_path,
            working_dir=codex_working_dir,
            timeout_s=timeout_s,
            reasoning_effort=codex_reasoning_effort,
        )

    raise RuntimeError("No routing backend available. Use bootstrap, set API key, or install/login codex CLI.")


def effective_codex_model(requested_model: str, backend_name: str) -> str:
    if requested_model:
        return requested_model
    if backend_name == "codex_cli":
        return "gpt-5.4"
    return ""


def run_router(
    *,
    source_item: dict[str, Any],
    prefilter: dict[str, Any],
    framework_specs: dict[str, FrameworkSpecView],
    backend_name: str,
    backend: Any,
    router_model: str,
) -> dict[str, Any]:
    source_id = source_item["source_id"]
    if backend_name == "bootstrap":
        entry = backend[source_id]
        return {
            "agent_name": "router",
            "model": entry["router_model"],
            "evaluated_at": entry["router_evaluated_at"],
            "top_choice": normalize_choice(entry["router_top_choice"]),
            "alternative_choices": [normalize_choice(choice) for choice in entry.get("router_alternatives", [])],
        }

    candidate_payloads = [build_candidate_packet(framework_specs[framework_id]) for framework_id in prefilter["candidate_framework_ids"]]
    raw = backend.complete_json(
        model=router_model,
        system_prompt=router_system_prompt(),
        user_prompt=router_user_prompt(build_source_packet(source_item), prefilter, candidate_payloads),
        output_schema=router_response_schema(),
    )
    return {
        "agent_name": "router",
        "model": router_model or "codex-default",
        "evaluated_at": isoformat_z(utc_now()),
        "top_choice": normalize_choice(raw["top_choice"]),
        "alternative_choices": [normalize_choice(choice) for choice in raw.get("alternative_choices", [])],
    }


def run_reviewer(
    *,
    source_item: dict[str, Any],
    prefilter: dict[str, Any],
    framework_specs: dict[str, FrameworkSpecView],
    router_result: dict[str, Any],
    backend_name: str,
    backend: Any,
    reviewer_model: str,
) -> dict[str, Any]:
    source_id = source_item["source_id"]
    if backend_name == "bootstrap":
        entry = backend[source_id]
        override_choice = entry.get("reviewer_override_choice")
        return {
            "agent_name": "reviewer",
            "model": entry["reviewer_model"],
            "evaluated_at": entry["reviewer_evaluated_at"],
            "agrees_with_router": bool(entry["reviewer_agrees_with_router"]),
            "override_choice": normalize_choice(override_choice) if override_choice else None,
            "concerns": compact_list(entry.get("reviewer_concerns", []))[:6],
            "requires_human_review": bool(entry.get("reviewer_requires_human_review", False)),
        }

    candidate_payloads = [build_candidate_packet(framework_specs[framework_id]) for framework_id in prefilter["candidate_framework_ids"]]
    raw = backend.complete_json(
        model=reviewer_model,
        system_prompt=reviewer_system_prompt(),
        user_prompt=reviewer_user_prompt(build_source_packet(source_item), prefilter, candidate_payloads, router_result),
        output_schema=reviewer_response_schema(),
    )
    override_choice = raw.get("override_choice")
    return {
        "agent_name": "reviewer",
        "model": reviewer_model or "codex-default",
        "evaluated_at": isoformat_z(utc_now()),
        "agrees_with_router": bool(raw["agrees_with_router"]),
        "override_choice": normalize_choice(override_choice) if override_choice else None,
        "concerns": compact_list(raw.get("concerns", []))[:6],
        "requires_human_review": bool(raw.get("requires_human_review", False)),
    }


def build_final_decision(router_result: dict[str, Any], reviewer_result: dict[str, Any]) -> dict[str, Any]:
    final_choice = reviewer_result["override_choice"] if reviewer_result["override_choice"] else router_result["top_choice"]
    requires_human_review = reviewer_result["requires_human_review"]
    if final_choice["framework_id"] in LOW_CONFIDENCE_FRAMEWORKS or final_choice["confidence"] == "low":
        requires_human_review = True
    return {
        "framework_id": final_choice["framework_id"],
        "submode_id": final_choice["submode_id"],
        "confidence": final_choice["confidence"],
        "rationale": final_choice["rationale"],
        "matched_sample_ids": final_choice["matched_sample_ids"],
        "requires_human_review": requires_human_review,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Framework Match {Path(payload['source_ref']).parent.name}",
        "",
        f"- Routing Mode: {payload['routing_mode']}",
        f"- Source Ref: {payload['source_ref']}",
        f"- Prefilter Candidates: {', '.join(payload['prefilter']['candidate_framework_ids'])}",
        f"- Final Decision: {payload['final_decision']['framework_id']} / {payload['final_decision']['submode_id']}",
        f"- Final Confidence: {payload['final_decision']['confidence']}",
        f"- Human Review: {payload['final_decision']['requires_human_review']}",
        "",
        "## Router",
        f"- Model: {payload['router_decision']['model']}",
        f"- Top Choice: {payload['router_decision']['top_choice']['framework_id']} / {payload['router_decision']['top_choice']['submode_id']}",
        f"- Rationale: {payload['router_decision']['top_choice']['rationale']}",
        "",
        "## Reviewer",
        f"- Model: {payload['reviewer_decision']['model']}",
        f"- Agrees With Router: {payload['reviewer_decision']['agrees_with_router']}",
        f"- Concerns: {', '.join(payload['reviewer_decision']['concerns']) if payload['reviewer_decision']['concerns'] else 'None'}",
    ]
    if payload["reviewer_decision"]["override_choice"]:
        lines.append(
            f"- Override Choice: {payload['reviewer_decision']['override_choice']['framework_id']} / {payload['reviewer_decision']['override_choice']['submode_id']}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-item-root", required=True, help="Directory containing source_item.json artifacts")
    parser.add_argument("--prefilter-root", required=True, help="Directory containing prefilter_result.json artifacts")
    parser.add_argument("--out-root", required=True, help="Directory for framework_match artifacts")
    parser.add_argument("--source-gate-root", help="Optional directory containing source_gate.json artifacts")
    parser.add_argument(
        "--framework-specs-dir",
        default="framework",
        help="Framework specs directory",
    )
    parser.add_argument("--framework-match-schema", default="framework/FRAMEWORK_MATCH_SCHEMA.json")
    parser.add_argument("--backend", choices=["auto", "bootstrap", "openai_compatible", "codex_cli"], default="auto")
    parser.add_argument("--bootstrap-decisions-file", help="Optional offline bootstrap decisions file")
    parser.add_argument("--router-model", default="", help="Router model name")
    parser.add_argument("--reviewer-model", default="", help="Reviewer model name")
    parser.add_argument("--api-base", default="https://api.openai.com/v1", help="OpenAI-compatible API base URL")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable containing API key")
    parser.add_argument("--codex-binary", default="codex", help="Codex CLI binary name or absolute path")
    parser.add_argument("--codex-working-dir", default="/tmp", help="Working directory used by codex exec backend")
    parser.add_argument("--codex-reasoning-effort", default="medium", help="Codex reasoning effort override")
    parser.add_argument("--timeout-s", type=int, default=90, help="HTTP timeout in seconds")
    args = parser.parse_args()

    source_item_root = Path(args.source_item_root).expanduser().resolve()
    prefilter_root = Path(args.prefilter_root).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    source_gate_root = Path(args.source_gate_root).expanduser().resolve() if args.source_gate_root else None

    framework_specs = read_framework_specs(Path(args.framework_specs_dir).expanduser().resolve())
    framework_match_schema = load_json(args.framework_match_schema)
    backend_name, backend = choose_backend(
        backend=args.backend,
        api_key_env=args.api_key_env,
        api_base=args.api_base,
        timeout_s=args.timeout_s,
        bootstrap_decisions_file=args.bootstrap_decisions_file,
        codex_binary=args.codex_binary,
        codex_working_dir=args.codex_working_dir,
        codex_reasoning_effort=args.codex_reasoning_effort,
    )
    router_model = effective_codex_model(args.router_model, backend_name)
    reviewer_model = effective_codex_model(args.reviewer_model, backend_name)

    results: list[dict[str, Any]] = []
    source_paths = sorted(source_item_root.glob("**/source_item.json"))
    for source_path in source_paths:
        source_item = load_json(source_path)
        source_id = source_item["source_id"]
        prefilter_path = prefilter_root / source_id / "prefilter_result.json"
        if not prefilter_path.exists():
            raise FileNotFoundError(f"Missing prefilter_result.json for source_id={source_id}: {prefilter_path}")
        prefilter_payload = load_json(prefilter_path)
        prefilter = prefilter_payload["prefilter"]
        source_gate = load_source_gate(source_gate_root / source_id / "source_gate.json") if source_gate_root else None

        if source_gate and not source_gate.get("longform_eligible", False):
            results.append(
                {
                    "source_id": source_id,
                    "status": "skipped_source_gate",
                    "output_json": "",
                    "output_md": "",
                    "final_framework_id": "",
                    "final_submode_id": "",
                    "requires_human_review": False,
                }
            )
            print(f"{source_id} -> skipped_source_gate")
            continue

        if not prefilter.get("candidate_framework_ids"):
            results.append(
                {
                    "source_id": source_id,
                    "status": "skipped_no_candidates",
                    "output_json": "",
                    "output_md": "",
                    "final_framework_id": "",
                    "final_submode_id": "",
                    "requires_human_review": False,
                }
            )
            print(f"{source_id} -> skipped_no_candidates")
            continue

        router_result = run_router(
            source_item=source_item,
            prefilter=prefilter,
            framework_specs=framework_specs,
            backend_name=backend_name,
            backend=backend,
            router_model=router_model,
        )
        reviewer_result = run_reviewer(
            source_item=source_item,
            prefilter=prefilter,
            framework_specs=framework_specs,
            router_result=router_result,
            backend_name=backend_name,
            backend=backend,
            reviewer_model=reviewer_model,
        )

        validate_choice(router_result["top_choice"], framework_specs)
        for choice in router_result["alternative_choices"]:
            validate_choice(choice, framework_specs)
        if reviewer_result["override_choice"]:
            validate_choice(reviewer_result["override_choice"], framework_specs)

        payload = {
            "schema_version": SCHEMA_VERSION,
            "source_ref": str(source_path.resolve()),
            "routing_mode": ROUTING_MODE,
            "prefilter": prefilter,
            "router_decision": router_result,
            "reviewer_decision": reviewer_result,
            "final_decision": build_final_decision(router_result, reviewer_result),
        }
        jsonschema.validate(payload, framework_match_schema)

        target_dir = out_root / source_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_json = target_dir / "framework_match.json"
        out_md = target_dir / "framework_match.md"
        dump_json(out_json, payload)
        out_md.write_text(render_markdown(payload), encoding="utf-8")

        results.append(
            {
                "source_id": source_id,
                "status": "ok",
                "output_json": str(out_json),
                "output_md": str(out_md),
                "final_framework_id": payload["final_decision"]["framework_id"],
                "final_submode_id": payload["final_decision"]["submode_id"],
                "requires_human_review": payload["final_decision"]["requires_human_review"],
            }
        )
        print(
            f"{source_id} -> {payload['final_decision']['framework_id']}/{payload['final_decision']['submode_id']}"
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "backend": backend_name,
        "source_item_root": str(source_item_root),
        "prefilter_root": str(prefilter_root),
        "source_gate_root": str(source_gate_root) if source_gate_root else "",
        "framework_specs_dir": str(Path(args.framework_specs_dir).expanduser().resolve()),
        "count": len(results),
        "results": results,
    }
    manifest_path = out_root / "framework_match_manifest.json"
    dump_json(manifest_path, manifest)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
