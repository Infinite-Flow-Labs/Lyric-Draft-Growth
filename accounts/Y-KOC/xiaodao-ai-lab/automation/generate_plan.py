from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime
import json
from pathlib import Path

TYPE_FILES = {}

# 7-day rotation for day-level mix (3 posts/day)
DAY_MIX = [
    ("B", "A", "E"),
    ("A", "B", "D"),
    ("C", "B", "E"),
    ("B", "D", "A"),
    ("E", "A", "C"),
    ("D", "B", "E"),
    ("A", "C", "B"),
]


def parse_topics(md_path: Path) -> list[tuple[str, str]]:
    txt = md_path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for line in txt.splitlines():
        m = re.match(r"\s*(\d+)\.\s*(.+)\s*$", line)
        if not m:
            continue
        out.append((m.group(1), m.group(2)))
    return out


def pick_topic(topics: list[tuple[str, str]], date: str, t: str, slot: int) -> tuple[str, str]:
    if not topics:
        return ("NA", "(empty)")
    seed = f"{date}-{t}-{slot}".encode("utf-8")
    h = int(hashlib.md5(seed).hexdigest(), 16)
    return topics[h % len(topics)]


def list_templates_for_type(acc: Path, t: str) -> list[str]:
    del acc, t
    return []


def pick_template(acc: Path, date: str, t: str, occurrence_in_week: int) -> str:
    del acc, date, t, occurrence_in_week
    return ""


def load_weekly_slots(acc: Path, date: str) -> list[dict]:
    p = acc / "weekly_plan" / "week-01.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return (data.get("days", {}).get(date, {}) or {}).get("slots", []) or []
    except Exception:
        return []


def parse_type_code(type_field: str) -> str:
    m = re.search(r"\(([A-E])\)", type_field or "")
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    date = args.date

    dt = datetime.strptime(date, "%Y-%m-%d")
    mix = DAY_MIX[dt.weekday() % len(DAY_MIX)]

    topics_map: dict[str, list[tuple[str, str]]] = {t: [] for t in ["A", "B", "C", "D", "E"]}

    weekly_slots = load_weekly_slots(acc, date)
    picks = []
    if weekly_slots:
        for i, ws in enumerate(weekly_slots[:3], 1):
            t = parse_type_code(ws.get("type", "")) or mix[i - 1]
            tid = ws.get("topic_id", "") or "NA"
            title = ws.get("topic", "") or "(empty)"
            picks.append(
                (
                    i,
                    t,
                    tid,
                    title,
                    "",
                    ws.get("mode", "FLEX"),
                    ws.get("angle", ""),
                    ws.get("audience", ""),
                    ws.get("outcome", ""),
                )
            )
        mix = tuple([p[1] for p in picks])  # refresh displayed day mix from weekly plan
    else:
        for i, t in enumerate(mix, 1):
            tid, title = pick_topic(topics_map[t], date, t, i)
            picks.append((i, t, tid, title, "", ["LOCK", "FLEX", "BREAKING"][i - 1], "", "", ""))

    day_dir = acc / "calendar" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    plan_path = day_dir / "plan.md"

    type_name = {
        "A": "机会与替代",
        "B": "方法与流程",
        "C": "结果与增长",
        "D": "工具与系统",
        "E": "风险与治理",
    }

    lines = [
        f"# {date} Plan — xiaodao-ai-lab",
        "",
        "## Day-level Mix (3 posts)",
        f"1) {type_name[mix[0]]} ({mix[0]})",
        f"2) {type_name[mix[1]]} ({mix[1]})",
        f"3) {type_name[mix[2]]} ({mix[2]})",
        "",
        "## Slots",
    ]

    slots = ["08:30", "12:00", "19:30"]

    type_seen: dict[str, int] = {}
    for (i, t, tid, title, pre_tpl, mode, angle, audience, outcome), tm in zip(picks, slots):
        type_seen[t] = type_seen.get(t, 0) + 1
        selected_template = pre_tpl or pick_template(acc, date, t, type_seen[t])
        lines.extend(
            [
                f"### {tm}",
                f"- Type: {type_name[t]} ({t})",
                f"- Mode: {mode}",
                f"- Topic ID: {tid}",
                f"- Topic: {title}",
                f"- Angle: {angle}",
                f"- Audience: {audience}",
                f"- Outcome: {outcome}",
                f"- Selected Template: {selected_template or '(none)'}",
                f"- Draft file: publish/posts/post_{i:02d}.md",
                f"- Asset file: publish/posts/assets/post_{i:02d}_1.jpg",
                "- Channel: X",
                "- Status: planned",
                "",
            ]
        )

    lines.extend(
        [
            "## Constraints",
            "- spacing >= 2–3 hours",
            "- keep light-structured writing",
            "- keep de-template tone",
        ]
    )

    plan_path.write_text("\n".join(lines), encoding="utf-8")
    print(plan_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
