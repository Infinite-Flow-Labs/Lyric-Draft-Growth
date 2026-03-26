from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


ATOM_NS = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
A_TAG_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))')
XML_FEED_MARKERS = ("<rss", "<feed", "<rdf:rdf")
JSON_FEED_PREFIX = "https://jsonfeed.org/version/"


@dataclass
class FeedCandidate:
    url: str
    method: str
    source_url: str
    notes: str = ""


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = html.unescape(HTML_TAG_RE.sub(" ", value))
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def isoformat_z(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_get(url: str, timeout: int = 25, accept: str | None = None) -> tuple[bytes, str]:
    headers = {"User-Agent": "Mozilla/5.0"}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "")
    return payload, content_type


def looks_like_feed(payload: bytes, content_type: str) -> bool:
    lowered = payload[:400].decode("utf-8", "ignore").lower()
    return (
        "rss" in content_type.lower()
        or "atom" in content_type.lower()
        or "xml" in content_type.lower()
        or "json" in content_type.lower()
        or any(marker in lowered for marker in XML_FEED_MARKERS)
        or lowered.lstrip().startswith("{")
    )


def _element_text(element: ET.Element, *names: str) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _atom_link_href(element: ET.Element) -> str:
    for link in element.findall(f"{ATOM_NS}link"):
        href = (link.get("href") or "").strip()
        rel = (link.get("rel") or "alternate").strip().lower()
        if href and rel in {"alternate", ""}:
            return href
    return ""


def _feed_channel(root: ET.Element) -> ET.Element:
    channel = root.find("channel")
    if channel is not None:
        return channel
    return root


def _feed_items(channel: ET.Element) -> list[ET.Element]:
    items = channel.findall("item")
    if items:
        return items
    return channel.findall(f"{ATOM_NS}entry")


def _clean_summary(element: ET.Element) -> str:
    return normalize_text(
        _element_text(
            element,
            "description",
            "summary",
            f"{CONTENT_NS}encoded",
            f"{ATOM_NS}summary",
            f"{ATOM_NS}content",
        )
    )


def parse_feed_payload(payload: bytes, url: str, content_type: str = "") -> dict[str, Any]:
    text = payload.decode("utf-8", "ignore").strip()
    if text.startswith("{"):
        data = json.loads(text)
        if not str(data.get("version", "")).startswith(JSON_FEED_PREFIX):
            raise ValueError("unsupported json payload")
        items = data.get("items", [])
        latest = items[0] if items else {}
        published = parse_datetime(str(latest.get("date_published") or latest.get("date_modified") or ""))
        return {
            "feed_type": "json_feed",
            "channel_title": normalize_text(str(data.get("title", ""))),
            "site_url": str(data.get("home_page_url", "")),
            "item_count": len(items),
            "latest_title": normalize_text(str(latest.get("title", ""))),
            "latest_url": str(latest.get("url", "")),
            "latest_published_at": isoformat_z(published),
            "items": [
                {
                    "title": normalize_text(str(item.get("title", ""))),
                    "origin_url": str(item.get("url", "")),
                    "published_at": isoformat_z(
                        parse_datetime(str(item.get("date_published") or item.get("date_modified") or ""))
                    ),
                    "summary": normalize_text(str(item.get("summary", "") or item.get("content_text", ""))),
                }
                for item in items
            ],
            "content_type": content_type,
            "feed_url": url,
        }

    root = ET.fromstring(payload)
    channel = _feed_channel(root)
    channel_title = _element_text(channel, "title", f"{ATOM_NS}title")
    site_url = _element_text(channel, "link")
    if not site_url:
        site_url = _atom_link_href(channel)
    items = _feed_items(channel)
    parsed_items: list[dict[str, Any]] = []
    for item in items:
        title = _element_text(item, "title", f"{ATOM_NS}title")
        link = _element_text(item, "link")
        if not link:
            link = _atom_link_href(item)
        published = parse_datetime(
            _element_text(
                item,
                "pubDate",
                "published",
                "updated",
                f"{ATOM_NS}published",
                f"{ATOM_NS}updated",
            )
        )
        parsed_items.append(
            {
                "title": normalize_text(title),
                "origin_url": link,
                "published_at": isoformat_z(published),
                "summary": _clean_summary(item),
            }
        )
    latest = parsed_items[0] if parsed_items else {}
    feed_type = "atom" if root.tag == f"{ATOM_NS}feed" or channel.tag == f"{ATOM_NS}feed" else "rss"
    return {
        "feed_type": feed_type,
        "channel_title": normalize_text(channel_title),
        "site_url": site_url,
        "item_count": len(parsed_items),
        "latest_title": latest.get("title", ""),
        "latest_url": latest.get("origin_url", ""),
        "latest_published_at": latest.get("published_at", ""),
        "items": parsed_items,
        "content_type": content_type,
        "feed_url": url,
    }


