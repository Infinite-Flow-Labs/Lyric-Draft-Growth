#!/usr/bin/env bash
set -euo pipefail

ACC_ROOT="/root/.openclaw/agent-workspaces/growth-assistant/accounts/Y-KOC/xiaodao-ai-lab"
WEEKLY_DIR="$ACC_ROOT/weekly_plan"
SCRIPT="$ACC_ROOT/automation/generate_weekly_plan.py"

mkdir -p "$WEEKLY_DIR"

# Next Monday (Asia/Shanghai context expected from cron CRON_TZ)
START_DATE=$(date -d 'next monday' +%F)

# find next week index
MAX_IDX=$(find "$WEEKLY_DIR" -maxdepth 1 -type f -name 'week-*.md' \
  | sed -E 's#.*week-([0-9]+)\.md#\1#' \
  | sort -n | tail -n1)

if [[ -z "${MAX_IDX:-}" ]]; then
  NEXT_IDX=1
else
  NEXT_IDX=$((10#$MAX_IDX + 1))
fi

WEEK_TAG=$(printf 'week-%02d' "$NEXT_IDX")
OUT_MD="$WEEKLY_DIR/$WEEK_TAG.md"

python3 "$SCRIPT" \
  --account-root "$ACC_ROOT" \
  --start-date "$START_DATE" \
  --days 7 \
  --out "$OUT_MD"

echo "[weekly_plan] generated: $OUT_MD"
