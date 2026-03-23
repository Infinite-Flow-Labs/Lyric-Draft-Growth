from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


def log(message: str) -> None:
    print(message, flush=True)


def normalize_browser_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("empty browser debug url")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"http://{value}"


def request_bit_browser_open(*, browser_id: str, bit_api_port: int, timeout_seconds: float = 10.0) -> str:
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

    result = json.loads(body)
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


def resolve_browser_id(accounts_csv: Path, account: str) -> tuple[str, int]:
    with accounts_csv.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("account", "")).strip() == account:
                return str(row["browser_id"]).strip(), int(str(row.get("bit_port", "54345")).strip() or "54345")
    raise RuntimeError(f"account not found in csv: {account}")


def load_context_page(browser: Browser) -> tuple[BrowserContext, Page]:
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("no browser contexts after connect_over_cdp")
    context = contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    return context, page


def click_first(page: Page, selectors: list[str], timeout_ms: int = 15000) -> None:
    last_exc: Exception | None = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(timeout=timeout_ms, state="visible")
            locator.click(timeout=timeout_ms)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"failed click selectors: {selectors} ({last_exc})")


def count_visible_media(page: Page) -> int:
    return page.evaluate(
        """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 48 && rect.height > 48;
  };
  return Array.from(document.querySelectorAll('img,video,canvas'))
    .filter((element) => isVisible(element))
    .filter((element) => element.getBoundingClientRect().top > 40)
    .length;
}"""
    )


def dump_top_button_candidates(page: Page) -> list[dict[str, Any]]:
    return page.evaluate(
        """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };
  const describe = (element) => ({
    text: (element.innerText || element.textContent || '').trim(),
    aria: element.getAttribute('aria-label') || '',
    title: element.getAttribute('title') || '',
    testid: element.getAttribute('data-testid') || '',
    top: element.getBoundingClientRect().top,
    left: element.getBoundingClientRect().left,
    tag: element.tagName.toLowerCase(),
  });
  return Array.from(document.querySelectorAll('button,[role="button"],label,a'))
    .filter((element) => isVisible(element))
    .map(describe)
    .filter((item) => item.top <= 420)
    .sort((a, b) => (a.top - b.top) || (a.left - b.left))
    .slice(0, 60);
}"""
    )


def dump_file_inputs(page: Page) -> list[dict[str, Any]]:
    return page.evaluate(
        """() => {
  const textAround = (element) => {
    const parent = element.parentElement;
    const grand = parent?.parentElement;
    return [
      parent?.innerText || '',
      grand?.innerText || '',
      element.getAttribute('accept') || '',
      element.getAttribute('multiple') || '',
      element.getAttribute('aria-label') || '',
      element.getAttribute('title') || '',
    ].join(' | ').trim();
  };
  return Array.from(document.querySelectorAll('input[type="file"]')).map((element, index) => {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    return {
      index,
      top: rect.top,
      left: rect.left,
      width: rect.width,
      height: rect.height,
      visible: style.display !== 'none' && style.visibility !== 'hidden' && (rect.width > 0 || rect.height > 0),
      desc: textAround(element),
    };
  });
}"""
    )


def synthetic_assign_file_to_input(page: Page, *, index: int, file_name: str, mime_type: str, file_bytes: bytes) -> dict[str, Any]:
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return page.evaluate(
        """(payload) => {
  const input = document.querySelectorAll('input[type="file"]')[payload.index];
  if (!input) return { ok: false, reason: 'input_not_found' };

  const decodeBase64 = (value) => {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  };

  const bytes = decodeBase64(payload.base64);
  const file = new File([bytes], payload.fileName, { type: payload.mimeType || 'image/png' });
  const dt = new DataTransfer();
  dt.items.add(file);

  let assignOk = false;
  try {
    input.files = dt.files;
    assignOk = true;
  } catch (error) {
    assignOk = false;
  }

  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));

  const parent = input.parentElement;
  const grand = parent?.parentElement;
  const target = [parent, grand, input].find(Boolean);
  if (target && typeof DragEvent !== 'undefined') {
    for (const type of ['dragenter', 'dragover', 'drop']) {
      try {
        const event = new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt });
        target.dispatchEvent(event);
      } catch (error) {
        // ignore
      }
    }
  }

  return {
    ok: true,
    assignOk,
    filesLength: input.files ? input.files.length : 0,
    inputAccept: input.getAttribute('accept') || '',
    targetText: ((parent?.innerText || '') + ' | ' + (grand?.innerText || '')).trim(),
  };
}""",
        {
            "index": index,
            "base64": encoded,
            "fileName": file_name,
            "mimeType": mime_type,
        },
    )


def synthetic_drop_cover_file(page: Page, *, file_name: str, mime_type: str, file_bytes: bytes) -> dict[str, Any]:
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return page.evaluate(
        """(payload) => {
  const decodeBase64 = (value) => {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  };
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };
  const textNodes = Array.from(document.querySelectorAll('div,section,article,span,p'))
    .filter((element) => isVisible(element))
    .map((element) => ({
      element,
      rect: element.getBoundingClientRect(),
      text: (element.innerText || element.textContent || '').trim().toLowerCase(),
    }))
    .filter((item) => item.text.includes('5:2 aspect ratio') || item.text.includes('best results'));

  const anchor = textNodes.sort((a, b) => b.rect.width * b.rect.height - a.rect.width * a.rect.height)[0];
  if (!anchor) return { ok: false, reason: 'cover_dropzone_anchor_not_found' };

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

  const bytes = decodeBase64(payload.base64);
  const file = new File([bytes], payload.fileName, { type: payload.mimeType || 'image/png' });
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
    dropTargetSize: { width: dropTarget.width, height: dropTarget.height, depth: dropTarget.depth },
    dispatched,
  };
}""",
        {
            "base64": encoded,
            "fileName": file_name,
            "mimeType": mime_type,
        },
    )


