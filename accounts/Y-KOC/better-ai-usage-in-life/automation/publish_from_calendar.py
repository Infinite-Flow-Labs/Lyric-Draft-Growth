from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

SLOTS = ["08:30", "12:00", "19:30"]


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--skip-validate", action="store_true")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    day = acc / "calendar" / args.date
    contents = day / "contents"
    assets = contents / "assets"

    if not contents.exists():
        raise SystemExit(f"missing contents dir: {contents}")

    if not args.skip_validate:
        validator = acc / "automation" / "pre_publish_validate.py"
        if not validator.exists():
            raise SystemExit(f"missing validator: {validator}")
        proc = subprocess.run(
            ["python3", str(validator), "--account-root", str(acc), "--date", args.date],
            text=True,
            capture_output=True,
        )
        if proc.stdout:
            print(proc.stdout.strip())
        if proc.stderr:
            print(proc.stderr.strip())
        if proc.returncode != 0:
            raise SystemExit(f"pre-publish validation failed (code={proc.returncode})")

    out_root = Path(args.out_dir).resolve() if args.out_dir else (acc / "automation" / "publish_ready" / args.date)
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in (1, 2, 3):
        post_md = contents / f"post_{i:02d}.md"
        post_img = assets / f"post_{i:02d}_1.jpg"
        target = out_root / f"slot_{i:02d}"
        target.mkdir(parents=True, exist_ok=True)

        if not post_md.exists():
            rows.append((i, "missing_md", str(post_md)))
            continue
        txt = extract_post_text(post_md.read_text(encoding="utf-8"))
        (target / "post.txt").write_text(txt, encoding="utf-8")

        if post_img.exists():
            shutil.copy2(post_img, target / "post.jpg")
            img_status = "ok"
        else:
            img_status = "missing_img"

        rows.append((i, "ok", str(target), img_status))

    print(f"publish_ready: {out_root}")
    for r in rows:
        print(r)

    print("\n# dry-run commands")
    for i, t in enumerate(SLOTS, 1):
        target = out_root / f"slot_{i:02d}"
        if not (target / "post.txt").exists() or not (target / "post.jpg").exists():
            continue
        print(
            "PYTHONPATH=./publish_tool python3 -m x_schedule_post.cli "
            f"--dir '{target}' --time '{args.date} {t}' --timezone 'Asia/Shanghai' --dry-run"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
