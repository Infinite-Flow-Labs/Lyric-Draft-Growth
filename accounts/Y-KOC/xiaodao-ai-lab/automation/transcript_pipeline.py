from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def normalize_lines(text: str) -> list[dict]:
    rows = []
    ts_pat = re.compile(r"^\s*(\[?\d{1,2}:\d{2}(?::\d{2})?\]?)?\s*([A-Za-z\u4e00-\u9fff0-9_\-]{1,20})?\s*[:：]?\s*(.*)$")
    idx = 0
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        m = ts_pat.match(s)
        ts = ""
        spk = ""
        content = s
        if m:
            ts = (m.group(1) or "").strip("[] ")
            spk = (m.group(2) or "").strip()
            content = (m.group(3) or "").strip() or s
        if not spk:
            spk = "Host" if idx % 2 == 0 else "Guest"
        idx += 1
        rows.append({"idx": idx, "timestamp": ts, "speaker": spk, "text": content})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--input", required=True, help="raw transcript txt/md path")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    day = acc / "calendar" / args.date
    out_dir = day / "publish" / "interview"
    out_dir.mkdir(parents=True, exist_ok=True)

    inp = Path(args.input).resolve()
    text = inp.read_text(encoding="utf-8")
    lines = normalize_lines(text)

    obj = {
        "source_file": str(inp),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "turns": lines,
    }
    (out_dir / "transcript.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "transcript_clean.txt").write_text("\n".join([f"{r['speaker']}: {r['text']}" for r in lines]), encoding="utf-8")
    print(out_dir / "transcript.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
