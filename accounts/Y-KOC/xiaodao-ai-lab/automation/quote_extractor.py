from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    d = acc / "calendar" / args.date / "publish" / "interview"
    src = d / "article_interview.md"
    if not src.exists():
        raise SystemExit(f"missing {src}")
    text = src.read_text(encoding="utf-8")

    cands = []
    for ln in text.splitlines():
        s = ln.strip(" -\t")
        if 18 <= len(s) <= 80 and re.search(r"(不是|而是|关键|本质|先|再|不要)", s):
            cands.append(s)
    cands = cands[:12]
    (d / "quotes.txt").write_text("\n".join(cands) + "\n", encoding="utf-8")
    (d / "quotes.json").write_text(json.dumps({"quotes": cands}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(d / "quotes.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
