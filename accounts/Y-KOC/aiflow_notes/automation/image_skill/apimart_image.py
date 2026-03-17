from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

from article_to_prompt import read_article_title_and_body, build_prompt_from_article

BASE = "https://api.apimart.ai/v1/images"


def _req(url: str, method: str = "GET", data: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    return json.loads(raw)


def submit_generation(prompt: str, token: str, size: str = "16:9", resolution: str = "2K", n: int = 1) -> str:
    payload = {
        "model": "gemini-3.1-flash-image-preview",
        "prompt": prompt,
        "size": size,
        "resolution": resolution,
        "n": n,
    }
    resp = _req(f"{BASE}/generations", method="POST", data=payload, token=token)
    data = resp.get("data") or []
    if not data:
        raise RuntimeError(f"submit failed: {resp}")
    task_id = data[0].get("task_id")
    if not task_id:
        raise RuntimeError(f"no task_id: {resp}")
    return task_id


def poll_task(task_id: str, token: str, max_wait_s: int = 180) -> dict:
    # Common task-result patterns, try both
    urls = [
        f"{BASE}/generations/{task_id}",
        f"{BASE}/generations/result/{task_id}",
    ]
    start = time.time()
    last_err = None
    while time.time() - start < max_wait_s:
        for u in urls:
            try:
                resp = _req(u, token=token)
                status = (resp.get("data") or [{}])[0].get("status") if isinstance(resp.get("data"), list) else resp.get("status")
                if str(status).lower() in {"succeeded", "success", "completed", "done"}:
                    return resp
                if str(status).lower() in {"failed", "error"}:
                    raise RuntimeError(f"task failed: {resp}")
                last_err = resp
            except Exception as e:
                last_err = str(e)
        time.sleep(3)
    raise TimeoutError(f"poll timeout task={task_id}, last={last_err}")


def extract_image_urls(resp: dict) -> list[str]:
    urls: list[str] = []
    data = resp.get("data")
    if isinstance(data, list):
        for item in data:
            for k in ("url", "image_url", "output", "output_url"):
                v = item.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    urls.append(v)
            outs = item.get("outputs")
            if isinstance(outs, list):
                for o in outs:
                    if isinstance(o, str) and o.startswith("http"):
                        urls.append(o)
                    elif isinstance(o, dict):
                        u = o.get("url") or o.get("image_url")
                        if isinstance(u, str) and u.startswith("http"):
                            urls.append(u)
    return list(dict.fromkeys(urls))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--article", required=True)
    ap.add_argument("--out", required=True, help="output json path")
    ap.add_argument("--size", default="16:9")
    ap.add_argument("--resolution", default="2K")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--wait", type=int, default=180)
    args = ap.parse_args()

    token = os.getenv("APIMART_API_KEY")
    if not token:
        raise RuntimeError("APIMART_API_KEY is required")

    article_path = Path(args.article).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    title, body = read_article_title_and_body(article_path)
    prompt = build_prompt_from_article(body, title)

    task_id = submit_generation(prompt, token, size=args.size, resolution=args.resolution, n=args.n)
    result = poll_task(task_id, token, max_wait_s=args.wait)
    image_urls = extract_image_urls(result)

    payload = {
        "article": str(article_path),
        "title": title,
        "prompt": prompt,
        "task_id": task_id,
        "result": result,
        "image_urls": image_urls,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))
    print(f"images={len(image_urls)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
