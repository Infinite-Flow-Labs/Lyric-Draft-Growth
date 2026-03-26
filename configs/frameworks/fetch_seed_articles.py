from __future__ import annotations

import argparse
import email.utils
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_rss(handle: str) -> list[dict]:
    url = f"https://nitter.net/{handle}/rss"
    try:
        data = http_get(url)
        root = ET.fromstring(data)
    except Exception:
        return []
    ch = root.find("channel")
    if ch is None:
        return []
    out = []
    for it in ch.findall("item"):
        link = (it.findtext("link") or "").strip().replace("https://nitter.net/", "https://x.com/").replace("#m", "")
        out.append(
            {
                "handle": handle,
                "title": (it.findtext("title") or "").strip(),
                "link": link,
                "pubDate": (it.findtext("pubDate") or "").strip(),
            }
        )
    return out


def parse_date(s: str) -> datetime | None:
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def fxtwitter_article(link: str) -> dict | None:
    m = re.search(r"x\.com/([^/]+)/status/(\d+)", link)
    if not m:
        return None
    handle, sid = m.group(1), m.group(2)
    api = f"https://api.fxtwitter.com/{handle}/status/{sid}"
    try:
        obj = json.loads(http_get(api, timeout=30).decode("utf-8", "ignore"))
    except Exception:
        return None
    tw = obj.get("tweet") or {}
    art = tw.get("article") or {}
    if not art:
        return None
    return {
        "url": tw.get("url", link),
        "author": (tw.get("author") or {}).get("screen_name", handle),
        "created_at": tw.get("created_at", ""),
        "views": tw.get("views", 0),
        "likes": tw.get("likes", 0),
        "retweets": tw.get("retweets", 0),
        "bookmarks": tw.get("bookmarks", 0),
        "replies": tw.get("replies", 0),
        "title": art.get("title", ""),
        "preview": art.get("preview_text", ""),
    }


def route_type(title: str, preview: str) -> str:
    text = f"{title}\n{preview}".lower()
    text_zh = f"{title}\n{preview}"
    if re.search(r"(赚|收入|美金|mrr|arr|revenue|income|变现)", text_zh):
        return "01_money_proof"
    if re.search(r"(发布|上线|launch|release|update|新功能|mcp|skill|app|product|llm|agent)", text_zh):
        return "02_launch_application"
    if re.search(r"(said|表示|访谈|podcast|观点|采访|对话)", text_zh):
        return "03_opinion_decode"
    if re.search(r"(失败|复盘|踩坑|教训|mistake|lesson)", text_zh):
        return "04_failure_reversal"
    if re.search(r"(vs|对比|评测|benchmark|横评)", text_zh):
        return "05_ab_benchmark"
    if re.search(r"(工作流|skill|提示词|prompt|教程|how to|步骤|配置|安装)", text_zh):
        return "06_checklist_template"
    if re.search(r"(反常识|误区|我不同意|contrarian)", text_zh):
        return "07_contrarian_take"
    return "08_signal_to_action"


def score(x: dict) -> float:
    views = float(x.get("views") or 0)
    eng = float(x.get("likes") or 0) + 1.2 * float(x.get("retweets") or 0) + 1.5 * float(x.get("bookmarks") or 0) + float(x.get("replies") or 0)
    return round((eng / max(100.0, views)) + 0.2, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-per-handle", type=int, default=20)
    args = ap.parse_args()

    seed = Path(args.seed)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    handles = [ln.strip().lstrip("@") for ln in seed.read_text(encoding="utf-8").splitlines() if ln.strip()]
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    all_rows = []
    for h in handles:
        rss_items = parse_rss(h)
        cnt = 0
        for it in rss_items:
            dt = parse_date(it.get("pubDate", ""))
            if dt and dt < cutoff:
                continue
            link = it.get("link", "")
            if "/status/" not in link:
                continue
            art = fxtwitter_article(link)
            if not art:
                continue
            art["type_guess"] = route_type(art.get("title", ""), art.get("preview", ""))
            art["score"] = score(art)
            all_rows.append(art)
            cnt += 1
            if cnt >= args.max_per_handle:
                break

    # dedup by url
    dedup = {}
    for r in all_rows:
        dedup[r["url"]] = r
    rows = list(dedup.values())
    rows.sort(key=lambda x: x.get("score", 0), reverse=True)

    out_json = out_dir / "seed_articles_30d.json"
    out_json.write_text(json.dumps({"count": len(rows), "items": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    # grouped markdown for review
    by_type = {}
    for r in rows:
        by_type.setdefault(r["type_guess"], []).append(r)

    md = [f"# Seed Articles Review (last {args.days} days)", "", f"Total: {len(rows)}", ""]
    order = [
        "01_money_proof", "02_launch_application", "03_opinion_decode", "04_failure_reversal",
        "05_ab_benchmark", "06_checklist_template", "07_contrarian_take", "08_signal_to_action",
    ]
    for t in order:
        arr = by_type.get(t, [])
        md.append(f"## {t} ({len(arr)})")
        for i, x in enumerate(arr[:50], 1):
            md.append(f"{i}. @{x['author']} | score={x['score']} | {x['title']}")
            md.append(f"   - {x['url']}")
        md.append("")

    out_md = out_dir / "seed_articles_grouped_30d.md"
    out_md.write_text("\n".join(md), encoding="utf-8")

    print(out_json)
    print(out_md)
    print(f"count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
