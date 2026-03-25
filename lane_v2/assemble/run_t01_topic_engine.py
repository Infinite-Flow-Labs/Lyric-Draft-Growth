from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "0.1.0"
HEAT_ONLY_FAMILIES = {"post_x"}
EVENT_SEED_FAMILIES = {"official_x", "article_x"}
GENERIC_FACT_ANCHOR_STOPLIST = {
    "we",
    "our",
    "post",
    "video",
    "video post",
    "canonical url",
    "read",
    "together",
    "ai",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_space(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def word_count(value: str) -> int:
    return len([part for part in normalize_space(value).split(" ") if part])


def infer_source_family(source_item_path: Path, source_item: dict[str, Any]) -> str:
    path_text = str(source_item_path).lower()
    if "/official_x/" in path_text:
        return "official_x"
    if "/article_x/" in path_text:
        return "article_x"
    if "/podcast/" in path_text:
        return "podcast"

    canonical_url = str(source_item.get("canonical_url") or "")
    host = (urlparse(canonical_url).netloc or "").lower()
    if "github.com" in host:
        return "github_trending"
    if source_item.get("platform") == "x":
        return "post_x"
    return "unknown"


def host_from_url(url: str) -> str:
    host = (urlparse(str(url or "")).netloc or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host


def dedupe_key(source_item: dict[str, Any]) -> str:
    canonical = normalize_space(source_item.get("canonical_url") or "")
    if canonical:
        return canonical.lower()
    source_id = normalize_space(source_item.get("source_id") or "")
    return source_id.lower()


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = normalize_space(value)
        if not clean:
            continue
        lowered = clean.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(clean)
    return out


def derive_release_signals(text: str) -> list[str]:
    lowered = str(text or "").lower()
    english_terms = [
        "launch",
        "launched",
        "release",
        "released",
        "announced",
        "introducing",
        "now available",
        "rollout",
        "beta",
        "preview",
        "open source",
        "update",
        "offering",
    ]
    chinese_terms = ["发布", "上线", "推出", "开放", "更新", "新增", "开源", "接入"]
    hits: list[str] = []
    for term in english_terms:
        if term in lowered:
            hits.append(term)
    for term in chinese_terms:
        if term in text:
            hits.append(term)
    return compact_list(hits)[:8]


@dataclass(frozen=True)
class GlobalGatePolicy:
    max_age_hours: int
    require_canonical_url: bool
    min_text_words: int
    drop_if_exact_duplicate: bool
    family_max_age_hours: dict[str, int]
    family_min_text_words: dict[str, int]


@dataclass(frozen=True)
class TopicPolicy:
    volume_weight: float
    velocity_weight: float
    cross_source_weight: float
    novelty_weight: float
    min_topic_priority_for_write: float
    max_signals_per_topic: int
    min_source_families_for_priority: int
    cluster_similarity_threshold: int
    lane_fit_weight: float
    lane_topic_weight: float


@dataclass(frozen=True)
class LaneSpec:
    lane_id: str
    lane_label: str
    framework_id: str
    submode_id: str
    composition_mode: str
    generation_ratio: float
    rewrite_ratio: float
    primary_sources_min: int
    supporting_sources_min: int
    fact_anchors_min: int
    require_official_primary: bool
    require_release_signal: bool
    require_external_source: bool
    require_hard_numbers: bool
    require_compare_signal: bool
    require_failure_signal: bool
    require_actionability_signal: bool
    prefer_stepwise_signal: bool
    prefer_contrarian_signal: bool


def load_global_gate_policy(policy_path: Path) -> GlobalGatePolicy:
    payload = load_json(policy_path)
    gate = payload.get("global_gate", {})
    family_overrides = payload.get("family_overrides", {})
    family_max_age_hours: dict[str, int] = {}
    family_min_text_words: dict[str, int] = {}
    for family, override in family_overrides.items():
        if not isinstance(override, dict):
            continue
        if "max_age_hours" in override:
            family_max_age_hours[str(family)] = int(override.get("max_age_hours", gate.get("max_age_hours", 96)))
        if "min_text_words" in override:
            family_min_text_words[str(family)] = int(override.get("min_text_words", gate.get("min_text_words", 40)))
    return GlobalGatePolicy(
        max_age_hours=int(gate.get("max_age_hours", 96)),
        require_canonical_url=bool(gate.get("require_canonical_url", True)),
        min_text_words=int(gate.get("min_text_words", 40)),
        drop_if_exact_duplicate=bool(gate.get("drop_if_exact_duplicate", True)),
        family_max_age_hours=family_max_age_hours,
        family_min_text_words=family_min_text_words,
    )


def load_topic_policy(policy_path: Path) -> TopicPolicy:
    payload = load_json(policy_path)
    weights = payload.get("topic_priority_weights", {})
    thresholds = payload.get("topic_thresholds", {})
    blend = payload.get("lane_blend", {})
    return TopicPolicy(
        volume_weight=float(weights.get("volume_score", 0.35)),
        velocity_weight=float(weights.get("velocity_score", 0.25)),
        cross_source_weight=float(weights.get("cross_source_resonance_score", 0.25)),
        novelty_weight=float(weights.get("novelty_score", 0.15)),
        min_topic_priority_for_write=float(thresholds.get("min_topic_priority_for_write", 60)),
        max_signals_per_topic=int(thresholds.get("max_signals_per_topic", 6)),
        min_source_families_for_priority=int(thresholds.get("min_source_families_for_priority", 2)),
        cluster_similarity_threshold=int(thresholds.get("cluster_similarity_threshold", 4)),
        lane_fit_weight=float(blend.get("lane_fit_weight", 0.7)),
        lane_topic_weight=float(blend.get("topic_priority_weight", 0.3)),
    )


def load_lane_specs(lane_map_path: Path) -> list[LaneSpec]:
    payload = load_json(lane_map_path)
    lanes = payload.get("lanes", [])
    if not lanes:
        raise ValueError("lane map has no lanes")
    lane_specs: list[LaneSpec] = []
    for lane in lanes:
        primary = lane.get("framework_primary", {})
        minimum = lane.get("minimum_source_requirements", {})
        routing_hints = lane.get("routing_hints", {})
        lane_specs.append(
            LaneSpec(
                lane_id=str(lane.get("lane_id") or "T01_release_decode"),
                lane_label=str(lane.get("lane_label") or ""),
                framework_id=str(primary.get("framework_id") or "02_launch_application"),
                submode_id=str(primary.get("submode_id") or "release_showcase"),
                composition_mode=str(lane.get("composition_mode") or "mixed"),
                generation_ratio=float(lane.get("generation_ratio", 0.8)),
                rewrite_ratio=float(lane.get("rewrite_ratio", 0.2)),
                primary_sources_min=int(minimum.get("primary_sources_min", 2)),
                supporting_sources_min=int(minimum.get("supporting_sources_min", 1)),
                fact_anchors_min=int(minimum.get("fact_anchors_min", 5)),
                require_official_primary=bool(minimum.get("require_official_primary", True)),
                require_release_signal=bool(routing_hints.get("require_release_signal", False)),
                require_external_source=bool(routing_hints.get("require_external_source", False)),
                require_hard_numbers=bool(routing_hints.get("require_hard_numbers", False)),
                require_compare_signal=bool(routing_hints.get("require_compare_signal", False)),
                require_failure_signal=bool(routing_hints.get("require_failure_signal", False)),
                require_actionability_signal=bool(routing_hints.get("require_actionability_signal", False)),
                prefer_stepwise_signal=bool(routing_hints.get("prefer_stepwise_signal", False)),
                prefer_contrarian_signal=bool(routing_hints.get("prefer_contrarian_signal", False)),
            )
        )
    return lane_specs


def collect_source_item_paths(roots: list[Path]) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if root.is_file() and root.name == "source_item.json":
            key = str(root.resolve())
            if key not in seen:
                seen.add(key)
                paths.append(root.resolve())
            continue
        if not root.exists():
            continue
        for path in sorted(root.glob("**/source_item.json")):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            paths.append(path.resolve())
    return sorted(paths)


def build_signal_item(source_item_path: Path, source_item: dict[str, Any]) -> dict[str, Any]:
    summary = normalize_space(source_item.get("content", {}).get("summary", ""))
    full_text = normalize_space(source_item.get("content", {}).get("full_text", ""))
    title = normalize_space(source_item.get("title", ""))
    merged_text = "\n\n".join([part for part in [title, summary, full_text] if part]).strip()
    fact_candidates = [normalize_space(item) for item in source_item.get("extracted_signals", {}).get("fact_anchors", [])]
    fact_candidates = [item for item in fact_candidates if item][:20]
    named_entities = [normalize_space(item) for item in source_item.get("extracted_signals", {}).get("named_entities", [])]
    named_entities = [item for item in named_entities if item][:20]
    source_assets = source_item.get("source_assets", [])
    linked_hosts: list[str] = []
    for asset in source_assets:
        host = host_from_url(str(asset.get("url") or ""))
        if host:
            linked_hosts.append(host)
    linked_hosts = sorted(set(linked_hosts))
    extracted_release = [normalize_space(item) for item in source_item.get("extracted_signals", {}).get("release_signals", [])]
    merged_release = compact_list(extracted_release + derive_release_signals(merged_text))

    published_at = str(source_item.get("published_at") or "")
    fetched_at = str(source_item.get("fetched_at") or "")

    return {
        "schema_version": SCHEMA_VERSION,
        "signal_id": str(source_item.get("source_id") or source_item_path.parent.name),
        "source_item_path": str(source_item_path),
        "source_family": infer_source_family(source_item_path, source_item),
        "source_kind": str(source_item.get("source_kind") or ""),
        "canonical_url": str(source_item.get("canonical_url") or ""),
        "published_at": published_at,
        "fetched_at": fetched_at,
        "author_id": str(source_item.get("author", {}).get("handle") or source_item.get("author", {}).get("display_name") or ""),
        "title": title,
        "text": merged_text,
        "text_words": word_count(merged_text),
        "release_signals": merged_release,
        "named_entities": named_entities,
        "linked_hosts": linked_hosts,
        "fact_candidates": fact_candidates,
        "trace": {
            "platform": str(source_item.get("platform") or ""),
            "build_time": isoformat_z(utc_now()),
            "source_item_fetched_at": fetched_at,
        },
    }


def apply_global_gate(
    signal_items: list[dict[str, Any]],
    *,
    policy: GlobalGatePolicy,
    now_utc: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for signal in signal_items:
        reasons: list[str] = []
        source_family = str(signal.get("source_family", "unknown"))
        min_text_words = policy.family_min_text_words.get(source_family, policy.min_text_words)
        max_age_hours = policy.family_max_age_hours.get(source_family, policy.max_age_hours)

        canonical_url = normalize_space(signal.get("canonical_url", ""))
        if policy.require_canonical_url and not canonical_url:
            reasons.append("missing_canonical_url")

        if signal.get("text_words", 0) < min_text_words:
            reasons.append(f"text_words_below_min:{signal.get('text_words', 0)}<{min_text_words}")

        published_at = parse_iso_datetime(str(signal.get("published_at", "")))
        if published_at is not None:
            age_hours = (now_utc - published_at.astimezone(timezone.utc)).total_seconds() / 3600.0
            if age_hours > max_age_hours:
                reasons.append(f"too_old:{age_hours:.1f}h>{max_age_hours}h")
        else:
            reasons.append("invalid_published_at")

        key = dedupe_key(signal)
        if policy.drop_if_exact_duplicate:
            if key in seen_keys:
                reasons.append("duplicate")
            else:
                seen_keys.add(key)

        if reasons:
            rejected.append(
                {
                    "signal_id": signal["signal_id"],
                    "source_family": signal.get("source_family", "unknown"),
                    "canonical_url": canonical_url,
                    "reasons": reasons,
                }
            )
        else:
            passed.append(signal)

    return passed, rejected


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def topic_id_from_signal(signal_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in signal_id)
    return f"topic-{safe}"[:80]


def score_topic(signal: dict[str, Any], policy: TopicPolicy, now_utc: datetime) -> dict[str, float]:
    fact_count = len(signal.get("fact_candidates", []))
    volume_score = clamp_score(20 + fact_count * 8)

    published_at = parse_iso_datetime(str(signal.get("published_at", "")))
    if published_at is None:
        velocity_score = 20.0
    else:
        age_hours = max(0.0, (now_utc - published_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
        velocity_score = clamp_score(100.0 - min(90.0, age_hours * 2.2))

    cross_source_score = 40.0
    novelty_score = 72.0 if signal.get("release_signals") else 45.0

    topic_priority = (
        policy.volume_weight * volume_score
        + policy.velocity_weight * velocity_score
        + policy.cross_source_weight * cross_source_score
        + policy.novelty_weight * novelty_score
    )
    return {
        "volume_score": round(volume_score, 2),
        "velocity_score": round(velocity_score, 2),
        "cross_source_resonance_score": round(cross_source_score, 2),
        "novelty_score": round(novelty_score, 2),
        "topic_priority": round(clamp_score(topic_priority), 2),
    }


GENERIC_ENTITIES = {
    "post",
    "canonical url",
    "video",
    "image",
    "research",
    "products",
    "business",
    "developers",
    "company",
    "foundation",
}
WEAK_EVENT_ENTITIES = {
    "read",
    "news",
    "update",
    "launch",
    "released",
    "release",
    "introducing",
    "announced",
    "together",
    "video",
    "canonical",
    "understanding",
    "memorandum",
    "post",
}
# High-frequency domain entities that appear in many unrelated signals.
# Matching on these alone does NOT prove two signals are about the same event.
BROAD_DOMAIN_ENTITIES = {
    "ai", "claude", "claude code", "codex", "openai", "gpt", "anthropic",
    "google", "deepmind", "meta", "llm", "agent", "model", "api",
    "chatgpt", "gemini", "copilot", "cursor", "github",
    "machine learning", "deep learning", "transformer",
}


def clean_entity(value: str) -> str:
    out = normalize_space(value).lower()
    if out in GENERIC_ENTITIES:
        return ""
    if len(out) < 3:
        return ""
    return out


def event_external_hosts(signal: dict[str, Any]) -> list[str]:
    hosts: list[str] = []
    for host in signal.get("linked_hosts", []):
        clean = str(host or "").strip().lower()
        if clean and clean not in {"x.com", "twitter.com", "nitter.net"}:
            hosts.append(clean)
    return sorted(set(hosts))


def event_key_for_seed(signal: dict[str, Any]) -> str:
    """Strict event key: seed families only, so topic identity is source-led, not post-led."""
    family = str(signal.get("source_family", "")).strip().lower()
    if family not in EVENT_SEED_FAMILIES:
        return ""
    release = normalize_space((signal.get("release_signals") or [""])[0]).lower() or "none"
    entity = ""
    for item in signal.get("named_entities", []):
        entity = clean_entity(item)
        if entity:
            break
    if not entity:
        entity = normalize_space(signal.get("author_id", "")).lower() or "unknown"
    hosts = event_external_hosts(signal)
    host = hosts[0] if hosts else "x.com"
    published = parse_iso_datetime(str(signal.get("published_at", "")))
    day_bucket = published.strftime("%Y-%m-%d") if published else "unknown-day"
    return f"{entity}|{release}|{host}|{day_bucket}"


def is_valid_fact_anchor_claim(claim: str) -> bool:
    cleaned = normalize_space(claim)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in GENERIC_FACT_ANCHOR_STOPLIST:
        return False
    if len(cleaned) < 12:
        return False
    if len(cleaned.split()) < 3 and not re.search(r"[\u4e00-\u9fff]{6,}", cleaned):
        return False
    if lowered.startswith(("post title:", "post summary:", "canonical url:")):
        return False
    # Must carry at least one informative signal: number, url, release/action token, or multi-word proper phrase.
    has_number = bool(re.search(r"\d", cleaned))
    has_url = "http://" in lowered or "https://" in lowered
    has_action = bool(
        re.search(
            r"(launch|release|announc|introduc|上线|发布|推出|更新|开放|合作|mou|pricing|quota|limit|beta|风险|限制)",
            lowered,
        )
    )
    has_rich_phrase = len(cleaned.split()) >= 6 or bool(re.search(r"[\u4e00-\u9fff]{10,}", cleaned))
    return bool(has_number or has_url or has_action or has_rich_phrase)


def extract_claim_candidates_from_text(text: str, *, max_items: int = 12) -> list[str]:
    cleaned = normalize_space(text)
    if not cleaned:
        return []
    candidates: list[str] = []
    # Split by sentence punctuation first, fallback to hard cuts for long paragraphs.
    chunks = re.split(r"[。！？!?]", cleaned)
    if len(chunks) <= 1:
        chunks = re.split(r"(?:\.\s+|\n+)", cleaned)
    for chunk in chunks:
        snippet = normalize_space(chunk)
        if len(snippet) < 18:
            continue
        if len(snippet) > 280:
            snippet = snippet[:280].rstrip()
        if not is_valid_fact_anchor_claim(snippet):
            continue
        candidates.append(snippet)
    return compact_list(candidates)[:max_items]


def cluster_signature(signal: dict[str, Any]) -> str:
    release = normalize_space((signal.get("release_signals") or [""])[0]).lower()
    entities = [clean_entity(item) for item in signal.get("named_entities", [])]
    entities = [item for item in entities if item]
    external_hosts = [
        host for host in signal.get("linked_hosts", []) if host and host not in {"x.com", "nitter.net", "twitter.com"}
    ]
    if release and entities:
        return f"{entities[0]}::{release}"
    if release and external_hosts:
        return f"{external_hosts[0]}::{release}"
    if external_hosts and entities:
        return f"{entities[0]}::{external_hosts[0]}"
    if entities:
        return entities[0]
    if external_hosts:
        return external_hosts[0]
    return signal["signal_id"]


def score_topic_cluster(signals: list[dict[str, Any]], policy: TopicPolicy, now_utc: datetime) -> dict[str, float]:
    total_facts = sum(len(signal.get("fact_candidates", [])) for signal in signals)
    volume_score = clamp_score(len(signals) * 25 + min(35, total_facts * 0.8))

    latest_published: datetime | None = None
    for signal in signals:
        parsed = parse_iso_datetime(str(signal.get("published_at", "")))
        if parsed is None:
            continue
        parsed_utc = parsed.astimezone(timezone.utc)
        if latest_published is None or parsed_utc > latest_published:
            latest_published = parsed_utc
    if latest_published is None:
        velocity_score = 20.0
    else:
        age_hours = max(0.0, (now_utc - latest_published).total_seconds() / 3600.0)
        velocity_score = clamp_score(100.0 - min(90.0, age_hours * 2.2))

    family_count = len({signal.get("source_family", "unknown") for signal in signals})
    cross_source_score = clamp_score(25.0 + family_count * 25.0)

    release_signals_count = sum(len(signal.get("release_signals", [])) for signal in signals)
    novelty_score = 72.0 if release_signals_count > 0 else 45.0

    topic_priority = (
        policy.volume_weight * volume_score
        + policy.velocity_weight * velocity_score
        + policy.cross_source_weight * cross_source_score
        + policy.novelty_weight * novelty_score
    )
    return {
        "volume_score": round(volume_score, 2),
        "velocity_score": round(velocity_score, 2),
        "cross_source_resonance_score": round(cross_source_score, 2),
        "novelty_score": round(novelty_score, 2),
        "topic_priority": round(clamp_score(topic_priority), 2),
    }


def cluster_signals(signals: list[dict[str, Any]], policy: TopicPolicy, now_utc: datetime) -> list[list[dict[str, Any]]]:
    """Event-first clustering: seed by official/article, attach post as heat-only."""
    seed_signals = [
        item
        for item in signals
        if str(item.get("source_family", "")).strip().lower() in EVENT_SEED_FAMILIES
    ]
    seed_signals = sorted(seed_signals, key=lambda item: item.get("published_at", ""), reverse=True)
    if not seed_signals:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for seed in seed_signals:
        key = event_key_for_seed(seed) or seed["signal_id"]
        grouped.setdefault(key, []).append(seed)
    clusters: list[list[dict[str, Any]]] = []
    for key in sorted(grouped.keys()):
        members = sorted(grouped[key], key=lambda item: item.get("published_at", ""), reverse=True)
        clusters.append(members[: policy.max_signals_per_topic])

    heat_signals = [
        item
        for item in signals
        if str(item.get("source_family", "")).strip().lower() in HEAT_ONLY_FAMILIES
    ]
    heat_signals = sorted(heat_signals, key=lambda item: post_heat_score(item, now_utc), reverse=True)

    attach_threshold = max(4, policy.cluster_similarity_threshold + 1)
    for heat in heat_signals:
        best_index = -1
        best_score = -1
        for index, cluster in enumerate(clusters):
            if len(cluster) >= policy.max_signals_per_topic:
                continue
            seed_members = [
                member for member in cluster if str(member.get("source_family", "")).strip().lower() in EVENT_SEED_FAMILIES
            ]
            if not seed_members:
                continue
            if not any(strong_event_overlap(seed, heat) for seed in seed_members):
                continue
            score = max(signal_similarity(heat, member) for member in seed_members)
            if score > best_score:
                best_score = score
                best_index = index
        if best_index < 0 or best_score < attach_threshold:
            continue
        clusters[best_index].append(heat)

    return clusters


def cluster_signature_for_group(group_signals: list[dict[str, Any]]) -> str:
    release_terms: list[str] = []
    entities: list[str] = []
    hosts: list[str] = []
    for signal in group_signals:
        release_terms.extend([normalize_space(item).lower() for item in signal.get("release_signals", []) if normalize_space(item)])
        entities.extend([clean_entity(item) for item in signal.get("named_entities", []) if clean_entity(item)])
        hosts.extend(
            [
                host
                for host in signal.get("linked_hosts", [])
                if host and host not in {"x.com", "nitter.net", "twitter.com"}
            ]
        )
    release = release_terms[0] if release_terms else ""
    entity = entities[0] if entities else ""
    host = hosts[0] if hosts else ""
    if entity and release:
        return f"{entity}::{release}"
    if host and release:
        return f"{host}::{release}"
    if entity and host:
        return f"{entity}::{host}"
    if entity:
        return entity
    if host:
        return host
    return group_signals[0]["signal_id"] if group_signals else "unknown"


def choose_topic_statement(signals: list[dict[str, Any]], seed_signal: dict[str, Any] | None) -> str:
    if seed_signal:
        title = normalize_space(seed_signal.get("title", ""))
        if title:
            return title
    by_length = sorted(signals, key=lambda item: len(normalize_space(item.get("title", ""))), reverse=True)
    for signal in by_length:
        title = normalize_space(signal.get("title", ""))
        if title:
            return title
    return normalize_space((signals[0].get("text", "") if signals else ""))[:120]


def build_topic_cards(
    signals: list[dict[str, Any]],
    policy: TopicPolicy,
    now_utc: datetime,
    lane_ids: list[str],
) -> list[dict[str, Any]]:
    clustered_groups = cluster_signals(signals, policy, now_utc)

    cards: list[dict[str, Any]] = []
    for group_signals in clustered_groups:
        group_signals = sorted(group_signals, key=lambda item: item.get("published_at", ""), reverse=True)
        seed_candidates = [
            item for item in group_signals if str(item.get("source_family", "")).strip().lower() in EVENT_SEED_FAMILIES
        ]
        seed_signal = seed_candidates[0] if seed_candidates else (group_signals[0] if group_signals else None)
        signature = cluster_signature_for_group(group_signals)
        topic_scores = score_topic_cluster(group_signals, policy, now_utc)
        statement = choose_topic_statement(group_signals, seed_signal)
        source_families = sorted({signal.get("source_family", "unknown") for signal in group_signals})
        topic_id_seed = (seed_signal or group_signals[0])["signal_id"] if group_signals else signature
        topic_id = topic_id_from_signal(topic_id_seed)
        has_min_family_span = len(source_families) >= policy.min_source_families_for_priority

        cards.append(
            {
                "schema_version": SCHEMA_VERSION,
                "topic_id": topic_id,
                "event_seed_signal_id": (seed_signal or {}).get("signal_id", ""),
                "event_seed_source_family": (seed_signal or {}).get("source_family", ""),
                "topic_statement": statement,
                "why_now": (
                    f"Clustered {len(group_signals)} recent signals across {len(source_families)} source families "
                    "with verifiable anchors."
                ),
                "topic_priority": topic_scores["topic_priority"],
                "heat_breakdown": {
                    "volume_score": topic_scores["volume_score"],
                    "velocity_score": topic_scores["velocity_score"],
                    "cross_source_resonance_score": topic_scores["cross_source_resonance_score"],
                    "novelty_score": topic_scores["novelty_score"],
                },
                "cluster_signature": signature,
                "cluster_signal_ids": [signal["signal_id"] for signal in group_signals],
                "source_families": source_families,
                "candidate_lanes": lane_ids,
                "eligible_for_write": bool(
                    topic_scores["topic_priority"] >= policy.min_topic_priority_for_write and has_min_family_span
                ),
                "signal_snapshot": {
                    "canonical_url": (seed_signal or group_signals[0]).get("canonical_url", "") if group_signals else "",
                    "published_at": (seed_signal or group_signals[0]).get("published_at", "") if group_signals else "",
                    "release_signals_count": sum(len(signal.get("release_signals", [])) for signal in group_signals),
                    "fact_candidates_count": sum(len(signal.get("fact_candidates", [])) for signal in group_signals),
                },
            }
        )
    cards.sort(key=lambda card: card.get("topic_priority", 0), reverse=True)
    return cards


def topic_feature_snapshot(signals: list[dict[str, Any]]) -> dict[str, Any]:
    families = {str(signal.get("source_family", "")).strip().lower() for signal in signals}
    merged_text = " ".join(str(signal.get("text", "")) for signal in signals)
    lowered = merged_text.lower()
    fact_avg = (
        sum(len(signal.get("fact_candidates", [])) for signal in signals) / max(1, len(signals))
        if signals
        else 0.0
    )
    external_hosts: set[str] = set()
    for signal in signals:
        for host in event_external_hosts(signal):
            external_hosts.add(host)

    return {
        "signal_count": len(signals),
        "family_count": len(families),
        "families": sorted(families),
        "has_release_signal": any(len(signal.get("release_signals", [])) > 0 for signal in signals),
        "has_official_source": "official_x" in families,
        "has_external_source": bool(
            external_hosts
            or families.intersection({"article_x", "podcast", "github_trending"})
        ),
        "has_hard_numbers": bool(
            re.search(r"(\$\d|\b\d+(?:\.\d+)?\s?%|\b\d+(?:\.\d+)?\s?(?:x|k|m|b|million|billion)\b|\b\d{2,}\b)", lowered)
        ),
        "has_compare_signal": bool(
            re.search(r"(\bvs\b|versus|compare|comparison|benchmark|a/b|ab test|对比|横评|评测|替代|选型)", lowered)
        ),
        "has_failure_signal": bool(
            re.search(r"(mistake|failed|failure|wrong|pivot|rebuild|rollback|lessons learned|封号|失败|翻车|复盘|重构|纠偏|转向|踩坑)", lowered)
        ),
        "has_actionability_signal": has_user_impact_signal(merged_text) and bool(
            re.search(r"(how to|step|checklist|playbook|guide|start with|quickstart|workflow|runbook|动作|步骤|清单|上手|怎么做|实操|落地)", lowered)
        ),
        "has_stepwise_signal": bool(
            re.search(r"(\bfirst\b|\bsecond\b|\bthird\b|\bstep\b|\b1\)|\b1\.|步骤|第一|第二|第三|清单)", lowered)
        ),
        "has_contrarian_signal": bool(
            re.search(r"(not .* but|isn't|myth|overrated|underestimated|不是.*而是|误区|反直觉|主流.*错|真正的问题)", lowered)
        ),
        "has_money_signal": bool(
            re.search(r"(\$|usd|mrr|arr|revenue|profit|earn|gmv|roi|预算|收入|盈利|回本|变现|美金|美元)", lowered)
        ),
        "has_postmortem_signal": bool(
            re.search(r"(postmortem|case study|breakdown|timeline|how we did|lessons learned|复盘|拆解|回顾|过程)", lowered)
        ),
        "has_user_impact": has_user_impact_signal(merged_text),
        "has_limit_or_risk": has_limit_or_risk_signal(merged_text),
        "fact_avg": round(float(fact_avg), 2),
    }


def lane_requirement_failures(lane_spec: LaneSpec, features: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    checks = [
        ("require_official_primary", lane_spec.require_official_primary, "has_official_source"),
        ("require_release_signal", lane_spec.require_release_signal, "has_release_signal"),
        ("require_external_source", lane_spec.require_external_source, "has_external_source"),
        ("require_hard_numbers", lane_spec.require_hard_numbers, "has_hard_numbers"),
        ("require_compare_signal", lane_spec.require_compare_signal, "has_compare_signal"),
        ("require_failure_signal", lane_spec.require_failure_signal, "has_failure_signal"),
        ("require_actionability_signal", lane_spec.require_actionability_signal, "has_actionability_signal"),
    ]
    for name, required, key in checks:
        if required and not bool(features.get(key, False)):
            failures.append(name)
    return failures


def lane_fit_score_for_spec(
    *,
    lane_spec: LaneSpec,
    features: dict[str, Any],
) -> tuple[float, list[str]]:
    score = 18.0
    reasons: list[str] = []

    if features.get("has_release_signal", False):
        score += 10.0
        reasons.append("release_signal_present")
    else:
        score -= 4.0
        reasons.append("release_signal_missing")

    if features.get("has_official_source", False):
        score += 8.0
        reasons.append("official_source_present")
    if features.get("has_external_source", False):
        score += 6.0
        reasons.append("external_source_present")

    fact_avg = float(features.get("fact_avg", 0.0))
    if fact_avg >= 8:
        score += 12.0
        reasons.append("strong_fact_density")
    elif fact_avg >= 5:
        score += 8.0
        reasons.append("enough_fact_density")
    elif fact_avg >= 3:
        score += 4.0
        reasons.append("basic_fact_density")
    else:
        score -= 8.0
        reasons.append("fact_density_too_low")

    if int(features.get("family_count", 0)) >= 2:
        score += 8.0
        reasons.append("cross_family_present")
    if features.get("has_user_impact", False):
        score += 6.0
        reasons.append("user_impact_present")
    if features.get("has_limit_or_risk", False):
        score += 4.0
        reasons.append("limit_or_risk_present")

    requirement_failures = lane_requirement_failures(lane_spec, features)
    for failure in requirement_failures:
        score -= 22.0
        reasons.append(f"missing_{failure}")
    for required, key in [
        (lane_spec.prefer_stepwise_signal, "has_stepwise_signal"),
        (lane_spec.prefer_contrarian_signal, "has_contrarian_signal"),
    ]:
        if required and bool(features.get(key, False)):
            score += 6.0
            reasons.append(f"preferred_{key}")

    lane_id = lane_spec.lane_id
    if lane_id == "T01_release_decode":
        if features.get("has_release_signal", False) and features.get("has_official_source", False):
            score += 20.0
            reasons.append("release_official_alignment")
        if features.get("has_actionability_signal", False):
            score += 8.0
            reasons.append("actionability_alignment")
    elif lane_id == "T03_money_proof":
        score += 12.0 if features.get("has_money_signal", False) else -22.0
        reasons.append("money_signal_hit" if features.get("has_money_signal", False) else "money_signal_missing")
        if features.get("has_postmortem_signal", False):
            score += 10.0
            reasons.append("postmortem_signal_hit")
        else:
            score -= 25.0
            reasons.append("postmortem_signal_missing")
            score = min(score, 52.0)
    elif lane_id == "T04_failure_reversal":
        score += 12.0 if features.get("has_failure_signal", False) else -16.0
        reasons.append("failure_signal_hit" if features.get("has_failure_signal", False) else "failure_signal_missing")
    elif lane_id == "T05_benchmark":
        score += 12.0 if features.get("has_compare_signal", False) else -18.0
        reasons.append("compare_signal_hit" if features.get("has_compare_signal", False) else "compare_signal_missing")
    elif lane_id == "T06_capability_delivery":
        score += 10.0 if features.get("has_stepwise_signal", False) else -10.0
        reasons.append("stepwise_signal_hit" if features.get("has_stepwise_signal", False) else "stepwise_signal_missing")
    elif lane_id == "T07_contrarian_take":
        score += 12.0 if features.get("has_contrarian_signal", False) else -14.0
        reasons.append("contrarian_signal_hit" if features.get("has_contrarian_signal", False) else "contrarian_signal_missing")
    elif lane_id == "T08_signal_to_action":
        score += 10.0 if features.get("has_actionability_signal", False) else -14.0
        reasons.append("actionability_signal_hit" if features.get("has_actionability_signal", False) else "actionability_signal_missing")
        if int(features.get("family_count", 0)) >= 2:
            score += 5.0
            reasons.append("multi_source_window")
        else:
            score -= 5.0
            reasons.append("single_source_window")

    return round(clamp_score(score), 2), reasons


def estimate_lane_value(
    backend: Any,
    model: str,
    topic_statement: str,
    lane_id: str,
    lane_label: str,
) -> tuple[float, str]:
    """Lightweight LLM call: would this topic produce unique reader value from this lane's angle?"""
    prompt = json.dumps(
        {
            "task": "Score whether this topic, written from this lane angle, would give readers a unique judgment they can't get from a plain news summary.",
            "topic_statement": topic_statement[:300],
            "lane_id": lane_id,
            "lane_label": lane_label,
            "scoring_guide": [
                "90-100: The lane angle unlocks a judgment readers can't form themselves (e.g. adoption path, failure analysis, contrarian reframe).",
                "60-89: The lane angle adds some value but much of it overlaps with a plain summary.",
                "30-59: The lane angle is technically applicable but the article would read like a reformatted announcement.",
                "0-29: Forcing this topic into this lane would feel artificial.",
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value_score", "reason"],
        "properties": {
            "value_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "reason": {"type": "string"},
        },
    }
    try:
        result = backend.complete_json(
            model=model,
            system_prompt="You evaluate whether a topic-lane pairing would produce unique reader value. Return JSON only.",
            user_prompt=prompt,
            output_schema=schema,
        )
        return float(result.get("value_score", 50)), str(result.get("reason", ""))
    except Exception:
        return 50.0, "value_estimate_failed"


def build_lane_assignments(
    topic_cards: list[dict[str, Any]],
    signal_by_id: dict[str, dict[str, Any]],
    lane_specs: list[LaneSpec],
    topic_policy: TopicPolicy,
    *,
    value_backend: Any | None = None,
    value_model: str = "",
) -> list[dict[str, Any]]:
    assignments: list[dict[str, Any]] = []
    for card in topic_cards:
        signal_ids = card.get("cluster_signal_ids", [])
        signals = [signal_by_id[signal_id] for signal_id in signal_ids if signal_id in signal_by_id]
        features = topic_feature_snapshot(signals)
        topic_priority = float(card.get("topic_priority", 0.0))
        meets_topic_threshold = bool(card.get("eligible_for_write", False))

        lane_candidates: list[dict[str, Any]] = []
        for lane_spec in lane_specs:
            lane_fit_score, fit_reasons = lane_fit_score_for_spec(lane_spec=lane_spec, features=features)
            lane_final_score = round(
                clamp_score(topic_policy.lane_fit_weight * lane_fit_score + topic_policy.lane_topic_weight * topic_priority),
                2,
            )
            requirement_failures = lane_requirement_failures(lane_spec, features)
            high_fit_override = lane_fit_score >= 75.0
            medium_fit_override = lane_fit_score >= 55.0 and not requirement_failures
            # Soft requirement failures: don't block write, just flag for review
            has_hard_failure = any(f in {"require_hard_numbers"} for f in requirement_failures)
            eligible_for_write = bool(
                (meets_topic_threshold or high_fit_override or medium_fit_override)
                and lane_final_score >= 40.0
                and not has_hard_failure
            )
            requires_human_review = bool(lane_final_score < 50.0 or requirement_failures)
            lane_candidates.append(
                {
                    "lane_id": lane_spec.lane_id,
                    "lane_label": lane_spec.lane_label,
                    "framework_id": lane_spec.framework_id,
                    "submode_id": lane_spec.submode_id,
                    "composition_mode": lane_spec.composition_mode,
                    "generation_ratio": lane_spec.generation_ratio,
                    "rewrite_ratio": lane_spec.rewrite_ratio,
                    "lane_fit_score": lane_fit_score,
                    "lane_final_score": lane_final_score,
                    "rationale": " | ".join(fit_reasons) if fit_reasons else "",
                    "requirement_failures": requirement_failures,
                    "eligible_for_write": eligible_for_write,
                    "requires_human_review": requires_human_review,
                }
            )

        lane_candidates.sort(key=lambda item: item["lane_final_score"], reverse=True)

        # Value estimate: ask LLM if each lane angle produces unique reader value.
        if value_backend and value_model:
            topic_statement = str(card.get("topic_statement", "")).strip()
            for candidate in lane_candidates:
                value_score, value_reason = estimate_lane_value(
                    backend=value_backend,
                    model=value_model,
                    topic_statement=topic_statement,
                    lane_id=candidate["lane_id"],
                    lane_label=candidate["lane_label"],
                )
                candidate["value_score"] = round(value_score, 1)
                candidate["value_reason"] = value_reason
                # Recompute final score: fit 50% + value 30% + topic_priority 20%
                candidate["lane_final_score"] = round(
                    clamp_score(
                        0.5 * candidate["lane_fit_score"]
                        + 0.3 * value_score
                        + 0.2 * topic_priority
                    ),
                    2,
                )
            # Re-sort after value adjustment
            lane_candidates.sort(key=lambda item: item["lane_final_score"], reverse=True)

        selected = lane_candidates[0] if lane_candidates else {}
        assignments.append(
            {
                "schema_version": SCHEMA_VERSION,
                "topic_id": card["topic_id"],
                "selected_lane_id": selected.get("lane_id", ""),
                "framework_id": selected.get("framework_id", ""),
                "submode_id": selected.get("submode_id", ""),
                "composition_mode": selected.get("composition_mode", ""),
                "generation_ratio": selected.get("generation_ratio"),
                "rewrite_ratio": selected.get("rewrite_ratio"),
                "lane_fit_score": selected.get("lane_fit_score", 0.0),
                "topic_priority": topic_priority,
                "lane_final_score": selected.get("lane_final_score", 0.0),
                "rationale": selected.get("rationale", ""),
                "requires_human_review": bool(selected.get("requires_human_review", True)),
                "eligible_for_write": bool(selected.get("eligible_for_write", False)),
                "feature_snapshot": features,
                "lane_candidates": lane_candidates[:2],
                "lane_candidates_all": lane_candidates,
            }
        )
    return assignments


def apply_forced_lane_override(
    *,
    assignments: list[dict[str, Any]],
    lane_specs_by_id: dict[str, LaneSpec],
    force_topic_id: str,
    force_lane_id: str,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "applied": False,
        "force_topic_id": force_topic_id,
        "force_lane_id": force_lane_id,
        "reason": "",
    }
    if not force_topic_id or not force_lane_id:
        report["reason"] = "force_args_empty"
        return report

    target = next((item for item in assignments if str(item.get("topic_id", "")).strip() == force_topic_id), None)
    if target is None:
        report["reason"] = "topic_not_found"
        return report

    all_candidates = target.get("lane_candidates_all", []) or target.get("lane_candidates", [])
    forced_candidate = next(
        (item for item in all_candidates if str(item.get("lane_id", "")).strip() == force_lane_id),
        None,
    )
    lane_spec = lane_specs_by_id.get(force_lane_id)
    if forced_candidate is None and lane_spec is not None:
        forced_candidate = {
            "lane_id": lane_spec.lane_id,
            "lane_label": lane_spec.lane_label,
            "framework_id": lane_spec.framework_id,
            "submode_id": lane_spec.submode_id,
            "composition_mode": lane_spec.composition_mode,
            "generation_ratio": lane_spec.generation_ratio,
            "rewrite_ratio": lane_spec.rewrite_ratio,
            "lane_fit_score": target.get("lane_fit_score", 0.0),
            "lane_final_score": target.get("lane_final_score", 0.0),
            "rationale": "forced_lane_override_without_candidate",
            "requirement_failures": [],
            "eligible_for_write": bool(target.get("eligible_for_write", False)),
            "requires_human_review": bool(target.get("requires_human_review", True)),
        }
    if forced_candidate is None:
        report["reason"] = "lane_not_found"
        return report

    previous = {
        "selected_lane_id": target.get("selected_lane_id", ""),
        "framework_id": target.get("framework_id", ""),
        "submode_id": target.get("submode_id", ""),
    }
    target["selected_lane_id"] = forced_candidate.get("lane_id", force_lane_id)
    target["framework_id"] = forced_candidate.get("framework_id", lane_spec.framework_id if lane_spec else "")
    target["submode_id"] = forced_candidate.get("submode_id", lane_spec.submode_id if lane_spec else "")
    target["composition_mode"] = forced_candidate.get(
        "composition_mode",
        lane_spec.composition_mode if lane_spec else target.get("composition_mode", "mixed"),
    )
    target["generation_ratio"] = forced_candidate.get(
        "generation_ratio",
        lane_spec.generation_ratio if lane_spec else target.get("generation_ratio"),
    )
    target["rewrite_ratio"] = forced_candidate.get(
        "rewrite_ratio",
        lane_spec.rewrite_ratio if lane_spec else target.get("rewrite_ratio"),
    )
    target["lane_fit_score"] = forced_candidate.get("lane_fit_score", target.get("lane_fit_score", 0.0))
    target["lane_final_score"] = forced_candidate.get("lane_final_score", target.get("lane_final_score", 0.0))
    target["rationale"] = f"{target.get('rationale', '')} | forced_to_{force_lane_id}".strip(" |")
    target["requires_human_review"] = bool(forced_candidate.get("requires_human_review", target.get("requires_human_review", True)))
    target["eligible_for_write"] = bool(forced_candidate.get("eligible_for_write", target.get("eligible_for_write", False)))
    target["forced_lane_override"] = {
        "applied": True,
        "force_topic_id": force_topic_id,
        "force_lane_id": force_lane_id,
        "previous": previous,
        "forced_candidate": forced_candidate,
    }

    report["applied"] = True
    report["reason"] = "ok"
    report["previous"] = previous
    return report


def source_priority(signal: dict[str, Any]) -> tuple[int, int]:
    family = signal.get("source_family", "unknown")
    family_rank = {
        "official_x": 0,
        "article_x": 1,
        "github_trending": 2,
        "podcast": 3,
        "post_x": 4,
        "unknown": 5,
    }.get(family, 9)
    fact_count = len(signal.get("fact_candidates", []))
    return family_rank, -fact_count


def is_fact_eligible_family(family: str) -> bool:
    return str(family or "").strip().lower() not in HEAT_ONLY_FAMILIES


def signal_similarity(base: dict[str, Any], candidate: dict[str, Any]) -> int:
    score = 0
    base_release = set(str(item).lower() for item in base.get("release_signals", []))
    candidate_release = set(str(item).lower() for item in candidate.get("release_signals", []))
    if base_release and candidate_release and base_release.intersection(candidate_release):
        score += 3

    base_hosts = {host for host in base.get("linked_hosts", []) if host not in {"x.com", "nitter.net", "twitter.com"}}
    candidate_hosts = {host for host in candidate.get("linked_hosts", []) if host not in {"x.com", "nitter.net", "twitter.com"}}
    if base_hosts and candidate_hosts and base_hosts.intersection(candidate_hosts):
        score += 3

    base_entities = {clean_entity(item) for item in base.get("named_entities", [])}
    candidate_entities = {clean_entity(item) for item in candidate.get("named_entities", [])}
    base_entities.discard("")
    candidate_entities.discard("")
    if base_entities and candidate_entities and base_entities.intersection(candidate_entities):
        score += 2

    base_time = parse_iso_datetime(str(base.get("published_at", "")))
    candidate_time = parse_iso_datetime(str(candidate.get("published_at", "")))
    if base_time and candidate_time:
        gap = abs((base_time.astimezone(timezone.utc) - candidate_time.astimezone(timezone.utc)).total_seconds()) / 3600.0
        if gap <= 36:
            score += 1
    if base.get("source_family") != candidate.get("source_family"):
        score += 1
    return score


def strong_event_overlap(seed: dict[str, Any], candidate: dict[str, Any]) -> bool:
    # Host overlap is strong evidence — if both link to the same external page, same event.
    seed_hosts = set(event_external_hosts(seed))
    candidate_hosts = set(event_external_hosts(candidate))
    if seed_hosts and candidate_hosts and seed_hosts.intersection(candidate_hosts):
        return True

    # Entity overlap — but filter out broad domain entities that appear everywhere.
    seed_entities = {clean_entity(item) for item in seed.get("named_entities", [])}
    candidate_entities = {clean_entity(item) for item in candidate.get("named_entities", [])}
    seed_entities.discard("")
    candidate_entities.discard("")
    seed_entities = {item for item in seed_entities if item not in WEAK_EVENT_ENTITIES and len(item) >= 4}
    candidate_entities = {item for item in candidate_entities if item not in WEAK_EVENT_ENTITIES and len(item) >= 4}

    # Split into specific entities and broad domain entities
    seed_specific = {item for item in seed_entities if item not in BROAD_DOMAIN_ENTITIES}
    candidate_specific = {item for item in candidate_entities if item not in BROAD_DOMAIN_ENTITIES}

    # If they share a SPECIFIC entity (e.g. "claude-to-im-skills", "openclaw"), that's strong.
    if seed_specific and candidate_specific and seed_specific.intersection(candidate_specific):
        return True

    # If they only share BROAD entities (e.g. "claude code"), require additional evidence.
    seed_broad_match = seed_entities and candidate_entities and seed_entities.intersection(candidate_entities)
    if seed_broad_match:
        # Evidence 1: release_signal content overlap (same product/feature keyword)
        seed_release_text = " ".join(str(r).lower() for r in seed.get("release_signals", []))
        candidate_release_text = " ".join(str(r).lower() for r in candidate.get("release_signals", []))
        if seed_release_text and candidate_release_text:
            generic_verbs = {"更新", "发布", "推出", "上线", "新增", "开放", "update", "release", "launch", "new"}
            seed_tokens = {t for t in re.split(r"[\s,;.，。；]+", seed_release_text) if len(t) >= 3 and t not in generic_verbs}
            candidate_tokens = {t for t in re.split(r"[\s,;.，。；]+", candidate_release_text) if len(t) >= 3 and t not in generic_verbs}
            if seed_tokens and candidate_tokens and seed_tokens.intersection(candidate_tokens):
                return True

        # Evidence 2: same author (likely a thread about the same topic)
        seed_author = str(seed.get("author_id", "")).strip().lower()
        candidate_author = str(candidate.get("author_id", "")).strip().lower()
        if seed_author and candidate_author and seed_author == candidate_author:
            return True

        # Evidence 3: published within 6 hours (tight time window suggests same event)
        seed_time = parse_iso_datetime(str(seed.get("published_at", "")))
        candidate_time = parse_iso_datetime(str(candidate.get("published_at", "")))
        if seed_time and candidate_time:
            gap_hours = abs((seed_time.astimezone(timezone.utc) - candidate_time.astimezone(timezone.utc)).total_seconds()) / 3600.0
            if gap_hours <= 6.0:
                return True

    return False


def post_heat_score(signal: dict[str, Any], now_utc: datetime) -> float:
    fact_count = float(len(signal.get("fact_candidates", [])))
    release_hits = float(len(signal.get("release_signals", [])))
    text_words = float(signal.get("text_words", 0))
    published_at = parse_iso_datetime(str(signal.get("published_at", "")))
    if published_at is None:
        freshness = 10.0
    else:
        age_hours = max(0.0, (now_utc - published_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
        freshness = max(0.0, 100.0 - min(90.0, age_hours * 2.0))
    return freshness * 0.55 + fact_count * 2.0 + release_hits * 4.0 + min(20.0, text_words / 20.0)


def choose_related_signals(
    *,
    cluster_signals: list[dict[str, Any]],
    all_signals: list[dict[str, Any]],
    exclude_ids: set[str],
    needed: int,
    fact_only: bool = False,
) -> list[dict[str, Any]]:
    if needed <= 0:
        return []
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for candidate in all_signals:
        candidate_id = candidate["signal_id"]
        if candidate_id in exclude_ids:
            continue
        if fact_only and not is_fact_eligible_family(str(candidate.get("source_family", ""))):
            continue
        similarity = max(signal_similarity(base, candidate) for base in cluster_signals) if cluster_signals else 0
        if similarity < 3:
            continue
        fact_count = len(candidate.get("fact_candidates", []))
        ranked.append((similarity, fact_count, candidate))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)

    out: list[dict[str, Any]] = []
    for _, _, candidate in ranked:
        out.append(candidate)
        if len(out) >= needed:
            break
    return out


def has_user_impact_signal(text: str) -> bool:
    return bool(
        re.search(
            r"(users?|developer|developers|team|teams|student|students|college|workflow|"
            r"用户|开发者|团队|学生|企业|成本|效率|适合|适用|上手|使用场景|接入)",
            text,
            re.IGNORECASE,
        )
    )


def has_limit_or_risk_signal(text: str) -> bool:
    return bool(re.search(r"(limit|quota|pricing|beta|not available|风险|限制|暂不|不支持|门槛|代价)", text, re.IGNORECASE))


def build_source_bundles(
    topic_cards: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    signal_by_id: dict[str, dict[str, Any]],
    all_signals: list[dict[str, Any]],
    lane_specs_by_id: dict[str, LaneSpec],
    now_utc: datetime,
) -> list[dict[str, Any]]:
    topic_by_id = {card["topic_id"]: card for card in topic_cards}
    bundles: list[dict[str, Any]] = []

    for assignment in assignments:
        topic_id = assignment["topic_id"]
        card = topic_by_id.get(topic_id)
        if not card:
            continue
        selected_lane_id = str(assignment.get("selected_lane_id", "")).strip()
        lane_spec = lane_specs_by_id.get(selected_lane_id)
        if lane_spec is None:
            continue
        signals = [signal_by_id[signal_id] for signal_id in card.get("cluster_signal_ids", []) if signal_id in signal_by_id]
        ranked = sorted(signals, key=source_priority)
        fact_ranked = [
            signal
            for signal in ranked
            if is_fact_eligible_family(str(signal.get("source_family", "")))
        ]
        post_ranked = sorted(
            [
                signal
                for signal in ranked
                if str(signal.get("source_family", "")).strip().lower() in HEAT_ONLY_FAMILIES
            ],
            key=lambda item: post_heat_score(item, now_utc),
            reverse=True,
        )
        seed_ids = {signal["signal_id"] for signal in ranked}

        primary_raw = fact_ranked[: lane_spec.primary_sources_min]
        supporting_raw = fact_ranked[lane_spec.primary_sources_min : lane_spec.primary_sources_min + 5]

        if len(primary_raw) < lane_spec.primary_sources_min:
            need_primary = lane_spec.primary_sources_min - len(primary_raw)
            primary_extensions = choose_related_signals(
                cluster_signals=fact_ranked or ranked,
                all_signals=all_signals,
                exclude_ids=seed_ids,
                needed=need_primary,
                fact_only=True,
            )
            primary_raw.extend(primary_extensions)
            seed_ids.update(signal["signal_id"] for signal in primary_extensions)

        if len(supporting_raw) < lane_spec.supporting_sources_min:
            need_support = lane_spec.supporting_sources_min - len(supporting_raw)
            support_extensions = choose_related_signals(
                cluster_signals=fact_ranked or ranked,
                all_signals=all_signals,
                exclude_ids=seed_ids,
                needed=need_support,
                fact_only=True,
            )
            supporting_raw.extend(support_extensions)
            seed_ids.update(signal["signal_id"] for signal in support_extensions)

        # Keep hottest post_x only as supporting heat evidence (capped).
        post_supporting_cap = 2
        existing_support_ids = {item["signal_id"] for item in supporting_raw}
        for post_signal in post_ranked:
            if len(supporting_raw) >= 5:
                break
            if post_supporting_cap <= 0:
                break
            if post_signal["signal_id"] in existing_support_ids:
                continue
            supporting_raw.append(post_signal)
            existing_support_ids.add(post_signal["signal_id"])
            post_supporting_cap -= 1

        primary_sources = [
            {
                "signal_id": signal["signal_id"],
                "source_family": signal.get("source_family", "unknown"),
                "canonical_url": signal.get("canonical_url", ""),
                "title": signal.get("title", ""),
                "published_at": signal.get("published_at", ""),
                "source_item_path": signal.get("source_item_path", ""),
            }
            for signal in primary_raw
        ]
        supporting_sources = [
            {
                "signal_id": signal["signal_id"],
                "source_family": signal.get("source_family", "unknown"),
                "canonical_url": signal.get("canonical_url", ""),
                "title": signal.get("title", ""),
                "published_at": signal.get("published_at", ""),
                "source_item_path": signal.get("source_item_path", ""),
            }
            for signal in supporting_raw
        ]

        fact_anchors: list[dict[str, str]] = []
        for signal in fact_ranked:
            canonical_url = str(signal.get("canonical_url", "")).strip()
            for claim in signal.get("fact_candidates", []):
                clean_claim = normalize_space(claim)
                if not clean_claim or not canonical_url:
                    continue
                if not is_valid_fact_anchor_claim(clean_claim):
                    continue
                fact_anchors.append({"claim": clean_claim, "source_url": canonical_url, "signal_id": signal["signal_id"]})
                if len(fact_anchors) >= 30:
                    break
            if len(fact_anchors) >= 30:
                break
        if len(fact_anchors) < lane_spec.fact_anchors_min:
            existing_claims = {item["claim"] for item in fact_anchors}
            for signal in fact_ranked:
                canonical_url = str(signal.get("canonical_url", "")).strip()
                if not canonical_url:
                    continue
                fallback_claims = extract_claim_candidates_from_text(str(signal.get("text", "")), max_items=10)
                for claim in fallback_claims:
                    if claim in existing_claims:
                        continue
                    existing_claims.add(claim)
                    fact_anchors.append({"claim": claim, "source_url": canonical_url, "signal_id": signal["signal_id"]})
                    if len(fact_anchors) >= 30:
                        break
                if len(fact_anchors) >= 30:
                    break

        merged_text = " ".join(str(signal.get("text", "")) for signal in fact_ranked)
        has_release_action = any(len(signal.get("release_signals", [])) > 0 for signal in fact_ranked)
        has_delta_detail = any(signal.get("text_words", 0) >= 120 for signal in fact_ranked)
        has_user_impact = has_user_impact_signal(merged_text)
        has_limit_or_risk = has_limit_or_risk_signal(merged_text)
        has_official_primary = any(source.get("source_family") == "official_x" for source in primary_sources)
        feature_snapshot = assignment.get("feature_snapshot", {})

        requirement_checks = {
            "primary_sources_min_ok": len(primary_sources) >= lane_spec.primary_sources_min,
            "supporting_sources_min_ok": len(supporting_sources) >= lane_spec.supporting_sources_min,
            "fact_anchors_min_ok": len(fact_anchors) >= lane_spec.fact_anchors_min,
            "official_primary_required_ok": (not lane_spec.require_official_primary) or has_official_primary,
        }
        signal_requirement_checks = {
            "release_signal_required_ok": (not lane_spec.require_release_signal) or bool(feature_snapshot.get("has_release_signal", False)),
            "external_source_required_ok": (not lane_spec.require_external_source) or bool(feature_snapshot.get("has_external_source", False)),
            "hard_numbers_required_ok": (not lane_spec.require_hard_numbers) or bool(feature_snapshot.get("has_hard_numbers", False)),
            "compare_signal_required_ok": (not lane_spec.require_compare_signal) or bool(feature_snapshot.get("has_compare_signal", False)),
            "failure_signal_required_ok": (not lane_spec.require_failure_signal) or bool(feature_snapshot.get("has_failure_signal", False)),
            "actionability_signal_required_ok": (not lane_spec.require_actionability_signal) or bool(feature_snapshot.get("has_actionability_signal", False)),
        }
        coverage_checks = {
            "has_release_action": has_release_action,
            "has_delta_detail": has_delta_detail,
            "has_user_impact": has_user_impact,
            "has_limit_or_risk": has_limit_or_risk,
        }
        coverage_core_ok = bool(has_release_action and (has_delta_detail or has_user_impact))
        req_pass_count = sum(1 for v in requirement_checks.values() if v)
        sig_pass_count = sum(1 for v in signal_requirement_checks.values() if v)
        has_facts = len(fact_anchors) >= 1
        is_eligible = bool(assignment.get("eligible_for_write", False))

        # Tiered quality: all topics enter the pool, quality determines treatment
        if is_eligible and has_facts and has_delta_detail and has_user_impact and has_limit_or_risk:
            quality_tier = "A"
        elif is_eligible and has_facts and (has_delta_detail or has_user_impact):
            quality_tier = "B"
        elif has_facts and (has_delta_detail or has_user_impact or coverage_core_ok):
            quality_tier = "C"
        elif has_facts:
            quality_tier = "D"
        else:
            quality_tier = "E"

        # validity_gate: all topics with at least 1 fact anchor can enter writer
        validity_gate = bool(has_facts)
        ready_for_writer = validity_gate

        bundles.append(
            {
                "schema_version": SCHEMA_VERSION,
                "topic_id": topic_id,
                "lane_id": assignment.get("selected_lane_id", lane_spec.lane_id),
                "framework_id": assignment.get("framework_id", lane_spec.framework_id),
                "submode_id": assignment.get("submode_id", lane_spec.submode_id),
                "composition_mode": assignment.get("composition_mode", lane_spec.composition_mode),
                "primary_sources": primary_sources,
                "supporting_sources": supporting_sources,
                "fact_anchors": fact_anchors,
                "forbidden_claims": [
                    "No unsupported percentage claims about performance or cost change.",
                    "No unsupported claim that this release fully replaces existing workflows.",
                    "No unsupported claim that all teams should adopt immediately.",
                ],
                "lane_requirement_profile": {
                    "primary_sources_min": lane_spec.primary_sources_min,
                    "supporting_sources_min": lane_spec.supporting_sources_min,
                    "fact_anchors_min": lane_spec.fact_anchors_min,
                    "require_official_primary": lane_spec.require_official_primary,
                    "require_release_signal": lane_spec.require_release_signal,
                    "require_external_source": lane_spec.require_external_source,
                    "require_hard_numbers": lane_spec.require_hard_numbers,
                    "require_compare_signal": lane_spec.require_compare_signal,
                    "require_failure_signal": lane_spec.require_failure_signal,
                    "require_actionability_signal": lane_spec.require_actionability_signal,
                },
                "coverage_checks": coverage_checks,
                "coverage_core_ok": coverage_core_ok,
                "validity_gate": validity_gate,
                "quality_tier": quality_tier,
                "requirement_checks": requirement_checks,
                "signal_requirement_checks": signal_requirement_checks,
                "ready_for_writer": ready_for_writer,
            }
        )

    return bundles


def load_source_excerpt_from_path(source_item_path: str, max_chars: int = 5000) -> dict[str, Any]:
    path = Path(source_item_path).expanduser().resolve()
    if not path.exists():
        return {"source_item_path": source_item_path, "error": "source_item_not_found"}
    try:
        payload = load_json(path)
    except Exception as exc:  # pragma: no cover
        return {"source_item_path": source_item_path, "error": f"{type(exc).__name__}: {exc}"}
    full_text = normalize_space(payload.get("content", {}).get("full_text", ""))
    return {
        "source_id": payload.get("source_id", ""),
        "source_family": infer_source_family(path, payload),
        "canonical_url": payload.get("canonical_url", ""),
        "title": payload.get("title", ""),
        "published_at": payload.get("published_at", ""),
        "excerpt": full_text[:max_chars],
        "source_item_path": str(path),
    }


def clean_output_stages(out_root: Path) -> None:
    for name in ["01_signal_pool", "02_topic_cards", "03_lane_assignments", "04_source_bundles", "05_writer_inputs", "06_writer_packets"]:
        target = out_root / name
        if target.exists():
            shutil.rmtree(target)
    for name in ["topic_engine_manifest.json", "topic_ranking.json"]:
        file_path = out_root / name
        if file_path.exists():
            file_path.unlink()


def load_approved_topic_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    if path.suffix.lower() in {".json", ".jsonl"}:
        payload = load_json(path)
        if isinstance(payload, list):
            return {str(item).strip() for item in payload if str(item).strip()}
        if isinstance(payload, dict):
            items = payload.get("topic_ids", [])
            if isinstance(items, list):
                return {str(item).strip() for item in items if str(item).strip()}
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        ids.add(cleaned)
    return ids


def build_topic_ranking(
    *,
    topic_cards: list[dict[str, Any]],
    lane_assignments: list[dict[str, Any]],
    source_bundles: list[dict[str, Any]],
    writer_quota: int,
    approved_topic_ids: set[str],
    auto_select_topics: bool,
) -> dict[str, Any]:
    assignment_by_id = {item["topic_id"]: item for item in lane_assignments}
    bundle_by_id = {item["topic_id"]: item for item in source_bundles}
    ranking_rows: list[dict[str, Any]] = []

    for card in topic_cards:
        topic_id = card["topic_id"]
        assignment = assignment_by_id.get(topic_id, {})
        bundle = bundle_by_id.get(topic_id, {})
        lane_final = float(assignment.get("lane_final_score", 0.0))
        topic_priority = float(card.get("topic_priority", 0.0))
        fact_anchor_count = len(bundle.get("fact_anchors", []))
        quality_tier = str(bundle.get("quality_tier", "REJECT"))
        tier_bonus = {"A": 12.0, "B": 8.0, "C": 4.0, "D": 0.0, "E": -6.0}.get(quality_tier, -6.0)
        evidence_bonus = min(12.0, fact_anchor_count * 0.35)
        valid_for_pool = bool(bundle.get("validity_gate", False))
        ranking_score = lane_final * 0.55 + topic_priority * 0.35 + tier_bonus + evidence_bonus * 0.1
        if not valid_for_pool:
            ranking_score -= 25.0
        ranking_score = round(clamp_score(ranking_score), 2)
        ranking_rows.append(
            {
                "topic_id": topic_id,
                "event_seed_signal_id": card.get("event_seed_signal_id", ""),
                "topic_statement": card.get("topic_statement", ""),
                "cluster_signature": card.get("cluster_signature", ""),
                "source_families": card.get("source_families", []),
                "selected_lane_id": assignment.get("selected_lane_id", ""),
                "framework_id": assignment.get("framework_id", ""),
                "submode_id": assignment.get("submode_id", ""),
                "lane_candidates": assignment.get("lane_candidates", []),
                "topic_priority": topic_priority,
                "lane_final_score": lane_final,
                "quality_tier": quality_tier,
                "fact_anchor_count": fact_anchor_count,
                "valid_for_pool": valid_for_pool,
                "ranking_score": ranking_score,
            }
        )

    ranking_rows.sort(key=lambda item: item["ranking_score"], reverse=True)

    selected_topic_ids: list[str] = []
    if approved_topic_ids:
        # Human-approved topics should be allowed to enter writer even when validity_gate is false.
        approved_order = [row["topic_id"] for row in ranking_rows if row["topic_id"] in approved_topic_ids]
        selected_topic_ids = approved_order[: max(1, writer_quota)]
    elif auto_select_topics:
        # Lane-diverse selection: cap per lane to avoid all articles being the same type.
        max_per_lane = max(2, writer_quota // 3)
        lane_count: dict[str, int] = {}
        for row in ranking_rows:
            if not row["valid_for_pool"]:
                continue
            lane_id = row["selected_lane_id"]
            if lane_count.get(lane_id, 0) >= max_per_lane:
                continue
            selected_topic_ids.append(row["topic_id"])
            lane_count[lane_id] = lane_count.get(lane_id, 0) + 1
            if len(selected_topic_ids) >= max(1, writer_quota):
                break

    selected_set = set(selected_topic_ids)
    for row in ranking_rows:
        row["selected_for_writer"] = row["topic_id"] in selected_set

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "writer_quota": writer_quota,
        "auto_select_topics": auto_select_topics,
        "approved_topic_ids_count": len(approved_topic_ids),
        "review_required": bool(not approved_topic_ids and not auto_select_topics),
        "selected_topic_ids": selected_topic_ids,
        "count": len(ranking_rows),
        "ranking": ranking_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-item-root",
        action="append",
        required=True,
        help="Path containing source_item.json artifacts. Repeatable.",
    )
    parser.add_argument("--out-root", required=True, help="Output root for topic engine artifacts")
    parser.add_argument(
        "--policy-path",
        default="lane_v2/configs/lane_pilot/topic_engine_policy.v1.json",
        help="Path to lane-pilot topic policy config",
    )
    parser.add_argument(
        "--lane-map-path",
        default="lane_v2/configs/lane_pilot/lane_framework_map.v1.json",
        help="Path to lane-framework map config",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional max source_item files to process")
    parser.add_argument("--writer-quota", type=int, default=8, help="How many topics can enter writer per run")
    parser.add_argument(
        "--approved-topic-ids-file",
        default="",
        help="Optional file (json list / json{topic_ids[]} / txt lines) approved by human review",
    )
    parser.add_argument(
        "--auto-select-topics",
        action="store_true",
        help="Bypass manual review stop and auto-select top ranked topics",
    )
    parser.add_argument("--force-topic-id", default="", help="Force a specific topic_id to a lane (requires --force-lane-id)")
    parser.add_argument("--force-lane-id", default="", help="Force lane_id for --force-topic-id")
    parser.add_argument("--clean-stages", dest="clean_stages", action="store_true", default=True)
    parser.add_argument("--no-clean-stages", dest="clean_stages", action="store_false")
    parser.add_argument("--enable-value-estimate", action="store_true", default=False, help="Use LLM to estimate reader value per lane candidate (top 3)")
    parser.add_argument("--value-model", default="claude-haiku-4-5-20251001", help="Model for value estimation LLM calls (light task)")
    parser.add_argument("--value-backend", choices=["auto", "anthropic", "openai_compatible", "codex_cli"], default="auto")
    parser.add_argument("--value-api-base", default="https://api.openai.com/v1")
    parser.add_argument("--value-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--value-codex-binary", default="codex")
    parser.add_argument("--value-timeout-s", type=int, default=60)
    args = parser.parse_args()

    roots = [Path(value).expanduser().resolve() for value in args.source_item_root]
    out_root = Path(args.out_root).expanduser().resolve()
    policy_path = Path(args.policy_path).expanduser().resolve()
    lane_map_path = Path(args.lane_map_path).expanduser().resolve()
    approved_topic_ids_path = Path(args.approved_topic_ids_file).expanduser().resolve() if args.approved_topic_ids_file else None

    if args.clean_stages:
        clean_output_stages(out_root)

    source_item_paths = collect_source_item_paths(roots)
    if args.limit and args.limit > 0:
        source_item_paths = source_item_paths[: args.limit]

    policy = load_global_gate_policy(policy_path)
    topic_policy = load_topic_policy(policy_path)
    lane_specs = load_lane_specs(lane_map_path)
    lane_specs_by_id = {spec.lane_id: spec for spec in lane_specs}
    force_topic_id = str(args.force_topic_id or "").strip()
    force_lane_id = str(args.force_lane_id or "").strip()
    if bool(force_topic_id) ^ bool(force_lane_id):
        raise ValueError("force_topic_id and force_lane_id must be provided together")
    now_utc = utc_now()

    signal_items: list[dict[str, Any]] = []
    load_errors: list[dict[str, Any]] = []
    for path in source_item_paths:
        try:
            source_item = load_json(path)
            signal_items.append(build_signal_item(path, source_item))
        except Exception as exc:  # pragma: no cover
            load_errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    passed, rejected = apply_global_gate(signal_items, policy=policy, now_utc=now_utc)
    topic_cards = build_topic_cards(passed, topic_policy, now_utc, [spec.lane_id for spec in lane_specs])
    signal_by_id = {signal["signal_id"]: signal for signal in passed}
    # Optional: LLM-based value estimation for lane routing
    value_backend = None
    value_model = ""
    if args.enable_value_estimate:
        ROUTE_DIR = Path(__file__).resolve().parents[1] / "route"
        if str(ROUTE_DIR) not in sys.path:
            sys.path.insert(0, str(ROUTE_DIR))
        from route_framework_matches import choose_backend as route_choose_backend
        _, value_backend = route_choose_backend(
            backend=args.value_backend,
            api_key_env=args.value_api_key_env,
            api_base=args.value_api_base,
            timeout_s=args.value_timeout_s,
            bootstrap_decisions_file=None,
            codex_binary=args.value_codex_binary,
            codex_working_dir="/tmp",
            codex_reasoning_effort="low",
        )
        value_model = args.value_model
        print(f"Value estimation enabled: model={value_model}, backend={args.value_backend}")

    lane_assignments = build_lane_assignments(
        topic_cards, signal_by_id, lane_specs, topic_policy,
        value_backend=value_backend, value_model=value_model,
    )
    forced_lane_override_report = apply_forced_lane_override(
        assignments=lane_assignments,
        lane_specs_by_id=lane_specs_by_id,
        force_topic_id=force_topic_id,
        force_lane_id=force_lane_id,
    )
    source_bundles = build_source_bundles(topic_cards, lane_assignments, signal_by_id, passed, lane_specs_by_id, now_utc)

    signal_pool_path = out_root / "01_signal_pool/signal_pool.json"
    gate_report_path = out_root / "01_signal_pool/gate_report.json"
    topic_cards_root = out_root / "02_topic_cards"
    topic_manifest_path = topic_cards_root / "topic_card_manifest.json"
    lane_assignment_root = out_root / "03_lane_assignments"
    lane_assignment_manifest_path = lane_assignment_root / "lane_assignment_manifest.json"
    source_bundle_root = out_root / "04_source_bundles"
    source_bundle_manifest_path = source_bundle_root / "source_bundle_manifest.json"
    topic_ranking_path = out_root / "topic_ranking.json"
    manifest_path = out_root / "topic_engine_manifest.json"

    dump_json(
        signal_pool_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "count": len(passed),
            "signals": passed,
        },
    )

    dump_json(
        gate_report_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "policy": {
                "max_age_hours": policy.max_age_hours,
                "require_canonical_url": policy.require_canonical_url,
                "min_text_words": policy.min_text_words,
                "drop_if_exact_duplicate": policy.drop_if_exact_duplicate,
                "family_max_age_hours": policy.family_max_age_hours,
                "family_min_text_words": policy.family_min_text_words,
            },
            "input_count": len(signal_items),
            "passed_count": len(passed),
            "rejected_count": len(rejected),
            "load_error_count": len(load_errors),
            "rejected": rejected,
            "load_errors": load_errors,
        },
    )

    topic_rows: list[dict[str, Any]] = []
    topic_card_paths: dict[str, Path] = {}
    for card in topic_cards:
        topic_dir = topic_cards_root / card["topic_id"]
        card_path = topic_dir / "topic_card.json"
        dump_json(card_path, card)
        topic_card_paths[card["topic_id"]] = card_path
        topic_rows.append(
            {
                "topic_id": card["topic_id"],
                "topic_priority": card["topic_priority"],
                "eligible_for_write": card["eligible_for_write"],
                "topic_card_json": str(card_path),
            }
        )

    dump_json(
        topic_manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "count": len(topic_rows),
            "topics": topic_rows,
        },
    )

    lane_rows: list[dict[str, Any]] = []
    lane_assignment_paths: dict[str, Path] = {}
    for assignment in lane_assignments:
        topic_dir = lane_assignment_root / assignment["topic_id"]
        assignment_path = topic_dir / "lane_assignment.json"
        dump_json(assignment_path, assignment)
        lane_assignment_paths[assignment["topic_id"]] = assignment_path
        lane_rows.append(
            {
                "topic_id": assignment["topic_id"],
                "selected_lane_id": assignment["selected_lane_id"],
                "framework_id": assignment.get("framework_id", ""),
                "submode_id": assignment.get("submode_id", ""),
                "lane_final_score": assignment["lane_final_score"],
                "eligible_for_write": assignment["eligible_for_write"],
                "forced_lane_override": assignment.get("forced_lane_override", {}),
                "lane_candidates": assignment.get("lane_candidates", []),
                "lane_assignment_json": str(assignment_path),
            }
        )

    dump_json(
        lane_assignment_manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "count": len(lane_rows),
            "assignments": lane_rows,
        },
    )

    source_bundle_rows: list[dict[str, Any]] = []
    source_bundle_paths: dict[str, Path] = {}
    for bundle in source_bundles:
        topic_dir = source_bundle_root / bundle["topic_id"]
        bundle_path = topic_dir / "source_bundle.json"
        dump_json(bundle_path, bundle)
        source_bundle_paths[bundle["topic_id"]] = bundle_path
        source_bundle_rows.append(
            {
                "topic_id": bundle["topic_id"],
                "ready_for_writer": bundle["ready_for_writer"],
                "validity_gate": bundle.get("validity_gate", False),
                "quality_tier": bundle.get("quality_tier", "REJECT"),
                "primary_count": len(bundle.get("primary_sources", [])),
                "supporting_count": len(bundle.get("supporting_sources", [])),
                "fact_anchor_count": len(bundle.get("fact_anchors", [])),
                "source_bundle_json": str(bundle_path),
            }
        )

    dump_json(
        source_bundle_manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "count": len(source_bundle_rows),
            "bundles": source_bundle_rows,
        },
    )

    approved_topic_ids = load_approved_topic_ids(approved_topic_ids_path)
    ranking = build_topic_ranking(
        topic_cards=topic_cards,
        lane_assignments=lane_assignments,
        source_bundles=source_bundles,
        writer_quota=max(1, args.writer_quota),
        approved_topic_ids=approved_topic_ids,
        auto_select_topics=bool(args.auto_select_topics),
    )
    dump_json(topic_ranking_path, ranking)
    selected_topic_ids = set(ranking.get("selected_topic_ids", []))

    writer_input_root = out_root / "05_writer_inputs"
    writer_input_manifest_path = writer_input_root / "writer_input_manifest.json"
    writer_rows: list[dict[str, Any]] = []
    for bundle in source_bundles:
        topic_id = bundle["topic_id"]
        if topic_id not in selected_topic_ids:
            continue
        writer_rows.append(
            {
                "topic_id": topic_id,
                "topic_card_json": str(topic_card_paths.get(topic_id, Path(""))),
                "lane_assignment_json": str(lane_assignment_paths.get(topic_id, Path(""))),
                "source_bundle_json": str(source_bundle_paths.get(topic_id, Path(""))),
            }
        )
    dump_json(
        writer_input_manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "count": len(writer_rows),
            "selection_mode": (
                "approved_topic_ids_file"
                if approved_topic_ids
                else ("auto_select_topics" if args.auto_select_topics else "review_pending")
            ),
            "review_required": bool(ranking.get("review_required", False)),
            "writer_inputs": writer_rows,
        },
    )

    topic_cards_by_id = {card["topic_id"]: card for card in topic_cards}
    assignments_by_topic_id = {assignment["topic_id"]: assignment for assignment in lane_assignments}
    source_bundles_by_topic_id = {bundle["topic_id"]: bundle for bundle in source_bundles}
    writer_packet_root = out_root / "06_writer_packets"
    writer_packet_rows: list[dict[str, Any]] = []

    for row in writer_rows:
        topic_id = row["topic_id"]
        topic_card = topic_cards_by_id.get(topic_id, {})
        assignment = assignments_by_topic_id.get(topic_id, {})
        source_bundle = source_bundles_by_topic_id.get(topic_id, {})

        source_refs = []
        source_refs.extend(source_bundle.get("primary_sources", []))
        source_refs.extend(source_bundle.get("supporting_sources", []))
        seen_paths: set[str] = set()
        source_materials: list[dict[str, Any]] = []
        for source_ref in source_refs:
            source_item_path = str(source_ref.get("source_item_path", "")).strip()
            if not source_item_path or source_item_path in seen_paths:
                continue
            seen_paths.add(source_item_path)
            source_materials.append(load_source_excerpt_from_path(source_item_path))

        packet = {
            "schema_version": SCHEMA_VERSION,
            "topic_id": topic_id,
            "lane_id": assignment.get("selected_lane_id", ""),
            "framework_id": assignment.get("framework_id", ""),
            "submode_id": assignment.get("submode_id", ""),
            "composition_mode": assignment.get("composition_mode", ""),
            "generation_ratio": assignment.get("generation_ratio"),
            "rewrite_ratio": assignment.get("rewrite_ratio"),
            "topic_card": topic_card,
            "lane_assignment": assignment,
            "source_bundle": source_bundle,
            "source_materials": source_materials,
        }
        packet_path = writer_packet_root / topic_id / "writer_packet.json"
        dump_json(packet_path, packet)
        writer_packet_rows.append(
            {
                "topic_id": topic_id,
                "writer_packet_json": str(packet_path),
                "source_material_count": len(source_materials),
            }
        )

    writer_packet_manifest_path = writer_packet_root / "writer_packet_manifest.json"
    dump_json(
        writer_packet_manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "count": len(writer_packet_rows),
            "writer_packets": writer_packet_rows,
        },
    )

    dump_json(
        manifest_path,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": isoformat_z(now_utc),
            "input_roots": [str(path) for path in roots],
            "lane_spec_count": len(lane_specs),
            "lane_ids": [spec.lane_id for spec in lane_specs],
            "source_item_count": len(source_item_paths),
            "loaded_count": len(signal_items),
            "passed_count": len(passed),
            "rejected_count": len(rejected),
            "load_error_count": len(load_errors),
            "topic_count": len(topic_cards),
            "lane_assignment_count": len(lane_assignments),
            "source_bundle_count": len(source_bundles),
            "writer_ready_count": len(writer_rows),
            "writer_packet_count": len(writer_packet_rows),
            "review_required": bool(ranking.get("review_required", False)),
            "selected_topic_ids_count": len(selected_topic_ids),
            "forced_lane_override": forced_lane_override_report,
            "outputs": {
                "signal_pool_json": str(signal_pool_path),
                "gate_report_json": str(gate_report_path),
                "topic_manifest_json": str(topic_manifest_path),
                "lane_assignment_manifest_json": str(lane_assignment_manifest_path),
                "source_bundle_manifest_json": str(source_bundle_manifest_path),
                "topic_ranking_json": str(topic_ranking_path),
                "writer_input_manifest_json": str(writer_input_manifest_path),
                "writer_packet_manifest_json": str(writer_packet_manifest_path),
            },
        },
    )

    print(
        f"loaded={len(signal_items)} passed={len(passed)} rejected={len(rejected)} "
        f"topics={len(topic_cards)} lane_assignments={len(lane_assignments)} "
        f"source_bundles={len(source_bundles)} writer_ready={len(writer_rows)} "
        f"writer_packets={len(writer_packet_rows)} review_required={ranking.get('review_required', False)} "
        f"load_errors={len(load_errors)}"
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
