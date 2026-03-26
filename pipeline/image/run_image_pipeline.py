from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.image.brief_builder import build_payload, dump_json
from pipeline.image.generator import (
    DEFAULT_API_BASE_URL,
    DEFAULT_MODEL,
    run_generation,
)


DEFAULT_TEMPLATE_PATH = ROOT / "configs/image/ARTICLE_IMAGE_BRIEF.template.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", required=True, help="Path to article_draft.json")
    parser.add_argument("--brief-out", default="", help="Where to write the assembled ARTICLE_IMAGE_BRIEF JSON")
    parser.add_argument("--images-out", default="", help="Directory for generated image assets")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--max-inline", type=int, default=6)
    parser.add_argument("--generate", action="store_true", help="Submit image generation tasks after assembling the brief")
    parser.add_argument("--api-key-env", default="KIE_API_KEY")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--callback-url", default="")
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def default_brief_path(article_path: Path) -> Path:
    return article_path.parent / "article_image_brief.json"


def default_images_dir(article_path: Path) -> Path:
    return article_path.parent / "image_assets"


def main() -> int:
    args = parse_args()
    article_path = Path(args.article).resolve()
    template_path = Path(args.template).resolve()
    brief_out = Path(args.brief_out).resolve() if args.brief_out else default_brief_path(article_path)
    images_out = Path(args.images_out).resolve() if args.images_out else default_images_dir(article_path)

    payload = build_payload(article_path, template_path, max_inline=max(0, args.max_inline))
    dump_json(brief_out, payload)

    summary: dict[str, object] = {
        "ok": True,
        "article": str(article_path),
        "brief_out": str(brief_out),
        "generate": bool(args.generate),
        "inline_count": len(payload.get("inline_images", [])),
    }

    if not args.generate:
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    token = ""
    if not args.dry_run:
        token = os.environ.get(args.api_key_env, "").strip()
        if not token:
            raise SystemExit(f"Missing API key. Set {args.api_key_env}.")

    manifest = run_generation(
        payload=payload,
        out_dir=images_out,
        model=args.model,
        api_base_url=args.api_base_url,
        callback_url=args.callback_url,
        token=token,
        wait=args.wait,
        timeout_seconds=args.timeout_seconds,
        poll_interval=args.poll_interval,
        dry_run=args.dry_run,
        brief_path=str(brief_out),
    )
    summary["images_out"] = str(images_out)
    summary["job_count"] = len(manifest.get("jobs", []))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
