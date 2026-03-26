from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FRAMEWORK_DIR = ROOT / "framework"
PIPELINE_DIR = ROOT / "content/pipeline"
RUNS_DIR = ROOT / "content/runs"
LIBRARY_DIR = ROOT / "content/library/articles"


@dataclass(frozen=True)
class Step:
    stage: str
    label: str
    argv: tuple[str, ...]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def run_id_for(family: str, profile: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    stamp = utc_stamp()
    if family == "podcast":
        return f"{stamp}__podcast_ingest__{profile}"
    return f"{stamp}__x_whitelist_ingest__{family}_{profile}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def effective_router_model(args: argparse.Namespace) -> str:
    if args.router_model:
        return args.router_model
    if args.backend == "codex_cli":
        return "gpt-5.4"
    return ""


def effective_reviewer_model(args: argparse.Namespace) -> str:
    if args.reviewer_model:
        return args.reviewer_model
    if args.backend == "codex_cli":
        return "gpt-5.4"
    return ""


def effective_writer_model(args: argparse.Namespace) -> str:
    if args.writer_model:
        return args.writer_model
    if args.backend == "codex_cli":
        return "gpt-5.4"
    return ""


def load_family_manifest(family: str) -> dict[str, str]:
    path = LIBRARY_DIR / "article_index.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["family"]: item["run_id"]
        for item in payload.get("articles", [])
        if item.get("family") == family and item.get("run_id")
    }


def draft_root_for(run_root: Path, family: str) -> Path:
    mapping = {
        "podcast": run_root / "08_articles/podcast/drafts",
        "official_x": run_root / "08_articles/official_x/drafts",
        "article_x": run_root / "08_articles/article_x/drafts",
    }
    return mapping[family]


def sync_library_articles(*, family: str, run_id: str, run_root: Path) -> dict[str, int | str]:
    src_root = draft_root_for(run_root, family)
    family_dir = LIBRARY_DIR / family / run_id
    family_dir.mkdir(parents=True, exist_ok=True)

    synced = 0
    for draft_json in sorted(src_root.glob("*/article_draft.json")):
        source_id = draft_json.parent.name
        dest_dir = family_dir / source_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(draft_json, dest_dir / "article_draft.json")
        draft_md = draft_json.with_name("article_draft.md")
        if draft_md.exists():
            shutil.copy2(draft_md, dest_dir / "article_draft.md")
        synced += 1

    index_items: list[dict[str, object]] = []
    for article_json in sorted(LIBRARY_DIR.glob("*/*/*/article_draft.json")):
        family_name = article_json.parts[-4]
        article_run_id = article_json.parts[-3]
        source_id = article_json.parts[-2]
        payload = json.loads(article_json.read_text(encoding="utf-8"))
        article_md = article_json.with_name("article_draft.md")
        index_items.append(
            {
                "family": family_name,
                "run_id": article_run_id,
                "source_id": source_id,
                "title": payload.get("title", ""),
                "framework_id": payload.get("framework_id", ""),
                "submode_id": payload.get("submode_id", ""),
                "generated_at": payload.get("generated_at", ""),
                "requires_human_review": payload.get("requires_human_review", False),
                "article_json": str(article_json.resolve()),
                "article_md": str(article_md.resolve()),
            }
        )

    index_payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "count": len(index_items),
        "articles": index_items,
    }
    index_path = LIBRARY_DIR / "article_index.json"
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "family": family,
        "run_id": run_id,
        "synced_count": synced,
        "index_count": len(index_items),
        "index_path": str(index_path.resolve()),
    }


def synced_article_json_paths(*, family: str, run_id: str) -> list[Path]:
    family_dir = LIBRARY_DIR / family / run_id
    if not family_dir.exists():
        return []
    return sorted(family_dir.glob("*/article_draft.json"))


