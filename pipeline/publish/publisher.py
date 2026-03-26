from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.publish.assemble_queues import choose_candidates, dump_json, load_json
from pipeline.writer.formatter import validate_article_publish_contract


ACCOUNTS_RUNTIME = ROOT / "accounts_runtime"
DISTRIBUTION_MANIFESTS = ROOT / "distribution_runtime/manifests"
PIPELINE_PUBLISH_DIR = ROOT / "content/pipeline/publish"


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_csv_set(raw: str) -> set[str]:
    return {part.strip() for part in str(raw or "").split(",") if part.strip()}


def parse_bool_phases(args: argparse.Namespace) -> tuple[bool, bool, bool]:
    phases = (bool(args.prepare_images), bool(args.assemble), bool(args.publish))
    if any(phases):
        return phases
    return (True, True, True)


def image_assets_ready(article_dir: Path) -> bool:
    brief_path = article_dir / "article_image_brief.json"
    if not brief_path.exists():
        return False
    cover_candidates = [
        article_dir / "image_assets/cover_01/result_1.png",
        article_dir / "image_assets/cover_01/result_1.jpg",
        article_dir / "image_assets/cover_01/result_1.jpeg",
        article_dir / "image_assets/cover_01/result_1.webp",
    ]
    return any(path.exists() for path in cover_candidates)


def run_image_pipeline_for_article(article_json: Path, args: argparse.Namespace) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(PIPELINE_PUBLISH_DIR / "run_article_image_pipeline.py"),
        "--article",
        str(article_json),
        "--max-inline",
        str(args.max_inline),
    ]
    if args.generate_images:
        cmd.append("--generate")
        cmd.extend(["--engine", args.image_engine])
        cmd.extend(["--api-key-env", args.image_api_key_env])
        cmd.extend(["--api-base-url", args.image_api_base_url])
        cmd.extend(["--model", args.image_model])
        if args.image_baoyu_script:
            cmd.extend(["--baoyu-script", args.image_baoyu_script])
        if args.image_baoyu_runtime:
            cmd.extend(["--baoyu-runtime", args.image_baoyu_runtime])
        if args.image_baoyu_provider:
            cmd.extend(["--baoyu-provider", args.image_baoyu_provider])
        if args.image_callback_url:
            cmd.extend(["--callback-url", args.image_callback_url])
        cmd.extend(["--timeout-seconds", str(args.image_timeout_seconds)])
        cmd.extend(["--poll-interval", str(args.image_poll_interval)])
        if args.image_wait:
            cmd.append("--wait")
        if args.image_dry_run:
            cmd.append("--dry-run")

    started_at = isoformat_z(datetime.now(timezone.utc))
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    finished_at = isoformat_z(datetime.now(timezone.utc))

    row: dict[str, Any] = {
        "article_json": str(article_json),
        "command": cmd,
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
    }
    if completed.returncode != 0:
        row["status"] = "error"
        return row

    payload: dict[str, Any] = {}
    stdout = (completed.stdout or "").strip()
    if stdout:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                    break
                except Exception:
                    continue
    row["status"] = "ok"
    row["result"] = payload
    return row


def phase_prepare_images(args: argparse.Namespace) -> dict[str, Any]:
    families = parse_csv_set(args.families)
    source_ids = parse_csv_set(args.source_ids)
    candidates = choose_candidates(
        families=families,
        include_human_review_required=bool(args.include_human_review_required),
        source_ids=source_ids or None,
    )
    if args.image_prepare_limit > 0:
        candidates = candidates[: args.image_prepare_limit]

    results: list[dict[str, Any]] = []
    for article in candidates:
        article_json = Path(str(article.get("article_json", ""))).expanduser().resolve()
        if not article_json.exists():
            results.append(
                {
                    "status": "missing_article_json",
                    "article_json": str(article_json),
                    "source_id": article.get("source_id", ""),
                }
            )
            continue

        article_dir = article_json.parent
        if (not args.force_image_refresh) and image_assets_ready(article_dir):
            results.append(
                {
                    "status": "skipped_assets_ready",
                    "article_json": str(article_json),
                    "source_id": article.get("source_id", ""),
                }
            )
            continue

        run_row = run_image_pipeline_for_article(article_json, args)
        run_row["source_id"] = article.get("source_id", "")
        run_row["family"] = article.get("family", "")
        run_row["run_id"] = article.get("run_id", "")
        results.append(run_row)

    payload = {
        "phase": "prepare_images",
        "generated_at": isoformat_z(datetime.now(timezone.utc)),
        "families": sorted(families),
        "source_ids": sorted(source_ids),
        "candidate_count": len(candidates),
        "generate_images": bool(args.generate_images),
        "results": results,
        "ok_count": len([row for row in results if row.get("status") == "ok"]),
        "error_count": len([row for row in results if row.get("status") == "error"]),
    }
    return payload


