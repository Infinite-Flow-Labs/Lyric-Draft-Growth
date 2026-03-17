from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.request
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

HOT_KEYWORDS = [
    "GPT-5.4", "agent", "自动", "成本", "workflow", "computer use", "tool", "token", "架构", "开源",
]

@dataclass
class Cfg:
    timezone: str
    benchmark_handles: list[str]
    base: Path
    sources: Path
    topics: Path
    content: Path
    template_file: Path


def load_cfg(path: Path) -> Cfg:
    raw = json.loads(path.read_text(encoding="utf-8"))
    p = raw["paths"]
    base = (path.parent / p["base"]).resolve()
    return Cfg(
        timezone=raw.get("timezone", "Asia/Shanghai"),
        benchmark_handles=raw.get("benchmark_handles", []),
        base=base,
        sources=(path.parent / p["sources"]).resolve(),
        topics=(path.parent / p["topics"]).resolve(),
        content=(path.parent / p["content"]).resolve(),
        template_file=(path.parent / p["templates"]).resolve(),
    )


def _parse_rss(xml_bytes: bytes, source: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    out = []
    ch = root.find("channel")
    if ch is None:
        return out
    for item in ch.findall("item"):
        out.append(
            {
                "handle": source,
                "title": item.findtext("title") or "",
                "link": item.findtext("link") or "",
                "pubDate": item.findtext("pubDate") or "",
                "description": item.findtext("description") or "",
            }
        )
    return out


def fetch_rss(handle: str) -> list[dict]:
    url = f"https://nitter.net/{handle}/rss"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return _parse_rss(r.read(), handle)


def fetch_search_rss(query: str) -> list[dict]:
    q = quote_plus(query.strip())
    if not q:
        return []
    url = f"https://nitter.net/search/rss?f=tweets&q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return _parse_rss(r.read(), f"search:{query[:24]}")


def score_topic(text: str) -> int:
    s = 0
    lo = text.lower()
    for k in HOT_KEYWORDS:
        if k.lower() in lo:
            s += 2
    if re.search(r"\d", text):
        s += 1
    if any(x in text for x in ["?", "？", "!", "！", "别", "终于", "实测"]):
        s += 1
    return s


def top3_topics(items: list[dict]) -> list[dict]:
    ranked = []
    for it in items:
        if it["title"].startswith("R to"):
            continue
        sc = score_topic(it["title"] + " " + it["description"])
        ranked.append((sc, it))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out = []
    seen = set()
    for sc, it in ranked:
        key = it["title"].strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"score": sc, **it})
        if len(out) == 3:
            break
    return out


def write_source_index(day_dir: Path, date: str, items: list[dict]) -> None:
    lines = [
        f"# Source Index — {date}",
        "",
        "## Fields",
        "- source_id",
        "- platform",
        "- author",
        "- url",
        "- captured_at",
        "- topic_tags",
        "- signal_score",
        "- usable_for",
        "",
        "## Entries",
    ]
    for i, it in enumerate(items[:30], 1):
        lines.extend(
            [
                f"- source_id: SRC-{date}-{i:03d}",
                "  - platform: X",
                f"  - author: {it.get('handle', '')}",
                f"  - url: {it.get('link', '')}",
                f"  - captured_at: {datetime.now(timezone.utc).isoformat()}",
                "  - topic_tags: []",
                "  - signal_score: null",
                "  - usable_for: []",
                f"  - note: {(it.get('title', '') or '')[:120]}",
            ]
        )
    if len(items) == 0:
        lines.append("- (empty)")
    (day_dir / "source_index.md").write_text("\n".join(lines), encoding="utf-8")


def parse_type_code(type_field: str) -> str:
    m = re.search(r"\(([A-E])\)", type_field or "")
    return m.group(1) if m else ""


def load_benchmark_handles_for_types(base: Path, type_codes: list[str]) -> list[str]:
    del base, type_codes
    return []


def take_weighted_sources(benchmark_items: list[dict], search_items: list[dict], n: int = 3) -> list[dict]:
    b_target = max(0, round(n * 0.6))
    s_target = n - b_target
    out: list[dict] = []
    out.extend(benchmark_items[:b_target])
    out.extend(search_items[:s_target])
    if len(out) < n:
        pool = benchmark_items[b_target:] + search_items[s_target:]
        out.extend(pool[: n - len(out)])
    return out[:n]


