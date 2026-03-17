from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

SLOTS = ["08:30", "12:00", "19:30"]


def pick_dir(day: Path, new_rel: str, old_rel: str) -> Path:
    n = day / new_rel
    if n.exists():
        return n
    return day / old_rel


def extract_post_text(md_text: str) -> str:
    lines = md_text.replace("\r\n", "\n").split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("# "):
            continue
        if s.startswith("今天内容类型：") or s.startswith("表达角度：") or s.startswith("目标对象：") or s.startswith("结果锚点："):
            continue
        if s.startswith("---"):
            break
        out.append(ln)
    text = "\n".join(out).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def package_posts(day: Path, out_root: Path) -> list[tuple]:
    posts = pick_dir(day, "publish/posts", "contents")
    assets = posts / "assets"
    rows = []
    for i in (1, 2, 3):
        post_md = posts / f"post_{i:02d}.md"
        post_img = assets / f"post_{i:02d}_1.jpg"
        target = out_root / f"slot_{i:02d}"
        target.mkdir(parents=True, exist_ok=True)

        if not post_md.exists():
            rows.append((i, "missing_md", str(post_md)))
            continue

        txt = extract_post_text(post_md.read_text(encoding="utf-8"))
        (target / "post.txt").write_text(txt, encoding="utf-8")
        (target / "content_type.txt").write_text("post\n", encoding="utf-8")

        if post_img.exists():
            shutil.copy2(post_img, target / "post.jpg")
            img_status = "ok"
        else:
            img_status = "missing_img"

        rows.append((i, "ok", str(target), img_status))
    return rows


def package_article(day: Path, out_root: Path) -> tuple | None:
    article_dir = pick_dir(day, "publish/article", "article")
    if not article_dir.exists():
        return None

    article_md = article_dir / "article.md"
    article_x_ready = article_dir / "article_x_ready.txt"
    meta = article_dir / "generation_meta.json"
    if not article_md.exists() or not article_x_ready.exists() or not meta.exists():
        return ("article", "missing_required_files", str(article_dir))

    target = out_root / "article"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(article_md, target / "article.md")
    shutil.copy2(article_x_ready, target / "article_x_ready.txt")
    shutil.copy2(meta, target / "generation_meta.json")
    (target / "content_type.txt").write_text("article\n", encoding="utf-8")

    try:
        obj = json.loads(meta.read_text(encoding="utf-8"))
        topic = obj.get("topic", "")
    except Exception:
        topic = ""
    return ("article", "ok", str(target), topic)


def package_interview(day: Path, out_root: Path) -> tuple | None:
    d = pick_dir(day, "publish/interview", "interview")
    if not d.exists():
        return None
    required = [d / "transcript.json", d / "article_interview.md", d / "article_interview_x_ready.txt", d / "interview_generation_meta.json"]
    if any(not p.exists() for p in required):
        return ("interview", "missing_required_files", str(d))

    target = out_root / "interview"
    target.mkdir(parents=True, exist_ok=True)
    for p in required:
        shutil.copy2(p, target / p.name)
    (target / "content_type.txt").write_text("interview\n", encoding="utf-8")
    return ("interview", "ok", str(target))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--skip-validate", action="store_true")
    ap.add_argument("--with-article", action="store_true")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    day = acc / "calendar" / args.date
    posts_dir = pick_dir(day, "publish/posts", "contents")
    if not posts_dir.exists():
        raise SystemExit(f"missing posts dir: {posts_dir}")

    if not args.skip_validate:
        validator = acc / "automation" / "pre_publish_validate.py"
        if not validator.exists():
            raise SystemExit(f"missing validator: {validator}")
        cmd = ["python3", str(validator), "--account-root", str(acc), "--date", args.date]
        if args.with_article:
            cmd.append("--with-article")
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.stdout:
            print(proc.stdout.strip())
        if proc.stderr:
            print(proc.stderr.strip())
        if proc.returncode != 0:
            raise SystemExit(f"pre-publish validation failed (code={proc.returncode})")

    out_root = Path(args.out_dir).resolve() if args.out_dir else (acc / "automation" / "publish_ready" / args.date)
    out_root.mkdir(parents=True, exist_ok=True)

    rows = package_posts(day, out_root)
    article_row = package_article(day, out_root)
    interview_row = package_interview(day, out_root)

    print(f"publish_ready: {out_root}")
    for r in rows:
        print(r)
    if article_row:
        print(article_row)
    if interview_row:
        print(interview_row)

    print("\n# dry-run commands")
    for i, t in enumerate(SLOTS, 1):
        target = out_root / f"slot_{i:02d}"
        if not (target / "post.txt").exists() or not (target / "post.jpg").exists():
            continue
        print(
            "PYTHONPATH=./publish_tool python3 -m x_schedule_post.cli "
            f"--dir '{target}' --time '{args.date} {t}' --timezone 'Asia/Shanghai' --dry-run"
        )

    if article_row and article_row[1] == "ok":
        print("\n# article artifact")
        print(f"cat '{out_root / 'article' / 'article_x_ready.txt'}'")
    if interview_row and interview_row[1] == "ok":
        print("\n# interview artifact")
        print(f"cat '{out_root / 'interview' / 'article_interview_x_ready.txt'}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
