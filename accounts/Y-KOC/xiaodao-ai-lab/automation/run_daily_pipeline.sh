#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATE_ARG="${1:-$(date +%F)}"
ACCOUNT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DAY_DIR="$ACCOUNT_ROOT/calendar/$DATE_ARG"

# Optional secret sources (priority: env > account-level > workspace-level)
if [[ -z "${KIE_API_KEY:-}" && -f "$SCRIPT_DIR/.kie.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.kie.env"
fi
if [[ -z "${KIE_API_KEY:-}" && -f "/root/.openclaw/agent-workspaces/growth-assistant/.kie.env" ]]; then
  # shellcheck disable=SC1091
  source "/root/.openclaw/agent-workspaces/growth-assistant/.kie.env"
fi

# 1) Post plan generation (day-level mix + topic picks)
/usr/bin/python3 generate_plan.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"

# 2) Post source/topic/content pipeline
/usr/bin/python3 daily_pipeline.py --config config.json --date "$DATE_ARG"

# 3) Post image generation (Kie) + asset binding
if [[ -z "${KIE_API_KEY:-}" ]]; then
  echo "[run_daily_pipeline] ERROR: KIE_API_KEY missing, image generation skipped" >&2
  exit 1
fi

KIE_SCRIPT="/root/.openclaw/agent-workspaces/growth-assistant/skills/apimart-image-gen/scripts/kie_image.py"
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

# 4) A-article chain (hot signals -> plan -> article)
HOT_SIGNAL_SCRIPT="/root/.openclaw/agent-workspaces/growth-assistant/accounts/Y-KOC/_shared/corpus/A_opportunity_replacement/scripts/build_hot_signals.py"
HOT_SIGNAL_OUT="$DAY_DIR/hot_signals.json"

/usr/bin/python3 "$HOT_SIGNAL_SCRIPT" --out "$HOT_SIGNAL_OUT" --days 7 --limit 20
/usr/bin/python3 generate_a_article_plan.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"
/usr/bin/python3 article_pipeline_a.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"

# 5) interview/transcript chain (optional)
# Usage: INTERVIEW_SOURCE=/abs/path/to/transcript.txt ./run_daily_pipeline.sh 2026-03-17
if [[ -n "${INTERVIEW_SOURCE:-}" ]]; then
  /usr/bin/python3 transcript_pipeline.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG" --input "$INTERVIEW_SOURCE"
  /usr/bin/python3 interview_rewrite.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"
  /usr/bin/python3 quote_extractor.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG"
fi

# 6) migrate calendar layout to unified dirs (sources + publish)
/usr/bin/python3 migrate_calendar_layout.py --account-root "$ACCOUNT_ROOT" --delete-legacy

# 7) package for local publisher (post + article + interview)
/usr/bin/python3 publish_from_calendar.py --account-root "$ACCOUNT_ROOT" --date "$DATE_ARG" --with-article

echo "[run_daily_pipeline] done: $ACCOUNT_ROOT $DATE_ARG (post + article + interview-optional)"