def phase_assemble(args: argparse.Namespace) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "content.pipeline.publish.assemble_account_queues",
        "--date",
        args.date,
        "--families",
        args.families,
        "--per-account-max",
        str(args.per_account_max),
    ]
    if args.source_ids.strip():
        cmd.extend(["--source-ids", args.source_ids])
    if args.include_human_review_required:
        cmd.append("--include-human-review-required")
    if args.assemble_dry_run:
        cmd.append("--dry-run")

    started_at = isoformat_z(datetime.now(timezone.utc))
    env = os.environ.copy()
    py_path = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = f"{str(ROOT)}:{py_path}" if py_path else str(ROOT)
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False, env=env)
    finished_at = isoformat_z(datetime.now(timezone.utc))

    payload = {
        "phase": "assemble_queues",
        "generated_at": finished_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
    }
    if completed.returncode != 0:
        payload["status"] = "error"
        return payload

    payload["status"] = "ok"
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    if lines:
        payload["plan_path"] = lines[0]
    if len(lines) > 1:
        payload["manifest_path"] = lines[1]
    if len(lines) > 2:
        payload["summary"] = lines[2]
    return payload


@dataclass(frozen=True)
class PublishTarget:
    account_id: str
    publisher_account: str
    bit_port: int
    accounts_csv_path: Path
    queue_dir: Path
    published_dir: Path


@dataclass(frozen=True)
class QueueJob:
    target: PublishTarget
    slot_dir: Path
    job_path: Path
    payload: dict[str, Any]


def load_publish_targets(accounts_filter: set[str] | None) -> list[PublishTarget]:
    targets: list[PublishTarget] = []
    default_csv = (ACCOUNTS_RUNTIME / "accounts_bitbrowser.csv").resolve()
    for account_dir in sorted(ACCOUNTS_RUNTIME.iterdir()):
        if not account_dir.is_dir() or account_dir.name.startswith("_"):
            continue
        profile_path = account_dir / "profile/account_profile.json"
        publisher_path = account_dir / "profile/publisher_config.json"
        if not profile_path.exists() or not publisher_path.exists():
            continue
        profile = load_json(profile_path)
        if not bool(profile.get("enabled", True)):
            continue
        account_id = str(profile.get("account_id", "")).strip()
        if not account_id:
            continue
        if accounts_filter and account_id not in accounts_filter:
            continue
        publisher = load_json(publisher_path)
        if str(publisher.get("publisher_type", "")).strip() != "x_post_bitbrowser":
            continue
        accounts_csv_raw = str(publisher.get("accounts_csv_path", "")).strip()
        accounts_csv_path = Path(accounts_csv_raw).expanduser().resolve() if accounts_csv_raw else default_csv
        bit_port_raw = publisher.get("bit_port")
        bit_port = int(bit_port_raw) if str(bit_port_raw or "").strip() else 54345
        targets.append(
            PublishTarget(
                account_id=account_id,
                publisher_account=str(publisher.get("publisher_account") or account_id).strip(),
                bit_port=bit_port,
                accounts_csv_path=accounts_csv_path,
                queue_dir=account_dir / "publish_queue",
                published_dir=account_dir / "published",
            )
        )
    return targets


