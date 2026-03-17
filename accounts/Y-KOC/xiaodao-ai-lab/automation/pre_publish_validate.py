from __future__ import annotations

import argparse
import json
from pathlib import Path


def pick_dir(day: Path, new_rel: str, old_rel: str) -> Path:
    n = day / new_rel
    if n.exists():
        return n
    return day / old_rel


def validate_post_slot(posts_dir: Path, idx: int) -> tuple[bool, str]:
    post_md = posts_dir / f"post_{idx:02d}.md"
    meta = posts_dir / f"post_{idx:02d}.generation_meta.json"

    if not post_md.exists():
        return False, f"post_{idx:02d}: missing post markdown"
    if not meta.exists():
        return False, f"post_{idx:02d}: missing generation_meta.json"

    try:
        obj = json.loads(meta.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"post_{idx:02d}: invalid generation_meta.json ({e})"

    if obj.get("quality_gate_passed") is not True:
        return False, f"post_{idx:02d}: quality_gate_passed != true"

    if not obj.get("prompt_hash"):
        return False, f"post_{idx:02d}: missing prompt_hash"

    model = (obj.get("model") or "").strip()
    if not model:
        return False, f"post_{idx:02d}: missing model"

    return True, f"post_{idx:02d}: ok"


def validate_article(day: Path) -> tuple[bool, str]:
    article_dir = pick_dir(day, "publish/article", "article")
    if not article_dir.exists():
        return False, "article: missing article dir"

    required = [article_dir / "article.md", article_dir / "article_x_ready.txt", article_dir / "generation_meta.json"]
    for p in required:
        if not p.exists():
            return False, f"article: missing {p.name}"

    try:
        meta = json.loads((article_dir / "generation_meta.json").read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"article: invalid generation_meta.json ({e})"

    if (meta.get("type") or "").upper() != "A":
        return False, "article: type != A"
    if not (meta.get("topic") or "").strip():
        return False, "article: missing topic"

    return True, "article: ok"


def validate_interview(day: Path) -> tuple[bool, str]:
    d = pick_dir(day, "publish/interview", "interview")
    if not d.exists():
        return True, "interview: skip"
    required = [d / "transcript.json", d / "article_interview.md", d / "article_interview_x_ready.txt", d / "interview_generation_meta.json"]
    for p in required:
        if not p.exists():
            return False, f"interview: missing {p.name}"
    return True, "interview: ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--with-article", action="store_true")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    day = acc / "calendar" / args.date
    posts_dir = pick_dir(day, "publish/posts", "contents")
    if not posts_dir.exists():
        raise SystemExit(f"missing posts dir: {posts_dir}")

    failed = []
    for i in (1, 2, 3):
        ok, msg = validate_post_slot(posts_dir, i)
        print(msg)
        if not ok:
            failed.append(msg)

    need_article = args.with_article or (day / "publish" / "article").exists() or (day / "article").exists()
    if need_article:
        ok, msg = validate_article(day)
        print(msg)
        if not ok:
            failed.append(msg)

    ok, msg = validate_interview(day)
    print(msg)
    if not ok:
        failed.append(msg)

    if failed:
        print("\nvalidation failed; publishing is blocked")
        return 2

    print("\nvalidation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