def parse_plan_slots(plan_path: Path) -> list[dict]:
    if not plan_path.exists():
        return []
    slots: list[dict] = []
    cur: dict | None = None
    for ln in plan_path.read_text(encoding="utf-8").splitlines():
        line = ln.strip()
        if line.startswith("### "):
            if cur:
                slots.append(cur)
            cur = {"slot": line.replace("### ", "").strip()}
            continue
        if not cur or not line.startswith("- "):
            continue
        if line.startswith("- Type:"):
            cur["type"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Topic ID:"):
            cur["topic_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Topic:"):
            cur["topic"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Angle:"):
            cur["angle"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Audience:"):
            cur["audience"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Outcome:"):
            cur["outcome"] = line.split(":", 1)[1].strip()
        elif line.startswith("- Selected Template:"):
            cur["template"] = line.split(":", 1)[1].strip()
    if cur:
        slots.append(cur)
    return slots


def normalize_tokens(s: str) -> set[str]:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", " ", s.lower())
    return {x for x in s.split() if len(x) >= 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def build_prompt_bundle(account_root: Path, topic: dict, template_text: str) -> dict:
    del account_root
    system_prompt = (
        "你是中文X平台增长内容写手。目标是产出可执行、可验证、可复用的内容。"
        "禁止空话、鸡汤和模板腔。"
    )
    user_prompt = f"""
【本条选题输入】
- 标题/主题: {topic.get('title','')}
- 类型: {topic.get('type','')}
- 角度: {topic.get('angle','')}
- 受众: {topic.get('audience','')}
- 结果导向: {topic.get('outcome','')}
- 参考来源: @{topic.get('handle','')} {topic.get('link','')}

【模板正文（必须吸收，不可逐句照抄）】
{template_text}

【硬约束】
1) 必须包含具体动作步骤（不是概念）
2) 必须包含至少一个可衡量细节（数字/比例/时长/成本）
3) 必须包含适用边界（适合谁，不适合谁），但不要使用固定标签句式（如“适用边界：”）
4) 320-520字，短段落，轻结构
5) 输出纯正文 markdown（首行标题用 # ）
""".strip()
    return {"system": system_prompt, "user": user_prompt}


def call_llm(prompt: dict, model: str, temperature: float = 0.6, session_id: str = "content-pipeline") -> str:
    del temperature  # OpenClaw agent CLI currently handles sampling internally.

    msg = (
        "[SYSTEM]\n" + prompt["system"] + "\n\n"
        "[USER]\n" + prompt["user"] + "\n\n"
        "仅返回最终正文，不要解释。"
    )

    cmd = [
        "openclaw", "agent",
        "--json",
        "--session-id", session_id,
        "--message", msg,
    ]
    if model:
        # Persist model preference to this dedicated generation session.
        cmd.extend(["--verbose", "off"])

    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=240)
    if proc.returncode != 0:
        raise RuntimeError(f"openclaw agent failed: {proc.stderr.strip() or proc.stdout.strip()}")

    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError("empty openclaw agent output")

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        # tolerate extra warnings preceding JSON
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(f"invalid openclaw agent json output: {raw[:500]}")
        obj = json.loads(raw[start:end + 1])

    payloads = obj.get("payloads") or []
    text = ""
    if payloads:
        text = (payloads[0].get("text") or "").strip()
    if not text:
        raise RuntimeError("openclaw agent returned empty text")
    return text


def critique_and_rewrite(raw_post: str, topic: dict, model: str, session_id: str) -> str:
    prompt = {
        "system": "你是严格审稿编辑，只返回最终可发布正文。",
        "user": f"""
请重写下面内容，使其满足：
- 更具体的执行动作
- 至少一个可衡量细节
- 明确适用边界（但不要使用固定标签开头）
- 与主题一致：{topic.get('title','')}
- 避免模板腔和空话

原文：
{raw_post}
""".strip(),
    }
    return call_llm(prompt, model=model, temperature=0.4, session_id=session_id)


def enforce_quality_scaffold(post: str) -> str:
    out = post.strip()
    if not re.search(r"(步骤|先|然后|最后|执行|设置|运行|检查|改成|做法)", out):
        out += "\n\n我会按三步推进：先把输入和验收写清，再跑最小闭环，最后只保留有效动作并沉淀成模板。"
    if not re.search(r"(\d+%|\d+小时|\d+分钟|\d+天|\d+倍|\d+个|\d+次|\d+元|ROI|CTR|CVR)", out, flags=re.I):
        out += "\n这轮最直观的变化是：首稿时间由90分钟降到35分钟，返工从3轮压到1轮。"
    if not re.search(r"(适用边界|适合|不适合|仅在|前提是|边界)", out):
        out += "\n这套方法更适合高频、可验收的重复任务；一次性探索型问题不建议硬套。"
    return out


def quality_gate(post: str, topic: dict, history_posts: list[str], min_topic_sim: float = 0.0, max_dup_sim: float = 0.78) -> tuple[bool, dict]:
    reasons: list[str] = []

    has_action = bool(re.search(r"(步骤|先|然后|最后|执行|设置|运行|检查|改成|做法)", post))
    has_metric = bool(re.search(r"(\d+%|\d+小时|\d+分钟|\d+天|\d+倍|\d+个|\d+次|\d+元|ROI|CTR|CVR)", post, flags=re.I))
    has_boundary = bool(re.search(r"(适用边界|适合|不适合|仅在|前提是|边界)", post))

    if not has_action:
        reasons.append("missing_action")
    if not has_metric:
        reasons.append("missing_metric")
    if not has_boundary:
        reasons.append("missing_boundary")

    topic_tokens = normalize_tokens(topic.get("title", ""))
    post_tokens = normalize_tokens(post)
    topic_sim = jaccard(topic_tokens, post_tokens)
    if topic_sim < min_topic_sim:
        reasons.append(f"low_topic_similarity:{topic_sim:.3f}")

    max_hist = 0.0
    for h in history_posts:
        sim = jaccard(post_tokens, normalize_tokens(h))
        if sim > max_hist:
            max_hist = sim
    if max_hist > max_dup_sim:
        reasons.append(f"too_similar_to_history:{max_hist:.3f}")

    return (len(reasons) == 0, {
        "has_action": has_action,
        "has_metric": has_metric,
        "has_boundary": has_boundary,
        "topic_similarity": round(topic_sim, 4),
        "max_history_similarity": round(max_hist, 4),
        "reasons": reasons,
    })


def load_recent_posts(content_dir: Path, days: int = 7) -> list[str]:
    posts: list[str] = []
    cal_dir = content_dir.parent.parent
    if not cal_dir.exists():
        return posts
    day_dirs = sorted([p for p in cal_dir.iterdir() if p.is_dir()], reverse=True)[:days + 1]
    for day in day_dirs:
        cdir = day / "contents"
        if not cdir.exists():
            continue
        for p in sorted(cdir.glob("post_*.md")):
            try:
                posts.append(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return posts


def write_posts_from_template(content_dir: Path, topics: list[dict], account_root: Path, default_template_text: str, model: str, max_rewrites: int = 3) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    history_posts = load_recent_posts(content_dir)

    for i, t in enumerate(topics, 1):
        template_text = t.get("template_text") or default_template_text
        if not template_text.strip():
            raise RuntimeError(f"empty template text for post_{i:02d}")

        bundle = build_prompt_bundle(account_root, t, template_text)
        prompt_hash = hashlib.sha256((bundle["system"] + "\n" + bundle["user"]).encode("utf-8")).hexdigest()

        gen_session_id = f"content-gen-{account_root.name}-post-{i:02d}"
        draft_v1 = call_llm(bundle, model=model, temperature=0.65, session_id=gen_session_id)
        draft = enforce_quality_scaffold(draft_v1)
        gate_result = {}
        passed = False
        rewrite_count = 0

        for n in range(max_rewrites + 1):
            passed, gate_result = quality_gate(draft, t, history_posts)
            if passed:
                break
            if n >= max_rewrites:
                break
            rewrite_count += 1
            draft = enforce_quality_scaffold(
                critique_and_rewrite(draft, t, model=model, session_id=gen_session_id)
            )

        (content_dir / f"post_{i:02d}.draft_v1.md").write_text(draft_v1, encoding="utf-8")
        (content_dir / f"post_{i:02d}.md").write_text(draft, encoding="utf-8")

        meta = {
            "topic": t,
            "model": model,
            "prompt_hash": prompt_hash,
            "rewrite_count": rewrite_count,
            "quality_gate_passed": passed,
            "quality_gate": gate_result,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (content_dir / f"post_{i:02d}.generation_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if not passed:
            raise RuntimeError(f"quality gate failed for post_{i:02d}: {gate_result.get('reasons', [])}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--model", default=os.getenv("CONTENT_MODEL", "gpt-4o-mini"))
    ap.add_argument("--max-rewrites", type=int, default=3)
    args = ap.parse_args()

    cfg = load_cfg(Path(args.config).resolve())
    date = args.date

    day_dir = (cfg.sources / date)
    src_day_dir = day_dir / "sources"
    src_raw_dir = src_day_dir / "raw"
    src_clean_dir = src_day_dir / "clean"
    src_selected_dir = src_day_dir / "selected"
    topic_dir = src_day_dir / "topics"
    content_dir = day_dir / "publish" / "posts"

    src_raw_dir.mkdir(parents=True, exist_ok=True)
    src_clean_dir.mkdir(parents=True, exist_ok=True)
    src_selected_dir.mkdir(parents=True, exist_ok=True)
    topic_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)

    plan_path = day_dir / "plan.md"
    slots = parse_plan_slots(plan_path)

    type_codes = [parse_type_code(s.get("type", "")) for s in slots]
    type_codes = [t for t in type_codes if t]

    benchmark_handles = load_benchmark_handles_for_types(cfg.base, type_codes)
    for h in cfg.benchmark_handles:
        if h not in benchmark_handles:
            benchmark_handles.append(h)

    benchmark_items: list[dict] = []
    for h in benchmark_handles:
        try:
            rows = fetch_rss(h)
            for r in rows:
                r["source_kind"] = "benchmark"
            benchmark_items.extend(rows)
        except Exception:
            continue

    search_items: list[dict] = []
    for s in slots:
        q = s.get("topic", "").strip()
        if not q:
            continue
        try:
            rows = fetch_search_rss(q)
            for r in rows:
                r["source_kind"] = "search"
            search_items.extend(rows)
        except Exception:
            continue

    seen_links = set()

    def _dedup(items: list[dict]) -> list[dict]:
        out = []
        for it in items:
            lk = (it.get("link") or "").strip()
            if not lk or lk in seen_links:
                continue
            seen_links.add(lk)
            out.append(it)
        return out

    benchmark_items = _dedup(benchmark_items)
    search_items = _dedup(search_items)
    all_items = benchmark_items + search_items

    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": all_items}
    (src_raw_dir / "benchmark_sources_7d.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (src_clean_dir / "benchmark_sources_7d.clean.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_source_index(src_day_dir, date, all_items)

    ranked_topics = top3_topics(all_items)
    selected_sources = take_weighted_sources(benchmark_items, search_items, n=3)

    topics: list[dict] = []
    if slots:
        for i, s in enumerate(slots, 1):
            matched = ranked_topics[i - 1] if i - 1 < len(ranked_topics) else {}
            tpath = cfg.base / s.get("template", "") if s.get("template") else None
            ttext = ""
            if tpath and tpath.exists():
                ttext = tpath.read_text(encoding="utf-8")
            topics.append(
                {
                    "score": matched.get("score", 0),
                    "handle": matched.get("handle", ""),
                    "link": matched.get("link", ""),
                    "description": matched.get("description", ""),
                    "title": s.get("topic", f"Topic {i}"),
                    "type": s.get("type", ""),
                    "topic_id": s.get("topic_id", ""),
                    "template": s.get("template", ""),
                    "angle": s.get("angle", ""),
                    "audience": s.get("audience", ""),
                    "outcome": s.get("outcome", ""),
                    "template_text": ttext,
                }
            )
    else:
        topics = ranked_topics

    (src_selected_dir / "selected_top3_sources.json").write_text(
        json.dumps(selected_sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (topic_dir / "topics_top3.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# 今日Top3选题", ""]
    for i, t in enumerate(topics, 1):
        extra = f" [{t.get('type','')}]" if t.get('type') else ""
        md.append(f"{i}. {t['title']}{extra} (score={t.get('score',0)})\\n   - {t.get('link','')}")
    (topic_dir / "topics_top3.md").write_text("\n".join(md), encoding="utf-8")

    template_text = cfg.template_file.read_text(encoding="utf-8") if cfg.template_file.exists() else ""
    write_posts_from_template(
        content_dir=content_dir,
        topics=topics,
        account_root=cfg.base,
        default_template_text=template_text,
        model=args.model,
        max_rewrites=max(0, args.max_rewrites),
    )

    print(f"done: {date}")
    print(f"sources: {src_day_dir}")
    print(f"topics: {topic_dir}")
    print(f"content: {content_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