def build_image_pipeline_result(
    *,
    article_json_paths: Sequence[Path],
    args: argparse.Namespace,
) -> dict[str, object]:
    results: list[dict[str, object]] = []
    for article_json in article_json_paths:
        argv = [
            sys.executable,
            rel(PIPELINE_DIR / "publish/run_article_image_pipeline.py"),
            "--article",
            rel(article_json),
            "--max-inline",
            str(args.image_max_inline),
        ]
        if args.generate_images:
            argv.append("--generate")
            if args.image_wait:
                argv.append("--wait")
            if args.image_dry_run:
                argv.append("--dry-run")
            if args.image_api_key_env:
                argv.extend(["--api-key-env", args.image_api_key_env])
            if args.image_api_base_url:
                argv.extend(["--api-base-url", args.image_api_base_url])
            if args.image_model:
                argv.extend(["--model", args.image_model])
            if args.image_callback_url:
                argv.extend(["--callback-url", args.image_callback_url])
            argv.extend(
                [
                    "--timeout-seconds",
                    str(args.image_timeout_seconds),
                    "--poll-interval",
                    str(args.image_poll_interval),
                ]
            )

        completed = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Image pipeline failed for {article_json}: exit={completed.returncode} stderr={completed.stderr.strip()}"
            )
        payload = json.loads((completed.stdout or "").strip() or "{}")
        results.append(payload)

    return {
        "article_count": len(article_json_paths),
        "generate_images": bool(args.generate_images),
        "results": results,
    }


def post_run_actions(*, args: argparse.Namespace, family: str, run_id: str) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if args.skip_library_sync:
        return actions

    actions.append(
        {
            "label": "sync_library_articles",
            "family": family,
            "run_id": run_id,
            "library_dir": str((LIBRARY_DIR / family / run_id).resolve()),
        }
    )
    if not args.skip_image_briefs:
        actions.append(
            {
                "label": "build_article_image_briefs",
                "family": family,
                "run_id": run_id,
                "generate_images": bool(args.generate_images),
                "image_max_inline": args.image_max_inline,
                "api_key_env": args.image_api_key_env,
                "api_base_url": args.image_api_base_url,
                "model": args.image_model,
                "wait": bool(args.image_wait),
                "dry_run": bool(args.image_dry_run),
            }
        )
    return actions


