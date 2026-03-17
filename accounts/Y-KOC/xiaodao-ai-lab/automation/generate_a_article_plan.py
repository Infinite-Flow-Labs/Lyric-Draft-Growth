from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def load_macro_topics(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(\d+)\.\s*\*\*(.+?)\*\*", ln)
        if m:
            out.append(m.group(2).strip())
    return out


def load_recent_hot_signals(signals_path: Path, limit: int = 10) -> list[dict]:
    if not signals_path.exists():
        return []
    try:
        data = json.loads(signals_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for s in (data.get("signals") or [])[:limit]:
        ex = (s.get("external_urls") or [])
        out.append(
            {
                "account": s.get("handle", ""),
                "post_url": s.get("link", ""),
                "external_url": ex[0] if ex else "",
                "published_at": s.get("published_at", ""),
                "title": s.get("title", "")[:180],
                "score": s.get("score", 0),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    date = args.date

    macro_path = (
        acc.parent
        / "_shared"
        / "corpus"
        / "A_opportunity_replacement"
        / "macro_topics_A_v1.md"
    )
    signals_path = acc / "calendar" / date / "hot_signals.json"

    topics = load_macro_topics(macro_path)
    if not topics:
        raise SystemExit(f"macro topics missing: {macro_path}")

    dt = datetime.strptime(date, "%Y-%m-%d")
    macro_topic = topics[dt.timetuple().tm_yday % len(topics)]

    hot_signals = load_recent_hot_signals(signals_path, limit=10)[:3]

    cutpoint = "客服质检环节 + 从人工抽检转为AI预审"

    day_dir = acc / "calendar" / date
    day_dir.mkdir(parents=True, exist_ok=True)

    plan = {
        "type": "A",
        "date": date,
        "macro_topic": macro_topic,
        "topic": cutpoint,
        "hot_signals": hot_signals,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (day_dir / "article_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    md = [
        f"# {date} A-Article Plan",
        "",
        f"- Type: A（机会与替代）",
        f"- Macro Topic: {macro_topic}",
        f"- Topic（当天切口）: {cutpoint}",
        "",
        "## Hot Signals",
    ]
    if hot_signals:
        for s in hot_signals:
            post = s.get("post_url", "")
            ext = s.get("external_url", "")
            if ext:
                md.append(f"- [{s.get('account','')}] post: {post}")
                md.append(f"  external: {ext}")
            else:
                md.append(f"- [{s.get('account','')}] post: {post}")
    else:
        md.append("- (none)")

    (day_dir / "article_plan.md").write_text("\n".join(md), encoding="utf-8")
    print(day_dir / "article_plan.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
