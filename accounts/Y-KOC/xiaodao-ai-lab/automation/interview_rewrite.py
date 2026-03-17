from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def call_llm(prompt: str, session_id: str) -> str:
    cmd = ["openclaw", "agent", "--json", "--session-id", session_id, "--message", prompt]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    raw = (proc.stdout or "").strip()
    s, e = raw.find("{"), raw.rfind("}")
    obj = json.loads(raw[s:e+1])
    text = ((obj.get("payloads") or [{}])[0].get("text") or "").strip()
    if not text:
        raise RuntimeError("empty llm output")
    return text


def x_ready(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"^(\d+)\.\s+", r"\1）", text, flags=re.M)
    text = text.replace("---", "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    out_dir = acc / "calendar" / args.date / "publish" / "interview"
    tj = out_dir / "transcript.json"
    if not tj.exists():
        raise SystemExit(f"missing transcript: {tj}")
    t = json.loads(tj.read_text(encoding="utf-8"))
    turns = t.get("turns", [])
    sample = "\n".join([f"{r.get('speaker','')}: {r.get('text','')}" for r in turns[:220]])

    prompt = f"""
你是一名内容总编。把下面访谈转写改写为：
1) 一篇有冲突和观点推进的中文深度文章（自然标题，不要Hook/Why now标签）。
2) 一份短帖线程（6-10条，每条独立可读）。
3) 末尾给3条可直接传播的金句。
语气：有人味、判断清晰、少模板腔。

访谈转写：
{sample}
""".strip()

    text = call_llm(prompt, session_id=f"interview-rw-{acc.name}")
    (out_dir / "article_interview.md").write_text(text, encoding="utf-8")
    (out_dir / "article_interview_x_ready.txt").write_text(x_ready(text), encoding="utf-8")

    meta = {
        "type": "INTERVIEW",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "turns_used": len(turns[:220]),
    }
    (out_dir / "interview_generation_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_dir / "article_interview.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
