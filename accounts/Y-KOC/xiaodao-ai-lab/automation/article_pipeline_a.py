from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def normalize_tokens(s: str) -> set[str]:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", " ", s.lower())
    return {x for x in s.split() if len(x) >= 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def retrieve_chunks(corpus_chunks: Path, topic: str, k: int = 8) -> list[dict]:
    rows = []
    for ln in corpus_chunks.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        text = obj.get("text", "")
        score = jaccard(normalize_tokens(topic), normalize_tokens(text))
        rows.append((score, obj))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in rows[:k]]


def call_llm(prompt: str, session_id: str) -> str:
    cmd = [
        "openclaw",
        "agent",
        "--json",
        "--session-id",
        session_id,
        "--message",
        prompt,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())

    raw = (proc.stdout or "").strip()
    s, e = raw.find("{"), raw.rfind("}")
    obj = json.loads(raw[s : e + 1])
    out = ((obj.get("payloads") or [{}])[0].get("text") or "").strip()
    if not out:
        raise RuntimeError("empty llm output")
    return out


def life_like_score(text: str) -> dict:
    # 生活化语感阈值（轻约束，仅记录，不拦截）
    first_person = len(re.findall(r"(我|我们|我当时|后来我|我发现)", text))
    scene_words = len(re.findall(r"(那天|当时|后来|一开始|结果|现场|同事|客户|团队里)", text))
    spoken = len(re.findall(r"(其实|说白了|说真的|坦白讲|老实说)", text))
    explicit_outline = len(re.findall(r"(^|\n)\s*(\d+\)|\d+\.|##\s*(Hook|Why now|重构映射|证据段|行动段|边界段|KPI))", text, flags=re.I))
    return {
        "first_person_hits": first_person,
        "scene_hits": scene_words,
        "spoken_style_hits": spoken,
        "explicit_outline_hits": explicit_outline,
        "life_like_ok": (first_person + scene_words + spoken) >= 8 and explicit_outline == 0,
    }


def format_for_x_article(text: str, max_chars: int = 180, max_sent_per_para: int = 2) -> str:
    """Post-process article into X-friendly short paragraphs."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []

    def split_para(p: str):
        p = p.strip()
        if not p:
            return []
        sents = re.split(r"(?<=[。！？!?])", p)
        sents = [s.strip() for s in sents if s.strip()]
        chunks, cur = [], ""
        sent_count = 0
        for s in sents:
            if (len(cur) + len(s) > max_chars) or (sent_count >= max_sent_per_para):
                if cur.strip():
                    chunks.append(cur.strip())
                cur = s
                sent_count = 1
            else:
                cur = (cur + " " + s).strip() if cur else s
                sent_count += 1
        if cur.strip():
            chunks.append(cur.strip())
        return chunks

    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        # normalize markdown heading/rule to plain-title style for X editor
        if s.startswith("#"):
            title = re.sub(r"^#+\s*", "", s).strip()
            out.append(f"【{title}】")
            out.append("")
            continue
        if s in {"---", "***", "___"}:
            out.append("")
            continue
        # avoid ordered-list auto-format in editor
        s = re.sub(r"^(\d+)\.\s+", r"\1）", s)
        out.extend(split_para(s))
        out.append("")

    # collapse excessive blanks
    cleaned = []
    blank = 0
    for ln in out:
        if ln.strip() == "":
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)
    return "\n".join(cleaned).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-root", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    acc = Path(args.account_root).resolve()
    day = acc / "calendar" / args.date
    plan = json.loads((day / "article_plan.json").read_text(encoding="utf-8"))

    corpus_chunks = (
        acc.parent / "_shared" / "corpus" / "A_opportunity_replacement" / "chunks.jsonl"
    )
    chunks = retrieve_chunks(corpus_chunks, plan["topic"], k=8)

    chunk_text = "\n\n".join(
        [f"[chunk:{c.get('chunk_id','')}]\n{c.get('text','')[:1000]}" for c in chunks]
    )

    prompt = f"""
写一篇中文长文，主题是：{plan['topic']}。
宏观选题：{plan['macro_topic']}。
请融合热点信号：{json.dumps(plan.get('hot_signals', []), ensure_ascii=False)}。

写作要求：
- 自然叙事写作，像真实操盘手复盘，不要讲课腔。
- 生活化语感：有场景、有转折、有人的动作和判断。
- 不要出现显式结构标签：例如“1) Hook / 2) Why now / KPI四件套 / 边界段”等。
- 但必须有“可读结构”：用 4-6 个自然小标题（人话风格），例如“先说结论 / 为什么是现在 / 具体怎么改 / 哪些坑别踩”。
- 每个小标题下 2-4 段短段落（每段 2-5 句），避免整篇大长段。
- 可以有清晰逻辑，但要藏在叙事里，不要模板化。
- 允许个性和随机性，不要千篇一律。

可参考语料：
{chunk_text}

输出：仅正文 markdown。
""".strip()

    article_raw = call_llm(prompt, session_id=f"a-article-natural-{acc.name}")
    article = format_for_x_article(article_raw, max_chars=170, max_sent_per_para=2)

    out_dir = day / "publish" / "article"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "article.md").write_text(article, encoding="utf-8")
    # plain text publish artifact for X editor (no markdown semantics)
    article_x_ready = re.sub(r"^【(.*?)】\s*$", r"\1", article, flags=re.M)
    article_x_ready = article_x_ready.replace("---", "")
    article_x_ready = re.sub(r"\n{3,}", "\n\n", article_x_ready).strip() + "\n"
    (out_dir / "article_x_ready.txt").write_text(article_x_ready, encoding="utf-8")

    style = life_like_score(article)
    meta = {
        "type": "A",
        "topic": plan["topic"],
        "macro_topic": plan["macro_topic"],
        "hot_signals": plan.get("hot_signals", []),
        "retrieved_chunks": [c.get("chunk_id", "") for c in chunks],
        "style_check": style,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "generation_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    notes = ["# Review Notes", "", "- quality_gate: removed (per user request)"]
    notes.append(f"- style_check: {json.dumps(style, ensure_ascii=False)}")
    (out_dir / "review_notes.md").write_text("\n".join(notes), encoding="utf-8")

    print(out_dir / "article.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
