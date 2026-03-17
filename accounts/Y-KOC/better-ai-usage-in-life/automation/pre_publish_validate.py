from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_slot(contents: Path, idx: int) -> tuple[bool, str]:
    post_md = contents / f"post_{idx:02d}.md"
    meta = contents / f"post_{idx:02d}.generation_meta.json"

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    contents = acc / "calendar" / args.date / "contents"
    if not contents.exists():
        raise SystemExit(f"missing contents dir: {contents}")

    failed = []
    for i in (1, 2, 3):
        ok, msg = validate_slot(contents, i)
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
