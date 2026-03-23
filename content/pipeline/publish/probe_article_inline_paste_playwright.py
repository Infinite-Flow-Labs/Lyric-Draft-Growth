from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
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


def open_article_writer(page: Page) -> None:
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    click_first(page, ['[aria-label*="More"]', '[aria-label*="more"]', 'button:has-text("More")'])
    page.wait_for_timeout(1000)
    click_first(page, ['a:has-text("Articles")', '[role="menuitem"]:has-text("Articles")', 'button:has-text("Articles")'])
    page.wait_for_timeout(2000)
    click_first(page, ['button:has-text("Write")', 'a:has-text("Write")'])
    page.wait_for_timeout(2500)


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


def focus_article_body(page: Page) -> None:
    ok = page.evaluate(
        """() => {
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
  const target =
    visible.find((item) => item.text.includes('start writing') || item.text.includes('writing')) ||
    visible.find((item) => item.top >= 140 && !item.text.includes('title')) ||
    visible[1] ||
    visible[0];
  if (!target) return false;
  target.element.focus();
  target.element.click();
  return true;
}"""
    )
    if not ok:
        raise RuntimeError("failed to focus article body")


def prime_clipboard_with_image(image_path: Path) -> None:
    command = ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", str(image_path)]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"xclip failed: {completed.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--accounts-csv", required=True)
    args = parser.parse_args()

    slot_dir = Path(args.dir).resolve()
    image_path = slot_dir / "inline_01.png"
    if not image_path.exists():
        raise RuntimeError(f"missing inline image: {image_path}")

    browser_id, bit_port = resolve_browser_id(Path(args.accounts_csv), args.account)
    browser_url = request_bit_browser_open(browser_id=browser_id, bit_api_port=bit_port)
    wait_for_browser_debug_ready(browser_url)
    log(f"browser_url={browser_url}")
    prime_clipboard_with_image(image_path)

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(browser_url)
        _, page = load_context_page(browser)
        open_article_writer(page)
        focus_article_body(page)
        baseline = count_visible_media(page)
        log(f"baselineMediaCount={baseline}")
        page.keyboard.press("Control+V")

        deadline = time.time() + 12
        last_count = baseline
        while time.time() < deadline:
            last_count = count_visible_media(page)
            if last_count > baseline:
                print(json.dumps({"ok": True, "baselineMediaCount": baseline, "finalMediaCount": last_count}, ensure_ascii=False))
                return 0
            page.wait_for_timeout(400)

        print(json.dumps({"ok": False, "baselineMediaCount": baseline, "finalMediaCount": last_count}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
