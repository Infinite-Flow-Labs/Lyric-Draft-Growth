from __future__ import annotations

import argparse
import csv
from contextlib import AsyncExitStack
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

LOGIN_URL_PARTS = ("/i/flow/login", "/login")


def now_stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log_step(msg: str) -> None:
    print(f"[{now_stamp()}] {msg}")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


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

    for entry in entries:
        if "button" not in entry.normalized and "input" not in entry.normalized:
            continue
        if includes_any(entry.normalized, choose_file_keywords):
            return entry.uid

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

    for entry in entries:
        if "input" not in entry.normalized and "button" not in entry.normalized:
            continue
        if includes_any(entry.normalized, keywords):
            return entry.uid

    for entry in entries:
        if "input" in entry.normalized and "file" in entry.normalized:
            return entry.uid

    return None


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
    image_path: Path
    text: str


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
    if not image_path.exists():
        raise ValueError(f"missing file: {image_path}")

    text = text_path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    if not text.strip():
        raise ValueError(f"post.txt is empty: {text_path}")

    return PostAssets(directory=directory, text_path=text_path, image_path=image_path, text=text)


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

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
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


def build_server_config(args: argparse.Namespace) -> tuple[str, list[str]]:
    mcp_args = ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]
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

    return args.mcp_command, mcp_args


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


async def take_snapshot_entries(mcp: ChromeMcpClient) -> list[SnapshotEntry]:
    snapshot_text = await mcp.call_text("take_snapshot", {})
    return parse_snapshot_entries(snapshot_text)


async def upload_image(mcp: ChromeMcpClient, image_path: Path) -> None:
    entries = await take_snapshot_entries(mcp)
    upload_uid = find_upload_uid(entries)

    if not upload_uid:
        hints = "\n".join(
            f"{entry.uid} {entry.raw}"
            for entry in entries
            if "button" in entry.normalized or "input" in entry.normalized
        )
        raise RuntimeError(f"failed to locate upload element in snapshot. candidates:\n{hints}")

    await mcp.call("upload_file", {"uid": upload_uid, "filePath": str(image_path)})
    await anyio.sleep(1.5)


async def click_with_keywords(mcp: ChromeMcpClient, *, step_name: str, keywords: list[str], selectors: list[str]) -> None:
    result = await mcp.call_json(
        "evaluate_script", {"function": build_button_click_script(keywords=keywords, selectors=selectors)}
    )
    if not result.get("ok"):
        raise RuntimeError(f"{step_name} failed: {json.dumps(result, ensure_ascii=False)}")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="x-schedule-post",
        description="通过 Chrome DevTools MCP 读取目录中的 post.txt/post.jpg 并在 X 设置定时发帖",
    )
    parser.add_argument("-d", "--dir", required=True, help="包含 post.txt 与 post.jpg 的目录")
    parser.add_argument(
        "-t",
        "--time",
        required=True,
        help="定时发布时间，例如: 2026-03-10 21:30 或 2026-03-10T21:30",
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
        "--allow-immediate-post",
        action="store_true",
        help="允许最终按钮不是“Schedule/定时”时也点击",
    )
    return parser.parse_args()


async def run_with_retry(step_name: str, fn, attempts: int = 3, delay_seconds: float = 2.5):
    last_exc: Exception | None = None
    for idx in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
            if idx < attempts:
                log_step(f"{step_name} failed (attempt {idx}/{attempts}), retrying: {exc}")
                await anyio.sleep(delay_seconds)
    assert last_exc is not None
    raise last_exc


async def run(args: argparse.Namespace) -> None:
    timezone = args.timezone
    if not timezone:
        local = datetime.now().astimezone().tzinfo
        timezone = getattr(local, "key", None) or "Asia/Shanghai"

    schedule_time = parse_schedule_time(args.time, timezone)
    assets = resolve_post_assets(args.dir)

    try:
        login_timeout_minutes = float(args.login_timeout_minutes)
    except ValueError as exc:
        raise ValueError("--login-timeout-minutes must be a positive number") from exc
    if login_timeout_minutes <= 0:
        raise ValueError("--login-timeout-minutes must be a positive number")

    if len(assets.text) > 300:
        log_step(f"警告：post.txt 文本长度为 {len(assets.text)}，可能超过 X 限制。")

    resolved_browser_url = resolve_browser_url_from_args(args)
    if resolved_browser_url:
        args.browser_url = resolved_browser_url

    command, mcp_args = build_server_config(args)

    log_step(f"内容目录: {assets.directory}")
    log_step(f"定时发布时间({timezone}): {schedule_time.strftime('%Y-%m-%d %H:%M')}")
    log_step(f"MCP command: {command} {' '.join(mcp_args)}")

    async with ChromeMcpClient(command=command, args=mcp_args) as mcp:
        log_step("打开 X 发帖页...")
        await run_with_retry(
            "open compose page",
            lambda: mcp.call("new_page", {"url": "https://x.com/compose/post"}),
            attempts=3,
            delay_seconds=3,
        )

        await ensure_logged_in(mcp, timeout_seconds=login_timeout_minutes * 60)

        log_step("输入 post.txt 内容...")
        await run_with_retry(
            "focus/type compose",
            lambda: focus_composer_and_type(mcp, assets.text),
            attempts=3,
            delay_seconds=2,
        )

        log_step("上传 post.jpg...")
        await run_with_retry(
            "upload image",
            lambda: upload_image(mcp, assets.image_path),
            attempts=3,
            delay_seconds=2,
        )

        log_step("打开定时面板...")
        await run_with_retry(
            "open schedule panel",
            lambda: open_schedule_panel(mcp),
            attempts=3,
            delay_seconds=2,
        )

        log_step("填写定时时间...")
        await run_with_retry(
            "set schedule time",
            lambda: set_schedule_time(mcp, schedule_time),
            attempts=2,
            delay_seconds=1.5,
        )

        log_step("确认定时设置...")
        await run_with_retry(
            "confirm schedule panel",
            lambda: confirm_schedule_panel(mcp),
            attempts=2,
            delay_seconds=1.5,
        )

        if args.dry_run:
            log_step("dry-run 模式：到达最终发布前已停止。")
            return

        log_step("点击最终定时发布按钮...")
        await run_with_retry(
            "submit scheduled post",
            lambda: submit_scheduled_post(mcp, allow_immediate_post=args.allow_immediate_post),
            attempts=2,
            delay_seconds=1.5,
        )
        log_step("已提交定时发帖。")


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
