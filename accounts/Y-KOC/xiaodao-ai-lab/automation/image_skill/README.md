# image_skill (apimart)

Generate cover images from article markdown using apimart image API.

## Setup

```bash
cd /root/.openclaw/agent-workspaces/growth-assistant/inbound_assets/xiaodao_benchmark_sources/accounts/xiaodao-ai-lab/automation/image_skill
```

Set API key via environment variable (do not hardcode in files):

```bash
export APIMART_API_KEY='YOUR_KEY'
```

## Run

```bash
python3 apimart_image.py \
  --article ../content/2026-03-09/post_01_2026-03-09.md \
  --out ../content/2026-03-09/images/post_01_result.json \
  --size 16:9 \
  --resolution 2K \
  --n 1
```

Output JSON includes:
- task_id
- prompt
- raw result payload
- extracted image_urls[]

## Notes
- API appears asynchronous (returns task_id first).
- Script tries common result endpoints automatically.
- If provider endpoint shape changes, update `poll_task()` and `extract_image_urls()`.
