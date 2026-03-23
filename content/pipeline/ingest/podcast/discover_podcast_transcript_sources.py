from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from attach_podcast_transcript import build_transcript_source, load_json, preview, render_markdown, select_episode


URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
WORD_RE = re.compile(r"\b[\w\u4e00-\u9fff]+\b")
TRIGGER_RE = re.compile(
    r"(transcript|show notes|shownotes|notes|episode notes|full episode|read more|subtitle|subtitles|cc|youtube|youtu\.be)",
    re.IGNORECASE,
)
YOUTUBE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{6,})", re.IGNORECASE)


def read_text_from_url(url: str, timeout: int = 30) -> str:
    candidate = url.strip()
    if candidate.startswith("http://") or candidate.startswith("https://"):
        if not candidate.startswith("https://r.jina.ai/"):
            if candidate.startswith("http://"):
                candidate = "https://r.jina.ai/http://" + candidate[len("http://") :]
            else:
                candidate = "https://r.jina.ai/" + candidate
    req = urllib.request.Request(candidate, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore").strip()


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in URL_RE.findall(text):
        cleaned = raw.rstrip(").,;!?\"]}'")
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def normalize_youtube_url(url: str) -> str:
    match = YOUTUBE_RE.search(url)
    if not match:
        return ""
    video_id = match.group(1)
    return f"https://www.youtube.com/watch?v={video_id}"


def candidate_urls(page_text: str, origin_url: str) -> list[dict[str, str]]:
    urls = extract_urls(page_text)
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url: str, reason: str) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        candidates.append({"url": url, "reason": reason})

    if origin_url:
        add(origin_url, "origin_url")

    for url in urls:
        if TRIGGER_RE.search(url):
            add(url, "keyword_url")
            continue
        yt = normalize_youtube_url(url)
        if yt:
            add(yt, "youtube_url")

    for marker in ("Transcript", "Show Notes", "Episode Notes", "Read more", "YouTube"):
        if marker.lower() in page_text.lower():
            for url in urls:
                if marker.lower() in url.lower():
                    add(url, f"{marker.lower()}_match")

    return candidates


