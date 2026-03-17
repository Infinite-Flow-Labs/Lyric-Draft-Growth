from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime
import json
from pathlib import Path

TYPE_FILES = {
    "A": "topics_A_work_replacement.md",
    "B": "topics_B_ai_results.md",
    "C": "topics_C_augmentation.md",
    "D": "topics_D_experience.md",
    "E": "topics_E_workflow.md",
}

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
    folder_map = {
        "A": "A_work_replacement",
        "B": "B_ai_results",
        "C": "C_augmentation",
        "D": "D_experience",
        "E": "E_workflow",
    }
    d = acc / "strategy" / "templates" / folder_map[t]
    if not d.exists():
        return []
    files = sorted([p.name for p in d.glob("*.md") if p.name != "README.md"])
    return [f"strategy/templates/{folder_map[t]}/{name}" for name in files]


def pick_template(acc: Path, date: str, t: str, occurrence_in_week: int) -> str:
    cands = list_templates_for_type(acc, t)
    if not cands:
        # fallback path
        fallback = {
            "A": "strategy/templates/A_work_replacement/style_contrast_review.md",
            "B": "strategy/templates/B_ai_results/style_contrast_review.md",
            "C": "strategy/templates/C_augmentation/style_contrast_review.md",
            "D": "strategy/templates/D_experience/style_contrast_review.md",
            "E": "strategy/templates/E_workflow/style_contrast_review.md",
        }
        return fallback[t]

    # Weekly non-repeating rotation (per type): same week shifts from a stable offset,
    # then advances by occurrence count for that type within the week.
    dt = datetime.strptime(date, "%Y-%m-%d")
    iso = dt.isocalendar()
    seed = f"tpl-week-{iso.year}-{iso.week}-{t}".encode("utf-8")
    h = int(hashlib.md5(seed).hexdigest(), 16)
    start = h % len(cands)
    idx = (start + max(0, occurrence_in_week - 1)) % len(cands)
    return cands[idx]


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

    strategy_dir = acc / "strategy"
    topics_map: dict[str, list[tuple[str, str]]] = {}
    for t, f in TYPE_FILES.items():
        p = strategy_dir / f
        topics_map[t] = parse_topics(p) if p.exists() else []

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
                    ws.get("template", ""),
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
        "A": "AI替代工作",
        "B": "AI创造结果",
        "C": "AI能力放大",
        "D": "AI使用体验",
        "E": "AI工作流分享",
    }

    lines = [
        f"# {date} Plan — {acc.name}",
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
                f"- Selected Template: {selected_template}",
                f"- Draft file: contents/post_{i:02d}.md",
                f"- Asset file: contents/assets/post_{i:02d}_1.jpg",
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
