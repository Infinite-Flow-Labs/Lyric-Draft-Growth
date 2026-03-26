from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

TYPES = [
    "01_money_proof",
    "02_launch_application",
    "03_opinion_decode",
    "04_failure_reversal",
    "05_ab_benchmark",
    "06_checklist_template",
    "07_contrarian_take",
    "08_signal_to_action",
]


def call_llm(item: dict, sid: str) -> tuple[str, str]:
    prompt = f"""
你是内容分类器。把下面文章候选只分到以下8类之一，并给一句中文理由：
{TYPES}

分类口径：
- 01_money_proof: 收入/变现/结果证明
- 02_launch_application: 新产品/新功能发布后如何应用
- 03_opinion_decode: 对他人观点/访谈/发言进行拆解解释
- 04_failure_reversal: 失败-复盘-纠偏
- 05_ab_benchmark: A/B对比评测
- 06_checklist_template: 技术分享（工作流/skill/提示词/教程）
- 07_contrarian_take: 反常识立场
- 08_signal_to_action: 信号趋势并给行动建议

输入：
title: {item.get('title','')}
preview: {item.get('preview','')}
author: @{item.get('author','')}
url: {item.get('url','')}

只输出JSON，不要多余文本：
{{"type":"...","reason":"..."}}
""".strip()

    cmd = [
        "openclaw", "agent", "--json",
        "--session-id", sid,
        "--message", prompt,
    ]
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=180)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    raw = (p.stdout or "").strip()
    s, e = raw.find("{"), raw.rfind("}")
    obj = json.loads(raw[s:e+1])
    txt = ((obj.get("payloads") or [{}])[0].get("text") or "").strip()
    s2, e2 = txt.find("{"), txt.rfind("}")
    res = json.loads(txt[s2:e2+1])
    t = (res.get("type") or "").strip()
    if t not in TYPES:
        t = "08_signal_to_action"
    return t, (res.get("reason") or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    src = Path(args.inp)
    out = Path(args.out)
    data = json.loads(src.read_text(encoding="utf-8"))
    items = data.get("items", [])

    rows = []
    changed = 0
    for i, it in enumerate(items, 1):
        old = it.get("type_guess", "")
        try:
            new, reason = call_llm(it, sid="reclassify-seed")
        except Exception as e:
            new, reason = old or "08_signal_to_action", f"fallback:{e}"
        if new != old:
            changed += 1
        r = dict(it)
        r["type_old"] = old
        r["type_new"] = new
        r["reclass_reason"] = reason
        rows.append(r)
        print(f"[{i}/{len(items)}] {old} -> {new}")

    grouped = {t: [] for t in TYPES}
    for r in rows:
        grouped[r["type_new"]].append(r)

    payload = {"count": len(rows), "changed": changed, "items": rows, "grouped": {k: len(v) for k, v in grouped.items()}}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# Reclassified Seed Articles", "", f"total={len(rows)} changed={changed}", ""]
    for t in TYPES:
        arr = grouped[t]
        md.append(f"## {t} ({len(arr)})")
        for j, x in enumerate(arr, 1):
            md.append(f"{j}. @{x.get('author','')} | old={x.get('type_old','')} | score={x.get('score',0)} | {x.get('title','')}")
            md.append(f"   - {x.get('url','')}")
            md.append(f"   - reason: {x.get('reclass_reason','')}")
        md.append("")
    out.with_suffix('.md').write_text('\n'.join(md), encoding='utf-8')
    print(out)
    print(out.with_suffix('.md'))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
