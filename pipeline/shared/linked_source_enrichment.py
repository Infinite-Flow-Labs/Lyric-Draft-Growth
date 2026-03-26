from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any


URL_RE = re.compile(r"https?://[^\s<>()\[\]{}\"']+")
WHITESPACE_RE = re.compile(r"\s+")
HTML_TAG_RE = re.compile(r"<[^>]+>")

SOCIAL_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "nitter.net",
    "www.nitter.net",
    "t.co",
    "www.t.co",
}

LINKED_REPORT_HINTS = ("report", "paper", "whitepaper", "research", "arxiv", ".pdf")
LINKED_DOCS_HINTS = ("docs.", "/docs", "documentation", "api.", "reference")
LINKED_CHANGELOG_HINTS = ("changelog", "release-notes", "releases", "/news")


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in URL_RE.findall(text):
        cleaned = raw.rstrip(").,;!?\"']}")
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def is_external_link(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    if not host:
        return False
    return host not in SOCIAL_HOSTS


def classify_link_kind(url: str) -> str:
    lowered = url.lower()
    if any(token in lowered for token in LINKED_REPORT_HINTS):
        return "linked_report"
    if any(token in lowered for token in LINKED_DOCS_HINTS):
        return "linked_docs"
    if any(token in lowered for token in LINKED_CHANGELOG_HINTS):
        return "linked_changelog"
    return "linked_article"


def _proxy_url(url: str) -> str:
    if url.startswith("https://r.jina.ai/"):
        return url
    if url.startswith("http://"):
        return "https://r.jina.ai/http://" + url[len("http://") :]
    return "https://r.jina.ai/" + url


def _clean_readable_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n")
    lines = cleaned.splitlines()
    filtered: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            filtered.append("")
            continue
        if line.startswith("Title: "):
            continue
        if line.startswith("URL Source: "):
            continue
        if line.startswith("Published Time: "):
            continue
        if line.startswith("Markdown Content:"):
            continue
        filtered.append(raw_line)
    merged = "\n".join(filtered)
    merged = HTML_TAG_RE.sub(" ", merged)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    merged = normalize_space(merged)
    return merged


def word_count(text: str) -> int:
    return len(text.split())


def fetch_link_context(
    url: str,
    *,
    timeout: int = 25,
    max_chars: int = 5000,
    min_words: int = 80,
) -> dict[str, Any]:
    proxied = _proxy_url(url)
    request = urllib.request.Request(proxied, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", "ignore")
    cleaned = _clean_readable_text(payload)
    words = word_count(cleaned)
    if words < min_words:
        raise ValueError(f"insufficient linked context words ({words} < {min_words})")
    clipped = cleaned[:max_chars].strip()
    return {
        "url": url,
        "proxy_url": proxied,
        "kind": classify_link_kind(url),
        "word_count": words,
        "text": clipped,
    }