def iter_queue_jobs(target: PublishTarget, *, date_text: str) -> list[QueueJob]:
    date_dir = target.queue_dir / date_text
    if not date_dir.exists():
        return []
    jobs: list[QueueJob] = []
    for slot_dir in sorted([path for path in date_dir.iterdir() if path.is_dir()]):
        job_path = slot_dir / "publish_job.json"
        if not job_path.exists():
            continue
        try:
            payload = load_json(job_path)
        except Exception:
            continue
        if str(payload.get("status", "")).strip() != "queued":
            continue
        jobs.append(
            QueueJob(
                target=target,
                slot_dir=slot_dir.resolve(),
                job_path=job_path.resolve(),
                payload=payload,
            )
        )
    return jobs


def pick_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.parent / f"{path.name}__{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1


def run_publish_job(job: QueueJob, args: argparse.Namespace) -> dict[str, Any]:
    spec_path_raw = str(job.payload.get("assets", {}).get("article_publish_spec_json", "")).strip()
    if not spec_path_raw:
        result_path = job.slot_dir / "publish_result.json"
        error_payload = {
            "status": "failed_preflight",
            "reason": "missing_article_publish_spec_json",
            "account_id": job.target.account_id,
            "slot_dir": str(job.slot_dir),
        }
        job_payload = load_json(job.job_path)
        job_payload["status"] = "failed"
        job_payload["publish_result_ref"] = str(result_path.resolve())
        dump_json(job.job_path, job_payload)
        dump_json(result_path, error_payload)
        return error_payload

    spec_path = Path(spec_path_raw).expanduser().resolve()
    if not spec_path.exists():
        result_path = job.slot_dir / "publish_result.json"
        error_payload = {
            "status": "failed_preflight",
            "reason": f"article_publish_spec_not_found:{spec_path}",
            "account_id": job.target.account_id,
            "slot_dir": str(job.slot_dir),
        }
        job_payload = load_json(job.job_path)
        job_payload["status"] = "failed"
        job_payload["publish_result_ref"] = str(result_path.resolve())
        dump_json(job.job_path, job_payload)
        dump_json(result_path, error_payload)
        return error_payload

    try:
        publish_spec = load_json(spec_path)
    except Exception as exc:
        result_path = job.slot_dir / "publish_result.json"
        error_payload = {
            "status": "failed_preflight",
            "reason": f"article_publish_spec_invalid_json:{type(exc).__name__}:{exc}",
            "account_id": job.target.account_id,
            "slot_dir": str(job.slot_dir),
        }
        job_payload = load_json(job.job_path)
        job_payload["status"] = "failed"
        job_payload["publish_result_ref"] = str(result_path.resolve())
        dump_json(job.job_path, job_payload)
        dump_json(result_path, error_payload)
        return error_payload

    contract_errors, contract_warnings = validate_article_publish_contract(
        article_blocks=publish_spec.get("article_blocks", []) or [],
        inline_insertions=publish_spec.get("inline_image_insertions", []) or [],
    )
    if contract_errors:
        result_path = job.slot_dir / "publish_result.json"
        error_payload = {
            "status": "failed_preflight",
            "reason": "publish_contract_invalid",
            "errors": contract_errors,
            "warnings": contract_warnings,
            "account_id": job.target.account_id,
            "slot_dir": str(job.slot_dir),
            "publish_spec_path": str(spec_path),
        }
        job_payload = load_json(job.job_path)
        job_payload["status"] = "failed"
        job_payload["publish_result_ref"] = str(result_path.resolve())
        dump_json(job.job_path, job_payload)
        dump_json(result_path, error_payload)
        return error_payload

    publish_mode = str(job.payload.get("publish_mode", "article")).strip() or "article"
    cmd = [
        args.publisher_python,
        args.publisher_cli,
        "--mode",
        publish_mode,
        "--dir",
        str(job.slot_dir),
        "--accounts-csv",
        str(job.target.accounts_csv_path),
        "--account",
        job.target.publisher_account,
        "--bit-api-port",
        str(job.target.bit_port),
    ]
    if publish_mode == "post":
        scheduled_time = str(job.payload.get("scheduled_time", "")).strip()
        timezone_text = str(job.payload.get("timezone", "Asia/Shanghai")).strip() or "Asia/Shanghai"
        if not scheduled_time:
            return {
                "status": "error_missing_schedule_time",
                "account_id": job.target.account_id,
                "slot_dir": str(job.slot_dir),
                "command": cmd,
            }
        cmd.extend(["--time", scheduled_time, "--timezone", timezone_text])

    if not args.publish_live:
        cmd.append("--dry-run")

    started_at = isoformat_z(datetime.now(timezone.utc))
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    finished_at = isoformat_z(datetime.now(timezone.utc))

    result_payload = {
        "account_id": job.target.account_id,
        "publisher_account": job.target.publisher_account,
        "publish_mode": publish_mode,
        "slot_dir": str(job.slot_dir),
        "job_path": str(job.job_path),
        "command": cmd,
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
        "dry_run": not args.publish_live,
    }

    if completed.returncode != 0:
        job_payload = load_json(job.job_path)
        job_payload["status"] = "failed"
        result_path = job.slot_dir / "publish_result.json"
        job_payload["publish_result_ref"] = str(result_path.resolve())
        dump_json(job.job_path, job_payload)
        dump_json(result_path, {**result_payload, "status": "failed"})
        return {**result_payload, "status": "failed"}

    if not args.publish_live:
        result_path = job.slot_dir / "publish_result.json"
        dump_json(result_path, {**result_payload, "status": "dry_run_ok"})
        return {**result_payload, "status": "dry_run_ok"}

    published_base = job.target.published_dir / job.slot_dir.parent.name / job.slot_dir.name
    published_dir = pick_unique_path(published_base)
    published_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(job.slot_dir), str(published_dir))

    moved_job_path = published_dir / "publish_job.json"
    moved_result_path = published_dir / "publish_result.json"
    moved_payload = load_json(moved_job_path)
    moved_payload["status"] = "published"
    moved_payload["publish_result_ref"] = str(moved_result_path.resolve())
    dump_json(moved_job_path, moved_payload)
    dump_json(moved_result_path, {**result_payload, "status": "published"})
    return {
        **result_payload,
        "status": "published",
        "published_dir": str(published_dir.resolve()),
    }


