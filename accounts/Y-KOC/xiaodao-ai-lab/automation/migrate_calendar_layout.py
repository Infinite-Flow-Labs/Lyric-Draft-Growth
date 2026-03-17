from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def move_if_exists(src: Path, dst: Path):
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return False
    shutil.move(str(src), str(dst))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--delete-legacy", action="store_true")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    cal = acc / "calendar"
    if not cal.exists():
        print("no calendar dir")
        return 0

    for day in sorted([p for p in cal.iterdir() if p.is_dir()]):
        pub = day / "publish"
        pub.mkdir(exist_ok=True)

        move_if_exists(day / "contents", pub / "posts")
        move_if_exists(day / "article", pub / "article")
        move_if_exists(day / "interview", pub / "interview")

        # topics merged into sources/topics for compact layout
        if (day / "topics").exists():
            (day / "sources").mkdir(exist_ok=True)
            move_if_exists(day / "topics", day / "sources" / "topics")

        if args.delete_legacy:
            for legacy in [day / "contents", day / "article", day / "interview", day / "topics"]:
                if legacy.exists():
                    if legacy.is_dir():
                        shutil.rmtree(legacy)
                    else:
                        legacy.unlink(missing_ok=True)

        print(f"migrated: {day.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
