from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import time
from pathlib import Path
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
                data.get("webSocketDebuggerUrl") or data.get("Browser") or data.get("Protocol-Version")
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


def open_article_writer(page: Page) -> None:
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    click_first(page, ['[aria-label*="More"]', '[aria-label*="more"]', 'button:has-text("More")'])
    page.wait_for_timeout(1000)
    click_first(page, ['a:has-text("Articles")', '[role="menuitem"]:has-text("Articles")', 'button:has-text("Articles")'])
    page.wait_for_timeout(2000)
    click_first(page, ['button:has-text("Write")', 'a:has-text("Write")'])
    page.wait_for_timeout(2500)


def focus_body(page: Page) -> None:
    script = """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };
  const candidates = Array.from(document.querySelectorAll('[contenteditable="true"], textarea'))
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
  const target = (candidates.find((item) => item.text.includes('start writing') || item.text.includes('writing') || item.text.includes('composer')) || candidates[0] || {}).element || null;
  if (!target) return { ok: false, count: candidates.length };
  target.focus();
  return { ok: true, text: [target.getAttribute('aria-label'), target.getAttribute('placeholder'), target.getAttribute('data-testid')].filter(Boolean).join(' ') };
}"""
    result = page.evaluate(script)
    if not result.get("ok"):
        raise RuntimeError(f"failed to focus article body: {json.dumps(result, ensure_ascii=False)}")


def write_image_to_clipboard(page: Page, image_path: Path) -> dict[str, object]:
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return page.evaluate(
        """async (payload) => {
  const bytes = Uint8Array.from(atob(payload.base64), (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: payload.mimeType });
  const item = new ClipboardItem({ [payload.mimeType]: blob });
  try {
    await navigator.clipboard.write([item]);
    return { ok: true, mimeType: payload.mimeType, size: bytes.length };
  } catch (error) {
    return { ok: false, error: String(error), mimeType: payload.mimeType, size: bytes.length };
  }
}""",
        {"base64": data, "mimeType": mime_type},
    )


def capture_state(page: Page) -> dict[str, object]:
    return page.evaluate(
        """() => {
  const isVisible = (element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    return rect.width > 0 && rect.height > 0;
  };
  const visibleText = (document.body?.innerText || '').slice(0, 4000);
  const imgs = Array.from(document.querySelectorAll('img')).filter((el) => isVisible(el)).map((el) => ({
    src: (el.getAttribute('src') || '').slice(0, 120),
    width: el.getBoundingClientRect().width,
    height: el.getBoundingClientRect().height,
    top: el.getBoundingClientRect().top,
  }));
  const canvases = Array.from(document.querySelectorAll('canvas')).filter((el) => isVisible(el)).map((el) => ({
    width: el.getBoundingClientRect().width,
    height: el.getBoundingClientRect().height,
    top: el.getBoundingClientRect().top,
  }));
  const editable = Array.from(document.querySelectorAll('[contenteditable=\"true\"], textarea')).filter((el) => isVisible(el)).map((el) => ({
    text: [
      el.getAttribute('aria-label'),
      el.getAttribute('placeholder'),
      el.getAttribute('data-testid'),
      el.innerText,
      el.textContent,
    ].filter(Boolean).join(' ').slice(0, 200),
    top: el.getBoundingClientRect().top,
    height: el.getBoundingClientRect().height,
  })).slice(0, 20);
  return {
    visibleText,
    hasCaptionText: visibleText.toLowerCase().includes('provide a caption') || visibleText.includes('Provide a caption') || visibleText.includes('提供'),
    imgCount: imgs.length,
    canvasCount: canvases.length,
    imgs,
    canvases,
    editables: editable,
    activeElement: {
      tag: document.activeElement?.tagName || '',
      text: [
        document.activeElement?.getAttribute?.('aria-label'),
        document.activeElement?.getAttribute?.('placeholder'),
        document.activeElement?.getAttribute?.('data-testid'),
        document.activeElement?.textContent,
      ].filter(Boolean).join(' ').slice(0, 200),
    }
  };
}"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--accounts-csv", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    slot_dir = Path(args.dir).resolve()
    out_path = Path(args.out).resolve()
    image_path = slot_dir / "inline_01.png"
    if not image_path.exists():
        raise RuntimeError(f"inline image not found: {image_path}")

    browser_id, bit_port = resolve_browser_id(Path(args.accounts_csv), args.account)
    browser_url = request_bit_browser_open(browser_id=browser_id, bit_api_port=bit_port)
    wait_for_browser_debug_ready(browser_url)
    log(f"browser_url={browser_url}")

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(browser_url)
        context, page = load_context_page(browser)
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://x.com")
        open_article_writer(page)
        focus_body(page)
        clip = write_image_to_clipboard(page, image_path)
        log("clipboardWrite=" + json.dumps(clip, ensure_ascii=False))
        page.keyboard.press("Control+V")
        page.wait_for_timeout(3000)
        state = capture_state(page)
        payload = {"clipboard": clip, "state": state}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
