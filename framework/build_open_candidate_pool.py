from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

QUERIES = [
    "AI agent workflow", "OpenClaw article", "MCP skill", "prompt engineering case study",
    "AI automation revenue", "AI side project income", "AI tool launch how to use",
    "LLM memory system", "RAG workflow", "AI founder interview article",
    "AI coding workflow", "Claude Code workflow", "Cursor workflow", "DeepSeek Kimi analysis",
    "OpenAI Anthropic product launch", "AI创业 复盘", "AI 工作流 教程", "提示词 实战",
    "AI 产品 发布 应用", "Agent 自动化 案例", "AI 赚钱 复盘", "播客 AI 访谈",
]


def http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search_rss(query: str) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    url = f"https://nitter.net/search/rss?f=tweets&q={q}"
    try:
        data = http_get(url)
    except Exception:
        return []
    try:
        root = ET.fromstring(data)
    except Exception:
        return []
    ch = root.find("channel")
    if ch is None:
        return []
    out = []
    for it in ch.findall("item"):
        out.append(
            {
                "query": query,
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip().replace("https://nitter.net/", "https://x.com/").replace("#m", ""),
                "pubDate": (it.findtext("pubDate") or "").strip(),
                "description": (it.findtext("description") or "").strip(),
            }
        )
    return out


def fxtwitter_status(url: str) -> dict | None:
    m = re.search(r"x\.com/([^/]+)/status/(\d+)", url)
    if not m:
        return None
    handle, sid = m.group(1), m.group(2)
    api = f"https://api.fxtwitter.com/{handle}/status/{sid}"
    try:
        obj = json.loads(http_get(api, timeout=30).decode("utf-8", "ignore"))
        return obj.get("tweet")
    except Exception:
        return None


def route_type(text: str) -> str:
    t = text.lower()
    if re.search(r"(赚|收入|美金|mrr|arr|增长\d|转化|revenue|income)", text):
        return "01_money_proof"
    if re.search(r"(发布|上线|introducing|launch|release|新功能|update|mcp|skill|app|product|llm|agent)", text):
        return "02_launch_application"
    if re.search(r"(said|表示|访谈|podcast|观点|认为|opinion|采访)", text):
        return "03_opinion_decode"
    if re.search(r"(失败|复盘|踩坑|教训|mistake|lesson)", text):
        return "04_failure_reversal"
    if re.search(r"(vs|对比|评测|benchmark|横评)", text):
        return "05_ab_benchmark"
    if re.search(r"(工作流|skill|提示词|prompt|教程|how to|步骤|配置)", text):
        return "06_checklist_template"
    if re.search(r"(反常识|误区|我不同意|contrarian)", text):
        return "07_contrarian_take"
    return "08_signal_to_action"


def score(tweet: dict) -> float:
    views = float(tweet.get("views") or 0)
    likes = float(tweet.get("likes") or 0)
    rt = float(tweet.get("retweets") or 0)
    bk = float(tweet.get("bookmarks") or 0)
    replies = float(tweet.get("replies") or 0)
    eng = likes + rt * 1.2 + bk * 1.5 + replies
    base = eng / max(100.0, views)
    art_bonus = 0.25 if tweet.get("article") else 0.0
    return round(base + art_bonus, 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    rows = []
    seen = set()
    for q in QUERIES:
        for it in search_rss(q)[:25]:
            link = it["link"]
            if not link or link in seen or "/status/" not in link:
                continue
            seen.add(link)
            tw = fxtwitter_status(link)
            if not tw:
                continue
            art = tw.get("article") or {}
            txt = (art.get("title") or "") + "\n" + (art.get("preview_text") or "")
            if not art:
                continue
            rows.append(
                {
                    "type_guess": route_type(txt),
                    "url": tw.get("url", link),
                    "author": (tw.get("author") or {}).get("screen_name", ""),
                    "title": art.get("title", ""),
                    "preview": art.get("preview_text", ""),
                    "created_at": tw.get("created_at", ""),
                    "views": tw.get("views", 0),
                    "likes": tw.get("likes", 0),
                    "retweets": tw.get("retweets", 0),
                    "bookmarks": tw.get("bookmarks", 0),
                    "replies": tw.get("replies", 0),
                    "score": score(tw),
                }
            )

    rows.sort(key=lambda x: x["score"], reverse=True)
    rows = rows[: args.limit]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queries": QUERIES,
        "count": len(rows),
        "candidates": rows,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(args.out)
    print(f"count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