def podcast_steps(run_root: Path, profile: str, args: argparse.Namespace) -> list[Step]:
    if profile != "default":
        raise ValueError("podcast currently supports profile=default only")
    discovery_root = ensure_dir(run_root / "01_discovery/podcast_ingest")
    catalog_dir = ensure_dir(discovery_root / "catalog")
    fulltext_dir = ensure_dir(discovery_root / "fulltext/auto_discovered")
    source_root = ensure_dir(run_root / "03_source_items/podcast/items")
    gate_root = ensure_dir(run_root / "04_gates/podcast/results")
    prefilter_root = ensure_dir(run_root / "05_prefilter/podcast/results")
    routing_root = ensure_dir(run_root / "06_routing/podcast/results")
    rewrite_root = ensure_dir(run_root / "07_rewrite_contexts/podcast/results")
    article_root = ensure_dir(run_root / "08_articles/podcast/drafts")

    episode_catalog = catalog_dir / "episode_catalog.json"
    transcript_manifest_root = fulltext_dir

    router_model = effective_router_model(args)
    reviewer_model = effective_reviewer_model(args)

    return [
        Step(
            "01_discovery",
            "discover_podcast_episodes",
            (
                sys.executable,
                rel(PIPELINE_DIR / "ingest/podcast/discover_podcast_episodes.py"),
                "--registry",
                rel(PIPELINE_DIR / "configs/podcast_discovery_registry.json"),
                "--out-dir",
                rel(catalog_dir),
            ),
        ),
        Step(
            "01_discovery",
            "discover_podcast_transcript_sources",
            (
                sys.executable,
                rel(PIPELINE_DIR / "ingest/podcast/discover_podcast_transcript_sources.py"),
                "--episode-catalog",
                rel(episode_catalog),
                "--out-root",
                rel(transcript_manifest_root),
            ),
        ),
        Step(
            "03_source_items",
            "build_source_items",
            (
                sys.executable,
                rel(PIPELINE_DIR / "normalize/build_source_items.py"),
                "--episode-catalog",
                rel(episode_catalog),
                "--transcript-root",
                rel(transcript_manifest_root),
                "--out-root",
                rel(source_root),
            ),
        ),
        Step(
            "04_gates",
            "evaluate_longform_gate",
            (
                sys.executable,
                rel(PIPELINE_DIR / "gate/evaluate_longform_gate.py"),
                "--source-item-root",
                rel(source_root),
                "--out-root",
                rel(gate_root),
            ),
        ),
        Step(
            "05_prefilter",
            "prefilter_framework_candidates",
            (
                sys.executable,
                rel(PIPELINE_DIR / "route/prefilter_framework_candidates.py"),
                "--source-item-root",
                rel(source_root),
                "--out-root",
                rel(prefilter_root),
            ),
        ),
        Step(
            "06_routing",
            "route_framework_matches",
            (
                sys.executable,
                rel(PIPELINE_DIR / "route/route_framework_matches.py"),
                "--source-item-root",
                rel(source_root),
                "--prefilter-root",
                rel(prefilter_root),
                "--source-gate-root",
                rel(gate_root),
                "--out-root",
                rel(routing_root),
                "--backend",
                args.backend,
                "--codex-working-dir",
                args.codex_working_dir,
                "--codex-reasoning-effort",
                args.codex_reasoning_effort,
                "--timeout-s",
                str(args.timeout_s),
                *(() if not router_model else ("--router-model", router_model)),
                *(() if not reviewer_model else ("--reviewer-model", reviewer_model)),
            ),
        ),
        Step(
            "07_rewrite_contexts",
            "build_rewrite_contexts",
            (
                sys.executable,
                rel(PIPELINE_DIR / "assemble/build_rewrite_contexts.py"),
                "--framework-match-root",
                rel(routing_root),
                "--out-root",
                rel(rewrite_root),
            ),
        ),
        Step(
            "08_articles",
            "write_framework_articles",
            (
                sys.executable,
                rel(PIPELINE_DIR / "write/write_framework_articles.py"),
                "--rewrite-context-root",
                rel(rewrite_root),
                "--source-gate-root",
                rel(gate_root),
                "--out-root",
                rel(article_root),
                "--backend",
                args.backend,
                "--codex-working-dir",
                args.codex_working_dir,
                "--codex-reasoning-effort",
                args.codex_reasoning_effort,
                "--timeout-s",
                str(args.timeout_s_write),
                "--output-language",
                args.output_language,
                *(() if not effective_writer_model(args) else ("--writer-model", effective_writer_model(args))),
                *(() if not args.include_human_review_required else ("--include-human-review-required",)),
            ),
        ),
    ]


