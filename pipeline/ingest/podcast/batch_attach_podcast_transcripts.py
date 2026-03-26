from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from attach_podcast_transcript import (
    build_transcript_source,
    load_json,
    load_transcript_text,
    load_transcript_text_from_url,
    render_markdown,
    select_episode,
    preview,
    isoformat_z,
    utc_now,
)


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str, limit: int = 64) -> str:
    cleaned = SLUG_RE.sub("-", value.lower()).strip("-")
    if not cleaned:
        return "item"
    return cleaned[:limit].strip("-") or "item"


def read_jobs(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, dict):
        for key in ("jobs", "items", "tasks"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise ValueError("Jobs file must be a list or a JSON object with a jobs/items/tasks array")


def resolve_path(base_dir: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def render_batch_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Podcast Transcript Batch Attach",
        "",
        f"- Status: {result.get('status', '')}",
        f"- Source ID: {result.get('source_id', '')}",
        f"- Attachment Mode: {result.get('attachment_mode', '')}",
        f"- Output Dir: {result.get('output_dir', '')}",
        f"- Transcript Words: {result.get('word_count', 0)}",
        f"- Error: {result.get('error', '')}",
        "",
    ]
    if result.get("summary"):
        lines.extend(["## Summary", result["summary"], ""])
    if result.get("transcript_preview"):
        lines.extend(["## Transcript Preview", result["transcript_preview"], ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-catalog", required=True, help="Path to episode_catalog.json")
    parser.add_argument("--jobs-file", required=True, help="JSON file containing batch transcript jobs")
    parser.add_argument("--out-root", required=True, help="Directory under which per-job outputs will be written")
    parser.add_argument(
        "--manifest-name",
        default="batch_transcript_manifest.json",
        help="Filename for the batch manifest in out-root",
    )
    args = parser.parse_args()

    catalog_path = Path(args.episode_catalog).expanduser().resolve()
    jobs_path = Path(args.jobs_file).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    catalog = load_json(catalog_path)
    jobs = read_jobs(jobs_path)

    results: list[dict[str, Any]] = []
    base_dir = jobs_path.parent

    for index, job in enumerate(jobs, 1):
        source_id = str(job.get("source_id") or "").strip()
        origin_url = str(job.get("origin_url") or "").strip()
        attachment_mode = str(job.get("attachment_mode") or "manual_dropin").strip() or "manual_dropin"
        transcript_file = str(job.get("transcript_file") or "").strip()
        transcript_url = str(job.get("transcript_url") or "").strip()
        explicit_out_dir = str(job.get("out_dir") or "").strip()
        label = str(job.get("label") or source_id or origin_url or f"job-{index}").strip()
        out_dir = resolve_path(out_root, explicit_out_dir) if explicit_out_dir else out_root / slugify(label)
        out_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Any] = {
            "index": index,
            "label": label,
            "source_id": source_id,
            "origin_url": origin_url,
            "attachment_mode": attachment_mode,
            "out_dir": str(out_dir),
            "status": "pending",
        }

        try:
            if not source_id and not origin_url:
                raise ValueError("One of source_id or origin_url is required")
            episode = select_episode(catalog, source_id or None, origin_url or None)

            transcript_text = ""
            transcript_path: Path | None = None
            if transcript_file:
                transcript_path = resolve_path(base_dir, transcript_file)
                transcript_text = load_transcript_text(transcript_path)
            elif transcript_url:
                transcript_text = load_transcript_text_from_url(transcript_url)
            else:
                raise ValueError("One of transcript_file or transcript_url is required")

            payload = build_transcript_source(
                catalog_path=catalog_path,
                episode=episode,
                transcript_text=transcript_text,
                transcript_path=transcript_path,
                transcript_url=transcript_url,
                attachment_mode=attachment_mode,
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

            result.update(
                {
                    "status": "ok",
                    "source_type": source_record.get("source_type", ""),
                    "source_fetch_status": source_record.get("fetch_status", ""),
                    "source_eligibility": source_record.get("eligibility", ""),
                    "word_count": transcript_meta.get("word_count", 0),
                    "output_json": str(out_json),
                    "output_md": str(out_md),
                    "source_record": source_record,
                }
            )
        except Exception as exc:
            result.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})

        results.append(result)
        print(f"[{index}/{len(jobs)}] {label} -> {result['status']}")

    manifest = {
        "schema_version": "0.1.0",
        "generated_at": isoformat_z(utc_now()),
        "catalog_ref": str(catalog_path),
        "jobs_ref": str(jobs_path),
        "count": len(results),
        "ok_count": sum(1 for row in results if row.get("status") == "ok"),
        "error_count": sum(1 for row in results if row.get("status") != "ok"),
        "results": results,
    }
    manifest_path = out_root / args.manifest_name
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_lines = [
        "# Podcast Transcript Batch Attach",
        "",
        f"- Catalog: {catalog_path}",
        f"- Jobs: {jobs_path}",
        f"- Count: {manifest['count']}",
        f"- OK: {manifest['ok_count']}",
        f"- Errors: {manifest['error_count']}",
        "",
    ]
    for row in results:
        summary_lines.append(f"- {row.get('label', '')} | {row.get('status', '')} | {row.get('out_dir', '')}")
        if row.get("error"):
            summary_lines.append(f"  - {row['error']}")
    (out_root / "batch_transcript_manifest.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(manifest_path)
    print(out_root / "batch_transcript_manifest.md")
    print(f"ok={manifest['ok_count']} errors={manifest['error_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