def score_text(text: str, episode_title: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    wc = word_count(text)
    if wc >= 300:
        score += 3
        reasons.append(f"word_count={wc}")
    elif wc >= 120:
        score += 1
        reasons.append(f"word_count={wc}")

    lowered = text.lower()
    if "transcript" in lowered:
        score += 3
        reasons.append("contains_transcript")
    if "show notes" in lowered or "shownotes" in lowered:
        score += 2
        reasons.append("contains_show_notes")
    if "featuring:" in lowered or "links:" in lowered or "summary" in lowered:
        score += 1
        reasons.append("structured_notes")
    if episode_title.lower().split("—")[0].strip()[:40] and episode_title.lower().split("—")[0].strip()[:40] in lowered:
        score += 1
        reasons.append("title_overlap")
    return score, reasons


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def fetch_youtube_subtitles(url: str, work_dir: Path) -> tuple[str, dict[str, Any]]:
    if not yt_dlp_available():
        raise RuntimeError("yt-dlp is not installed")
    work_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(work_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--write-auto-sub",
        "--write-sub",
        "--sub-lang",
        "zh-Hans,zh,en",
        "--convert-subs",
        "vtt",
        "--skip-download",
        "-o",
        out_template,
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    vtt_files = sorted(work_dir.glob("*.vtt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not vtt_files:
        raise FileNotFoundError("yt-dlp completed but no .vtt subtitle file was created")
    return vtt_files[0].read_text(encoding="utf-8", errors="ignore"), {
        "method": "yt-dlp",
        "subtitle_file": str(vtt_files[0]),
        "command": cmd,
    }


def select_best_candidate(
    episode: dict[str, Any],
    page_text: str,
    page_url: str,
    candidate_rows: list[dict[str, str]],
    max_candidates: int,
    work_dir: Path,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    evaluated: list[dict[str, Any]] = []
    episode_title = episode.get("title", "")

    def evaluate(url: str, reason: str) -> None:
        if not url:
            return
        row: dict[str, Any] = {"url": url, "reason": reason, "status": "pending"}
        try:
            if "youtube.com/watch" in url or "youtu.be/" in url:
                text, extra = fetch_youtube_subtitles(url, work_dir / "youtube")
                score, reasons = score_text(text, episode_title)
                row.update(
                    {
                        "status": "ok",
                        "score": score + 2,
                        "score_reasons": reasons + ["youtube_subtitle"],
                        "text": text,
                        "attachment_mode": "subtitle_auto",
                        "transcript_url": url,
                        "fulltext_path": extra.get("subtitle_file", ""),
                        "evidence": extra,
                    }
                )
            else:
                text = read_text_from_url(url)
                score, reasons = score_text(text, episode_title)
                row.update(
                    {
                        "status": "ok",
                        "score": score,
                        "score_reasons": reasons,
                        "text": text,
                        "attachment_mode": "show_notes_auto" if "show" in reason.lower() or "note" in reason.lower() else "page_auto",
                        "transcript_url": url,
                        "fulltext_path": url,
                    }
                )
        except Exception as exc:
            row.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        evaluated.append(row)

    score, reasons = score_text(page_text, episode_title)
    evaluated.append(
        {
            "url": page_url,
            "reason": "origin_url",
            "status": "ok",
            "score": score,
            "score_reasons": reasons,
            "text": page_text,
            "attachment_mode": "origin_page_auto",
            "transcript_url": page_url,
            "fulltext_path": page_url,
        }
    )

    for row in candidate_rows[:max_candidates]:
        url = row["url"]
        evaluate(url, row.get("reason", "candidate"))

    best = max((row for row in evaluated if row.get("status") == "ok"), key=lambda row: row.get("score", 0), default=None)
    if best is None:
        return "", {"status": "not_found", "evaluated": evaluated}, evaluated

    text = best.get("text", "")
    meta = {
        "status": "direct",
        "chosen_url": best.get("url", ""),
        "attachment_mode": best.get("attachment_mode", "origin_page_auto"),
        "score": best.get("score", 0),
        "score_reasons": best.get("score_reasons", []),
        "fulltext_path": best.get("fulltext_path", ""),
        "transcript_url": best.get("transcript_url", ""),
        "evidence": best.get("evidence", {}),
        "evaluated": evaluated,
        "text": text,
    }
    return text, meta, evaluated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-catalog", required=True, help="Path to episode_catalog.json")
    parser.add_argument("--out-root", required=True, help="Directory where discovered transcript sources will be written")
    parser.add_argument("--max-candidates", type=int, default=5, help="Maximum discovered links to evaluate per episode")
    parser.add_argument(
        "--min-word-count",
        type=int,
        default=120,
        help="Minimum word count to treat a readable page as usable transcript/show notes",
    )
    args = parser.parse_args()

    catalog_path = Path(args.episode_catalog).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    catalog = load_json(catalog_path)
    episodes = catalog.get("episodes", [])
    results: list[dict[str, Any]] = []

    for index, episode in enumerate(episodes, 1):
        episode_dir = out_root / episode.get("source_id", f"episode-{index}")
        episode_dir.mkdir(parents=True, exist_ok=True)
        origin_url = episode.get("origin_url", "")
        row: dict[str, Any] = {
            "index": index,
            "source_id": episode.get("source_id", ""),
            "show_label": episode.get("show_label", ""),
            "origin_url": origin_url,
            "status": "pending",
            "out_dir": str(episode_dir),
            "candidate_urls": [],
        }

        try:
            page_text = read_text_from_url(origin_url)
            candidates = candidate_urls(page_text, origin_url)
            row["candidate_urls"] = candidates

            text, meta, evaluated = select_best_candidate(
                episode=episode,
                page_text=page_text,
                page_url=origin_url,
                candidate_rows=candidates,
                max_candidates=args.max_candidates,
                work_dir=episode_dir / "_work",
            )
            row["evaluated_count"] = len(evaluated)
            row["discovery"] = meta

            if meta.get("status") != "direct" or word_count(text) < args.min_word_count:
                row["status"] = "candidate_only" if candidates else "not_found"
                if meta.get("status") == "direct":
                    row["status"] = "weak_direct"
                row["note"] = "Readable page found, but transcript threshold not met." if text else "No usable transcript/page found."
                continue

            payload = build_transcript_source(
                catalog_path=catalog_path,
                episode=episode,
                transcript_text=text,
                transcript_path=None,
                transcript_url=meta.get("transcript_url") or meta.get("chosen_url") or origin_url,
                attachment_mode=meta.get("attachment_mode", "origin_page_auto"),
            )
            payload["source_record"]["discovery_mode"] = "auto_discover"
            payload["source_record"]["discovery_evidence"] = {
                "chosen_url": meta.get("chosen_url", ""),
                "score": meta.get("score", 0),
                "score_reasons": meta.get("score_reasons", []),
                "evaluated_count": len(evaluated),
            }
            out_json = episode_dir / "transcript_source.json"
            out_md = episode_dir / "transcript_source.md"
            out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            out_md.write_text(
                render_markdown(payload["source_record"], payload["transcript"], preview(text)),
                encoding="utf-8",
            )

            row.update(
                {
                    "status": "direct",
                    "output_json": str(out_json),
                    "output_md": str(out_md),
                    "word_count": payload["transcript"]["word_count"],
                    "source_record": payload["source_record"],
                }
            )
        except Exception as exc:
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        results.append(row)
        print(f"[{index}/{len(episodes)}] {episode.get('source_id', '')} -> {row['status']}")

    manifest = {
        "schema_version": "0.1.0",
        "catalog_ref": str(catalog_path),
        "count": len(results),
        "direct_count": sum(1 for row in results if row.get("status") == "direct"),
        "candidate_only_count": sum(1 for row in results if row.get("status") == "candidate_only"),
        "weak_direct_count": sum(1 for row in results if row.get("status") == "weak_direct"),
        "not_found_count": sum(1 for row in results if row.get("status") == "not_found"),
        "error_count": sum(1 for row in results if row.get("status") == "error"),
        "results": results,
    }
    manifest_path = out_root / "transcript_discovery_manifest.json"
    manifest_md = out_root / "transcript_discovery_manifest.md"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_md.write_text(
        "\n".join(
            [
                "# Transcript Discovery Manifest",
                "",
                f"- Catalog: {catalog_path}",
                f"- Direct: {manifest['direct_count']}",
                f"- Candidate only: {manifest['candidate_only_count']}",
                f"- Weak direct: {manifest['weak_direct_count']}",
                f"- Not found: {manifest['not_found_count']}",
                f"- Errors: {manifest['error_count']}",
                "",
            ]
            + [
                f"- {row.get('source_id', '')} | {row.get('status', '')} | {row.get('out_dir', '')}"
                + (f" | {row.get('error', '')}" if row.get("error") else "")
                for row in results
            ]
        ),
        encoding="utf-8",
    )

    print(manifest_path)
    print(manifest_md)
    print(
        f"direct={manifest['direct_count']} candidate_only={manifest['candidate_only_count']} weak_direct={manifest['weak_direct_count']} not_found={manifest['not_found_count']} errors={manifest['error_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
