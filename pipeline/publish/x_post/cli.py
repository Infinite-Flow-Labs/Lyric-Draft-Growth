from __future__ import annotations

import argparse
import csv
from contextlib import AsyncExitStack
import base64
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, ProxyHandler, build_opener
import mimetypes
from zoneinfo import ZoneInfo

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency for upload compression
    Image = None  # type: ignore[assignment]

LOGIN_URL_PARTS = ("/i/flow/login", "/login")
MAX_X_UPLOAD_BYTES = 4_500_000


def now_stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_step(msg: str) -> None:
    print(f"[{now_stamp()}] {msg}")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def prepare_image_for_x_upload(image_path: Path, *, role: str) -> Path:
    image_path = image_path.expanduser().resolve()
    suffix = image_path.suffix.lower()
    size = image_path.stat().st_size
    if size <= MAX_X_UPLOAD_BYTES and suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return image_path
    if Image is None:
        return image_path

    output_dir = image_path.parent / ".upload_cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / f"{image_path.stem}.{role}.upload.jpg"

    max_width, max_height = (2200, 1400) if role == "cover" else (1800, 1800)
    quality = 88
    min_quality = 64

    with Image.open(image_path) as img:
        work = img.convert("RGB")
        work.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        while True:
            work.save(target_path, format="JPEG", quality=quality, optimize=True, progressive=True)
            if target_path.stat().st_size <= MAX_X_UPLOAD_BYTES or quality <= min_quality:
                break
            quality -= 6

    return target_path if target_path.exists() else image_path


def extract_tool_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if not isinstance(content, list):
        return ""

    texts: list[str] = []
    for item in content:
        if getattr(item, "type", None) == "text" and hasattr(item, "text"):
            texts.append(str(item.text))
    return "\n".join(texts)


def parse_json_from_tool_text(text: str) -> Any | None:
    if not text:
        return None

    fenced = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            return None

    prefix = "Script ran on page and returned:"
    raw = text[len(prefix) :].strip() if text.startswith(prefix) else text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@dataclass
class SnapshotEntry:
    uid: str
    raw: str
    normalized: str


def parse_snapshot_entries(snapshot_text: str) -> list[SnapshotEntry]:
    entries: list[SnapshotEntry] = []
    for line in snapshot_text.splitlines():
        match = re.match(r"^\s*uid=([^\s]+)\s+(.*)$", line)
        if not match:
            continue
        entries.append(
            SnapshotEntry(uid=match.group(1), raw=match.group(2), normalized=normalize_text(match.group(2)))
        )
    return entries


def includes_any(target: str, keywords: list[str]) -> bool:
    return any(keyword in target for keyword in keywords)


def find_upload_uid(entries: list[SnapshotEntry]) -> str | None:
    choose_file_keywords = [
        "choose files",
        "choose file",
        "no file chosen",
        "file chooser",
        "选择文件",
        "未选择文件",
        "选取文件",
        "文件",
    ]

    keywords = [
        "add photos or video",
        "add photos",
        "photo",
        "photos",
        "video",
        "media",
        "image",
        "file",
        "upload",
        "attach",
        "图片",
        "照片",
        "相片",
        "媒体",
        "上传",
        "附件",
        "添加照片",
        "添加媒体",
    ]

    negative_keywords = [
        "insert",
        "gif",
        "posts",
        "divider",
        "code",
        "latex",
    ]

    # Prefer real file input first. `upload_file` is much more stable on inputs than on proxy buttons.
    for entry in reversed(entries):
        if "input" not in entry.normalized:
            continue
        if "file" in entry.normalized and not includes_any(entry.normalized, negative_keywords):
            return entry.uid

    scored: list[tuple[int, int, SnapshotEntry]] = []
    for index, entry in enumerate(entries):
        if "input" not in entry.normalized and "button" not in entry.normalized:
            continue
        if not includes_any(entry.normalized, keywords + choose_file_keywords):
            continue
        score = 0
        if includes_any(entry.normalized, choose_file_keywords):
            score += 4
        if includes_any(entry.normalized, keywords):
            score += 2
        if "input" in entry.normalized and "file" in entry.normalized:
            score += 2
        if includes_any(entry.normalized, ["add photo", "add media", "cover", "封面"]):
            score += 2
        if includes_any(entry.normalized, negative_keywords):
            score -= 3
        scored.append((score, index, entry))

    if scored:
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return scored[0][2].uid

    # Last fallback: pick the latest file input candidate (most recently opened surface).
    for entry in reversed(entries):
        if "input" in entry.normalized and "file" in entry.normalized:
            return entry.uid

    return None


def summarize_upload_candidates(entries: list[SnapshotEntry], limit: int = 20) -> list[str]:
    keywords = [
        "choose file",
        "choose files",
        "file",
        "upload",
        "media",
        "image",
        "photo",
        "图片",
        "照片",
        "上传",
        "媒体",
    ]
    candidates: list[str] = []
    for entry in entries:
        if "input" not in entry.normalized and "button" not in entry.normalized:
            continue
        if not includes_any(entry.normalized, keywords):
            continue
        candidates.append(f"{entry.uid} {entry.raw}")
        if len(candidates) >= limit:
            break
    return candidates


def build_button_click_script(*, keywords: list[str], selectors: list[str]) -> str:
    return f"""() => {{
  const keywords = {json.dumps([k.lower() for k in keywords], ensure_ascii=False)};
  const selectors = {json.dumps(selectors, ensure_ascii=False)};
  const candidateElements = [];
  const seen = new Set();

  const addCandidate = (el) => {{
    if (!el || seen.has(el)) return;
    seen.add(el);
    candidateElements.push(el);
  }};

  for (const selector of selectors) {{
    for (const element of Array.from(document.querySelectorAll(selector))) {{
      addCandidate(element);
    }}
  }}

  for (const element of Array.from(document.querySelectorAll('button,[role="button"]'))) {{
    addCandidate(element);
  }}

  const isVisible = (element) => {{
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  }};

  for (const element of candidateElements) {{
    const attrs = [
      element.innerText,
      element.textContent,
      element.getAttribute('aria-label'),
      element.getAttribute('title'),
      element.getAttribute('data-testid'),
      element.getAttribute('name'),
    ].filter(Boolean).join(' ').toLowerCase();

    const disabled = element.disabled === true || element.getAttribute('aria-disabled') === 'true';
    const matched = keywords.some((keyword) => attrs.includes(keyword));
    if (!matched || disabled || !isVisible(element)) continue;

    element.click();
    return {{ ok: true, matchedBy: keywords.find((keyword) => attrs.includes(keyword)), attrs }};
  }}

  return {{ ok: false, scanned: candidateElements.length, foundKeywords: keywords }};
}}"""


def build_focus_composer_script() -> str:
    selectors = [
        'div[data-testid="tweetTextarea_0"] div[role="textbox"]',
        'div[data-testid="tweetTextarea_0"]',
        'div[role="textbox"][contenteditable="true"]',
    ]
    return f"""() => {{
  const selectors = {json.dumps(selectors)};
  const isVisible = (element) => {{
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  }};

  for (const selector of selectors) {{
    const element = document.querySelector(selector);
    if (!element || !isVisible(element)) continue;
    element.focus();
    return {{ ok: true, selector }};
  }}

  return {{ ok: false, selectors }};
}}"""


def build_set_schedule_script(target: dict[str, int]) -> str:
    return f"""() => {{
  const target = {json.dumps(target)};
  const root = document.querySelector('div[role="dialog"]') || document;
  const controls = Array.from(root.querySelectorAll('select, input, [role="spinbutton"]'));
  const selects = Array.from(root.querySelectorAll('select'));

  const getLabelText = (element) => {{
    const label = element.closest('label');
    return label ? label.textContent : '';
  }};

  const normalized = (value) => String(value || '').toLowerCase();
  const buildDescriptor = (element) => normalized([
    element.getAttribute('aria-label'),
    element.getAttribute('placeholder'),
    element.getAttribute('name'),
    element.getAttribute('id'),
    element.getAttribute('data-testid'),
    getLabelText(element),
  ].filter(Boolean).join(' '));

  const byField = {{ year: null, month: null, day: null, hour: null, minute: null, ampm: null }};
  const keywords = {{
    year: ['year', 'yyyy', '年'],
    month: ['month', 'mm', '月'],
    day: ['day', 'dd', 'date', '日'],
    hour: ['hour', 'hh', 'time hour', '小时', '時', '点'],
    minute: ['minute', 'min', 'time minute', '分钟', '分'],
    ampm: ['am', 'pm', '上午', '下午'],
  }};

  const classifySelectByOptions = (control) => {{
    const options = Array.from(control.options || []);
    const texts = options.map((opt) => String(opt.textContent || '').trim().toLowerCase());
    const values = options.map((opt) => String(opt.value || '').trim().toLowerCase());
    const merged = texts.concat(values).join(' ');
    const nums = texts.map((text) => Number(text.replace(/[^0-9]/g, ''))).filter((n) => Number.isFinite(n) && n > 0);

    const hasAMPM = merged.includes('am') || merged.includes('pm') || merged.includes('上午') || merged.includes('下午');
    if (hasAMPM) return 'ampm';

    const hasMonthHint = merged.includes('月') || merged.includes('jan') || merged.includes('feb') || merged.includes('mar');
    if (hasMonthHint && nums.every((n) => n >= 1 && n <= 12)) return 'month';

    if (nums.length >= 55 && nums.every((n) => n >= 0 && n <= 59)) return 'minute';

    const yearLikeCount = nums.filter((n) => n >= 2000 && n <= 2100).length;
    if (yearLikeCount >= 2) return 'year';

    const dayLike = nums.length >= 28 && nums.every((n) => n >= 1 && n <= 31);
    if (dayLike) return 'day';

    const hourLike = nums.length >= 12 && nums.length <= 24 && nums.every((n) => n >= 1 && n <= 24);
    if (hourLike) return 'hour';

    return null;
  }};

  for (const control of selects) {{
    const classified = classifySelectByOptions(control);
    if (classified && !byField[classified]) {{
      byField[classified] = control;
    }}
  }}

  for (const control of controls) {{
    const descriptor = buildDescriptor(control);
    for (const [field, fieldKeywords] of Object.entries(keywords)) {{
      if (byField[field]) continue;
      if (fieldKeywords.some((keyword) => descriptor.includes(keyword))) byField[field] = control;
    }}
  }}

  const used = new Set(Object.values(byField).filter(Boolean));
  const remainingSelects = selects.filter((control) => !used.has(control));

  const orderFallback = ['month', 'day', 'year', 'hour', 'minute'];
  for (const field of orderFallback) {{
    if (!byField[field] && remainingSelects.length > 0) byField[field] = remainingSelects.shift();
  }}

  if (!byField.ampm) {{
    for (const control of remainingSelects) {{
      if (control.tagName.toLowerCase() !== 'select') continue;
      const allText = Array.from(control.options || []).map((opt) => String(opt.textContent || '').toLowerCase()).join(' ');
      if (allText.includes('am') || allText.includes('pm') || allText.includes('上午') || allText.includes('下午')) {{
        byField.ampm = control;
        break;
      }}
    }}
  }}

  const toTwo = (value) => String(value).padStart(2, '0');
  const setValue = (element, field, value) => {{
    if (!element) return {{ field, ok: false, reason: 'missing' }};

    const tagName = element.tagName.toLowerCase();
    if (tagName === 'select') {{
      const options = Array.from(element.options || []);
      const targetText = String(value).toLowerCase();
      const candidates = [String(value), String(Number(value)), toTwo(value), targetText];
      let matched = options.find((option) => {{
        const optionValue = String(option.value || '').toLowerCase();
        const optionText = String(option.textContent || '').trim().toLowerCase();
        return candidates.includes(optionValue) || candidates.includes(optionText);
      }});

      if (!matched && field === 'ampm') {{
        matched = options.find((option) => {{
          const optionText = String(option.textContent || '').toLowerCase();
          if (targetText === 'pm') return optionText.includes('pm') || optionText.includes('下午');
          return optionText.includes('am') || optionText.includes('上午');
        }});
      }}

      if (!matched) matched = options.find((option) => String(option.textContent || '').includes(String(Number(value))));
      if (!matched) return {{ field, ok: false, reason: 'option_not_found' }};
      element.value = matched.value;
    }} else {{
      element.focus();
      element.value = '';
      element.value = String(value);
    }}

    element.dispatchEvent(new Event('input', {{ bubbles: true }}));
    element.dispatchEvent(new Event('change', {{ bubbles: true }}));
    element.dispatchEvent(new Event('blur', {{ bubbles: true }}));

    return {{ field, ok: true, assigned: String(value), actual: String(element.value || '') }};
  }};

  const hasAmPm = Boolean(byField.ampm);
  const rawHour = Number(target.hour);
  const hourValue = hasAmPm ? ((rawHour % 12) || 12) : rawHour;
  const ampmValue = rawHour >= 12 ? 'pm' : 'am';

  const results = [
    setValue(byField.year, 'year', target.year),
    setValue(byField.month, 'month', target.month),
    setValue(byField.day, 'day', target.day),
    setValue(byField.hour, 'hour', hourValue),
    setValue(byField.minute, 'minute', target.minute),
  ];

  if (byField.ampm) results.push(setValue(byField.ampm, 'ampm', ampmValue));

  const ok = results.every((result) => result.ok);
  return {{
    ok,
    controlsCount: controls.length,
    matchedFields: Object.fromEntries(Object.entries(byField).map(([key, value]) => [key, Boolean(value)])),
    results,
  }};
}}"""


