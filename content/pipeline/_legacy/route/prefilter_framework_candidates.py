from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1.0"
FRAMEWORK_LOW_CONFIDENCE = {"05_ab_benchmark", "08_signal_to_action"}
SPECIAL_TERM_PATTERNS = {
    "$": r"\$\s*\d",
    "%": r"\b\d+(?:\.\d+)?%",
    "k ": r"\b\d+(?:\.\d+)?k\b",
    " vs ": r"\bvs\b",
}
BUSINESS_METRIC_PATTERN = re.compile(
    r"(\$\s*\d|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?k\b|\b(?:arr|mrr|gmv|revenue|profit|customers?|users?|signups?|traffic|conversion)\b)",
    re.IGNORECASE,
)
TIME_ONLY_METRIC_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:min|mins|minutes|hour|hours|sec|secs|seconds)\b",
    re.IGNORECASE,
)
MONEY_PROOF_STRONG_TERMS = (
    "revenue",
    "arr",
    "mrr",
    "gmv",
    "profit",
    "growth",
    "conversion",
    "signed",
    "customers",
    "fundraise",
    "traffic",
    "seo",
    "funnel",
    "pricing",
)


@dataclass
class SearchBlobs:
    title_summary: str
    support: str
    body: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


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


def normalize_text(value: Any) -> str:
    return " ".join(str(value).lower().split()).strip()


def term_pattern(term: str) -> str:
    if term in SPECIAL_TERM_PATTERNS:
        return SPECIAL_TERM_PATTERNS[term]
    cleaned = term.strip()
    return rf"(?<!\w){re.escape(cleaned)}(?!\w)"


def text_has_term(text: str, term: str) -> bool:
    return bool(text and re.search(term_pattern(term), text, re.IGNORECASE))


def collect_search_blobs(source_item: dict[str, Any]) -> SearchBlobs:
    title_summary = normalize_text(
        "\n".join(
            [
                source_item.get("title", ""),
                source_item.get("content", {}).get("summary", ""),
            ]
        )
    )
    support = normalize_text(
        "\n".join(
            [
                " ".join(source_item.get("extracted_signals", {}).get("task_hints", [])),
                " ".join(source_item.get("extracted_signals", {}).get("fact_anchors", [])),
                " ".join(source_item.get("extracted_signals", {}).get("named_entities", [])),
            ]
        )
    )
    body = normalize_text(source_item.get("content", {}).get("full_text", "")[:12000])
    return SearchBlobs(title_summary=title_summary, support=support, body=body)


def relevant_metric_signals(signals: list[str], *, business_only: bool = False) -> list[str]:
    filtered: list[str] = []
    for value in signals:
        normalized = normalize_text(value)
        if not normalized or TIME_ONLY_METRIC_PATTERN.search(normalized):
            continue
        if business_only and not BUSINESS_METRIC_PATTERN.search(normalized):
            continue
        filtered.append(value)
    return filtered


def read_framework_specs(specs_dir: Path) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for spec_path in sorted(specs_dir.glob("*/FRAMEWORK_SPEC.json")):
        spec = load_json(spec_path)
        framework_id = spec["metadata"]["framework_id"]
        specs[framework_id] = {
            "path": str(spec_path.resolve()),
            "label": spec["metadata"]["framework_label"],
            "confidence": spec["metadata"]["confidence"],
            "routing": spec["routing"],
        }
    return specs


@dataclass
class RuleSet:
    framework_id: str
    source_kind_terms: tuple[str, ...] = ()
    required_hints: tuple[str, ...] = ()
    positive_terms: tuple[str, ...] = ()
    negative_terms: tuple[str, ...] = ()
    min_score: int = 1