def official_x_steps(run_root: Path, profile: str, args: argparse.Namespace) -> list[Step]:
    if profile != "original_only":
        raise ValueError("official_x currently supports profile=original_only only")
    discovery_root = ensure_dir(run_root / "01_discovery/x_whitelist_ingest/catalog")
    source_root = ensure_dir(run_root / "03_source_items/official_x/items")
    gate_root = ensure_dir(run_root / "04_gates/official_x/results")
    prefilter_root = ensure_dir(run_root / "05_prefilter/official_x/results")
    routing_root = ensure_dir(run_root / "06_routing/official_x/results")
    rewrite_root = ensure_dir(run_root / "07_rewrite_contexts/official_x/results")
    article_root = ensure_dir(run_root / "08_articles/official_x/drafts")
    catalog_path = discovery_root / "guest_rss_catalog.json"

    router_model = effective_router_model(args)
    reviewer_model = effective_reviewer_model(args)

    return [
        Step(
            "01_discovery",
            "discover_official_x_guest_rss",
            (
                sys.executable,
                rel(PIPELINE_DIR / "ingest/x_whitelist/discover_official_x_guest_rss.py"),
                "--account-profile",
                rel(PIPELINE_DIR / "configs/official_x_account_profile.json"),
                "--out-dir",
                rel(discovery_root),
            ),
        ),
        Step(
            "03_source_items",
            "build_source_items_official_x",
            (
                sys.executable,
                rel(PIPELINE_DIR / "normalize/build_source_items_official_x.py"),
                "--guest-rss-catalog",
                rel(catalog_path),
                "--account-profile",
                rel(PIPELINE_DIR / "configs/official_x_account_profile.json"),
                "--out-root",
                rel(source_root),
            ),
        ),
        Step(
            "04_gates",
            "evaluate_longform_gate",
            (
                sys.executable,
                rel(PIPELINE_DIR / "gate/evaluate_longform_gate.py"),
                "--source-item-root",
                rel(source_root),
                "--out-root",
                rel(gate_root),
            ),
        ),
        Step(
            "05_prefilter",
            "prefilter_framework_candidates",
            (
                sys.executable,
                rel(PIPELINE_DIR / "route/prefilter_framework_candidates.py"),
                "--source-item-root",
                rel(source_root),
                "--out-root",
                rel(prefilter_root),
            ),
        ),
        Step(
            "06_routing",
            "route_framework_matches",
            (
                sys.executable,
                rel(PIPELINE_DIR / "route/route_framework_matches.py"),
                "--source-item-root",
                rel(source_root),
                "--prefilter-root",
                rel(prefilter_root),
                "--source-gate-root",
                rel(gate_root),
                "--out-root",
                rel(routing_root),
                "--backend",
                args.backend,
                "--codex-working-dir",
                args.codex_working_dir,
                "--codex-reasoning-effort",
                args.codex_reasoning_effort,
                "--timeout-s",
                str(args.timeout_s),
                *(() if not router_model else ("--router-model", router_model)),
                *(() if not reviewer_model else ("--reviewer-model", reviewer_model)),
            ),
        ),
        Step(
            "07_rewrite_contexts",
            "build_rewrite_contexts",
            (
                sys.executable,
                rel(PIPELINE_DIR / "assemble/build_rewrite_contexts.py"),
                "--framework-match-root",
                rel(routing_root),
                "--out-root",
                rel(rewrite_root),
            ),
        ),
        Step(
            "08_articles",
            "write_framework_articles",
            (
                sys.executable,
                rel(PIPELINE_DIR / "write/write_framework_articles.py"),
                "--rewrite-context-root",
                rel(rewrite_root),
                "--source-gate-root",
                rel(gate_root),
                "--out-root",
                rel(article_root),
                "--backend",
                args.backend,
                "--codex-working-dir",
                args.codex_working_dir,
                "--codex-reasoning-effort",
                args.codex_reasoning_effort,
                "--timeout-s",
                str(args.timeout_s_write),
                "--output-language",
                args.output_language,
                *(() if not effective_writer_model(args) else ("--writer-model", effective_writer_model(args))),
                *(() if not args.include_human_review_required else ("--include-human-review-required",)),
            ),
        ),
    ]


