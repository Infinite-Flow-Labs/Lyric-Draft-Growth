from __future__ import annotations

import argparse
import html
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.1.0"
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
VTT_TIMECODE_RE = re.compile(r"^\s*\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}")
SRT_TIMECODE_RE = re.compile(r"^\s*\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    value = html.unescape(value)
    return WHITESPACE_RE.sub(" ", value).strip()


def strip_markup(text: str) -> str:
    return normalize_text(HTML_TAG_RE.sub(" ", text))


def fetch_url_text(url: str, timeout: int = 30) -> str:
    candidate = url.strip()
    if candidate.startswith("http://") or candidate.startswith("https://"):
        if not candidate.startswith("https://r.jina.ai/"):
            candidate = "https://r.jina.ai/" + candidate
    req = urllib.request.Request(candidate, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore").strip()


def load_subtitle_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.upper() == "WEBVTT":
            continue
        if stripped.isdigit():
            continue
        if VTT_TIMECODE_RE.match(stripped) or SRT_TIMECODE_RE.match(stripped):
            continue
        if stripped.startswith(("NOTE", "STYLE", "REGION")):
            continue
        stripped = strip_markup(stripped)
        if stripped:
            lines.append(stripped)
    return "\n".join(lines).strip()


def load_transcript_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for key in ("text", "transcript", "content", "body"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        raise ValueError("JSON transcript file must contain one of: text, transcript, content, body")
    if suffix in {".vtt", ".srt"}:
        return load_subtitle_text(path)
    return path.read_text(encoding="utf-8").strip()


def load_transcript_text_from_url(url: str) -> str:
    text = fetch_url_text(url)
    if not text:
        raise ValueError(f"Empty transcript content from URL: {url}")
    return text


def word_count(text: str) -> int:
    return len([token for token in text.split() if token])


def line_count(text: str) -> int:
    return len(text.splitlines())


def preview(text: str, limit: int = 800) -> str:
    compact = text.strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def select_episode(catalog: dict[str, Any], source_id: str | None, origin_url: str | None) -> dict[str, Any]:
    episodes = catalog.get("episodes", [])
    if source_id:
        for episode in episodes:
            if episode.get("source_id") == source_id:
                return episode
        raise ValueError(f"source_id not found: {source_id}")
    if origin_url:
        for episode in episodes:
            if episode.get("origin_url") == origin_url:
                return episode
        raise ValueError(f"origin_url not found: {origin_url}")
    raise ValueError("One of --source-id or --origin-url is required")


def render_markdown(source: dict[str, Any], transcript_meta: dict[str, Any], transcript_preview: str) -> str:
    lines = [
        f"# {source.get('title', 'Podcast Transcript Source')}",
        "",
        f"- Show: {source.get('show_label', '')}",
        f"- Published: {source.get('published_at', '')}",
        f"- Origin URL: {source.get('origin_url', '')}",
        f"- Transcript Path: {transcript_meta.get('path', '')}",
        f"- Transcript URL: {transcript_meta.get('source_url', '')}",
        f"- Word Count: {transcript_meta.get('word_count', 0)}",
        f"- Line Count: {transcript_meta.get('line_count', 0)}",
        "",
        "## Summary",
        source.get("summary", ""),
        "",
        "## Transcript Preview",
        transcript_preview,
        "",
    ]
    return "\n".join(lines)


def build_transcript_source(
    *,
    catalog_path: Path,
    episode: dict[str, Any],
    transcript_text: str,
    transcript_path: Path | None,
    transcript_url: str,
    attachment_mode: str,
) -> dict[str, Any]:
    transcript_meta = {
        "path": str(transcript_path) if transcript_path else "",
        "source_url": transcript_url,
        "attachment_mode": attachment_mode,
        "char_count": len(transcript_text),
        "word_count": word_count(transcript_text),
        "line_count": line_count(transcript_text),
        "attached_at": isoformat_z(utc_now()),
    }

    source_record = dict(episode)
    source_record["source_type"] = "podcast_transcript"
    source_record["fulltext_path"] = str(transcript_path) if transcript_path else transcript_url
    source_record["eligibility"] = "direct_draft_source"
    source_record["fetch_status"] = "transcript_attached"
    if transcript_url:
        source_record["fulltext_url"] = transcript_url

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat_z(utc_now()),
        "episode_catalog_ref": str(catalog_path),
        "source_record": source_record,
        "transcript": transcript_meta,
        "text": transcript_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-catalog", required=True, help="Path to episode_catalog.json")
    parser.add_argument("--transcript-file", help="Path to transcript .txt, .md, .vtt, .srt, or .json file")
    parser.add_argument("--transcript-url", help="Remote transcript/show-notes URL to fetch through a readable proxy")
    parser.add_argument("--out-dir", required=True, help="Output directory for transcript_source artifacts")
    parser.add_argument("--source-id", help="Episode source_id from episode_catalog.json")
    parser.add_argument("--origin-url", help="Episode origin URL from episode_catalog.json")
    parser.add_argument(
        "--attachment-mode",
        default="manual_dropin",
        help="How this transcript was attached, for example manual_dropin, show_notes, subtitle_export.",
    )
    args = parser.parse_args()

    catalog_path = Path(args.episode_catalog).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.transcript_file and not args.transcript_url:
        raise ValueError("One of --transcript-file or --transcript-url is required")

    catalog = load_json(catalog_path)
    episode = select_episode(catalog, args.source_id, args.origin_url)
    transcript_path: Path | None = None
    transcript_text = ""
    if args.transcript_file:
        transcript_path = Path(args.transcript_file).expanduser().resolve()
        transcript_text = load_transcript_text(transcript_path)
    else:
        transcript_text = load_transcript_text_from_url(args.transcript_url or "")
    payload = build_transcript_source(
        catalog_path=catalog_path,
        episode=episode,
        transcript_text=transcript_text,
        transcript_path=transcript_path,
        transcript_url=args.transcript_url or "",
        attachment_mode=args.attachment_mode,
    )
    source_record = payload["source_record"]
    transcript_meta = payload["transcript"]

    out_json = out_dir / "transcript_source.json"
    out_md = out_dir / "transcript_source.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(
        render_markdown(source_record, transcript_meta, preview(transcript_text)),
        encoding="utf-8",
    )

    print(out_json)
    print(out_md)
    print(f"source_id={source_record['source_id']} words={transcript_meta['word_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