def build_submit_scheduled_script(allow_immediate_post: bool) -> str:
    not_schedule_guard = "false" if allow_immediate_post else "true"
    return f"""() => {{
  const selectors = [
    'button[data-testid="tweetButton"]',
    'button[data-testid="tweetButtonInline"]',
    'button[data-testid="tweetButtonDraft"]',
  ];

  const scheduleKeywords = ['schedule', 'scheduled', '定时', '排程', '预约', '排期', '预排期', '安排表'];
  const isVisible = (element) => {{
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  }};

  for (const selector of selectors) {{
    const button = document.querySelector(selector);
    if (!button || !isVisible(button)) continue;

    const text = [
      button.innerText,
      button.textContent,
      button.getAttribute('aria-label'),
      button.getAttribute('data-testid'),
    ].filter(Boolean).join(' ').toLowerCase();

    const disabled = button.disabled === true || button.getAttribute('aria-disabled') === 'true';
    if (disabled) return {{ ok: false, reason: 'tweet_button_disabled', selector, text }};

    const isScheduleButton = scheduleKeywords.some((keyword) => text.includes(keyword));
    if (!isScheduleButton && {not_schedule_guard}) {{
      return {{ ok: false, reason: 'not_schedule_button', selector, text }};
    }}

    button.click();
    return {{ ok: true, selector, text, isScheduleButton }};
  }}

  return {{ ok: false, reason: 'tweet_button_not_found' }};
}}"""


class ChromeMcpClient:
    def __init__(self, *, command: str, args: list[str]):
        self.command = command
        self.args = args
        self._stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "ChromeMcpClient":
        server = StdioServerParameters(command=self.command, args=self.args)
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        read_stream, write_stream = await self._stack.enter_async_context(stdio_client(server))
        self.session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is not None:
            await self._stack.__aexit__(exc_type, exc, tb)
            self._stack = None
        self.session = None

    async def call(self, name: str, args: dict[str, Any] | None = None) -> Any:
        if self.session is None:
            raise RuntimeError("MCP session is not initialized")
        result = await self.session.call_tool(name, args or {})
        if getattr(result, "isError", False):
            raise RuntimeError(f"[{name}] {extract_tool_text(result) or 'tool returned an error'}")
        return result

    async def call_text(self, name: str, args: dict[str, Any] | None = None) -> str:
        return extract_tool_text(await self.call(name, args))

    async def call_json(self, name: str, args: dict[str, Any] | None = None) -> Any:
        text = await self.call_text(name, args)
        parsed = parse_json_from_tool_text(text)
        if parsed is None:
            raise RuntimeError(f"[{name}] failed to parse JSON response: {text}")
        return parsed


@dataclass
class PostAssets:
    directory: Path
    text_path: Path
    image_path: Path | None
    text: str


@dataclass
class ArticleAssets:
    directory: Path
    title_path: Path
    body_path: Path
    publish_spec_path: Path | None
    cover_path: Path | None
    title: str
    body: str
    publish_spec: dict[str, Any] | None


@dataclass
class ArticleBlock:
    block_type: str
    text: str
    items: list[str]
    url: str | None
    label: str | None


@dataclass
class BitAccountMapping:
    account: str
    browser_id: str
    bit_port: int | None
    note: str


def resolve_post_assets(base_dir: str) -> PostAssets:
    directory = Path(base_dir).expanduser().resolve()
    text_path = directory / "post.txt"
    image_path = directory / "post.jpg"

    if not text_path.exists():
        raise ValueError(f"missing file: {text_path}")

    text = text_path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    if not text.strip():
        raise ValueError(f"post.txt is empty: {text_path}")

    resolved_image_path = image_path if image_path.exists() else None
    return PostAssets(directory=directory, text_path=text_path, image_path=resolved_image_path, text=text)


def resolve_article_assets(base_dir: str) -> ArticleAssets:
    directory = Path(base_dir).expanduser().resolve()
    title_path = directory / "title.txt"
    body_path = directory / "article.md"
    publish_spec_path = directory / "article_publish_spec.json"
    cover_candidates = [
        directory / "cover.jpg",
        directory / "cover.png",
        directory / "cover.jpeg",
        directory / "cover.webp",
    ]

    if not title_path.exists():
        raise ValueError(f"missing file: {title_path}")
    if not body_path.exists():
        raise ValueError(f"missing file: {body_path}")

    title = title_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    body = body_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    if not title:
        raise ValueError(f"title.txt is empty: {title_path}")
    if not body:
        raise ValueError(f"article.md is empty: {body_path}")

    # X Articles editor renders markdown-style blank-line paragraph gaps too loosely.
    # Collapse repeated blank lines before typing so the result matches normal article spacing.
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r"[ \t]*\n[ \t]*\n[ \t]*", "\n", body)

    publish_spec: dict[str, Any] | None = None
    resolved_spec_path = publish_spec_path if publish_spec_path.exists() else None
    if resolved_spec_path is not None:
        publish_spec = json.loads(resolved_spec_path.read_text(encoding="utf-8"))

    resolved_cover_path = next((path for path in cover_candidates if path.exists()), None)
    return ArticleAssets(
        directory=directory,
        title_path=title_path,
        body_path=body_path,
        publish_spec_path=resolved_spec_path,
        cover_path=resolved_cover_path,
        title=title,
        body=body,
        publish_spec=publish_spec,
    )


def normalize_multiline_text(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def render_article_body_from_spec(spec: dict[str, Any] | None, fallback_body: str) -> str:
    if not isinstance(spec, dict):
        return normalize_multiline_text(fallback_body)

    blocks = spec.get("article_blocks") or []
    hints = spec.get("publishing_hints") or {}
    parts: list[str] = []

    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue
        block_type = str(raw_block.get("type", "")).strip()
        text = normalize_text(raw_block.get("text", ""))
        items = [normalize_text(item) for item in raw_block.get("items", []) if normalize_text(item)]
        url = normalize_text(raw_block.get("url", ""))
        label = normalize_text(raw_block.get("label", ""))

        if block_type == "bullet_list":
            if text:
                parts.append(text)
            if items:
                parts.append("\n".join(f"• {item}" for item in items))
            continue
        if block_type == "quote":
            if text:
                parts.append(f"“{text}”")
            continue
        if block_type == "link_cta":
            chunk: list[str] = []
            if text:
                chunk.append(text)
            if url:
                chunk.append(label or url)
                chunk.append(url)
            if chunk:
                parts.append("\n".join(chunk))
            continue
        if text:
            parts.append(text)

    source_label = normalize_text(hints.get("source_label", ""))
    source_url = normalize_text(hints.get("source_url", ""))
    if source_label or source_url:
        source_lines = []
        if source_label and source_url:
            source_lines.append(f"来源：{source_label}")
            source_lines.append(source_url)
        elif source_label:
            source_lines.append(f"来源：{source_label}")
        else:
            source_lines.append(source_url)
        parts.append("\n".join(source_lines))

    primary_link_url = normalize_text(hints.get("primary_link_url", ""))
    if primary_link_url:
        link_lines = []
        primary_link_label = normalize_text(hints.get("primary_link_label", ""))
        if primary_link_label:
            link_lines.append(primary_link_label)
        link_lines.append(primary_link_url)
        parts.append("\n".join(link_lines))

    closing_slogan = normalize_text(hints.get("closing_slogan", ""))
    if closing_slogan:
        parts.append(closing_slogan)

    rendered = "\n\n".join(part for part in parts if part.strip())
    return normalize_multiline_text(rendered or fallback_body)


def extract_article_blocks(spec: dict[str, Any] | None, fallback_body: str) -> list[ArticleBlock]:
    if not isinstance(spec, dict) or not isinstance(spec.get("article_blocks"), list) or not spec.get("article_blocks"):
        return [ArticleBlock(block_type="paragraph", text=normalize_multiline_text(fallback_body), items=[], url=None, label=None)]

    blocks: list[ArticleBlock] = []
    for raw_block in spec.get("article_blocks", []):
        if not isinstance(raw_block, dict):
            continue
        block_type = normalize_text(raw_block.get("type", ""))
        text = normalize_multiline_text(raw_block.get("text", ""))
        items = [normalize_multiline_text(item) for item in raw_block.get("items", []) if normalize_multiline_text(item)]
        url = normalize_multiline_text(raw_block.get("url", "")) or None
        label = normalize_multiline_text(raw_block.get("label", "")) or None
        if block_type == "bullet_list" and not items:
            continue
        if block_type != "bullet_list" and not text and not url:
            continue
        blocks.append(ArticleBlock(block_type=block_type, text=text, items=items, url=url, label=label))
    return blocks or [ArticleBlock(block_type="paragraph", text=normalize_multiline_text(fallback_body), items=[], url=None, label=None)]


def extract_inline_image_insertions(spec: dict[str, Any] | None) -> dict[int, list[Path]]:
    if not isinstance(spec, dict):
        return {}

    mapped: dict[int, list[Path]] = {}
    for raw in spec.get("inline_image_insertions", []):
        if not isinstance(raw, dict):
            continue
        try:
            ordinal = int(raw.get("after_block_ordinal", 0))
        except (TypeError, ValueError):
            continue
        image_path_raw = str(raw.get("image_path", "")).strip()
        if ordinal <= 0 or not image_path_raw:
            continue
        image_path = Path(image_path_raw).expanduser().resolve()
        if not image_path.exists():
            continue
        mapped.setdefault(ordinal, []).append(image_path)
    return mapped


def build_publish_ops_from_spec(spec: dict[str, Any] | None, fallback_body: str) -> list[dict[str, Any]]:
    blocks = extract_article_blocks(spec, fallback_body)
    inline_image_insertions = extract_inline_image_insertions(spec)
    ops: list[dict[str, Any]] = []

    for ordinal, block in enumerate(blocks, start=1):
        op: dict[str, Any] = {
            "op": "type_block",
            "block_type": block.block_type,
        }
        if block.text:
            op["text"] = block.text
        if block.items:
            op["items"] = block.items
        if block.url:
            op["url"] = block.url
        if block.label:
            op["label"] = block.label
        ops.append(op)

        for image_path in inline_image_insertions.get(ordinal, []):
            ops.append(
                {
                    "op": "insert_media",
                    "image_path": image_path,
                }
            )
    return ops


def extract_publish_ops(spec: dict[str, Any] | None, fallback_body: str) -> list[dict[str, Any]]:
    raw_ops = spec.get("publish_ops") if isinstance(spec, dict) else None
    parsed_ops: list[dict[str, Any]] = []

    if isinstance(raw_ops, list):
        for raw in raw_ops:
            if not isinstance(raw, dict):
                continue
            op_type = normalize_text(raw.get("op", ""))
            if op_type == "insert_media":
                image_path_raw = str(raw.get("image_path", "")).strip()
                if not image_path_raw:
                    continue
                image_path = Path(image_path_raw).expanduser().resolve()
                if not image_path.exists():
                    continue
                parsed_ops.append({"op": "insert_media", "image_path": image_path})
                continue

            if op_type != "type_block":
                continue

            block_type = normalize_text(raw.get("block_type", "")) or "paragraph"
            op: dict[str, Any] = {
                "op": "type_block",
                "block_type": block_type,
            }
            text = normalize_multiline_text(raw.get("text", ""))
            if text:
                op["text"] = text
            items = [normalize_multiline_text(item) for item in raw.get("items", []) if normalize_multiline_text(item)]
            if items:
                op["items"] = items
            url = normalize_multiline_text(raw.get("url", "")) or None
            if url:
                op["url"] = url
            label = normalize_multiline_text(raw.get("label", "")) or None
            if label:
                op["label"] = label
            parsed_ops.append(op)

    if parsed_ops:
        return parsed_ops
    return build_publish_ops_from_spec(spec, fallback_body)


def validate_publish_spec_before_publish(spec: dict[str, Any] | None) -> list[str]:
    if not isinstance(spec, dict):
        return ["publish_spec_missing"]
    raw_blocks = spec.get("article_blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        return ["article_blocks_missing"]

    errors: list[str] = []
    normalized_blocks = extract_article_blocks(spec, "")
    if not normalized_blocks:
        return ["article_blocks_empty_after_normalization"]

    # hero_heading is optional — title/dek are handled separately
    if normalized_blocks[0].block_type not in {"hero_heading", "quote", "paragraph"}:
        errors.append("first_block_must_be_hero_heading_or_quote_or_paragraph")

    quote_count = sum(1 for block in normalized_blocks if block.block_type == "quote")
    bullet_count = sum(1 for block in normalized_blocks if block.block_type == "bullet_list")
    if quote_count < 1:
        errors.append("quote_block_required")
    if bullet_count < 1:
        errors.append("bullet_list_block_required")

    inline_insertions = extract_inline_image_insertions(spec)
    total_blocks = len(normalized_blocks)
    for ordinal, paths in inline_insertions.items():
        if ordinal <= 0 or ordinal > total_blocks:
            errors.append(f"inline_insertion_out_of_range:{ordinal}/{total_blocks}")
            continue
        if not paths:
            errors.append(f"inline_insertion_empty:{ordinal}")
    return errors


def parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid integer value in CSV: {value}") from exc


def first_non_empty(data: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_account_mappings(csv_path: str) -> list[BitAccountMapping]:
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"accounts CSV not found: {path}")

    rows: list[BitAccountMapping] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"accounts CSV is missing header row: {path}")

        for index, row in enumerate(reader, start=2):
            normalized = {str(k).strip().lower(): str(v or "").strip() for k, v in row.items() if k}
            if not any(normalized.values()):
                continue
            account = first_non_empty(normalized, ["account", "username", "email", "x_account"])
            browser_id = first_non_empty(
                normalized, ["browser_id", "bit_browser_id", "window_id", "profile_id", "id"]
            )
            bit_port = parse_optional_int(
                first_non_empty(normalized, ["bit_port", "bit_api_port", "local_port", "api_port"])
            )
            note = first_non_empty(normalized, ["note", "remark", "desc", "description"])

            if not account:
                raise ValueError(f"accounts CSV line {index}: missing account column value")
            if not browser_id:
                raise ValueError(f"accounts CSV line {index}: missing browser_id column value")

            rows.append(BitAccountMapping(account=account, browser_id=browser_id, bit_port=bit_port, note=note))

    if not rows:
        raise ValueError(f"accounts CSV has no valid data rows: {path}")
    return rows


def find_account_mapping(mappings: list[BitAccountMapping], account: str) -> BitAccountMapping:
    target = normalize_text(account)
    exact = [item for item in mappings if normalize_text(item.account) == target]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"duplicate account rows found in CSV: {account}")

    partial = [item for item in mappings if target in normalize_text(item.account)]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        names = ", ".join(item.account for item in partial[:5])
        raise ValueError(f"multiple accounts matched '{account}': {names}")

    raise ValueError(f"account not found in CSV: {account}")


