from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from jsonschema import validate as jsonschema_validate
except Exception:  # pragma: no cover - optional runtime dependency
    jsonschema_validate = None


SCHEMA_VERSION = "0.1.0"
WHITESPACE_RE = re.compile(r"\s+")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
METRIC_RE = re.compile(
    r"\$\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s?(?:k|m|b|million|billion|hours?|days?|weeks?|months?|years?|mins?|minutes?)\b",
    re.IGNORECASE,
)
TITLE_ENTITY_RE = re.compile(r"\b(?:[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9&.-]+){0,3}|[A-Z]{2,}(?:\s+[A-Z]{2,}){0,2})\b")
SPEAKER_RE = re.compile(r"^([A-Z][A-Za-z0-9 .'\-]{1,40}):(?:\[[0-9:]+\])?\s*(.+)$")

RELEASE_KEYWORDS = [
    "launch",
    "launched",
    "release",
    "released",
    "announced",
    "update",
    "updated",
    "rollout",
    "ship",
    "shipped",
    "introducing",
]
TASK_HINT_PATTERNS = {
    "installation": [r"\binstall\b", r"\bsetup\b", r"\bconfigure\b", r"\bconfig\b"],
    "workflow": [r"\bworkflow\b", r"\bpipeline\b", r"\bprocess\b", r"\bsteps\b"],
    "tutorial": [r"\bhow to\b", r"\bguide\b", r"\btutorial\b"],
    "comparison": [r"\bvs\b", r"\bcompare\b", r"\bcomparison\b", r"\bbenchmark\b"],
    "release": [r"\blaunch\b", r"\brelease\b", r"\bannounced\b", r"\bupdate\b"],
    "opinion_decode": [r"\bmeans\b", r"\bwhy\b", r"\bthink\b", r"\bopinion\b", r"\bwhat happens\b"],
    "interview": [r"\bguest\b", r"\bhost\b", r"\binterview\b", r"\bfeaturing\b"],
}
STOP_ENTITIES = {
    "Title",
    "URL Source",
    "Markdown Content",
    "More episodes",
    "Share",
    "Subscribe",
    "Download",
    "Links",
    "Upcoming Events",
    "Transcript",
    "Episode Details",
    "Creators and Guests",
    "What Is",
}
PARTICIPANT_SECTION_HEADERS = {
    "Featuring",
    "Featuring:",
    "Creators and Guests",
    "Creators & Guests",
}
PARTICIPANT_SECTION_BREAKERS = {
    "Links",
    "Links:",
    "Upcoming Events",
    "Upcoming Events:",
    "Show Notes",
    "Show Notes:",
    "Sponsors",
    "Sponsors:",
    "Episode Details",
    "Episode",
    "Transcript",
    "What is Practical AI?",
    "What Is Practical AI?",
    "Follow",
}
PERSON_NAME_RE = re.compile(r"^[A-Z][a-zA-Z.'-]+$")
PARTICIPANT_NAME_STOP_WORDS = {
    "Published",
    "Time",
    "Episode",
    "Transcript",
    "Summary",
    "Sponsors",
    "Links",
    "Follow",
    "Menu",
    "Search",
    "Home",
    "About",
}
GENERIC_ENTITY_WORDS = {
    "What",
    "When",
    "Where",
    "Why",
    "How",
    "In",
    "On",
    "At",
    "We",
    "I",
    "The",
    "A",
    "An",
    "And",
    "But",
    "If",
    "This",
    "That",
    "These",
    "Those",
    "Age",
    "Links",
    "Featuring",
    "Follow",
    "Transcript",
    "Guest",
    "Host",
}
NOISE_LINE_PATTERNS = [
    re.compile(r"^Copied to clipboard$", re.IGNORECASE),
    re.compile(r"^Share Copied to clipboard$", re.IGNORECASE),
    re.compile(r"^Embed Copied to clipboard$", re.IGNORECASE),
    re.compile(r"^RSS Feed URL Copied!?$", re.IGNORECASE),
    re.compile(r"^Start at$", re.IGNORECASE),
    re.compile(r"^/\s*$"),
]
SUMMARY_CUTOFF_MARKERS = [
    "Featuring:",
    "Links:",
    "Upcoming Events:",
    "**Brought to you by:**",
    "Brought to you by:",
    "SUBMISSIONS CLOSING SOON",
    "Learn more about AGENT MADNESS:",
    "The AI Daily Brief helps you understand",
    "Our Newsletter is BACK:",
    "Interested in sponsoring the show?",
]
EPISODE_PAGE_CUTOFF_MARKERS = [
    "\n**SUBMISSIONS CLOSING SOON",
    "\n**Learn more about AGENT MADNESS",
    "\n**Brought to you by:**",
    "\nBrought to you by:",
    "\n**Interested in sponsoring the show?**",
    "\nInterested in sponsoring the show?",
    "\nThe AI Daily Brief helps you understand",
    "\nOur Newsletter is BACK:",
]
DATE_SECTION_RE = re.compile(r"(?m)^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def compact_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = normalize_space(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def clean_summary_text(text: str) -> tuple[str, list[str]]:
    cleaned = normalize_space(text)
    if not cleaned:
        return "", []
    notes: list[str] = []
    cutoff = len(cleaned)
    for marker in SUMMARY_CUTOFF_MARKERS:
        index = cleaned.find(marker)
        if index != -1 and index < cutoff:
            cutoff = index
    if cutoff != len(cleaned):
        cleaned = cleaned[:cutoff].rstrip(" -–|,;")
        notes.append("Trimmed summary at first non-core marker.")
    return cleaned, notes


def has_transcript_cues(text: str) -> bool:
    if re.search(r"(?m)^####\s+Transcript\s*$", text):
        return True
    if re.search(r"(?m)^[A-Z][A-Za-z0-9 .'\-]{1,40}:(?:\[[0-9:]+\])?", text):
        return True
    return False


def trim_episode_page_noise(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if has_transcript_cues(text):
        return text, notes

    trimmed = text
    cutoff = len(trimmed)
    for marker in EPISODE_PAGE_CUTOFF_MARKERS:
        index = trimmed.find(marker)
        if index != -1 and index < cutoff:
            cutoff = index
    if cutoff != len(trimmed):
        trimmed = trimmed[:cutoff].rstrip()
        notes.append("Trimmed episode page at sponsor/footer marker.")

    heading_positions = [match.start() for match in re.finditer(r"(?m)^####\s+", trimmed)]
    if len(heading_positions) >= 2:
        trimmed = trimmed[: heading_positions[1]].rstrip()
        notes.append("Trimmed episode page before second content heading.")

    date_positions = [match.start() for match in DATE_SECTION_RE.finditer(trimmed)]
    if len(date_positions) >= 2:
        trimmed = trimmed[: date_positions[1]].rstrip()
        notes.append("Trimmed episode page before second date-stamped section.")

    return trimmed, notes


def clean_full_text(text: str, source_kind: str = "", title: str = "") -> tuple[str, list[str]]:
    notes: list[str] = []
    cleaned = text.replace("\r\n", "\n")
    if cleaned.startswith("Title:"):
        lines = cleaned.splitlines()
        filtered: list[str] = []
        for line in lines:
            if line.startswith("Title: "):
                notes.append("Removed Jina title wrapper.")
                continue
            if line.startswith("URL Source: "):
                notes.append("Removed Jina URL wrapper.")
                continue
            if line.startswith("Markdown Content:"):
                notes.append("Removed Jina markdown wrapper.")
                continue
            filtered.append(line)
        cleaned = "\n".join(filtered)
    cleaned = IMAGE_RE.sub("", cleaned)
    cleaned = LINK_RE.sub(r"\1", cleaned)
    filtered_lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            filtered_lines.append("")
            continue
        if any(pattern.match(line) for pattern in NOISE_LINE_PATTERNS):
            notes.append(f"Removed noise line: {line}")
            continue
        if "%3A%2F%2F" in line:
            notes.append("Removed encoded social/share URL line.")
            continue
        if line.startswith("[]("):
            notes.append("Removed empty markdown link line.")
            continue
        if line.startswith("Listen On**") or line.startswith("Subscribe**"):
            notes.append("Removed platform CTA line.")
            continue
        if line.startswith("**SUBMISSIONS CLOSING SOON") or line.startswith("**Learn more about AGENT MADNESS"):
            notes.append("Removed promo line.")
            continue
        if line.count("http") >= 2 and len(line.split()) < 12:
            notes.append("Removed dense URL-only line.")
            continue
        filtered_lines.append(raw_line)
    cleaned = "\n".join(filtered_lines)
    if source_kind == "podcast_transcript":
        cleaned, extra_notes = trim_episode_page_noise(cleaned)
        notes.extend(extra_notes)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, compact_list(notes)


def extract_sections(text: str, limit: int = 24) -> list[str]:
    sections: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_space(raw_line)
        if not line or len(line) > 140:
            continue
        if line.endswith(":") and len(line.split()) <= 10:
            sections.append(line)
            continue
        if line.startswith("#"):
            sections.append(line.lstrip("# ").strip())
            continue
        if TIMESTAMP_RE.search(line) and len(line.split()) <= 18:
            sections.append(line)
    return compact_list(sections)[:limit]


def extract_raw_quotes(text: str, limit: int = 5) -> list[dict[str, str]]:
    quotes: list[dict[str, str]] = []
    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
        line = normalize_space(raw_line)
        match = SPEAKER_RE.match(line)
        if not match:
            continue
        speaker = normalize_space(match.group(1))
        quote_text = normalize_space(match.group(2))
        if not quote_text:
            for next_line in lines[index + 1 : index + 4]:
                candidate = normalize_space(next_line)
                if candidate:
                    quote_text = candidate
                    break
        if len(quote_text.split()) < 10:
            continue
        quotes.append(
            {
                "text": f"{speaker}: {quote_text}",
                "why_it_matters": "Direct source quote for routing and fact preservation.",
            }
        )
        if len(quotes) >= limit:
            break
    return quotes


def extract_named_entities(*texts: str, limit: int = 20) -> list[str]:
    entities: list[str] = []
    for text in texts:
        for match in TITLE_ENTITY_RE.findall(text):
            entity = normalize_space(match)
            if entity in STOP_ENTITIES:
                continue
            if "http" in entity.lower():
                continue
            if len(entity.split()) == 1 and entity in GENERIC_ENTITY_WORDS:
                continue
            if len(entity) <= 1:
                continue
            entities.append(entity)
    return compact_list(entities)[:limit]


def extract_metric_signals(*texts: str, limit: int = 20) -> list[str]:
    metrics: list[str] = []
    for text in texts:
        metrics.extend(METRIC_RE.findall(text))
    return compact_list(metrics)[:limit]


def extract_release_signals(*texts: str) -> list[str]:
    joined = " ".join(texts).lower()
    return [keyword for keyword in RELEASE_KEYWORDS if keyword in joined]


def extract_task_hints(source_kind: str, title: str, summary: str, text: str, participants: list[dict[str, str]]) -> list[str]:
    joined = " ".join([source_kind, title, summary, text[:4000]]).lower()
    hints = ["podcast"] if "podcast" in source_kind else []
    if participants:
        hints.append("interview")
    for hint, patterns in TASK_HINT_PATTERNS.items():
        if any(re.search(pattern, joined) for pattern in patterns):
            hints.append(hint)
    return compact_list(hints)


def extract_fact_anchors(title: str, published_at: str, metrics: list[str], entities: list[str], summary: str) -> list[str]:
    anchors: list[str] = []
    if title:
        anchors.append(title)
    if published_at:
        anchors.append(published_at)
    anchors.extend(metrics[:8])
    anchors.extend(entities[:10])
    summary_sentence = summary.split(".")[0].strip()
    if summary_sentence:
        anchors.append(summary_sentence)
    return compact_list(anchors)[:20]


def collect_participant_context_blocks(summary: str, text: str) -> list[str]:
    blocks: list[str] = []

    inline_match = re.search(r"Featuring:\s*(.*?)(?:Links:|Upcoming Events:|$)", f"{summary}\n{text[:4000]}", re.IGNORECASE | re.DOTALL)
    if inline_match:
        blocks.append(normalize_space(inline_match.group(1)))

    lines = text.splitlines()
    collecting = False
    current: list[str] = []
    for raw_line in lines:
        line = normalize_space(raw_line)
        if not line:
            if collecting and current:
                current.append("")
            continue
        if line in PARTICIPANT_SECTION_HEADERS:
            collecting = True
            current = []
            continue
        if collecting and line in PARTICIPANT_SECTION_BREAKERS:
            if current:
                blocks.append("\n".join(current))
            collecting = False
            current = []
            continue
        if collecting:
            current.append(line)
            if len(current) >= 30:
                blocks.append("\n".join(current))
                collecting = False
                current = []
    if collecting and current:
        blocks.append("\n".join(current))

    return compact_list(blocks)


def looks_like_person_name(name: str) -> bool:
    cleaned = normalize_space(name)
    if not cleaned or any(char.isdigit() for char in cleaned):
        return False
    words = cleaned.split()
    if not 1 <= len(words) <= 3:
        return False
    if any(word in PARTICIPANT_NAME_STOP_WORDS for word in words):
        return False
    if any(word.isupper() and len(word) > 2 for word in words):
        return False
    return all(PERSON_NAME_RE.match(word) for word in words)


def extract_participants(summary: str, text: str) -> list[dict[str, Any]]:
    participants: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for line in text.splitlines():
        current = normalize_space(line)
        if not current or len(current) > 80:
            continue
        if current in {"Host", "Guest", "Speaker", "Narrator"}:
            continue
    role_blocks = re.findall(r"\n(Host|Guest)\n\n?([A-Z][A-Za-z .'\-]{2,60})", text)
    for role, name in role_blocks:
        cleaned_name = normalize_space(name)
        if cleaned_name in seen_names:
            continue
        seen_names.add(cleaned_name)
        participants.append(
            {
                "name": cleaned_name,
                "role": role.lower(),
                "handle": None,
                "profile_url": None,
            }
        )

    for block in collect_participant_context_blocks(summary, text):
        for name in re.findall(r"([A-Z][A-Za-z .'\-]{2,60})\s+[-–]", block):
            cleaned_name = normalize_space(name)
            if cleaned_name in seen_names:
                continue
            seen_names.add(cleaned_name)
            participants.append(
                {
                    "name": cleaned_name,
                    "role": "guest",
                    "handle": None,
                    "profile_url": None,
                }
            )

    if not participants:
        transcript_lines = text.splitlines()
        transcript_start = 0
        for index, raw_line in enumerate(transcript_lines):
            if normalize_space(raw_line) == "Transcript":
                transcript_start = index + 1
                break
        for raw_line in transcript_lines[transcript_start : transcript_start + 240]:
            match = SPEAKER_RE.match(normalize_space(raw_line))
            if not match:
                continue
            name = match.group(1)
            cleaned_name = normalize_space(name)
            if not looks_like_person_name(cleaned_name):
                continue
            if cleaned_name in seen_names or cleaned_name in STOP_ENTITIES:
                continue
            seen_names.add(cleaned_name)
            participants.append(
                {
                    "name": cleaned_name,
                    "role": "speaker",
                    "handle": None,
                    "profile_url": None,
                }
            )
            if len(participants) >= 4:
                break
    return participants[:8]


def choose_primary_text_source(source_kind: str, attachment_mode: str, text: str, metadata_only: bool) -> str:
    if metadata_only:
        return "rss_summary"
    lowered = text.lower()
    if "subtitle" in attachment_mode:
        return "subtitles"
    if "show_notes" in attachment_mode:
        return "show_notes"
    if "transcript" in lowered or re.search(r"^[A-Z][A-Za-z0-9 .'\-]{1,40}:\[[0-9:]+\]", text, re.MULTILINE):
        return "transcript"
    return "show_notes" if "show notes" in lowered else "episode_page"


def build_source_assets(record: dict[str, Any], transcript_meta: dict[str, Any] | None, selected_url: str, selected_kind: str) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []

    def add(asset_kind: str, url: str, selected_for_text: bool = False, notes: str | None = None) -> None:
        url = normalize_space(url)
        if not url:
            return
        for existing in assets:
            if existing["asset_kind"] == asset_kind and existing["url"] == url:
                if selected_for_text:
                    existing["selected_for_text"] = True
                if notes and not existing.get("notes"):
                    existing["notes"] = notes
                return
        assets.append(
            {
                "asset_kind": asset_kind,
                "url": url,
                "selected_for_text": selected_for_text,
                "notes": notes,
            }
        )

    add("rss_feed", record.get("feed_url", ""))
    add("episode_page", record.get("origin_url", ""), selected_for_text=selected_kind == "episode_page")
    add("audio", record.get("audio_url", ""))
    if transcript_meta:
        if transcript_meta.get("path"):
            asset_kind = "subtitle" if transcript_meta["path"].endswith((".vtt", ".srt")) else "transcript"
            add(asset_kind, transcript_meta["path"], selected_for_text=True, notes=transcript_meta.get("attachment_mode"))
        if transcript_meta.get("source_url"):
            add(selected_kind, transcript_meta["source_url"], selected_for_text=selected_url == transcript_meta["source_url"], notes=transcript_meta.get("attachment_mode"))
    elif selected_url:
        add("rss_feed", record.get("feed_url", ""), selected_for_text=True, notes="metadata-only RSS summary source")
    return assets


def build_source_item_from_transcript(path: Path, schema_version: str) -> dict[str, Any]:
    payload = load_json(path)
    record = payload["source_record"]
    transcript_meta = payload.get("transcript", {})
    raw_text = payload.get("text", "")
    summary_text, summary_notes = clean_summary_text(record.get("summary", ""))
    cleaned_text, clean_notes = clean_full_text(raw_text, record.get("source_type", ""), record.get("title", ""))
    participants = extract_participants(summary_text, cleaned_text)
    primary_text_source = choose_primary_text_source(record.get("source_type", ""), transcript_meta.get("attachment_mode", ""), cleaned_text, False)
    source_assets = build_source_assets(record, transcript_meta, transcript_meta.get("source_url", ""), primary_text_source)
    metrics = extract_metric_signals(record.get("title", ""), summary_text, cleaned_text[:10000])
    entities = extract_named_entities(record.get("title", ""), summary_text, cleaned_text[:5000])
    task_hints = extract_task_hints(record.get("source_type", ""), record.get("title", ""), summary_text, cleaned_text, participants)
    normalization_notes = summary_notes + clean_notes + [f"Built from transcript_source.json: {path}"]

    return {
        "schema_version": schema_version,
        "source_id": record["source_id"],
        "fetched_at": payload.get("generated_at") or isoformat_z(utc_now()),
        "platform": "podcast",
        "source_kind": record.get("source_type", "podcast_transcript"),
        "canonical_url": record.get("origin_url", ""),
        "author": {
            "handle": None,
            "display_name": record.get("show_label") or record.get("author"),
            "account_url": None,
        },
        "title": record.get("title"),
        "language": record.get("language") or "unknown",
        "published_at": record.get("published_at"),
        "participants": participants,
        "source_assets": source_assets,
        "content": {
            "primary_text_source": primary_text_source,
            "summary": summary_text,
            "full_text": cleaned_text,
            "sections": extract_sections(cleaned_text),
            "raw_quotes": extract_raw_quotes(cleaned_text),
            "assembly_notes": "; ".join(compact_list(normalization_notes + [f"Primary text source selected: {primary_text_source}."])),
        },
        "extracted_signals": {
            "release_signals": extract_release_signals(record.get("title", ""), summary_text, cleaned_text[:5000]),
            "metric_signals": metrics,
            "named_entities": entities,
            "task_hints": task_hints,
            "fact_anchors": extract_fact_anchors(record.get("title", ""), record.get("published_at", ""), metrics, entities, summary_text),
            "normalization_notes": "; ".join(compact_list(normalization_notes)),
        },
    }


def build_source_item_from_episode(episode: dict[str, Any], fetched_at: str, schema_version: str) -> dict[str, Any]:
    summary_text = normalize_space(episode.get("summary", ""))
    title = episode.get("title", "")
    full_text = "\n\n".join([part for part in [title, summary_text] if part]).strip()
    participants = extract_participants(summary_text, summary_text)
    metrics = extract_metric_signals(title, summary_text)
    entities = extract_named_entities(title, summary_text)
    notes = [
        "Metadata-only source item built from RSS episode catalog.",
        "full_text contains title plus RSS summary only.",
        "Not suitable for rewrite until transcript or show notes are attached.",
    ]
    return {
        "schema_version": schema_version,
        "source_id": episode["source_id"],
        "fetched_at": fetched_at,
        "platform": "podcast",
        "source_kind": episode.get("source_type", "podcast_episode_metadata"),
        "canonical_url": episode.get("origin_url", ""),
        "author": {
            "handle": None,
            "display_name": episode.get("show_label") or episode.get("author"),
            "account_url": None,
        },
        "title": episode.get("title"),
        "language": episode.get("language") or "unknown",
        "published_at": episode.get("published_at"),
        "participants": participants,
        "source_assets": build_source_assets(episode, None, episode.get("feed_url", ""), "rss_feed"),
        "content": {
            "primary_text_source": "rss_summary",
            "summary": summary_text or None,
            "full_text": full_text or title or episode.get("origin_url", ""),
            "sections": [],
            "raw_quotes": [],
            "assembly_notes": "; ".join(notes),
        },
        "extracted_signals": {
            "release_signals": extract_release_signals(title, summary_text),
            "metric_signals": metrics,
            "named_entities": entities,
            "task_hints": extract_task_hints(episode.get("source_type", ""), title, summary_text, summary_text, participants),
            "fact_anchors": extract_fact_anchors(title, episode.get("published_at", ""), metrics, entities, summary_text),
            "normalization_notes": "; ".join(notes),
        },
    }


def load_schema(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return load_json(path)


def validate_payload(payload: dict[str, Any], schema: dict[str, Any] | None) -> str | None:
    if schema is None or jsonschema_validate is None:
        return None
    try:
        jsonschema_validate(payload, schema)
    except Exception as exc:  # pragma: no cover - validation detail surfacing
        return f"{type(exc).__name__}: {exc}"
    return None


def write_source_item(output_dir: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_json = output_dir / "source_item.json"
    out_md = output_dir / "source_item.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = [
        f"# {payload.get('title') or payload['source_id']}",
        "",
        f"- Source ID: {payload['source_id']}",
        f"- Platform: {payload['platform']}",
        f"- Source Kind: {payload['source_kind']}",
        f"- Canonical URL: {payload['canonical_url']}",
        f"- Published: {payload.get('published_at', '')}",
        f"- Primary Text Source: {payload['content'].get('primary_text_source', '')}",
        f"- Participants: {len(payload.get('participants', []))}",
        "",
        "## Summary",
        payload["content"].get("summary") or "",
        "",
        "## Fact Anchors",
    ]
    for item in payload["extracted_signals"].get("fact_anchors", []):
        md_lines.append(f"- {item}")
    out_md.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
    return out_json, out_md


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-catalog", required=True, help="Path to episode_catalog.json")
    parser.add_argument("--transcript-root", help="Directory containing transcript_source.json artifacts")
    parser.add_argument("--out-root", required=True, help="Directory where source_item artifacts will be written")
    parser.add_argument("--include-metadata-only", action="store_true", help="Also emit source_item.json for metadata-only episodes without transcript sources")
    parser.add_argument(
        "--schema-path",
        default="framework/SOURCE_ITEM_SCHEMA.json",
        help="Path to SOURCE_ITEM_SCHEMA.json for validation",
    )
    args = parser.parse_args()

    catalog_path = Path(args.episode_catalog).expanduser().resolve()
    transcript_root = Path(args.transcript_root).expanduser().resolve() if args.transcript_root else None
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    schema_path = Path(args.schema_path).expanduser().resolve() if args.schema_path else None

    catalog = load_json(catalog_path)
    schema = load_schema(schema_path)
    results: list[dict[str, Any]] = []
    transcript_ids: set[str] = set()

    transcript_paths = sorted(transcript_root.glob("**/transcript_source.json")) if transcript_root and transcript_root.exists() else []
    for path in transcript_paths:
        payload = build_source_item_from_transcript(path, SCHEMA_VERSION)
        validation_error = validate_payload(payload, schema)
        output_dir = out_root / payload["source_id"]
        out_json, out_md = write_source_item(output_dir, payload)
        transcript_ids.add(payload["source_id"])
        row = {
            "source_id": payload["source_id"],
            "status": "ok" if validation_error is None else "schema_error",
            "kind": payload["source_kind"],
            "output_json": str(out_json),
            "output_md": str(out_md),
            "validation_error": validation_error,
        }
        results.append(row)
        print(f"[transcript] {payload['source_id']} -> {row['status']}")

    if args.include_metadata_only:
        fetched_at = catalog.get("generated_at") or isoformat_z(utc_now())
        for episode in catalog.get("episodes", []):
            if episode["source_id"] in transcript_ids:
                continue
            payload = build_source_item_from_episode(episode, fetched_at, SCHEMA_VERSION)
            validation_error = validate_payload(payload, schema)
            output_dir = out_root / payload["source_id"]
            out_json, out_md = write_source_item(output_dir, payload)
            row = {
                "source_id": payload["source_id"],
                "status": "ok" if validation_error is None else "schema_error",
                "kind": payload["source_kind"],
                "output_json": str(out_json),
                "output_md": str(out_md),
                "validation_error": validation_error,
            }
            results.append(row)
            print(f"[metadata] {payload['source_id']} -> {row['status']}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "episode_catalog_ref": str(catalog_path),
        "transcript_root": str(transcript_root) if transcript_root else "",
        "out_root": str(out_root),
        "count": len(results),
        "ok_count": sum(1 for row in results if row["status"] == "ok"),
        "schema_error_count": sum(1 for row in results if row["status"] == "schema_error"),
        "results": results,
    }
    manifest_path = out_root / "source_item_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(manifest_path)
    print(f"ok={manifest['ok_count']} schema_errors={manifest['schema_error_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
