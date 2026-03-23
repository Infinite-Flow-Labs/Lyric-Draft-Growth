from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_API_BASE_URL = "https://api.kie.ai"
DEFAULT_MODEL = "nano-banana-2"
SUPPORTED_ASPECTS = {
    "1:1",
    "1:4",
    "1:8",
    "2:3",
    "3:2",
    "3:4",
    "4:1",
    "4:3",
    "4:5",
    "5:4",
    "8:1",
    "9:16",
    "16:9",
    "21:9",
    "auto",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def map_aspect_ratio(value: str) -> str:
    cleaned = clean_text(value)
    if cleaned in SUPPORTED_ASPECTS:
        return cleaned
    if cleaned == "5:2":
        return "21:9"
    return "auto"


def ext_for_format(value: str) -> str:
    cleaned = clean_text(value).lower()
    if cleaned == "png":
        return "png"
    return "jpg"


def build_prompt(global_rules: dict[str, Any], brief: dict[str, Any]) -> str:
    palette = global_rules.get("palette") or {}
    overlay = brief.get("on_canvas_text") or {}
    text_budget = brief.get("text_budget") or {}
    lines: list[str] = []

    lines.append("Create a high-quality editorial knowledge graphic for an X Article.")
    lines.append("All on-canvas text must be in Simplified Chinese only, except unavoidable product or model names.")
    lines.append("Do not use English headings, translated body text, UI labels, or bilingual duplication unless explicitly requested.")
    lines.append(f"Role: {clean_text(brief.get('role', 'inline'))}.")
    lines.append(f"Image grammar: {clean_text(brief.get('image_grammar', 'section_reset'))}.")
    lines.append(f"Purpose: {clean_text(brief.get('purpose', ''))}.")
    lines.append(f"Diagram type: {clean_text(brief.get('diagram_type', 'other'))}.")
    lines.append(f"Concept summary: {clean_text(brief.get('concept_summary', ''))}.")

    style_direction = clean_text(global_rules.get("style_direction", ""))
    if style_direction:
        lines.append(f"Style direction: {style_direction}.")

    background = clean_text(palette.get("background", ""))
    if background:
        lines.append(f"Background: {background}.")

    primary_accents = dedupe(list(palette.get("primary_accents") or []))
    if primary_accents:
        lines.append(f"Primary accents: {', '.join(primary_accents)}.")

    linework = clean_text(palette.get("linework", ""))
    if linework:
        lines.append(f"Line work: {linework}.")

    scene_elements = dedupe(list(brief.get("scene_elements") or []))
    if scene_elements:
        lines.append(f"Scene elements: {', '.join(scene_elements)}.")

    relationships = dedupe(list(brief.get("key_relationships") or []))
    if relationships:
        lines.append(f"Key relationships to visualize: {', '.join(relationships)}.")

    composition = brief.get("composition") or {}
    layout_pattern = clean_text(composition.get("layout_pattern", ""))
    if layout_pattern:
        lines.append(f"Layout pattern: {layout_pattern}.")
    diagram_focus = clean_text(composition.get("diagram_focus", ""))
    if diagram_focus:
        lines.append(f"Diagram focus: {diagram_focus}.")
    text_position = clean_text(composition.get("text_position", ""))
    if text_position:
        lines.append(f"Text position: {text_position}.")

    headline = clean_text(overlay.get("headline", ""))
    subheadline = clean_text(overlay.get("subheadline", ""))
    short_labels = dedupe(list(overlay.get("short_labels") or []))
    max_text_blocks = text_budget.get("max_text_blocks")
    headline_max_chars = text_budget.get("headline_max_chars")
    subheadline_max_chars = text_budget.get("subheadline_max_chars")
    label_max_chars = text_budget.get("label_max_chars")
    max_labels = text_budget.get("max_labels")
    if max_text_blocks:
        lines.append(f"Text budget: no more than {max_text_blocks} major text blocks on the image.")
    if headline_max_chars:
        lines.append(f"Headline budget: <= {headline_max_chars} Chinese characters.")
    if subheadline_max_chars is not None:
        lines.append(f"Subheadline budget: <= {subheadline_max_chars} Chinese characters.")
    if label_max_chars:
        lines.append(f"Label budget: <= {label_max_chars} Chinese characters per label.")
    if max_labels is not None:
        lines.append(f"Label count budget: <= {max_labels} labels.")
    if headline:
        lines.append(f'On-canvas headline: "{headline}".')
    if subheadline:
        lines.append(f'On-canvas subheadline: "{subheadline}".')
    if short_labels:
        lines.append(f"Use short Chinese labels only: {', '.join(short_labels)}.")

    grammar = clean_text(brief.get("image_grammar", "section_reset"))
    grammar_rules = {
        "hook_cover": [
            "This is a hook-first cover, not a summary board.",
            "Show one tension or one question and one payoff only.",
            "Use 2-4 large visual nodes max.",
            "Do not turn the article into a dense chart."
        ],
        "framework_map": [
            "Show the full framework at a glance.",
            "Do not exceed 4 major zones or branches.",
            "Keep labels ultra-short."
        ],
        "concept_cluster": [
            "Use one center node and 3-5 surrounding concepts.",
            "This is a mental map, not a paragraph explanation.",
            "Each node should be instantly scannable."
        ],
        "example_comparison": [
            "Use a left-vs-right or before-vs-after structure.",
            "One example should prove the section point immediately.",
            "Avoid extra supporting text blocks."
        ],
        "skip_board": [
            "Use a strong top verdict and 4-6 rejection cards.",
            "This should feel like a fast scan board.",
            "No paragraphs. No dense explanation."
        ],
        "decision_board": [
            "Make the decision logic instantly obvious.",
            "Use 3-4 cards or tiers max.",
            "Support fast skimming."
        ],
        "workflow_map": [
            "Show 3-4 stages max.",
            "This is a process graphic, not an article summary.",
            "Each stage must be visually distinct."
        ],
        "evolution_map": [
            "Show how the logic shifts over time.",
            "Use 3 stages max.",
            "The transition should be more important than detailed text."
        ],
        "section_reset": [
            "This image should reset attention around one idea.",
            "One concept should dominate.",
            "Avoid extra text and side ideas."
        ],
    }
    if grammar_rules.get(grammar):
        lines.append(f"Grammar rules: {' '.join(grammar_rules[grammar])}")

    must_have = dedupe(list(global_rules.get("must_have") or []))
    visual_constraints = dedupe(list(brief.get("visual_constraints") or []))
    if must_have or visual_constraints:
        lines.append(f"Must have: {', '.join(dedupe(must_have + visual_constraints))}.")

    must_avoid = dedupe(list(global_rules.get("must_avoid") or []))
    negative_constraints = dedupe(list(brief.get("negative_constraints") or []))
    if must_avoid or negative_constraints:
        lines.append(f"Must avoid: {', '.join(dedupe(must_avoid + negative_constraints))}.")

    prompt_seed = clean_text(brief.get("prompt_seed", ""))
    if prompt_seed:
        lines.append(f"Additional direction: {prompt_seed}.")

    lines.append("The result should look like a premium creator-made article infographic, not generic AI art.")
    lines.append("Keep the composition clean, explanatory, and mobile-legible.")
    lines.append("Do not simply render the article's paragraph text into the image.")

    return "\n".join(line for line in lines if line.strip())


@dataclass(frozen=True)
class ImageTask:
    image_id: str
    role: str
    prompt: str
    image_input: list[str]
    aspect_ratio: str
    resolution: str
    output_format: str


def build_tasks(payload: dict[str, Any]) -> list[ImageTask]:
    global_rules = payload["global_visual_rules"]
    tasks: list[ImageTask] = []

    all_briefs = [payload["cover_image"], *payload.get("inline_images", [])]
    for brief in all_briefs:
        prefs = brief.get("generation_prefs") or {}
        composition = brief.get("composition") or {}
        tasks.append(
            ImageTask(
                image_id=clean_text(brief["image_id"]),
                role=clean_text(brief["role"]),
                prompt=build_prompt(global_rules, brief),
                image_input=dedupe(list(brief.get("reference_image_urls") or [])),
                aspect_ratio=map_aspect_ratio(
                    clean_text(prefs.get("aspect_ratio") or composition.get("aspect_ratio") or "auto")
                ),
                resolution=clean_text(prefs.get("resolution") or "1K") or "1K",
                output_format=ext_for_format(clean_text(prefs.get("output_format") or "png") or "png"),
            )
        )
    return tasks


def http_json(method: str, url: str, *, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "growth-engine-pipeline/1.0",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        curl_bin = shutil.which("curl")
        if not curl_bin:
            raise RuntimeError(f"Request failed for {url}: {exc}") from exc
        command = [
            curl_bin,
            "-sS",
            "-X",
            method,
            "-H",
            f"Authorization: Bearer {token}",
            "-H",
            "User-Agent: growth-engine-pipeline/1.0",
            "-H",
            "Accept: application/json",
        ]
        if payload is not None:
            command.extend(
                [
                    "-H",
                    "Content-Type: application/json",
                    "--data",
                    json.dumps(payload, ensure_ascii=False),
                ]
            )
        command.append(url)
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"Request failed for {url}: {exc}; curl fallback failed: {stderr}") from exc
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as json_exc:
            raise RuntimeError(
                f"Request failed for {url}: {exc}; curl fallback returned non-JSON: {completed.stdout[:500]}"
            ) from json_exc


def submit_task(*, api_base_url: str, token: str, model: str, task: ImageTask, callback_url: str | None) -> dict[str, Any]:
    payload = {
        "model": model,
        "input": {
            "prompt": task.prompt,
            "image_input": task.image_input,
            "aspect_ratio": task.aspect_ratio,
            "resolution": task.resolution,
            "output_format": task.output_format,
        },
    }
    if callback_url:
        payload["callBackUrl"] = callback_url
    return http_json("POST", f"{api_base_url}/api/v1/jobs/createTask", token=token, payload=payload)


def get_task_record(*, api_base_url: str, token: str, task_id: str) -> dict[str, Any]:
    query = urlencode({"taskId": task_id})
    return http_json("GET", f"{api_base_url}/api/v1/jobs/recordInfo?{query}", token=token)


def extract_result_urls(task_record: dict[str, Any]) -> list[str]:
    data = task_record.get("data") or {}
    result_json = data.get("resultJson")
    if isinstance(result_json, str) and result_json.strip():
        try:
            parsed = json.loads(result_json)
        except json.JSONDecodeError:
            parsed = {}
    elif isinstance(result_json, dict):
        parsed = result_json
    else:
        parsed = {}

    urls: list[str] = []
    if isinstance(parsed, dict):
        for key in ["resultUrls", "result_urls", "urls"]:
            values = parsed.get(key)
            if isinstance(values, list):
                urls.extend(str(value).strip() for value in values if str(value).strip())
        for key in ["resultUrl", "result_url", "url"]:
            value = parsed.get(key)
            if value:
                urls.append(str(value).strip())
    return dedupe(urls)


def download_file(url: str, dest: Path) -> None:
    request = Request(
        url,
        method="GET",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=120) as response:
            dest.write_bytes(response.read())
        return
    except Exception as primary_error:
        curl_bin = shutil.which("curl")
        if not curl_bin:
            raise RuntimeError(f"Primary download failed and curl is unavailable: {primary_error}") from primary_error
        result = subprocess.run(
            [curl_bin, "-L", "-o", str(dest), url],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Primary download failed ({primary_error}); curl fallback failed: {stderr}"
            ) from primary_error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", required=True, help="Path to ARTICLE_IMAGE_BRIEF JSON")
    parser.add_argument("--out-dir", required=True, help="Directory to store request, task, and downloaded image files")
    parser.add_argument("--api-key-env", default="KIE_API_KEY", help="Environment variable containing the KIE API key")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--callback-url", default="")
    parser.add_argument("--wait", action="store_true", help="Poll until each task completes")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run_generation(
    *,
    payload: dict[str, Any],
    out_dir: Path,
    model: str,
    api_base_url: str,
    callback_url: str,
    token: str,
    wait: bool,
    timeout_seconds: int,
    poll_interval: float,
    dry_run: bool,
    brief_path: str,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tasks = build_tasks(payload)

    request_manifest = {
        "brief_path": brief_path,
        "model": model,
        "task_count": len(tasks),
        "tasks": [
            {
                "image_id": task.image_id,
                "role": task.role,
                "aspect_ratio": task.aspect_ratio,
                "resolution": task.resolution,
                "output_format": task.output_format,
                "image_input_count": len(task.image_input),
                "prompt": task.prompt,
            }
            for task in tasks
        ],
    }
    dump_json(out_dir / "request_manifest.json", request_manifest)

    if dry_run:
        manifest = {
            "brief_path": brief_path,
            "model": model,
            "jobs": [],
            "dry_run": True,
        }
        dump_json(out_dir / "generation_manifest.json", manifest)
        return manifest

    manifest: dict[str, Any] = {
        "brief_path": brief_path,
        "model": model,
        "jobs": [],
    }

    for task in tasks:
        job_dir = out_dir / task.image_id
        job_dir.mkdir(parents=True, exist_ok=True)
        submit_response = submit_task(
            api_base_url=api_base_url,
            token=token,
            model=model,
            task=task,
            callback_url=clean_text(callback_url) or None,
        )
        dump_json(job_dir / "submit_response.json", submit_response)

        task_id = str(((submit_response.get("data") or {}).get("taskId")) or "").strip()
        job_entry: dict[str, Any] = {
            "image_id": task.image_id,
            "role": task.role,
            "task_id": task_id,
            "state": "submitted",
        }

        if not wait or not task_id:
            manifest["jobs"].append(job_entry)
            continue

        start = time.time()
        latest_record: dict[str, Any] = {}
        while True:
            latest_record = get_task_record(api_base_url=api_base_url, token=token, task_id=task_id)
            dump_json(job_dir / "task_record.json", latest_record)
            state = str(((latest_record.get("data") or {}).get("state")) or "").strip()
            job_entry["state"] = state or "unknown"
            if state == "success":
                result_urls = extract_result_urls(latest_record)
                job_entry["result_urls"] = result_urls
                download_errors: list[dict[str, Any]] = []
                for index, url in enumerate(result_urls, start=1):
                    file_path = job_dir / f"result_{index}.{task.output_format}"
                    try:
                        download_file(url, file_path)
                    except Exception as exc:
                        download_errors.append(
                            {
                                "url": url,
                                "error": str(exc),
                            }
                        )
                if download_errors:
                    job_entry["download_errors"] = download_errors
                break
            if state == "fail":
                job_entry["fail_code"] = ((latest_record.get("data") or {}).get("failCode")) or ""
                job_entry["fail_msg"] = ((latest_record.get("data") or {}).get("failMsg")) or ""
                break
            if time.time() - start > timeout_seconds:
                job_entry["state"] = "timeout"
                break
            time.sleep(max(1.0, poll_interval))

        manifest["jobs"].append(job_entry)

    dump_json(out_dir / "generation_manifest.json", manifest)
    return manifest


def main() -> int:
    args = parse_args()
    brief_path = Path(args.brief).resolve()
    out_dir = Path(args.out_dir).resolve()
    payload = load_json(brief_path)

    token = ""
    if not args.dry_run:
        token = os.environ.get(args.api_key_env, "").strip()
        if not token:
            raise SystemExit(f"Missing API key. Set {args.api_key_env}.")

    manifest = run_generation(
        payload=payload,
        out_dir=out_dir,
        model=args.model,
        api_base_url=args.api_base_url,
        callback_url=args.callback_url,
        token=token,
        wait=args.wait,
        timeout_seconds=args.timeout_seconds,
        poll_interval=args.poll_interval,
        dry_run=args.dry_run,
        brief_path=str(brief_path),
    )
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": bool(args.dry_run),
                "jobs": len(manifest["jobs"]),
                "out_dir": str(out_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