RULES: dict[str, RuleSet] = {
    "01_money_proof": RuleSet(
        framework_id="01_money_proof",
        positive_terms=(
            "revenue", "arr", "mrr", "gmv", "profit", "growth", "conversion", "signed", "customers",
            "meetings", "fundraise", "traffic", "seo", "funnel", "$", "million", "k ", "%", "pricing",
        ),
        negative_terms=("podcast trailer", "subscribe", "creators and guests"),
        min_score=3,
    ),
    "02_launch_application": RuleSet(
        framework_id="02_launch_application",
        required_hints=("release",),
        positive_terms=("launch", "released", "introducing", "new feature", "new capability", "update", "rollout"),
        min_score=2,
    ),
    "03_opinion_decode": RuleSet(
        framework_id="03_opinion_decode",
        source_kind_terms=("podcast_transcript",),
        required_hints=("interview",),
        positive_terms=("conversation", "discuss", "guest", "host", "what this means", "future", "opinion", "think"),
        min_score=2,
    ),
    "04_failure_reversal": RuleSet(
        framework_id="04_failure_reversal",
        positive_terms=(
            "mistake", "wrong", "failed", "failure", "pivot", "switched", "uninstall", "constraint", "bottleneck",
            "not working", "didn't work", "reframe", "no longer",
        ),
        min_score=2,
    ),
    "05_ab_benchmark": RuleSet(
        framework_id="05_ab_benchmark",
        required_hints=("comparison",),
        positive_terms=(" vs ", "compare", "comparison", "benchmark", "shortlist", "alternative", "tradeoff"),
        min_score=3,
    ),
    "06_checklist_template": RuleSet(
        framework_id="06_checklist_template",
        required_hints=("workflow",),
        positive_terms=("steps", "guide", "tutorial", "workflow", "architecture", "how to", "setup", "configure", "install"),
        min_score=2,
    ),
    "07_contrarian_take": RuleSet(
        framework_id="07_contrarian_take",
        positive_terms=(
            "everyone thinks", "most people", "wrong", "actually", "contrary", "my unpopular", "we should stop",
            "the real problem", "not the future", "i disagree",
        ),
        min_score=2,
    ),
    "08_signal_to_action": RuleSet(
        framework_id="08_signal_to_action",
        positive_terms=("window", "signal", "skills", "job", "career", "next 12 months", "future", "opportunity", "positioning"),
        min_score=3,
    ),
}