def article_x_steps(run_root: Path, profile: str, args: argparse.Namespace) -> list[Step]:
    if profile != "original_only":
        raise ValueError("article_x currently supports profile=original_only only")
    discovery_root = ensure_dir(run_root / "01_discovery/x_whitelist_ingest/catalog")
    classification_root = ensure_dir(run_root / "02_classification/article_x/results")
    source_root = ensure_dir(run_root / "03_source_items/article_x/items")
    gate_root = ensure_dir(run_root / "04_gates/article_x/results")
    prefilter_root = ensure_dir(run_root / "05_prefilter/article_x/results")
    routing_root = ensure_dir(run_root / "06_routing/article_x/results")
    rewrite_root = ensure_dir(run_root / "07_rewrite_contexts/article_x/results")
    article_root = ensure_dir(run_root / "08_articles/article_x/drafts")
    discovery_catalog = discovery_root / "guest_rss_catalog.json"
    classified_catalog = classification_root / "guest_rss_catalog.json"

    router_model = effective_router_model(args)
    reviewer_model = effective_reviewer_model(args)

    return [
        Step(
            "01_discovery",
            "discover_x_whitelist_guest_rss",
            (
                sys.executable,
                rel(PIPELINE_DIR / "ingest/x_whitelist/discover_official_x_guest_rss.py"),
                "--account-profile",
                rel(PIPELINE_DIR / "configs/x_whitelist_account_profile.json"),
                "--out-dir",
                rel(discovery_root),
            ),
        ),
        Step(
            "02_classification",
            "filter_x_rss_article_candidates",
            (
                sys.executable,
                rel(PIPELINE_DIR / "classify/filter_x_rss_article_candidates.py"),
                "--in-catalog",
                rel(discovery_catalog),
                "--out-dir",
                rel(classification_root),
            ),
        ),
        Step(
            "03_source_items",
            "build_source_items_article_x",
            (
                sys.executable,
                rel(PIPELINE_DIR / "normalize/build_source_items_official_x.py"),
                "--guest-rss-catalog",
                rel(classified_catalog),
                "--account-profile",
                rel(PIPELINE_DIR / "configs/x_whitelist_account_profile.json"),
                "--out-root",
                rel(source_root),
            ),
        ),
        Step(
            "04_gates",
            "evaluate_longform_gate",
            (
                sys.executable,
                rel(PIPELINE_DIR / "gate/evaluate_longform_gate.py"),
                "--source-item-root",
                rel(source_root),
                "--out-root",
                rel(gate_root),
            ),
        ),
        Step(
            "05_prefilter",
            "prefilter_framework_candidates",
            (
                sys.executable,
                rel(PIPELINE_DIR / "route/prefilter_framework_candidates.py"),
                "--source-item-root",
                rel(source_root),
                "--out-root",
                rel(prefilter_root),
            ),
        ),
        Step(
            "06_routing",
            "route_framework_matches",
            (
                sys.executable,
                rel(PIPELINE_DIR / "route/route_framework_matches.py"),
                "--source-item-root",
                rel(source_root),
                "--prefilter-root",
                rel(prefilter_root),
                "--source-gate-root",
                rel(gate_root),
                "--out-root",
                rel(routing_root),
                "--backend",
                args.backend,
                "--codex-working-dir",
                args.codex_working_dir,
                "--codex-reasoning-effort",
                args.codex_reasoning_effort,
                "--timeout-s",
                str(args.timeout_s),
                *(() if not router_model else ("--router-model", router_model)),
                *(() if not reviewer_model else ("--reviewer-model", reviewer_model)),
            ),
        ),
        Step(
            "07_rewrite_contexts",
            "build_rewrite_contexts",
            (
                sys.executable,
                rel(PIPELINE_DIR / "assemble/build_rewrite_contexts.py"),
                "--framework-match-root",
                rel(routing_root),
                "--out-root",
                rel(rewrite_root),
            ),
        ),
        Step(
            "08_articles",
            "write_framework_articles",
            (
                sys.executable,
                rel(PIPELINE_DIR / "write/write_framework_articles.py"),
                "--rewrite-context-root",
                rel(rewrite_root),
                "--source-gate-root",
                rel(gate_root),
                "--out-root",
                rel(article_root),
                "--backend",
                args.backend,
                "--codex-working-dir",
                args.codex_working_dir,
                "--codex-reasoning-effort",
                args.codex_reasoning_effort,
                "--timeout-s",
                str(args.timeout_s_write),
                "--output-language",
                args.output_language,
                *(() if not effective_writer_model(args) else ("--writer-model", effective_writer_model(args))),
                *(() if not args.include_human_review_required else ("--include-human-review-required",)),
            ),
        ),
    ]