def open_article_writer(page: Page) -> None:
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    click_first(page, ['[aria-label*="More"]', '[aria-label*="more"]', 'button:has-text("More")'])
    page.wait_for_timeout(1000)
    click_first(page, ['a:has-text("Articles")', '[role="menuitem"]:has-text("Articles")', 'button:has-text("Articles")'])
    page.wait_for_timeout(2000)
    click_first(page, ['button:has-text("Write")', 'a:has-text("Write")'])
    page.wait_for_timeout(2500)


def upload_cover(page: Page, cover_path: Path) -> dict[str, Any]:
    baseline = count_visible_media(page)
    log(f"baselineMediaCount={baseline}")
    candidates = dump_top_button_candidates(page)
    log("topButtonCandidates=" + json.dumps(candidates[:20], ensure_ascii=False))
    file_inputs = dump_file_inputs(page)
    log("fileInputs=" + json.dumps(file_inputs, ensure_ascii=False))

    inputs = page.locator('input[type="file"]')
    count = inputs.count()
    if count < 1:
        page.screenshot(path=str(cover_path.parent / "playwright_cover_no_input.png"), full_page=True)
        raise RuntimeError("no file input present on article editor")

    attempts: list[dict[str, Any]] = []
    file_bytes = cover_path.read_bytes()
    mime_type = mimetypes.guess_type(str(cover_path))[0] or "image/png"
    for index in range(count):
        try:
            inputs.nth(index).set_input_files(str(cover_path), timeout=15000)
        except Exception as exc:
            attempts.append({"index": index, "setFilesOk": False, "error": str(exc)})
            continue

        files_len = page.evaluate(
            """(idx) => {
  const input = document.querySelectorAll('input[type="file"]')[idx];
  return input?.files?.length || 0;
}""",
            index,
        )

        deadline = time.time() + 8
        last_count = baseline
        while time.time() < deadline:
            last_count = count_visible_media(page)
            if last_count > baseline:
                return {
                    "ok": True,
                    "baselineMediaCount": baseline,
                    "finalMediaCount": last_count,
                    "inputIndex": index,
                    "filesLength": files_len,
                    "fileInputs": file_inputs,
                    "attempts": attempts,
                }
            page.wait_for_timeout(400)

        attempts.append(
            {
                "method": "native_set_input_files",
                "index": index,
                "setFilesOk": True,
                "filesLength": files_len,
                "finalMediaCount": last_count,
            }
        )

        synthetic_result = synthetic_assign_file_to_input(
            page,
            index=index,
            file_name=cover_path.name,
            mime_type=mime_type,
            file_bytes=file_bytes,
        )
        deadline = time.time() + 8
        last_count = baseline
        while time.time() < deadline:
            last_count = count_visible_media(page)
            if last_count > baseline:
                return {
                    "ok": True,
                    "baselineMediaCount": baseline,
                    "finalMediaCount": last_count,
                    "inputIndex": index,
                    "filesLength": int(synthetic_result.get("filesLength", 0) or 0),
                    "method": "synthetic_assign_file_to_input",
                    "fileInputs": file_inputs,
                    "attempts": attempts,
                    "syntheticResult": synthetic_result,
                }
            page.wait_for_timeout(400)

        attempts.append(
            {
                "method": "synthetic_assign_file_to_input",
                "index": index,
                "assignOk": bool(synthetic_result.get("assignOk")),
                "filesLength": int(synthetic_result.get("filesLength", 0) or 0),
                "finalMediaCount": last_count,
                "targetText": synthetic_result.get("targetText", ""),
            }
        )

    drop_result = synthetic_drop_cover_file(
        page,
        file_name=cover_path.name,
        mime_type=mime_type,
        file_bytes=file_bytes,
    )
    deadline = time.time() + 8
    last_count = baseline
    while time.time() < deadline:
        last_count = count_visible_media(page)
        if last_count > baseline:
            return {
                "ok": True,
                "baselineMediaCount": baseline,
                "finalMediaCount": last_count,
                "method": "synthetic_drop_cover_file",
                "fileInputs": file_inputs,
                "attempts": attempts,
                "dropResult": drop_result,
            }
        page.wait_for_timeout(400)

    attempts.append(
        {
            "method": "synthetic_drop_cover_file",
            "filesLength": int(drop_result.get("filesLength", 0) or 0),
            "dropTargetText": drop_result.get("dropTargetText", ""),
            "finalMediaCount": last_count,
        }
    )

    return {
        "ok": False,
        "baselineMediaCount": baseline,
        "finalMediaCount": count_visible_media(page),
        "fileInputs": file_inputs,
        "attempts": attempts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--accounts-csv", required=True)
    args = parser.parse_args()

    slot_dir = Path(args.dir).resolve()
    cover_path = next((slot_dir / name for name in ("cover.png", "cover.jpg", "cover.jpeg", "cover.webp") if (slot_dir / name).exists()), None)
    if cover_path is None:
        raise RuntimeError(f"no cover image in {slot_dir}")

    browser_id, bit_port = resolve_browser_id(Path(args.accounts_csv), args.account)
    browser_url = request_bit_browser_open(browser_id=browser_id, bit_api_port=bit_port)
    wait_for_browser_debug_ready(browser_url)
    log(f"browser_url={browser_url}")

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(browser_url)
        _, page = load_context_page(browser)
        open_article_writer(page)
        result = upload_cover(page, cover_path)
        print(json.dumps(result, ensure_ascii=False))
        if not result.get("ok"):
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