def _attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(tag):
        name = match.group(1).lower()
        value = match.group(3) or match.group(4) or match.group(5) or ""
        attrs[name] = html.unescape(value.strip())
    return attrs


def _link_candidates_from_tag(tag: str, base_url: str) -> list[FeedCandidate]:
    attrs = _attrs(tag)
    href = attrs.get("href", "")
    if not href:
        return []
    rel = attrs.get("rel", "").lower()
    typ = attrs.get("type", "").lower()
    full = urllib.parse.urljoin(base_url, href)
    out: list[FeedCandidate] = []
    if "alternate" in rel and any(
        token in typ for token in ("rss", "atom", "xml", "json")
    ):
        out.append(FeedCandidate(url=full, method="html_link_rel", source_url=base_url, notes=f"type={typ or 'unknown'}"))
    elif any(token in href.lower() for token in ("/feed", "rss", "atom", "index.xml", "feed.xml")):
        out.append(FeedCandidate(url=full, method="html_link_href", source_url=base_url))
    return out


def extract_feed_candidates_from_html(html_text: str, base_url: str) -> list[FeedCandidate]:
    out: list[FeedCandidate] = []
    seen: set[tuple[str, str]] = set()
    for tag in LINK_TAG_RE.findall(html_text):
        for candidate in _link_candidates_from_tag(tag, base_url):
            key = (candidate.url, candidate.method)
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
    for match in A_TAG_RE.finditer(html_text):
        tag = match.group(0)
        text = normalize_text(match.group(1))
        attrs = _attrs(tag)
        href = attrs.get("href", "")
        if not href:
            continue
        href_lower = href.lower()
        if "rss" in text.lower() or "feed" in text.lower() or any(
            token in href_lower for token in ("/feed", "rss", "atom", "index.xml", "feed.xml")
        ):
            full = urllib.parse.urljoin(base_url, href)
            key = (full, "anchor_hint")
            if key in seen:
                continue
            seen.add(key)
            out.append(FeedCandidate(url=full, method="anchor_hint", source_url=base_url, notes=f"text={text[:80]}"))
    return out


def common_feed_paths(page_url: str) -> list[FeedCandidate]:
    parsed = urllib.parse.urlparse(page_url)
    if not parsed.scheme or not parsed.netloc:
        return []
    bases = [
        urllib.parse.urljoin(page_url, "./"),
        f"{parsed.scheme}://{parsed.netloc}/",
    ]
    suffixes = [
        "feed",
        "feed/",
        "feed.xml",
        "rss",
        "rss/",
        "rss.xml",
        "atom.xml",
        "index.xml",
        "feed.json",
    ]
    out: list[FeedCandidate] = []
    seen: set[str] = set()
    for base in bases:
        for suffix in suffixes:
            candidate = urllib.parse.urljoin(base, suffix)
            if candidate in seen:
                continue
            seen.add(candidate)
            out.append(FeedCandidate(url=candidate, method="common_path", source_url=page_url, notes=f"base={base}"))
    return out