def normalize_browser_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("empty browser debug url")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"http://{value}"


def request_bit_browser_open(*, browser_id: str, bit_api_port: int, timeout_seconds: float = 10.0) -> str:
    if bit_api_port <= 0:
        raise ValueError("--bit-api-port must be a positive integer")

    api_url = f"http://127.0.0.1:{bit_api_port}/browser/open"
    payload = json.dumps({"id": browser_id}).encode("utf-8")
    request = Request(api_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

    opener = build_opener(ProxyHandler({}))

    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", "ignore")
    except HTTPError as exc:
        msg = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"bit browser API request failed ({exc.code}): {msg}") from exc
    except URLError as exc:
        raise RuntimeError(f"failed to connect bit browser API {api_url}: {exc}") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"bit browser API returned invalid JSON: {body[:300]}") from exc

    if not isinstance(result, dict) or not result.get("success"):
        raise RuntimeError(f"bit browser API open failed: {json.dumps(result, ensure_ascii=False)}")

    data = result.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"bit browser API open missing data: {json.dumps(result, ensure_ascii=False)}")

    http_value = data.get("http")
    if isinstance(http_value, str) and http_value.strip():
        return normalize_browser_url(http_value)

    ws_value = data.get("ws")
    if isinstance(ws_value, str) and ws_value.strip():
        parsed = urlparse(ws_value)
        if parsed.hostname and parsed.port:
            return f"http://{parsed.hostname}:{parsed.port}"

    raise RuntimeError(f"bit browser API open did not return http/ws endpoint: {json.dumps(data, ensure_ascii=False)}")


def wait_for_browser_debug_ready(browser_url: str, timeout_seconds: float = 20.0) -> None:
    version_url = f"{browser_url.rstrip('/')}/json/version"
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout_seconds
    last_error = "unknown"

    while time.monotonic() < deadline:
        request = Request(version_url, headers={"Accept": "application/json"}, method="GET")
        try:
            with opener.open(request, timeout=3.0) as response:
                body = response.read().decode("utf-8", "ignore")
            data = json.loads(body)
            if isinstance(data, dict) and (
                data.get("webSocketDebuggerUrl")
                or data.get("Browser")
                or data.get("Protocol-Version")
            ):
                return
            last_error = f"unexpected response: {body[:200]}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.8)

    raise RuntimeError(f"browser debug endpoint not ready: {browser_url} ({last_error})")


def resolve_browser_url_from_args(args: argparse.Namespace) -> str | None:
    if args.browser_url:
        return normalize_browser_url(args.browser_url)

    if not args.account and not args.bit_browser_id:
        return None

    bit_api_port = int(args.bit_api_port)

    if args.account:
        mappings = load_account_mappings(args.accounts_csv)
        mapping = find_account_mapping(mappings, args.account)
        browser_id = mapping.browser_id
        if mapping.bit_port:
            bit_api_port = mapping.bit_port
        log_step(
            f"CSV匹配账号: {mapping.account} -> browser_id={browser_id} "
            f"(bit-api-port={bit_api_port})"
        )
    else:
        browser_id = str(args.bit_browser_id).strip()
        if not browser_id:
            raise ValueError("--bit-browser-id is empty")
        log_step(f"使用指定 browser_id: {browser_id} (bit-api-port={bit_api_port})")

    timeout_seconds = float(args.bit_open_timeout_seconds)
    if timeout_seconds <= 0:
        raise ValueError("--bit-open-timeout-seconds must be > 0")
    browser_url = request_bit_browser_open(
        browser_id=browser_id, bit_api_port=bit_api_port, timeout_seconds=timeout_seconds
    )
    wait_for_browser_debug_ready(browser_url, timeout_seconds=max(8.0, timeout_seconds * 2))
    log_step(f"已通过比特API获取调试地址: {browser_url}")
    return browser_url


def parse_schedule_time(raw: str, timezone: str) -> datetime:
    value = (raw or "").strip()
    tz = ZoneInfo(timezone)

    formats = [
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    dt: datetime | None = None
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            dt = parsed.replace(tzinfo=tz)
            break
        except ValueError:
            continue

    if dt is None:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid --time value: {value}") from exc
        dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)
        dt = dt.astimezone(tz)

    now = datetime.now(tz)
    if dt <= now + timedelta(minutes=2):
        raise ValueError(f"schedule time must be at least 2 minutes in the future ({timezone})")

    return dt


