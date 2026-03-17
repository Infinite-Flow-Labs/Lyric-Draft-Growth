from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

TYPE_FILES = {
    "A": "topics_A_work_replacement.md",
    "B": "topics_B_ai_results.md",
    "C": "topics_C_augmentation.md",
    "D": "topics_D_experience.md",
    "E": "topics_E_workflow.md",
}

TYPE_NAME = {
    "A": "AI替代工作",
    "B": "AI创造结果",
    "C": "AI能力放大",
    "D": "AI使用体验",
    "E": "AI工作流分享",
}

TEMPLATE_FOLDER = {
    "A": "A_work_replacement",
    "B": "B_ai_results",
    "C": "C_augmentation",
    "D": "D_experience",
    "E": "E_workflow",
}

DAY_MIX = [
    ("B", "A", "E"),
    ("A", "B", "D"),
    ("C", "B", "E"),
    ("B", "D", "A"),
    ("E", "A", "C"),
    ("D", "B", "E"),
    ("A", "C", "B"),
]

SLOTS = ["08:30", "12:00", "19:30"]
MODES = ["LOCK", "FLEX", "BREAKING"]


def parse_topics(md_path: Path) -> list[tuple[str, str]]:
    if not md_path.exists():
        return []
    txt = md_path.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for line in txt.splitlines():
        m = re.match(r"\s*(\d+)\.\s*(.+)\s*$", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def pick_topic(topics: list[tuple[str, str]], date: str, t: str, slot: int) -> tuple[str, str]:
    if not topics:
        return ("NA", "(empty)")
    seed = f"topic-{date}-{t}-{slot}".encode("utf-8")
    h = int(hashlib.md5(seed).hexdigest(), 16)
    return topics[h % len(topics)]


def list_templates(acc: Path, t: str) -> list[str]:
    d = acc / "strategy" / "templates" / TEMPLATE_FOLDER[t]
    if not d.exists():
        return []
    names = sorted([p.name for p in d.glob("*.md") if p.name != "README.md"])
    return [f"strategy/templates/{TEMPLATE_FOLDER[t]}/{n}" for n in names]


def pick_template(acc: Path, date: str, t: str, occ: int) -> str:
    cands = list_templates(acc, t)
    if not cands:
        return f"strategy/templates/{TEMPLATE_FOLDER[t]}/style_contrast_review.md"
    dt = datetime.strptime(date, "%Y-%m-%d")
    iso = dt.isocalendar()
    seed = f"tpl-week-{iso.year}-{iso.week}-{t}".encode("utf-8")
    h = int(hashlib.md5(seed).hexdigest(), 16)
    start = h % len(cands)
    idx = (start + max(0, occ - 1)) % len(cands)
    return cands[idx]


ANGLE_OPTIONS = ["反常识", "踩坑复盘", "数据对比", "方法拆解", "执行清单"]
AUDIENCE_OPTIONS = ["增长负责人", "内容运营", "独立开发者", "产品经理", "小团队创始人"]
OUTCOME_OPTIONS = ["节省时间", "提升产量", "降低返工", "提升稳定交付", "提高转化效率"]


def pick_meta(date: str, t: str, slot_idx: int) -> tuple[str, str, str]:
    seed = f"meta-{date}-{t}-{slot_idx}".encode("utf-8")
    h = int(hashlib.md5(seed).hexdigest(), 16)
    angle = ANGLE_OPTIONS[h % len(ANGLE_OPTIONS)]
    audience = AUDIENCE_OPTIONS[(h // 7) % len(AUDIENCE_OPTIONS)]
    outcome = OUTCOME_OPTIONS[(h // 13) % len(OUTCOME_OPTIONS)]
    return angle, audience, outcome


def source_directions(type_codes: list[str]) -> list[str]:
    mapping = {
        "A": "替代工作类对标博主近7天实操帖（自动化、流程替代、降本提效）",
        "B": "结果导向类对标博主案例帖（数据增长、转化提升、交付提速）",
        "C": "能力放大类对标博主方法帖（并行能力、决策杠杆、团队化协作）",
        "D": "使用体验类对标博主复盘帖（上手体验、优缺点、踩坑修正）",
        "E": "工作流类对标博主教程帖（SOP、workflow、可复制步骤）",
    }
    out = []
    seen = set()
    for t in type_codes:
        if t in mapping and t not in seen:
            seen.add(t)
            out.append(mapping[t])
    out.append("当天选题关键词反推热点源（保证时效）")
    out.append("抓源比例：60%类型对标博主源 + 40%选题反推热点源")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    strategy_dir = acc / "strategy"
    dt0 = datetime.strptime(args.start_date, "%Y-%m-%d")

    topics_map: dict[str, list[tuple[str, str]]] = {
        t: parse_topics(strategy_dir / f) for t, f in TYPE_FILES.items()
    }

    weekly_struct = {
        "start_date": args.start_date,
        "end_date": (dt0 + timedelta(days=args.days - 1)).strftime("%Y-%m-%d"),
        "days": {},
    }

    lines = [
        f"# Weekly Plan ({weekly_struct['start_date']} ~ {weekly_struct['end_date']})",
        "",
    ]

    for i in range(args.days):
        d = (dt0 + timedelta(days=i)).strftime("%Y-%m-%d")
        mix = DAY_MIX[(dt0 + timedelta(days=i)).weekday() % len(DAY_MIX)]

        slots = []
        type_seen: dict[str, int] = {}
        for idx, (tm, t, mode) in enumerate(zip(SLOTS, mix, MODES), 1):
            tid, topic = pick_topic(topics_map.get(t, []), d, t, idx)
            type_seen[t] = type_seen.get(t, 0) + 1
            tpl = pick_template(acc, d, t, type_seen[t])
            angle, audience, outcome = pick_meta(d, t, idx)
            slots.append(
                {
                    "slot": tm,
                    "type": f"{TYPE_NAME[t]} ({t})",
                    "mode": mode,
                    "topic_id": tid,
                    "topic": topic,
                    "template": tpl,
                    "angle": angle,
                    "audience": audience,
                    "outcome": outcome,
                }
            )

        weekly_struct["days"][d] = {"slots": slots}

        lines.append(f"## {d}")
        lines.append("- 内容源方向：")
        for s in source_directions(list(mix)):
            lines.append(f"  - {s}")
        lines.append("- 当天3条：")
        for j, s in enumerate(slots, 1):
            lines.append(f"  {j}) 时间：{s['slot']} | 内容类型：{s['type']} | 模式：{s['mode']}")
            lines.append(f"     选题：{s['topic']}")
            lines.append(f"     模板：{Path(s['template']).stem}")
            lines.append(f"     角度：{s['angle']} | 对象：{s['audience']} | 结果锚点：{s['outcome']}")
        lines.append("")

    out_path = Path(args.out).resolve() if args.out else (acc / "weekly_plan" / "week-01.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(weekly_struct, ensure_ascii=False, indent=2), encoding="utf-8")

    print(out_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
