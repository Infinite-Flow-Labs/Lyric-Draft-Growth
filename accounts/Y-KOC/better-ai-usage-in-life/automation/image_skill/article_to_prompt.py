from __future__ import annotations

from pathlib import Path


def build_prompt_from_article(text: str, title: str | None = None) -> str:
    title = title or "AI workflow results"
    # KOC-style clean infographic cover prompt
    return (
        "Create a clean, modern X/Twitter cover image in 16:9 infographic style. "
        f"Topic: {title}. "
        "Visualize: real workflow, clear before/after improvement, practical and credible tone, "
        "minimal icons, high readability, no clutter, no watermark, no logo, no extra text artifacts. "
        "Color style: dark background with blue-purple accent, professional and restrained."
    )


def read_article_title_and_body(path: Path) -> tuple[str, str]:
    txt = path.read_text(encoding="utf-8")
    lines = txt.splitlines()
    title = ""
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        body = txt.strip()
    return title, body