def score_framework(source_item: dict[str, Any], framework_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    rules = RULES[framework_id]
    blobs = collect_search_blobs(source_item)
    task_hints = set(source_item.get("extracted_signals", {}).get("task_hints", []))
    source_kind = source_item.get("source_kind", "")
    participants = source_item.get("participants", [])
    release_signals = source_item.get("extracted_signals", {}).get("release_signals", [])
    metric_signals = source_item.get("extracted_signals", {}).get("metric_signals", [])
    business_metric_signals = relevant_metric_signals(metric_signals, business_only=True)

    score = 0
    reasons: list[str] = []
    strong_evidence = 0

    if rules.source_kind_terms and any(term == source_kind for term in rules.source_kind_terms):
        score += 2
        reasons.append(f"source_kind={source_kind}")
        strong_evidence += 1

    for hint in rules.required_hints:
        if hint in task_hints:
            score += 2
            reasons.append(f"task_hint={hint}")
            strong_evidence += 1

    for term in rules.positive_terms:
        if text_has_term(blobs.title_summary, term):
            score += 2
            reasons.append(f"title_hit={term}")
            strong_evidence += 1
        elif text_has_term(blobs.support, term):
            score += 2
            reasons.append(f"signal_hit={term}")
            strong_evidence += 1
        elif text_has_term(blobs.body, term):
            score += 1
            reasons.append(f"body_hit={term}")

    for term in rules.negative_terms:
        if text_has_term(blobs.title_summary, term) or text_has_term(blobs.support, term) or text_has_term(blobs.body, term):
            score -= 1
            reasons.append(f"negative_hit={term}")

    if framework_id == "01_money_proof" and business_metric_signals:
        score += min(3, len(business_metric_signals))
        reasons.append(f"business_metric_signals={len(business_metric_signals)}")
        strong_evidence += 1

    if framework_id == "02_launch_application" and release_signals and (
        "release" in task_hints or any(text_has_term(blobs.title_summary, term) for term in rules.positive_terms)
    ):
        score += min(3, len(release_signals))
        reasons.append(f"release_signals={','.join(release_signals[:3])}")
        strong_evidence += 1

    if framework_id == "03_opinion_decode":
        if participants:
            score += 2
            reasons.append(f"participants={len(participants)}")
            strong_evidence += 1
        if source_kind == "podcast_transcript":
            score += 1
            reasons.append("podcast_transcript_source")
            strong_evidence += 1

    if framework_id == "05_ab_benchmark" and len(metric_signals) >= 2:
        score += 1
        reasons.append("multiple_metrics_present")

    if framework_id == "06_checklist_template":
        if "tutorial" in task_hints or "workflow" in task_hints:
            score += 1
            reasons.append("execution_path_hint")
            strong_evidence += 1
        if source_item.get("content", {}).get("sections"):
            score += 1
            reasons.append("sectioned_source")

    if framework_id == "08_signal_to_action" and any(hint in task_hints for hint in ("workflow", "tutorial")):
        score -= 1
        reasons.append("tutorial_bias_against_signal_to_action")

    matched = score >= rules.min_score
    if source_kind == "podcast_transcript" and framework_id != "03_opinion_decode":
        if strong_evidence == 0:
            matched = False
            reasons.append("podcast_gate=body_only_evidence")
        elif framework_id == "01_money_proof":
            money_proof_support = any(text_has_term(blobs.title_summary, term) or text_has_term(blobs.support, term) for term in MONEY_PROOF_STRONG_TERMS)
            if not money_proof_support:
                matched = False
                reasons.append("podcast_gate=no_result_signal_outside_body")
    return {
        "framework_id": framework_id,
        "framework_label": spec["label"],
        "confidence_tier": spec["confidence"],
        "score": score,
        "matched": matched,
        "rule_threshold": rules.min_score,
        "reasons": compact_list(reasons),
        "routing_source_fit": spec["routing"].get("source_fit", [])[:3],
    }


def candidate_ids(scored_rows: list[dict[str, Any]], source_kind: str) -> list[str]:
    matched = [row for row in scored_rows if row["matched"]]
    matched.sort(key=lambda row: (row["score"], row["confidence_tier"] == "high"), reverse=True)

    results: list[str] = []
    for row in matched:
        framework_id = row["framework_id"]
        if framework_id in FRAMEWORK_LOW_CONFIDENCE and row["score"] < 4:
            continue
        results.append(framework_id)

    if not results and matched:
        results = [matched[0]["framework_id"]]

    if "03_opinion_decode" in [row["framework_id"] for row in matched]:
        if "03_opinion_decode" not in results:
            results.append("03_opinion_decode")

    if source_kind == "podcast_transcript" and "03_opinion_decode" in results:
        results = ["03_opinion_decode"] + [framework_id for framework_id in results if framework_id != "03_opinion_decode"]

    return results[:3]


def explain_candidates(scored_rows: list[dict[str, Any]], candidate_framework_ids: list[str]) -> list[str]:
    by_id = {row["framework_id"]: row for row in scored_rows}
    why: list[str] = []
    for framework_id in candidate_framework_ids:
        row = by_id[framework_id]
        reasons = ", ".join(row["reasons"][:4]) if row["reasons"] else "matched framework routing heuristics"
        why.append(f"{framework_id}: score={row['score']} because {reasons}")
    return why


def build_prefilter_result(source_item_path: Path, framework_specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_item = load_json(source_item_path)
    scored = [score_framework(source_item, framework_id, spec) for framework_id, spec in framework_specs.items()]
    scored.sort(key=lambda row: (row["matched"], row["score"]), reverse=True)
    candidates = candidate_ids(scored, source_item.get("source_kind", ""))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "source_ref": str(source_item_path.resolve()),
        "prefilter": {
            "candidate_framework_ids": candidates,
            "why_these_candidates": explain_candidates(scored, candidates),
        },
        "diagnostics": {
            "all_scores": scored,
            "low_confidence_frameworks": sorted(FRAMEWORK_LOW_CONFIDENCE),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-item-root", required=True, help="Directory containing source_item.json artifacts")
    parser.add_argument(
        "--framework-specs-dir",
        default="framework",
        help="Framework specs directory",
    )
    parser.add_argument("--out-root", required=True, help="Directory for prefilter artifacts")
    args = parser.parse_args()

    source_item_root = Path(args.source_item_root).expanduser().resolve()
    framework_specs_dir = Path(args.framework_specs_dir).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    framework_specs = read_framework_specs(framework_specs_dir)
    source_paths = sorted(source_item_root.glob("**/source_item.json"))
    results: list[dict[str, Any]] = []

    for path in source_paths:
        payload = build_prefilter_result(path, framework_specs)
        source_id = load_json(path)["source_id"]
        target_dir = out_root / source_id
        target_dir.mkdir(parents=True, exist_ok=True)
        out_json = target_dir / "prefilter_result.json"
        out_md = target_dir / "prefilter_result.md"
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        md_lines = [
            f"# Prefilter {source_id}",
            "",
            f"- Source Ref: {payload['source_ref']}",
            f"- Candidates: {', '.join(payload['prefilter']['candidate_framework_ids'])}",
            "",
            "## Why These Candidates",
        ]
        for line in payload["prefilter"]["why_these_candidates"]:
            md_lines.append(f"- {line}")
        md_lines.extend(["", "## Scores"])
        for row in payload["diagnostics"]["all_scores"]:
            md_lines.append(f"- {row['framework_id']} | score={row['score']} | matched={row['matched']}")
        out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        results.append(
            {
                "source_id": source_id,
                "output_json": str(out_json),
                "output_md": str(out_md),
                "candidate_framework_ids": payload["prefilter"]["candidate_framework_ids"],
            }
        )
        print(f"{source_id} -> {','.join(payload['prefilter']['candidate_framework_ids'])}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "source_item_root": str(source_item_root),
        "framework_specs_dir": str(framework_specs_dir),
        "count": len(results),
        "results": results,
    }
    manifest_path = out_root / "prefilter_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