def phase_publish(args: argparse.Namespace) -> dict[str, Any]:
    accounts_filter = parse_csv_set(args.accounts)
    targets = load_publish_targets(accounts_filter or None)

    jobs: list[QueueJob] = []
    for target in targets:
        jobs.extend(iter_queue_jobs(target, date_text=args.date))
    jobs.sort(key=lambda row: (row.target.account_id, row.slot_dir.name))
    if args.publish_limit > 0:
        jobs = jobs[: args.publish_limit]

    results: list[dict[str, Any]] = []
    for job in jobs:
        row = run_publish_job(job, args)
        results.append(row)
        if str(row.get("status", "")).startswith("failed") and args.stop_on_publish_error:
            break

    payload = {
        "phase": "publish_queue",
        "generated_at": isoformat_z(datetime.now(timezone.utc)),
        "date": args.date,
        "publish_live": bool(args.publish_live),
        "targets": [target.account_id for target in targets],
        "job_count": len(jobs),
        "results": results,
        "published_count": len([row for row in results if row.get("status") == "published"]),
        "dry_run_ok_count": len([row for row in results if row.get("status") == "dry_run_ok"]),
        "failed_count": len([row for row in results if str(row.get("status", "")).startswith("failed")]),
    }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run article image generation, account queue assembly, and x-post publishing in one flow."
    )
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--families", default="podcast,official_x,article_x")
    parser.add_argument("--source-ids", default="")
    parser.add_argument("--include-human-review-required", action="store_true")

    parser.add_argument("--prepare-images", action="store_true")
    parser.add_argument("--image-prepare-limit", type=int, default=0)
    parser.add_argument("--force-image-refresh", action="store_true")
    parser.add_argument("--generate-images", action="store_true")
    parser.add_argument("--max-inline", type=int, default=6)
    parser.add_argument("--image-engine", choices=["kie", "baoyu"], default="kie")
    parser.add_argument("--image-api-key-env", default="KIE_API_KEY")
    parser.add_argument("--image-api-base-url", default="https://api.kie.ai")
    parser.add_argument("--image-model", default="nano-banana-2")
    parser.add_argument("--image-baoyu-script", default="")
    parser.add_argument("--image-baoyu-runtime", default="")
    parser.add_argument("--image-baoyu-provider", default="")
    parser.add_argument("--image-callback-url", default="")
    parser.add_argument("--image-timeout-seconds", type=int, default=900)
    parser.add_argument("--image-poll-interval", type=float, default=3.0)
    parser.add_argument("--image-wait", action="store_true")
    parser.add_argument("--image-dry-run", action="store_true")

    parser.add_argument("--assemble", action="store_true")
    parser.add_argument("--per-account-max", type=int, default=1)
    parser.add_argument("--assemble-dry-run", action="store_true")

    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--publish-live", action="store_true", help="Actually click Publish. Default keeps dry-run mode.")
    parser.add_argument("--accounts", default="", help="Comma-separated account_id filter")
    parser.add_argument("--publish-limit", type=int, default=0)
    parser.add_argument("--stop-on-publish-error", action="store_true")
    parser.add_argument("--publisher-python", default=str(Path(__file__).resolve().parents[2] / "pipeline/publish/x_post/.venv/bin/python"))
    parser.add_argument("--publisher-cli", default=str(Path(__file__).resolve().parents[2] / "pipeline/publish/x_post/cli.py"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prepare_images, assemble, publish = parse_bool_phases(args)

    run_root = DISTRIBUTION_MANIFESTS / args.date
    run_root.mkdir(parents=True, exist_ok=True)
    flow_started_at = isoformat_z(datetime.now(timezone.utc))

    summary: dict[str, Any] = {
        "date": args.date,
        "generated_at": flow_started_at,
        "phases": {
            "prepare_images": prepare_images,
            "assemble": assemble,
            "publish": publish,
        },
    }

    if prepare_images:
        image_payload = phase_prepare_images(args)
        image_manifest = run_root / "image_prepare_manifest.json"
        dump_json(image_manifest, image_payload)
        summary["image_prepare_manifest"] = str(image_manifest.resolve())
        summary["image_prepare"] = {
            "ok_count": image_payload.get("ok_count", 0),
            "error_count": image_payload.get("error_count", 0),
            "candidate_count": image_payload.get("candidate_count", 0),
        }
        if image_payload.get("error_count", 0):
            summary["status"] = "error_prepare_images"
            final_manifest = run_root / "run_image_distribute_publish_manifest.json"
            dump_json(final_manifest, summary)
            print(str(final_manifest.resolve()))
            return 1

    if assemble:
        assemble_payload = phase_assemble(args)
        assemble_manifest = run_root / "queue_assemble_manifest.json"
        dump_json(assemble_manifest, assemble_payload)
        summary["queue_assemble_manifest"] = str(assemble_manifest.resolve())
        summary["queue_assemble"] = {
            "status": assemble_payload.get("status"),
            "summary": assemble_payload.get("summary", ""),
        }
        if assemble_payload.get("status") != "ok":
            summary["status"] = "error_assemble"
            final_manifest = run_root / "run_image_distribute_publish_manifest.json"
            dump_json(final_manifest, summary)
            print(str(final_manifest.resolve()))
            return 1

    if publish:
        publish_payload = phase_publish(args)
        publish_manifest = run_root / "publish_execution_manifest.json"
        dump_json(publish_manifest, publish_payload)
        summary["publish_execution_manifest"] = str(publish_manifest.resolve())
        summary["publish_execution"] = {
            "job_count": publish_payload.get("job_count", 0),
            "published_count": publish_payload.get("published_count", 0),
            "dry_run_ok_count": publish_payload.get("dry_run_ok_count", 0),
            "failed_count": publish_payload.get("failed_count", 0),
        }
        if publish_payload.get("failed_count", 0):
            summary["status"] = "error_publish"
            final_manifest = run_root / "run_image_distribute_publish_manifest.json"
            dump_json(final_manifest, summary)
            print(str(final_manifest.resolve()))
            return 1

    summary["status"] = "ok"
    summary["finished_at"] = isoformat_z(datetime.now(timezone.utc))
    final_manifest = run_root / "run_image_distribute_publish_manifest.json"
    dump_json(final_manifest, summary)
    print(str(final_manifest.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