FAMILY_BUILDERS = {
    "podcast": podcast_steps,
    "official_x": official_x_steps,
    "article_x": article_x_steps,
}


def run_step(step: Step, cwd: Path) -> None:
    completed = subprocess.run(step.argv, cwd=cwd, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Step failed: {step.label} (stage={step.stage}, exit={completed.returncode})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=sorted(FAMILY_BUILDERS))
    parser.add_argument("--profile", default="", help="Family profile. Defaults to family-specific standard profile.")
    parser.add_argument("--run-id", default="", help="Explicit run_id. If omitted, generate one.")
    parser.add_argument("--backend", choices=["auto", "openai_compatible", "codex_cli"], default="auto")
    parser.add_argument("--router-model", default="")
    parser.add_argument("--reviewer-model", default="")
    parser.add_argument("--writer-model", default="")
    parser.add_argument("--codex-working-dir", default="/tmp")
    parser.add_argument("--codex-reasoning-effort", default="medium")
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--timeout-s-write", type=int, default=180)
    parser.add_argument("--output-language", default="zh-CN")
    parser.add_argument("--include-human-review-required", action="store_true")
    parser.add_argument("--skip-library-sync", action="store_true")
    parser.add_argument("--skip-image-briefs", action="store_true")
    parser.add_argument("--generate-images", action="store_true")
    parser.add_argument("--image-max-inline", type=int, default=4)
    parser.add_argument("--image-api-key-env", default="KIE_API_KEY")
    parser.add_argument("--image-api-base-url", default="https://api.kie.ai")
    parser.add_argument("--image-model", default="nano-banana-2")
    parser.add_argument("--image-callback-url", default="")
    parser.add_argument("--image-timeout-seconds", type=int, default=900)
    parser.add_argument("--image-poll-interval", type=float, default=3.0)
    parser.add_argument("--image-wait", action="store_true")
    parser.add_argument("--image-dry-run", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned commands without executing them.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    default_profiles = {
        "podcast": "default",
        "official_x": "original_only",
        "article_x": "original_only",
    }
    profile = args.profile or default_profiles[args.family]
    run_id = run_id_for(args.family, profile, args.run_id or None)
    run_root = RUNS_DIR / run_id
    ensure_dir(run_root)

    steps = FAMILY_BUILDERS[args.family](run_root, profile, args)
    manifest = {
        "family": args.family,
        "profile": profile,
        "run_id": run_id,
        "run_root": str(run_root.resolve()),
        "framework_specs_dir": str(DEFAULT_FRAMEWORK_DIR.resolve()),
        "steps": [
            {
                "stage": step.stage,
                "label": step.label,
                "argv": list(step.argv),
            }
            for step in steps
        ],
        "post_run_actions": post_run_actions(args=args, family=args.family, run_id=run_id),
    }
    manifest_path = run_root / "scheduler_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    for step in steps:
        print(f"[{step.stage}] {step.label}")
        run_step(step, ROOT)

    post_run_root = ensure_dir(run_root / "09_post_run")
    if not args.skip_library_sync:
        sync_result = sync_library_articles(family=args.family, run_id=run_id, run_root=run_root)
        (post_run_root / "library_sync_result.json").write_text(
            json.dumps(sync_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(sync_result, ensure_ascii=False))
        if not args.skip_image_briefs:
            article_json_paths = synced_article_json_paths(family=args.family, run_id=run_id)
            image_result = build_image_pipeline_result(article_json_paths=article_json_paths, args=args)
            (post_run_root / "image_pipeline_result.json").write_text(
                json.dumps(image_result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(image_result, ensure_ascii=False))

    print(str(manifest_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