def resolve_cached_chrome_devtools_mcp() -> Path | None:
    candidates = sorted(
        Path.home().glob(".npm/_npx/*/node_modules/.bin/chrome-devtools-mcp"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def build_server_config(args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.mcp_command == "npx":
        cached_binary = resolve_cached_chrome_devtools_mcp()
        if cached_binary is not None:
            command = str(cached_binary)
            mcp_args = ["--no-usage-statistics"]
        else:
            command = args.mcp_command
            mcp_args = ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]
    else:
        command = args.mcp_command
        mcp_args = ["--no-usage-statistics"]

    if args.mcp_arg:
        mcp_args.extend(args.mcp_arg)

    if args.browser_url:
        mcp_args.append(f"--browser-url={normalize_browser_url(args.browser_url)}")
    else:
        default_profile = Path.home() / ".cache" / "x-post-tool" / "chrome-profile"
        profile = Path(args.user_data_dir).expanduser().resolve() if args.user_data_dir else default_profile
        mcp_args.append(f"--user-data-dir={profile}")

    if args.headless:
        mcp_args.append("--headless=true")

    return command, mcp_args


async def get_current_url(mcp: ChromeMcpClient) -> str:
    data = await mcp.call_json("evaluate_script", {"function": "() => ({ href: window.location.href, title: document.title })"})
    return str(data.get("href", ""))


async def ensure_logged_in(mcp: ChromeMcpClient, timeout_seconds: float) -> None:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    url = await get_current_url(mcp)
    if not any(part in url for part in LOGIN_URL_PARTS):
        return

    log_step("检测到登录页，请在打开的 Chrome 中手动登录 X，脚本会自动继续。")
    while datetime.now() < deadline:
        await anyio.sleep(3)
        url = await get_current_url(mcp)
        if not any(part in url for part in LOGIN_URL_PARTS):
            log_step("登录成功，继续执行。")
            return

    raise RuntimeError("waiting for login timed out")


async def focus_composer_and_type(mcp: ChromeMcpClient, text: str) -> None:
    focused = await mcp.call_json("evaluate_script", {"function": build_focus_composer_script()})
    if not focused.get("ok"):
        raise RuntimeError(f"failed to focus compose textbox: {json.dumps(focused, ensure_ascii=False)}")

    await mcp.call("type_text", {"text": text})

    verify = await mcp.call_json(
        "evaluate_script",
        {
            "function": """() => {
  const selectors = [
    'div[data-testid="tweetTextarea_0"] div[role="textbox"]',
    'div[data-testid="tweetTextarea_0"]',
    'div[role="textbox"][contenteditable="true"]',
  ];
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (!element) continue;
    const content = (element.innerText || element.textContent || '').trim();
    if (content.length > 0) return { ok: true, selector, contentLength: content.length };
  }
  return { ok: false };
}"""
        },
    )

    if not verify.get("ok"):
        raise RuntimeError("text verification failed after typing")


def build_focus_article_title_script() -> str:
    return """() => {
  const candidates = Array.from(document.querySelectorAll('[contenteditable="true"], textarea, input'));
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  };

  const visible = candidates
    .filter((element) => isVisible(element))
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const text = [
        element.getAttribute('aria-label'),
        element.getAttribute('placeholder'),
        element.getAttribute('data-testid'),
        element.innerText,
        element.textContent,
      ].filter(Boolean).join(' ').toLowerCase();
      return { element, top: rect.top, text };
    })
    .sort((a, b) => a.top - b.top);

  for (const item of visible) {
    if (item.text.includes('add a title') || item.text.includes('title')) {
      item.element.focus();
      return { ok: true, descriptor: item.text, mode: 'placeholder_match' };
    }
  }

  const nearTop = visible.find((item) => item.top <= 220);
  if (nearTop) {
    nearTop.element.focus();
    return { ok: true, descriptor: nearTop.text || 'near_top_editable', mode: 'position_match' };
  }

  return { ok: false, visibleCount: visible.length };
}"""


def build_focus_article_body_script() -> str:
    return """() => {
  const candidates = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'));
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  };

  const visible = candidates
    .filter((element) => isVisible(element))
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const text = [
        element.getAttribute('aria-label'),
        element.getAttribute('placeholder'),
        element.getAttribute('data-testid'),
        element.innerText,
        element.textContent,
      ].filter(Boolean).join(' ').toLowerCase();
      return { element, top: rect.top, text };
    })
    .sort((a, b) => a.top - b.top);

  const preferred = visible.find((item) => item.text.includes('start writing') || item.text.includes('writing') || item.text.includes('composer'));
  const nonCaption = visible.filter((item) =>
    !item.text.includes('caption') &&
    !item.text.includes('optional') &&
    !item.text.includes('标题说明') &&
    !item.text.includes('提供说明')
  );

  for (const item of nonCaption) {
    if (item.text.includes('start writing') || item.text.includes('writing')) {
      item.element.focus();
      return { ok: true, descriptor: item.text, mode: 'placeholder_match' };
    }
  }

  if (preferred) {
    preferred.element.focus();
    return { ok: true, descriptor: preferred.text || 'preferred_editable', mode: 'preferred_match' };
  }

  const belowTitle = nonCaption.find((item) => item.top >= 140 && !item.text.includes('title'));
  if (belowTitle) {
    belowTitle.element.focus();
    return { ok: true, descriptor: belowTitle.text || 'below_title_editable', mode: 'position_match' };
  }

  if (nonCaption.length >= 2) {
    nonCaption[1].element.focus();
    return { ok: true, descriptor: nonCaption[1].text || 'second_visible_editable', mode: 'second_editable' };
  }

  if (nonCaption.length >= 1) {
    nonCaption[0].element.focus();
    return { ok: true, descriptor: nonCaption[0].text || 'first_non_caption_editable', mode: 'fallback_non_caption' };
  }

  return { ok: false, visibleCount: visible.length };
}"""


def build_focus_article_body_end_script() -> str:
    return """() => {
  const candidates = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'));
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  };

  const visible = candidates
    .filter((element) => isVisible(element))
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const text = [
        element.getAttribute('aria-label'),
        element.getAttribute('placeholder'),
        element.getAttribute('data-testid'),
        element.innerText,
        element.textContent,
      ].filter(Boolean).join(' ').toLowerCase();
      return { element, top: rect.top, text };
    })
    .filter((item) => !item.text.includes('caption'))
    .filter((item) => !item.text.includes('optional'))
    .filter((item) => !item.text.includes('标题说明'))
    .filter((item) => !item.text.includes('提供说明'))
    .sort((a, b) => a.top - b.top);

  const preferred = visible.find((item) => item.text.includes('start writing') || item.text.includes('writing') || item.text.includes('composer'));
  const target = (preferred || visible[visible.length - 1] || {}).element || null;
  if (!target) {
    return { ok: false, visibleCount: visible.length };
  }

  target.focus();
  if (target.isContentEditable) {
    const range = document.createRange();
    range.selectNodeContents(target);
    range.collapse(false);
    const selection = window.getSelection();
    if (selection) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
  } else if ('selectionStart' in target && typeof target.value === 'string') {
    const length = target.value.length;
    target.selectionStart = length;
    target.selectionEnd = length;
  }

  return {
    ok: true,
    descriptor: [
      target.getAttribute?.('aria-label'),
      target.getAttribute?.('placeholder'),
      target.getAttribute?.('data-testid'),
    ].filter(Boolean).join(' ') || 'article_body_end',
  };
}"""


async def focus_article_title_and_type(mcp: ChromeMcpClient, text: str) -> None:
    deadline = datetime.now() + timedelta(seconds=12)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        focused = await mcp.call_json("evaluate_script", {"function": build_focus_article_title_script()})
        last_result = focused if isinstance(focused, dict) else {}
        if last_result.get("ok"):
            await mcp.call("type_text", {"text": text})
            return
        await anyio.sleep(0.8)
    raise RuntimeError(f"failed to focus article title: {json.dumps(last_result, ensure_ascii=False)}")


async def focus_article_body_and_type(mcp: ChromeMcpClient, text: str) -> None:
    deadline = datetime.now() + timedelta(seconds=12)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        focused = await mcp.call_json("evaluate_script", {"function": build_focus_article_body_script()})
        last_result = focused if isinstance(focused, dict) else {}
        if last_result.get("ok"):
            await mcp.call("type_text", {"text": text})
            return
        await anyio.sleep(0.8)
    raise RuntimeError(f"failed to focus article body: {json.dumps(last_result, ensure_ascii=False)}")


async def ensure_article_body_focus(mcp: ChromeMcpClient) -> None:
    deadline = datetime.now() + timedelta(seconds=12)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        focused = await mcp.call_json("evaluate_script", {"function": build_focus_article_body_script()})
        last_result = focused if isinstance(focused, dict) else {}
        if last_result.get("ok"):
            return
        await anyio.sleep(0.8)
    raise RuntimeError(f"failed to focus article body: {json.dumps(last_result, ensure_ascii=False)}")


async def ensure_article_body_focus_at_end(mcp: ChromeMcpClient) -> None:
    deadline = datetime.now() + timedelta(seconds=12)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        focused = await mcp.call_json("evaluate_script", {"function": build_focus_article_body_end_script()})
        last_result = focused if isinstance(focused, dict) else {}
        if last_result.get("ok"):
            return
        await anyio.sleep(0.8)
    raise RuntimeError(f"failed to focus article body at end: {json.dumps(last_result, ensure_ascii=False)}")


def build_resume_after_media_script() -> str:
    return """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };

  const mediaElements = Array.from(document.querySelectorAll('img,video,canvas'))
    .filter((element) => isVisible(element))
    .filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width > 48 && rect.height > 48 && rect.top > 40;
    })
    .sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);

  const lastMedia = mediaElements[0];
  const mediaBottom = lastMedia ? lastMedia.getBoundingClientRect().bottom : 0;

  const editables = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'))
    .filter((element) => isVisible(element))
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const text = [
        element.getAttribute('aria-label'),
        element.getAttribute('placeholder'),
        element.getAttribute('data-testid'),
        element.innerText,
        element.textContent,
      ].filter(Boolean).join(' ').toLowerCase();
      return { element, rect, text };
    })
    .sort((a, b) => a.rect.top - b.rect.top);

  const nonCaptionEditables = editables.filter((item) =>
    !item.text.includes('caption') &&
    !item.text.includes('optional') &&
    !item.text.includes('提供说明') &&
    !item.text.includes('标题说明')
  );

  const composerEditable = editables.find((item) =>
    item.text.includes('composer') ||
    item.text.includes('start writing') ||
    item.text.includes('writing')
  );

  const target =
    (mediaBottom > 0 ? nonCaptionEditables.find((item) => item.rect.top >= mediaBottom - 6) : null) ||
    composerEditable ||
    nonCaptionEditables[nonCaptionEditables.length - 1] ||
    editables[editables.length - 1];
  if (!target) {
    return { ok: false, reason: 'resume_target_not_found', mediaBottom, editableCount: editables.length };
  }

  target.element.focus();

  if (target.element.isContentEditable) {
    const range = document.createRange();
    range.selectNodeContents(target.element);
    range.collapse(false);
    const selection = window.getSelection();
    if (selection) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
  } else if ('selectionStart' in target.element && typeof target.element.value === 'string') {
    const length = target.element.value.length;
    target.element.selectionStart = length;
    target.element.selectionEnd = length;
  }

  return {
    ok: true,
    mediaBottom,
    targetTop: target.rect.top,
    targetText: [
      target.element.getAttribute('aria-label'),
      target.element.getAttribute('placeholder'),
      target.element.getAttribute('data-testid'),
    ].filter(Boolean).join(' ') || 'resume_after_media_target',
  };
}"""


async def resume_typing_after_media(mcp: ChromeMcpClient) -> None:
    result = await mcp.call_json("evaluate_script", {"function": build_resume_after_media_script()})
    payload = result if isinstance(result, dict) else {}
    log_step(f"媒体后恢复输入定位: {json.dumps(payload, ensure_ascii=False)}")
    if not payload.get("ok"):
        raise RuntimeError(f"failed to resume after media: {json.dumps(payload, ensure_ascii=False)}")
    await anyio.sleep(0.2)
    await mcp.call("press_key", {"key": "Enter"})
    await anyio.sleep(0.25)


async def click_toolbar_button(
    mcp: ChromeMcpClient,
    *,
    step_name: str,
    keywords: list[str],
    selectors: list[str] | None = None,
    timeout_seconds: float = 8.0,
) -> None:
    await click_with_keywords(
        mcp,
        step_name=step_name,
        keywords=keywords,
        selectors=selectors
        or [
            'button',
            '[role="button"]',
            '[aria-label]',
        ],
        timeout_seconds=timeout_seconds,
    )


async def set_article_text_style(mcp: ChromeMcpClient, style: str) -> None:
    await click_toolbar_button(
        mcp,
        step_name="open text style menu",
        keywords=["body", "heading", "subheading"],
        selectors=['button', '[role="button"]'],
        timeout_seconds=8.0,
    )
    option_keywords = {
        "body": ["body", "paragraph", "normal"],
        "heading": ["heading"],
        "subheading": ["subheading"],
    }[style]
    await click_toolbar_button(
        mcp,
        step_name=f"choose text style {style}",
        keywords=option_keywords,
        selectors=['button', '[role="button"]', '[role="menuitem"]', 'li'],
        timeout_seconds=8.0,
    )
    await anyio.sleep(0.2)
    await mcp.call("press_key", {"key": "Escape"})
    await anyio.sleep(0.2)
    try:
        await ensure_article_body_focus(mcp)
    except Exception:
        await mcp.call("press_key", {"key": "Escape"})
        await anyio.sleep(0.2)


async def try_set_article_text_style(mcp: ChromeMcpClient, style: str, *, context: str) -> bool:
    try:
        await set_article_text_style(mcp, style)
        return True
    except Exception as exc:
        log_step(f"样式切换失败({context} -> {style})，继续执行: {exc}")
        return False


def build_click_article_cover_uploader_script() -> str:
    return """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  };

  const describe = (element) => [
    element.innerText,
    element.textContent,
    element.getAttribute('aria-label'),
    element.getAttribute('title'),
    element.getAttribute('data-testid'),
    element.getAttribute('name'),
  ].filter(Boolean).join(' ').trim().toLowerCase();

  const isBadText = (text) => (
    text.includes('insert') ||
    text.includes('gif') ||
    text.includes('posts') ||
    text.includes('divider') ||
    text.includes('code') ||
    text.includes('latex') ||
    text.includes('body') ||
    text.includes('heading') ||
    text.includes('subheading') ||
    text.includes('publish') ||
    text.includes('more')
  );

  const dialogs = Array.from(document.querySelectorAll('div[role="dialog"], [aria-modal="true"], .modal, .Dialog'))
    .filter((element) => isVisible(element))
    .filter((element) => {
      const text = (element.innerText || element.textContent || '').toLowerCase();
      return text.includes('edit media') || text.includes('编辑媒体');
    });
  if (dialogs.length > 0) {
    return {
      ok: true,
      strategy: 'edit_media_dialog_already_open',
      text: 'edit_media_dialog_already_open',
      score: 999,
    };
  }

  const viewportCenterX = window.innerWidth / 2;
  const candidates = [];
  const addCandidate = (element, strategy, baseScore) => {
    const rect = element.getBoundingClientRect();
    const text = describe(element);
    if (!isVisible(element)) return;
    if (!text) return;
    if (isBadText(text)) return;
    if (!(text.includes('add photo') || text.includes('add media') || text.includes('photo') || text.includes('media') || text.includes('图片') || text.includes('照片') || text.includes('添加'))) return;

    let score = baseScore;
    if (text.includes('add photo')) score += 20;
    if (text.includes('add media')) score += 10;
    if (text.includes('photo') || text.includes('图片') || text.includes('照片')) score += 8;
    if (rect.top >= 160 && rect.top <= 620) score += 20;
    if (rect.top < 120) score -= 30;
    const centerX = rect.left + rect.width / 2;
    const offset = Math.abs(centerX - viewportCenterX);
    if (offset < 180) score += 12;
    if (offset > 420) score -= 10;
    candidates.push({ element, rect, text, strategy, score });
  };

  const coverSurfaceRoots = Array.from(document.querySelectorAll('section,article,div'))
    .filter((element) => isVisible(element))
    .filter((element) => {
      const text = (element.innerText || element.textContent || '').toLowerCase();
      return (
        text.includes('5:2 aspect ratio') ||
        text.includes('5:2') ||
        text.includes('recommend an image') ||
        text.includes('推荐') ||
        text.includes('添加图片')
      );
    })
    .sort((a, b) => {
      const ra = a.getBoundingClientRect();
      const rb = b.getBoundingClientRect();
      return (rb.width * rb.height) - (ra.width * ra.height);
    })
    .slice(0, 8);

  for (const root of coverSurfaceRoots) {
    const controls = Array.from(root.querySelectorAll('button,[role="button"],label,a'));
    for (const control of controls) addCandidate(control, 'cover_surface_text_root', 80);
  }

  const globalControls = Array.from(document.querySelectorAll('button,[role="button"],label,a'));
  for (const control of globalControls) addCandidate(control, 'global_scan', 30);

  const deduped = [];
  const seen = new Set();
  for (const item of candidates) {
    if (seen.has(item.element)) continue;
    seen.add(item.element);
    deduped.push(item);
  }
  deduped.sort((a, b) => (b.score - a.score) || (a.rect.top - b.rect.top) || (a.rect.left - b.rect.left));

  const target = deduped[0];
  if (!target) {
    return {
      ok: false,
      reason: 'cover_uploader_not_found',
      matches: deduped.slice(0, 12).map((item) => ({
        text: item.text,
        strategy: item.strategy,
        score: item.score,
        top: item.rect.top,
        left: item.rect.left,
      })),
    };
  }

  target.element.click();
  return {
    ok: true,
    strategy: target.strategy,
    text: target.text,
    score: target.score,
    top: target.rect.top,
    left: target.rect.left,
    candidates: deduped.slice(0, 6).map((item) => ({
      text: item.text,
      strategy: item.strategy,
      score: item.score,
      top: item.rect.top,
      left: item.rect.left,
    })),
  };
}"""


async def open_article_cover_uploader(mcp: ChromeMcpClient, timeout_seconds: float = 12.0) -> None:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        result = await mcp.call_json("evaluate_script", {"function": build_click_article_cover_uploader_script()})
        last_result = result if isinstance(result, dict) else {}
        if last_result.get("ok"):
            log_step(
                "封面入口点击: "
                + json.dumps(
                    {
                        "strategy": last_result.get("strategy"),
                        "text": last_result.get("text"),
                        "score": last_result.get("score"),
                        "top": last_result.get("top"),
                        "left": last_result.get("left"),
                    },
                    ensure_ascii=False,
                )
            )
            await anyio.sleep(0.8)
            return
        await anyio.sleep(0.6)
    raise RuntimeError(f"cover uploader failed: {json.dumps(last_result, ensure_ascii=False)}")


def build_cover_apply_action_script() -> str:
    return """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };
  const roots = Array.from(document.querySelectorAll('div[role="dialog"], [aria-modal="true"], .modal, .Dialog'))
    .filter((element) => isVisible(element))
    .filter((element) => {
      const text = (element.innerText || element.textContent || '').toLowerCase();
      return text.includes('edit media') || text.includes('编辑媒体');
    });

  const root = roots[0];
  if (!root) {
    return { ok: true, state: 'no_edit_dialog' };
  }

  const buttons = Array.from(root.querySelectorAll('button,[role="button"]'))
    .filter((element) => isVisible(element))
    .map((element) => {
      const text = [
        element.innerText,
        element.textContent,
        element.getAttribute('aria-label'),
        element.getAttribute('title'),
        element.getAttribute('data-testid'),
      ].filter(Boolean).join(' ').trim().toLowerCase();
      return { element, text };
    });

  const apply = buttons.find((item) => item.text.includes('apply') || item.text.includes('应用'));
  if (!apply) {
    return { ok: false, state: 'apply_not_found', buttonTexts: buttons.map((item) => item.text).slice(0, 20) };
  }

  const element = apply.element;
  const disabled = element.disabled === true || element.getAttribute('aria-disabled') === 'true';
  if (disabled) {
    return { ok: false, state: 'apply_disabled' };
  }

  element.click();
  return { ok: true, state: 'clicked_apply' };
}"""


async def ensure_cover_apply_if_needed(
    mcp: ChromeMcpClient,
    timeout_seconds: float = 16.0,
    wait_for_dialog_seconds: float = 4.0,
) -> None:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    started_at = datetime.now()
    last_result: dict[str, Any] = {}
    clicked = False
    saw_dialog = False
    while datetime.now() < deadline:
        result = await mcp.call_json("evaluate_script", {"function": build_cover_apply_action_script()})
        last_result = result if isinstance(result, dict) else {}
        state = str(last_result.get("state", "")).strip()
        if state == "no_edit_dialog":
            elapsed = (datetime.now() - started_at).total_seconds()
            if not saw_dialog and elapsed < wait_for_dialog_seconds:
                await anyio.sleep(0.4)
                continue
            return
        saw_dialog = True
        if state == "clicked_apply":
            clicked = True
            await anyio.sleep(0.5)
            continue
        if state == "apply_disabled":
            await anyio.sleep(0.4)
            continue
        if state == "apply_not_found":
            await anyio.sleep(0.4)
            continue
        await anyio.sleep(0.5)

    if clicked:
        # Best-effort: if we clicked at least once but dialog-close probing timed out, continue.
        log_step(f"封面 Apply 已点击，但未确认弹层关闭: {json.dumps(last_result, ensure_ascii=False)}")
        return
    raise RuntimeError(f"cover apply failed: {json.dumps(last_result, ensure_ascii=False)}")


def build_click_article_inline_toolbar_control_script(control_index: int) -> str:
    return f"""() => {{
  const controlIndex = {control_index};
  const isVisible = (element) => {{
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 && rect.height > 0;
  }};

  const describe = (element) => [
    element.innerText,
    element.textContent,
    element.getAttribute('aria-label'),
    element.getAttribute('title'),
    element.getAttribute('data-testid'),
    element.getAttribute('name'),
  ].filter(Boolean).join(' ').trim().toLowerCase();

  const buttons = Array.from(document.querySelectorAll('button,[role="button"]'))
    .filter((element) => isVisible(element))
    .map((element) => {{
      const rect = element.getBoundingClientRect();
      return {{
        element,
        rect,
        text: describe(element),
      }};
    }});

  const anchorCandidates = buttons
    .filter((item) => item.text.includes('body') || item.text.includes('heading') || item.text.includes('subheading'))
    .filter((item) => !item.text.includes('publish'))
    .sort((a, b) => a.rect.left - b.rect.left);

  const anchor = anchorCandidates[0];
  if (!anchor) {{
    return {{ ok: false, reason: 'anchor_not_found', buttons: buttons.slice(0, 20).map((item) => item.text) }};
  }}

  const sameRowButtons = buttons
    .filter((item) => item.element !== anchor.element)
    .filter((item) => item.rect.left > anchor.rect.right + 2)
    .filter((item) => Math.abs(item.rect.top - anchor.rect.top) <= 24)
    .filter((item) => (item.rect.left - anchor.rect.right) <= 220)
    .filter((item) => !['publish', 'next', 'previous', 'account menu', 'create', 'more'].some((token) => item.text.includes(token)))
    .sort((a, b) => a.rect.left - b.rect.left);

  const target = sameRowButtons[controlIndex];
  if (!target) {{
    return {{
      ok: false,
      reason: 'target_not_found',
      anchorText: anchor.text,
      candidateTexts: sameRowButtons.map((item) => item.text || '[icon]'),
    }};
  }}

  target.element.click();
  return {{
    ok: true,
    anchorText: anchor.text,
    targetIndex: controlIndex,
    targetText: target.text || '[icon]',
    candidateTexts: sameRowButtons.map((item) => item.text || '[icon]'),
  }};
}}"""


async def click_article_inline_toolbar_control(
    mcp: ChromeMcpClient, *, control_index: int, step_name: str, timeout_seconds: float = 8.0
) -> None:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        result = await mcp.call_json(
            "evaluate_script",
            {"function": build_click_article_inline_toolbar_control_script(control_index)},
        )
        last_result = result if isinstance(result, dict) else {}
        if last_result.get("ok"):
            await anyio.sleep(0.3)
            return
        await anyio.sleep(0.6)
    raise RuntimeError(f"{step_name} failed: {json.dumps(last_result, ensure_ascii=False)}")


async def enable_quote_style(mcp: ChromeMcpClient) -> None:
    try:
        await click_article_inline_toolbar_control(
            mcp,
            control_index=0,
            step_name="enable quote style",
            timeout_seconds=4.0,
        )
    except Exception:
        await click_toolbar_button(
            mcp,
            step_name="enable quote style",
            keywords=["quote", "blockquote"],
            selectors=['button', '[role="button"]', '[role="menuitem"]', 'li'],
            timeout_seconds=8.0,
        )
    await anyio.sleep(0.5)


async def enable_bullet_list(mcp: ChromeMcpClient) -> None:
    try:
        await click_article_inline_toolbar_control(
            mcp,
            control_index=1,
            step_name="enable bullet list",
            timeout_seconds=4.0,
        )
    except Exception:
        await click_toolbar_button(
            mcp,
            step_name="enable bullet list",
            keywords=["bullet", "bulleted", "unordered", "list"],
            selectors=['button', '[role="button"]', '[role="menuitem"]', 'li'],
            timeout_seconds=8.0,
        )
    await anyio.sleep(0.5)


async def enable_number_list(mcp: ChromeMcpClient) -> None:
    try:
        await click_article_inline_toolbar_control(
            mcp,
            control_index=2,
            step_name="enable number list",
            timeout_seconds=4.0,
        )
    except Exception:
        await click_toolbar_button(
            mcp,
            step_name="enable number list",
            keywords=["number", "numbered", "ordered", "list"],
            selectors=['button', '[role="button"]', '[role="menuitem"]', 'li'],
            timeout_seconds=8.0,
        )
    await anyio.sleep(0.5)


async def log_visible_toolbar_candidates(mcp: ChromeMcpClient, *, context: str, limit: int = 20) -> None:
    try:
        entries = await take_snapshot_entries(mcp)
    except Exception as exc:
        log_step(f"{context}：获取按钮快照失败: {exc}")
        return

    candidates = [
        f"{entry.uid} {entry.raw}"
        for entry in entries
        if any(token in entry.normalized for token in ["button", "menuitem", "toolbar"])
    ]
    if not candidates:
        log_step(f"{context}：未找到可见工具栏候选。")
        return
    preview = " | ".join(candidates[:limit])
    log_step(f"{context} 候选: {preview}")


def block_separator_key_presses(previous_block_type: str) -> int:
    if previous_block_type == "bullet_list":
        return 2
    # quote exit already pressed Enter once, so only need 1 more for paragraph gap
    return 1


async def open_article_insert_menu(mcp: ChromeMcpClient) -> None:
    await click_with_keywords(
        mcp,
        step_name="open insert menu",
        keywords=["insert"],
        selectors=[
            "button",
            "[role=\"button\"]",
            "[role=\"menuitem\"]",
            "a",
        ],
        timeout_seconds=12.0,
    )
    await anyio.sleep(0.8)


async def open_article_media_insert(mcp: ChromeMcpClient) -> None:
    await click_with_keywords(
        mcp,
        step_name="open media insert",
        keywords=["media"],
        selectors=[
            "[role=\"menuitem\"]",
            "button",
            "[role=\"button\"]",
            "li",
            "a",
        ],
        timeout_seconds=12.0,
    )
    await anyio.sleep(0.8)


async def wait_for_article_media_surface(mcp: ChromeMcpClient, timeout_seconds: float = 12.0) -> None:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_result: dict[str, Any] = {}
    script = """() => {
  const text = (document.body?.innerText || '').toLowerCase();
  const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
  const visibleFileInputs = fileInputs.filter((element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden') return false;
    return rect.width > 0 || rect.height > 0;
  });
  const hasSurfaceText =
    text.includes('choose a file or drag it here') ||
    text.includes('选择一个文件或拖到这里') ||
    text.includes('每个模块可以包含一个动图、视频或一组照片');
  return {
    ok: hasSurfaceText || visibleFileInputs.length > 0,
    hasSurfaceText,
    visibleFileInputs: visibleFileInputs.length,
  };
}"""
    while datetime.now() < deadline:
        result = await mcp.call_json("evaluate_script", {"function": script})
        last_result = result if isinstance(result, dict) else {}
        if last_result.get("ok"):
            return
        await anyio.sleep(0.5)
    raise RuntimeError(f"article media surface did not become ready: {json.dumps(last_result, ensure_ascii=False)}")


def build_article_media_probe_script() -> str:
    return """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };

  const text = (document.body?.innerText || '').toLowerCase();
  const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'));
  const visibleFileInputs = fileInputs.filter((element) => isVisible(element));
  const hasSurfaceText =
    text.includes('choose a file or drag it here') ||
    text.includes('选择一个文件或拖到这里') ||
    text.includes('每个模块可以包含一个动图、视频或一组照片');

  const mediaElements = Array.from(document.querySelectorAll('img, video, canvas'))
    .filter((element) => isVisible(element))
    .filter((element) => {
      const rect = element.getBoundingClientRect();
      if (rect.width < 48 || rect.height < 48) return false;
      if (rect.top < 80) return false;
      const blockedAncestor = element.closest('[role="menu"],[role="menuitem"],header,nav,aside');
      return !blockedAncestor;
    });

  const buttonTexts = Array.from(document.querySelectorAll('button,[role="button"]'))
    .filter((element) => isVisible(element))
    .map((element) => [
      element.innerText,
      element.textContent,
      element.getAttribute('aria-label'),
      element.getAttribute('title'),
      element.getAttribute('data-testid'),
    ].filter(Boolean).join(' ').toLowerCase());
  const hasRemovePhoto = buttonTexts.some((value) => (
    value.includes('remove photo') ||
    value.includes('移除照片') ||
    value.includes('删除照片') ||
    value.includes('remove media') ||
    value.includes('移除图片')
  ));

  return {
    mediaCount: mediaElements.length,
    hasRemovePhoto,
    hasSurfaceText,
    visibleFileInputs: visibleFileInputs.length,
    uploadSurfaceOpen: hasSurfaceText || visibleFileInputs.length > 0,
    hasCaptionText:
      text.includes('provide a caption') ||
      text.includes('caption (optional)') ||
      text.includes('提供说明') ||
      text.includes('标题说明'),
    uploadingMedia:
      text.includes('uploading media') ||
      text.includes('cancel upload') ||
      text.includes('正在上传'),
  };
}"""


async def probe_article_media_state(mcp: ChromeMcpClient) -> dict[str, Any]:
    result = await mcp.call_json("evaluate_script", {"function": build_article_media_probe_script()})
    return result if isinstance(result, dict) else {}


async def wait_for_inline_media_inserted(
    mcp: ChromeMcpClient,
    *,
    baseline_media_count: int,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        last_result = await probe_article_media_state(mcp)
        media_count = int(last_result.get("mediaCount", 0) or 0)
        upload_surface_open = bool(last_result.get("uploadSurfaceOpen"))
        has_caption_text = bool(last_result.get("hasCaptionText"))
        uploading_media = bool(last_result.get("uploadingMedia"))
        if (media_count > baseline_media_count or has_caption_text) and not upload_surface_open:
            return last_result
        if has_caption_text and uploading_media:
            return last_result
        await anyio.sleep(0.6)
    raise RuntimeError(
        "inline media did not appear in article body: "
        + json.dumps(
            {
                "baselineMediaCount": baseline_media_count,
                "lastProbe": last_result,
            },
            ensure_ascii=False,
        )
    )


async def wait_for_cover_media_inserted(
    mcp: ChromeMcpClient,
    *,
    baseline_media_count: int,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        last_result = await probe_article_media_state(mcp)
        media_count = int(last_result.get("mediaCount", 0) or 0)
        has_remove_photo = bool(last_result.get("hasRemovePhoto"))
        if media_count > baseline_media_count or has_remove_photo:
            return last_result
        await anyio.sleep(0.6)
    raise RuntimeError(
        "cover media did not appear in article header/body: "
        + json.dumps(
            {
                "baselineMediaCount": baseline_media_count,
                "lastProbe": last_result,
            },
            ensure_ascii=False,
        )
    )


def build_dump_file_inputs_script() -> str:
    return """() => {
  const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
  return {
    count: inputs.length,
    rows: inputs.map((element, index) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return {
        index,
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        visible:
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          (rect.width > 0 || rect.height > 0),
        accept: element.getAttribute('accept') || '',
      };
    }),
  };
}"""


async def dump_file_inputs(mcp: ChromeMcpClient) -> dict[str, Any]:
    result = await mcp.call_json("evaluate_script", {"function": build_dump_file_inputs_script()})
    return result if isinstance(result, dict) else {}


def build_assign_file_to_input_script(*, index: int, image_name: str, mime_type: str, image_base64: str) -> str:
    payload = {
        "index": index,
        "imageName": image_name,
        "mimeType": mime_type,
        "imageBase64": image_base64,
    }
    return f"""() => {{
  const payload = {json.dumps(payload, ensure_ascii=False)};
  const input = document.querySelectorAll('input[type="file"]')[payload.index];
  if (!input) {{
    return {{ ok: false, reason: 'input_not_found', index: payload.index }};
  }}

  const decodeBase64 = (value) => {{
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }};

  const bytes = decodeBase64(payload.imageBase64);
  const file = new File([bytes], payload.imageName, {{ type: payload.mimeType || 'image/png' }});
  const dt = new DataTransfer();
  dt.items.add(file);

  let assignOk = false;
  try {{
    input.files = dt.files;
    assignOk = true;
  }} catch (error) {{
    assignOk = false;
  }}

  input.dispatchEvent(new Event('input', {{ bubbles: true }}));
  input.dispatchEvent(new Event('change', {{ bubbles: true }}));

  const parent = input.parentElement;
  const grand = parent?.parentElement;
  const target = [parent, grand, input].find(Boolean);
  if (target && typeof DragEvent !== 'undefined') {{
    for (const type of ['dragenter', 'dragover', 'drop']) {{
      try {{
        const event = new DragEvent(type, {{ bubbles: true, cancelable: true, dataTransfer: dt }});
        target.dispatchEvent(event);
      }} catch (error) {{
        // ignore
      }}
    }}
  }}

  return {{
    ok: true,
    assignOk,
    filesLength: input.files ? input.files.length : 0,
    inputAccept: input.getAttribute('accept') || '',
  }};
}}"""


async def upload_cover_via_dom_input_assignment(
    mcp: ChromeMcpClient,
    *,
    cover_path: Path,
    baseline_media_count: int,
) -> None:
    input_state = await dump_file_inputs(mcp)
    count = int(input_state.get("count", 0) or 0)
    if count < 1:
        raise RuntimeError(f"no file input found: {json.dumps(input_state, ensure_ascii=False)}")

    image_bytes = cover_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = mimetypes.guess_type(str(cover_path))[0] or "image/png"

    attempts: list[dict[str, Any]] = []
    for index in reversed(range(count)):
        script = build_assign_file_to_input_script(
            index=index,
            image_name=cover_path.name,
            mime_type=mime_type,
            image_base64=image_base64,
        )
        result = await mcp.call_json("evaluate_script", {"function": script})
        payload = result if isinstance(result, dict) else {}
        attempts.append({"index": index, "result": payload})
        if not payload.get("ok"):
            continue
        files_length = int(payload.get("filesLength", 0) or 0)
        if files_length >= 1:
            await anyio.sleep(0.4)
            return
        await anyio.sleep(0.5)
        continue

    raise RuntimeError(f"dom file input assignment failed: {json.dumps(attempts, ensure_ascii=False)}")


def build_synthetic_drop_cover_file_script(*, image_name: str, mime_type: str, image_base64: str) -> str:
    payload = {
        "imageName": image_name,
        "mimeType": mime_type,
        "imageBase64": image_base64,
    }
    template = """() => {
  const payload = __PAYLOAD__;
  const decodeBase64 = (value) => {{
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }};
  const isVisible = (element) => {{
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  }};
  const textNodes = Array.from(document.querySelectorAll('div,section,article,span,p'))
    .filter((element) => isVisible(element))
    .map((element) => ({
      element,
      rect: element.getBoundingClientRect(),
      text: (element.innerText || element.textContent || '').trim().toLowerCase(),
    }));

  const describe = (element) => [
    element.innerText,
    element.textContent,
    element.getAttribute('aria-label'),
    element.getAttribute('title'),
    element.getAttribute('data-testid'),
    element.getAttribute('name'),
  ].filter(Boolean).join(' ').trim().toLowerCase();

  const coverControls = Array.from(document.querySelectorAll('button,[role="button"],label,a'))
    .filter((element) => isVisible(element))
    .map((element) => ({
      element,
      rect: element.getBoundingClientRect(),
      text: describe(element),
    }))
    .filter((item) => (
      item.text.includes('add photo') ||
      item.text.includes('add photos') ||
      item.text.includes('add media') ||
      item.text.includes('图片') ||
      item.text.includes('照片')
    ))
    .filter((item) => item.rect.top >= 120 && item.rect.top <= 520 && item.rect.left >= 420)
    .sort((a, b) => (a.rect.top - b.rect.top) || (a.rect.left - b.rect.left));

  const controlAnchor = coverControls[0] || null;

  const hintNodes = textNodes.filter((item) => (
    item.text.includes('5:2 aspect ratio') ||
    item.text.includes('best results') ||
    item.text.includes('5:2') ||
    item.text.includes('recommend an image') ||
    item.text.includes('add photo') ||
    item.text.includes('add photos') ||
    item.text.includes('add media') ||
    item.text.includes('图片') ||
    item.text.includes('照片') ||
    item.text.includes('添加')
  ));

  const topLargeContainers = textNodes.filter((item) => (
    item.rect.top >= 120 &&
    item.rect.top <= 520 &&
    item.rect.left >= 420 &&
    item.rect.width >= 480 &&
    item.rect.height >= 120
  ));

  const anchor = (
    (controlAnchor ? { element: controlAnchor.element, rect: controlAnchor.rect, text: controlAnchor.text } : null) ||
    hintNodes.sort((a, b) => b.rect.width * b.rect.height - a.rect.width * a.rect.height)[0] ||
    topLargeContainers.sort((a, b) => b.rect.width * b.rect.height - a.rect.width * a.rect.height)[0]
  );
  if (!anchor) {
    return {
      ok: false,
      reason: 'cover_dropzone_anchor_not_found',
      controls: coverControls.slice(0, 10).map((item) => ({
        top: item.rect.top,
        left: item.rect.left,
        width: item.rect.width,
        height: item.rect.height,
        text: item.text.slice(0, 160),
      })),
      samples: textNodes
        .filter((item) => item.rect.top >= 80 && item.rect.top <= 560)
        .sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height))
        .slice(0, 20)
        .map((item) => ({
          top: item.rect.top,
          left: item.rect.left,
          width: item.rect.width,
          height: item.rect.height,
          text: item.text.slice(0, 160),
        })),
    };
  }

  const candidates = [];
  let current = anchor.element;
  for (let depth = 0; depth < 6 && current; depth += 1) {
    const rect = current.getBoundingClientRect();
    candidates.push({
      element: current,
      depth,
      width: rect.width,
      height: rect.height,
      text: (current.innerText || current.textContent || '').trim().slice(0, 240),
    });
    current = current.parentElement;
  }

  const dropTarget = candidates
    .filter((item) => item.width >= 300 && item.height >= 120)
    .sort((a, b) => (b.width * b.height) - (a.width * a.height))[0] || candidates[0];
  if (!dropTarget) return { ok: false, reason: 'cover_drop_target_not_found' };

  const bytes = decodeBase64(payload.imageBase64);
  const file = new File([bytes], payload.imageName, { type: payload.mimeType || 'image/png' });
  const dt = new DataTransfer();
  dt.items.add(file);

  const dispatched = [];
  for (const type of ['dragenter', 'dragover', 'drop']) {
    try {
      const event = new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt });
      dispatched.push({ type, ok: dropTarget.element.dispatchEvent(event) });
    } catch (error) {
      dispatched.push({ type, ok: false, error: String(error) });
    }
  }
  return {
    ok: true,
    filesLength: dt.files.length,
    dropTargetText: dropTarget.text,
    dispatched,
  };
}"""
    return template.replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))


async def upload_cover_via_synthetic_drop(
    mcp: ChromeMcpClient,
    *,
    cover_path: Path,
    baseline_media_count: int,
) -> None:
    image_bytes = cover_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = mimetypes.guess_type(str(cover_path))[0] or "image/png"
    script = build_synthetic_drop_cover_file_script(
        image_name=cover_path.name,
        mime_type=mime_type,
        image_base64=image_base64,
    )
    result = await mcp.call_json("evaluate_script", {"function": script})
    payload = result if isinstance(result, dict) else {}
    if not payload.get("ok"):
        raise RuntimeError(f"synthetic drop setup failed: {json.dumps(payload, ensure_ascii=False)}")
    await anyio.sleep(0.4)


async def upload_article_cover_image(mcp: ChromeMcpClient, cover_path: Path) -> None:
    upload_path = prepare_image_for_x_upload(cover_path, role="cover")
    if upload_path != cover_path:
        log_step(
            f"封面图自动瘦身: {cover_path.name} ({cover_path.stat().st_size} bytes) -> "
            f"{upload_path.name} ({upload_path.stat().st_size} bytes)"
        )
    baseline_state = await probe_article_media_state(mcp)
    baseline_media_count = int(baseline_state.get("mediaCount", 0) or 0)
    baseline_has_remove_photo = bool(baseline_state.get("hasRemovePhoto"))
    if baseline_media_count > 0 or baseline_has_remove_photo:
        log_step(
            f"检测到已有封面信号(mediaCount={baseline_media_count}, hasRemovePhoto={baseline_has_remove_photo})，跳过封面上传。"
        )
        return
    errors: list[str] = []

    async def try_finalize_pending_cover(stage: str) -> bool:
        try:
            await ensure_cover_apply_if_needed(mcp, timeout_seconds=8.0, wait_for_dialog_seconds=2.5)
            await wait_for_cover_media_inserted(mcp, baseline_media_count=baseline_media_count, timeout_seconds=10.0)
            log_step(f"封面补救成功: {stage}")
            return True
        except Exception:
            return False

    # Phase 0: synthetic drop directly on cover area (avoids native picker side-effects).
    try:
        await upload_cover_via_synthetic_drop(
            mcp,
            cover_path=upload_path,
            baseline_media_count=baseline_media_count,
        )
        await ensure_cover_apply_if_needed(mcp)
        await wait_for_cover_media_inserted(mcp, baseline_media_count=baseline_media_count)
        return
    except Exception as exc:
        errors.append(f"synthetic_drop_direct: {exc}")
        log_step(f"封面上传 fallback#0: {exc}")

    # Phase 1: native upload_file via snapshot uid.
    try:
        await open_article_cover_uploader(mcp)
        await upload_image(mcp, upload_path)
        await ensure_cover_apply_if_needed(mcp)
        await wait_for_cover_media_inserted(mcp, baseline_media_count=baseline_media_count)
        return
    except Exception as exc:
        if await try_finalize_pending_cover("native_upload_file"):
            return
        errors.append(f"native_upload_file: {exc}")
        log_step(f"封面上传 fallback#1: {exc}")

    # Phase 2: assign file to current file inputs and dispatch change/drop.
    try:
        await open_article_cover_uploader(mcp)
        await upload_cover_via_dom_input_assignment(
            mcp,
            cover_path=upload_path,
            baseline_media_count=baseline_media_count,
        )
        await ensure_cover_apply_if_needed(mcp)
        await wait_for_cover_media_inserted(mcp, baseline_media_count=baseline_media_count)
        return
    except Exception as exc:
        if await try_finalize_pending_cover("dom_input_assignment"):
            return
        errors.append(f"dom_input_assignment: {exc}")
        log_step(f"封面上传 fallback#2: {exc}")

    # Phase 3: synthetic drop after uploader click.
    try:
        await open_article_cover_uploader(mcp)
        await upload_cover_via_synthetic_drop(
            mcp,
            cover_path=upload_path,
            baseline_media_count=baseline_media_count,
        )
        await ensure_cover_apply_if_needed(mcp)
        await wait_for_cover_media_inserted(mcp, baseline_media_count=baseline_media_count)
        return
    except Exception as exc:
        if await try_finalize_pending_cover("synthetic_drop"):
            return
        errors.append(f"synthetic_drop: {exc}")
        log_step(f"封面上传 fallback#3: {exc}")

    raise RuntimeError("cover upload failed after fallbacks: " + " | ".join(errors))


def build_write_image_to_browser_clipboard_script(*, image_name: str, mime_type: str, image_base64: str) -> str:
    payload = {
        "imageName": image_name,
        "mimeType": mime_type,
        "imageBase64": image_base64,
    }
    return f"""() => {{
  const payload = {json.dumps(payload, ensure_ascii=False)};
  const decodeBase64 = (value) => {{
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }};
  const hasClipboardItem = typeof ClipboardItem !== 'undefined';
  const hasClipboardWrite = !!(navigator.clipboard && navigator.clipboard.write);
  if (!hasClipboardItem || !hasClipboardWrite) {{
    return {{ ok: false, reason: 'clipboard_api_unavailable', hasClipboardItem, hasClipboardWrite }};
  }}
  const bytes = decodeBase64(payload.imageBase64);
  const blob = new Blob([bytes], {{ type: payload.mimeType || 'image/png' }});
  const item = new ClipboardItem({{ [payload.mimeType || 'image/png']: blob }});
  return navigator.clipboard.write([item])
    .then(() => ({{
      ok: true,
      mimeType: payload.mimeType,
      bytesLength: bytes.length,
      imageName: payload.imageName,
    }}))
    .catch((error) => ({{
      ok: false,
      reason: 'clipboard_write_failed',
      error: String(error),
      mimeType: payload.mimeType,
    }}));
}}"""


async def write_image_to_browser_clipboard(mcp: ChromeMcpClient, image_path: Path) -> dict[str, Any]:
    image_bytes = image_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    script = build_write_image_to_browser_clipboard_script(
        image_name=image_path.name,
        mime_type=mime_type,
        image_base64=image_base64,
    )
    result = await mcp.call_json("evaluate_script", {"function": script})
    return result if isinstance(result, dict) else {}


async def paste_inline_media_image_via_browser_clipboard(mcp: ChromeMcpClient, image_path: Path) -> None:
    log_step(f"正文图片粘贴(browser clipboard): {image_path.name}")
    await ensure_article_body_focus(mcp)
    baseline_state = await probe_article_media_state(mcp)
    baseline_media_count = int(baseline_state.get("mediaCount", 0) or 0)
    clip_result = await write_image_to_browser_clipboard(mcp, image_path)
    log_step(f"browser clipboard 写入结果: {json.dumps(clip_result, ensure_ascii=False)}")
    if not clip_result.get("ok"):
        raise RuntimeError(f"browser clipboard write failed: {json.dumps(clip_result, ensure_ascii=False)}")
    await mcp.call("press_key", {"key": "Control+V"})
    await wait_for_inline_media_inserted(mcp, baseline_media_count=baseline_media_count)


def build_paste_image_into_article_body_script(*, image_name: str, mime_type: str, image_base64: str) -> str:
    payload = {
        "imageName": image_name,
        "mimeType": mime_type,
        "imageBase64": image_base64,
    }
    return f"""() => {{
  const payload = {json.dumps(payload, ensure_ascii=False)};
  const decodeBase64 = (value) => {{
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }};
  const isVisible = (element) => {{
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  }};
  const candidates = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'))
    .filter((element) => isVisible(element))
    .map((element) => {{
      const rect = element.getBoundingClientRect();
      const text = [
        element.getAttribute('aria-label'),
        element.getAttribute('placeholder'),
        element.getAttribute('data-testid'),
        element.innerText,
        element.textContent,
      ].filter(Boolean).join(' ').toLowerCase();
      return {{ element, top: rect.top, text }};
    }})
    .sort((a, b) => a.top - b.top);

  let target = document.activeElement;
  if (!(target instanceof HTMLElement) || !target.isContentEditable) {{
    target = null;
  }}
  if (!target) {{
    const preferred = candidates.find((item) => item.text.includes('start writing') || item.text.includes('writing'));
    const fallback = candidates.find((item) => item.top >= 140 && !item.text.includes('title')) || candidates[1] || candidates[0];
    target = (preferred || fallback)?.element || null;
  }}
  if (!(target instanceof HTMLElement)) {{
    return {{ ok: false, reason: 'article_body_target_not_found', candidateCount: candidates.length }};
  }}

  target.focus();
  const bytes = decodeBase64(payload.imageBase64);
  const file = new File([bytes], payload.imageName, {{ type: payload.mimeType || 'image/png' }});
  const dt = new DataTransfer();
  dt.items.add(file);

  let pasteDispatchOk = false;
  try {{
    const pasteEvent = new ClipboardEvent('paste', {{ bubbles: true, cancelable: true }});
    Object.defineProperty(pasteEvent, 'clipboardData', {{ value: dt }});
    pasteDispatchOk = target.dispatchEvent(pasteEvent);
  }} catch (error) {{
    pasteDispatchOk = false;
  }}

  try {{
    const beforeInput = new InputEvent('beforeinput', {{
      bubbles: true,
      cancelable: true,
      inputType: 'insertFromPaste',
      data: '',
    }});
    Object.defineProperty(beforeInput, 'dataTransfer', {{ value: dt }});
    target.dispatchEvent(beforeInput);
  }} catch (error) {{
    // ignore
  }}

  return {{
    ok: true,
    pasteDispatchOk,
    dataTransferFiles: dt.files.length,
    targetText: [
      target.getAttribute('aria-label'),
      target.getAttribute('placeholder'),
      target.getAttribute('data-testid'),
    ].filter(Boolean).join(' '),
  }};
}}"""


async def paste_inline_media_image(mcp: ChromeMcpClient, image_path: Path) -> None:
    log_step(f"粘贴正文图片: {image_path.name}")
    await ensure_article_body_focus(mcp)
    baseline_state = await probe_article_media_state(mcp)
    baseline_media_count = int(baseline_state.get("mediaCount", 0) or 0)
    image_bytes = image_path.read_bytes()
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    script = build_paste_image_into_article_body_script(
        image_name=image_path.name,
        mime_type=mime_type,
        image_base64=base64.b64encode(image_bytes).decode("ascii"),
    )
    result = await mcp.call_json("evaluate_script", {"function": script})
    result_payload = result if isinstance(result, dict) else {}
    log_step(f"正文图片粘贴结果: {json.dumps(result_payload, ensure_ascii=False)}")
    if not result_payload.get("ok"):
        raise RuntimeError(f"inline paste setup failed: {json.dumps(result_payload, ensure_ascii=False)}")
    await wait_for_inline_media_inserted(mcp, baseline_media_count=baseline_media_count)


async def insert_inline_media_image(mcp: ChromeMcpClient, image_path: Path) -> None:
    upload_path = prepare_image_for_x_upload(image_path, role="inline")
    if upload_path != image_path:
        log_step(
            f"正文图自动瘦身: {image_path.name} ({image_path.stat().st_size} bytes) -> "
            f"{upload_path.name} ({upload_path.stat().st_size} bytes)"
        )
    try:
        await paste_inline_media_image_via_browser_clipboard(mcp, upload_path)
        return
    except Exception as exc:
        log_step(f"browser clipboard 粘贴失败，回退 synthetic paste: {exc}")
    await paste_inline_media_image(mcp, upload_path)


async def publish_article_blocks(mcp: ChromeMcpClient, article_assets: ArticleAssets) -> None:
    ops = extract_publish_ops(article_assets.publish_spec, article_assets.body)
    previous_block_type: str | None = None
    previous_op_kind: str | None = None

    for op in ops:
        op_kind = str(op.get("op", "")).strip()
        if op_kind == "insert_media":
            image_path = op.get("image_path")
            if isinstance(image_path, Path):
                await insert_inline_media_image(mcp, image_path)
                previous_op_kind = "insert_media"
            continue

        block_type = normalize_text(op.get("block_type", "")) or "paragraph"
        block_text = normalize_multiline_text(op.get("text", ""))
        block_items = [normalize_multiline_text(item) for item in op.get("items", []) if normalize_multiline_text(item)]
        block_url = normalize_multiline_text(op.get("url", "")) or None
        block_label = normalize_multiline_text(op.get("label", "")) or None

        if previous_op_kind == "type_block" and previous_block_type is not None:
            await ensure_article_body_focus(mcp)
            for _ in range(block_separator_key_presses(previous_block_type)):
                await mcp.call("press_key", {"key": "Enter"})
                await anyio.sleep(0.15)
        elif previous_op_kind == "insert_media":
            await resume_typing_after_media(mcp)

        await ensure_article_body_focus(mcp)

        if block_type in {"hero_heading", "section_heading"}:
            await try_set_article_text_style(mcp, "subheading", context=block_type)
            await mcp.call("type_text", {"text": block_text})
            previous_block_type = block_type
            previous_op_kind = "type_block"
            continue

        if block_type == "quote":
            await try_set_article_text_style(mcp, "body", context=block_type)
            try:
                await enable_quote_style(mcp)
            except Exception as exc:
                log_step(f"引用样式切换失败，继续执行: {exc}")
                await log_visible_toolbar_candidates(mcp, context="引用按钮快照")
            await mcp.call("type_text", {"text": block_text})
            # Exit quote block: Enter once exits quote in X Articles editor
            await mcp.call("press_key", {"key": "Enter"})
            await anyio.sleep(0.2)
            await try_set_article_text_style(mcp, "body", context=f"{block_type}_reset")
            previous_block_type = block_type
            previous_op_kind = "type_block"
            continue

        if block_type == "bullet_list":
            await try_set_article_text_style(mcp, "body", context=block_type)
            try:
                await enable_bullet_list(mcp)
            except Exception as exc:
                log_step(f"列表样式切换失败，继续执行: {exc}")
                await log_visible_toolbar_candidates(mcp, context="列表按钮快照")
            for item_index, item in enumerate(block_items):
                if item_index > 0:
                    await mcp.call("press_key", {"key": "Enter"})
                    await anyio.sleep(0.1)
                await mcp.call("type_text", {"text": item})
            await try_set_article_text_style(mcp, "body", context=f"{block_type}_reset")
            previous_block_type = block_type
            previous_op_kind = "type_block"
            continue

        if block_type == "link_cta":
            await try_set_article_text_style(mcp, "body", context=block_type)
            chunk: list[str] = []
            if block_text:
                chunk.append(block_text)
            if block_label and block_url:
                chunk.append(block_label)
            if block_url:
                chunk.append(block_url)
            await mcp.call("type_text", {"text": "\n".join(chunk)})
            previous_block_type = block_type
            previous_op_kind = "type_block"
            continue

        await try_set_article_text_style(mcp, "body", context=block_type or "paragraph")
        await mcp.call("type_text", {"text": block_text})
        previous_block_type = block_type
        previous_op_kind = "type_block"


async def take_snapshot_entries(mcp: ChromeMcpClient) -> list[SnapshotEntry]:
    snapshot_text = await mcp.call_text("take_snapshot", {})
    return parse_snapshot_entries(snapshot_text)


async def upload_image(mcp: ChromeMcpClient, image_path: Path) -> None:
    entries = await take_snapshot_entries(mcp)
    candidate_lines = summarize_upload_candidates(entries)
    if candidate_lines:
        log_step("上传候选元素:\n" + "\n".join(candidate_lines))
    input_lines = [f"{entry.uid} {entry.raw}" for entry in entries if "input" in entry.normalized]
    if input_lines:
        log_step("快照中的 input 元素:\n" + "\n".join(input_lines[:20]))
    upload_uid = find_upload_uid(entries)

    if not upload_uid:
        hints = "\n".join(
            f"{entry.uid} {entry.raw}"
            for entry in entries
            if "button" in entry.normalized or "input" in entry.normalized
        )
        raise RuntimeError(f"failed to locate upload element in snapshot. candidates:\n{hints}")

    matched_entry = next((entry for entry in entries if entry.uid == upload_uid), None)
    if matched_entry:
        log_step(f"命中上传元素: {matched_entry.uid} {matched_entry.raw}")
    await mcp.call("upload_file", {"uid": upload_uid, "filePath": str(image_path)})
    await anyio.sleep(1.5)


async def click_with_keywords(
    mcp: ChromeMcpClient,
    *,
    step_name: str,
    keywords: list[str],
    selectors: list[str],
    timeout_seconds: float = 12.0,
) -> None:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_result: dict[str, Any] = {}
    while datetime.now() < deadline:
        result = await mcp.call_json(
            "evaluate_script", {"function": build_button_click_script(keywords=keywords, selectors=selectors)}
        )
        last_result = result if isinstance(result, dict) else {}
        if last_result.get("ok"):
            return
        await anyio.sleep(0.8)
    raise RuntimeError(f"{step_name} failed: {json.dumps(last_result, ensure_ascii=False)}")


async def open_articles_writer(mcp: ChromeMcpClient) -> None:
    await mcp.call("new_page", {"url": "https://x.com/home"})
    await anyio.sleep(3)
    await click_with_keywords(
        mcp,
        step_name="open more menu",
        keywords=["more"],
        selectors=[
            '[aria-label*="More"]',
            '[aria-label*="more"]',
            'button',
            '[role="button"]',
        ],
        timeout_seconds=20,
    )
    await anyio.sleep(1)
    await click_with_keywords(
        mcp,
        step_name="open articles entry",
        keywords=["articles"],
        selectors=[
            '[href*="articles"]',
            'a',
            'button',
            '[role="menuitem"]',
            '[role="button"]',
        ],
        timeout_seconds=20,
    )
    await anyio.sleep(2)
    await click_with_keywords(
        mcp,
        step_name="open article writer",
        keywords=["write"],
        selectors=[
            'button',
            '[role="button"]',
            'a',
        ],
        timeout_seconds=20,
    )
    await anyio.sleep(2)


async def get_schedule_panel_state(mcp: ChromeMcpClient) -> dict[str, Any]:
    state = await mcp.call_json(
        "evaluate_script",
        {
            "function": """() => {
  const url = window.location.href;
  const dialog = document.querySelector('div[role="dialog"]');
  const root = dialog || document;
  const selects = Array.from(root.querySelectorAll('select'));
  const inputs = Array.from(root.querySelectorAll('input'));
  const spinbuttons = Array.from(root.querySelectorAll('[role="spinbutton"]'));
  return {
    url,
    hasDialog: Boolean(dialog),
    selectCount: selects.length,
    inputCount: inputs.length,
    spinbuttonCount: spinbuttons.length,
    controlsCount: selects.length + inputs.length + spinbuttons.length,
  };
}"""
        },
    )
    return state if isinstance(state, dict) else {}


async def wait_for_schedule_panel(mcp: ChromeMcpClient, timeout_seconds: float = 20.0) -> dict[str, Any]:
    deadline = datetime.now() + timedelta(seconds=timeout_seconds)
    last_state: dict[str, Any] = {}
    while datetime.now() < deadline:
        last_state = await get_schedule_panel_state(mcp)
        has_controls = int(last_state.get("controlsCount", 0)) >= 4
        if last_state.get("hasDialog") and has_controls:
            return last_state
        if "/compose/post/schedule" in str(last_state.get("url", "")) and has_controls:
            return last_state
        await anyio.sleep(0.4)
    raise RuntimeError(f"schedule panel did not become ready: {json.dumps(last_state, ensure_ascii=False)}")


async def open_schedule_panel(mcp: ChromeMcpClient) -> None:
    await click_with_keywords(
        mcp,
        step_name="open schedule panel",
        keywords=["schedule post", "schedule", "定时", "排程", "预约"],
        selectors=[
            'button[data-testid*="schedule"]',
            'button[aria-label*="Schedule"]',
            'button[aria-label*="schedule"]',
            'button[aria-label*="定时"]',
            'button[aria-label*="排程"]',
        ],
    )
    await wait_for_schedule_panel(mcp, timeout_seconds=20)


async def set_schedule_time(mcp: ChromeMcpClient, schedule_time: datetime) -> None:
    await wait_for_schedule_panel(mcp, timeout_seconds=20)
    payload = {
        "year": schedule_time.year,
        "month": schedule_time.month,
        "day": schedule_time.day,
        "hour": schedule_time.hour,
        "minute": schedule_time.minute,
    }
    last_result: dict[str, Any] = {}
    for _ in range(4):
        result = await mcp.call_json("evaluate_script", {"function": build_set_schedule_script(payload)})
        last_result = result if isinstance(result, dict) else {}
        if last_result.get("ok"):
            return
        await anyio.sleep(0.4)
    raise RuntimeError(f"set schedule values failed: {json.dumps(last_result, ensure_ascii=False)}")


async def confirm_schedule_panel(mcp: ChromeMcpClient) -> None:
    await click_with_keywords(
        mcp,
        step_name="confirm schedule panel",
        keywords=["confirm", "done", "确定", "完成", "保存"],
        selectors=[
            'div[role="dialog"] button[data-testid*="sched"]',
            'div[role="dialog"] button[data-testid*="confirm"]',
            'div[role="dialog"] button',
            'div[role="dialog"] [role="button"]',
        ],
    )
    await anyio.sleep(1)


async def submit_scheduled_post(mcp: ChromeMcpClient, allow_immediate_post: bool) -> None:
    result = await mcp.call_json(
        "evaluate_script", {"function": build_submit_scheduled_script(allow_immediate_post=allow_immediate_post)}
    )
    if not result.get("ok"):
        raise RuntimeError(f"submit post failed: {json.dumps(result, ensure_ascii=False)}")


async def submit_article_publish(mcp: ChromeMcpClient) -> None:
    await click_with_keywords(
        mcp,
        step_name="publish article",
        keywords=["publish"],
        selectors=[
            'button',
            '[role="button"]',
            'a',
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="x-schedule-post",
        description="通过 Chrome DevTools MCP 读取目录中的 post.txt（可选 post.jpg）并在 X 设置定时发帖",
    )
    parser.add_argument("-d", "--dir", required=True, help="包含 post.txt，且可选包含 post.jpg 的目录")
    parser.add_argument("--mode", choices=["post", "article"], default="post", help="发布模式")
    parser.add_argument(
        "-t",
        "--time",
        help="post 模式下的定时发布时间，例如: 2026-03-10 21:30 或 2026-03-10T21:30",
    )
    parser.add_argument("-z", "--timezone", help="时区，默认系统时区")
    parser.add_argument("--headless", action="store_true", help="以无头模式启动 Chrome")
    parser.add_argument("--browser-url", help="连接已运行的 Chrome 调试地址，例如 http://127.0.0.1:9222")
    parser.add_argument(
        "--accounts-csv",
        default="accounts_bitbrowser.csv",
        help="账号映射CSV路径（默认 ./accounts_bitbrowser.csv）",
    )
    parser.add_argument("--account", help="按账号从CSV里查找对应比特浏览器窗口")
    parser.add_argument("--bit-browser-id", help="比特浏览器窗口ID（将调用 /browser/open 获取调试地址）")
    parser.add_argument("--bit-api-port", type=int, default=54345, help="比特本地API端口，默认 54345")
    parser.add_argument(
        "--bit-open-timeout-seconds",
        default="10",
        help="调用比特 /browser/open 接口的超时秒数，默认 10",
    )
    parser.add_argument("--user-data-dir", help="Chrome 用户数据目录，默认 ~/.cache/x-post-tool/chrome-profile")
    parser.add_argument("--mcp-command", default="npx", help="启动 MCP 的命令")
    parser.add_argument("--mcp-arg", nargs="+", help="传递给 chrome-devtools-mcp 的附加参数")
    parser.add_argument("--login-timeout-minutes", default="8", help="等待手动登录超时（分钟）")
    parser.add_argument("--dry-run", action="store_true", help="执行到最终发布前停止（不真正点击发布）")
    parser.add_argument(
        "--skip-publish-spec-check",
        action="store_true",
        help="跳过 article_publish_spec 结构校验（默认开启校验）",
    )
    parser.add_argument(
        "--allow-immediate-post",
        action="store_true",
        help="允许最终按钮不是“Schedule/定时”时也点击",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    timezone = args.timezone
    if not timezone:
        local = datetime.now().astimezone().tzinfo
        timezone = getattr(local, "key", None) or "Asia/Shanghai"

    if args.mode == "post":
        if not args.time:
            raise ValueError("--time is required in post mode")
        schedule_time = parse_schedule_time(args.time, timezone)
        post_assets = resolve_post_assets(args.dir)
        article_assets = None
    else:
        schedule_time = None
        post_assets = None
        article_assets = resolve_article_assets(args.dir)
        if not args.skip_publish_spec_check:
            publish_spec_errors = validate_publish_spec_before_publish(article_assets.publish_spec)
            if publish_spec_errors:
                raise ValueError("article publish spec failed preflight: " + "; ".join(publish_spec_errors))

    try:
        login_timeout_minutes = float(args.login_timeout_minutes)
    except ValueError as exc:
        raise ValueError("--login-timeout-minutes must be a positive number") from exc
    if login_timeout_minutes <= 0:
        raise ValueError("--login-timeout-minutes must be a positive number")

    if post_assets is not None and len(post_assets.text) > 300:
        log_step(f"警告：post.txt 文本长度为 {len(post_assets.text)}，可能超过 X 限制。")

    resolved_browser_url = resolve_browser_url_from_args(args)
    if resolved_browser_url:
        args.browser_url = resolved_browser_url

    command, mcp_args = build_server_config(args)

    assets_dir = post_assets.directory if post_assets is not None else article_assets.directory
    log_step(f"内容目录: {assets_dir}")
    if schedule_time is not None:
        log_step(f"定时发布时间({timezone}): {schedule_time.strftime('%Y-%m-%d %H:%M')}")
    log_step(f"MCP command: {command} {' '.join(mcp_args)}")

    async with ChromeMcpClient(command=command, args=mcp_args) as mcp:
        if args.mode == "post":
            log_step("打开 X 发帖页...")
            await mcp.call("new_page", {"url": "https://x.com/compose/post"})

            await ensure_logged_in(mcp, timeout_seconds=login_timeout_minutes * 60)

            log_step("输入 post.txt 内容...")
            await focus_composer_and_type(mcp, post_assets.text)

            if post_assets.image_path is not None:
                log_step("上传 post.jpg...")
                await upload_image(mcp, post_assets.image_path)
            else:
                log_step("未检测到 post.jpg，按纯文字帖继续。")

            log_step("打开定时面板...")
            await open_schedule_panel(mcp)

            log_step("填写定时时间...")
            await set_schedule_time(mcp, schedule_time)

            log_step("确认定时设置...")
            await confirm_schedule_panel(mcp)

            if args.dry_run:
                log_step("dry-run 模式：到达最终发布前已停止。")
                return

            log_step("点击最终定时发布按钮...")
            await submit_scheduled_post(mcp, allow_immediate_post=args.allow_immediate_post)
            log_step("已提交定时发帖。")
            return

        log_step("打开 Articles 写作入口...")
        await open_articles_writer(mcp)
        await ensure_logged_in(mcp, timeout_seconds=login_timeout_minutes * 60)

        if article_assets.cover_path is not None:
            log_step("上传封面图 cover.jpg...")
            await upload_article_cover_image(mcp, article_assets.cover_path)
        else:
            log_step("未检测到 cover.jpg，跳过封面图。")

        log_step("输入 article 标题...")
        await focus_article_title_and_type(mcp, article_assets.title)

        log_step("输入 article 正文...")
        if article_assets.publish_spec and article_assets.publish_spec.get("article_blocks"):
            await publish_article_blocks(mcp, article_assets)
        else:
            article_body = render_article_body_from_spec(article_assets.publish_spec, article_assets.body)
            await focus_article_body_and_type(mcp, article_body)

        if args.dry_run:
            log_step("dry-run 模式：到达 Publish 前已停止。")
            return

        log_step("点击 Publish...")
        await submit_article_publish(mcp)
        log_step("Article 发布动作已提交。")


def main() -> None:
    args = parse_args()
    try:
        anyio.run(run, args)
    except BaseException as exc:  # pragma: no cover
        root: BaseException = exc
        while isinstance(root, BaseExceptionGroup) and root.exceptions:
            child = root.exceptions[0]
            if isinstance(child, BaseException):
                root = child
                continue
            break
        print(f"\n[x-schedule-post] {root}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
