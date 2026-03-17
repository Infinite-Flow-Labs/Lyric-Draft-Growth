#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATE_ARG="${1:-$(date +%F)}"
ACCOUNT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Optional secret sources (priority: env > account-level > workspace-level)
if [[ -z "${KIE_API_KEY:-}" && -f "$SCRIPT_DIR/.kie.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.kie.env"
fi
if [[ -z "${KIE_API_KEY:-}" && -f "/root/.openclaw/agent-workspaces/growth-assistant/.kie.env" ]]; then
  # shellcheck disable=SC1091
  source "/root/.openclaw/agent-workspaces/growth-assistant/.kie.env"
fi

# 1) AI plan generation (day-level mix + topic picks)
/usr/bin/python3 generate_plan.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"

# 2) source/topic/content pipeline
/usr/bin/python3 daily_pipeline.py --config config.json --date "$DATE_ARG"

# 3) image generation (Kie) + asset binding
if [[ -z "${KIE_API_KEY:-}" ]]; then
  echo "[run_daily_pipeline] ERROR: KIE_API_KEY missing, image generation skipped" >&2
  exit 1
fi

KIE_SCRIPT="/root/.openclaw/agent-workspaces/growth-assistant/skills/apimart-image-gen/scripts/kie_image.py"
DAY_DIR="$ACCOUNT_ROOT/calendar/$DATE_ARG"
ASSET_DIR="$DAY_DIR/contents/assets"
mkdir -p "$ASSET_DIR"

for i in 1 2 3; do
  n=$(printf '%02d' "$i")
  article="$DAY_DIR/contents/post_${n}.md"
  outjson="$ASSET_DIR/post_${n}_kie.json"

  /usr/bin/python3 "$KIE_SCRIPT" \
    --article "$article" \
    --out "$outjson" \
    --aspect-ratio 16:9 \
    --resolution 2K \
    --output-format jpg \
    --wait 300 \
    --download-dir "$ASSET_DIR" \
    --filename-prefix "post_${n}_kie"

  first=$(/usr/bin/python3 - <<PY
import json
obj=json.load(open('$outjson','r',encoding='utf-8'))
arr=obj.get('downloaded_files') or []
print(arr[0] if arr else '')
PY
)

  if [[ -z "$first" || ! -f "$first" ]]; then
    echo "[run_daily_pipeline] ERROR: no image downloaded for post_${n}" >&2
    exit 1
  fi

  cp -f "$first" "$ASSET_DIR/post_${n}_1.jpg"
done

# 4) package for local publisher
/usr/bin/python3 publish_from_calendar.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"

echo "[run_daily_pipeline] done: $ACCOUNT_ROOT $DATE_ARG"
