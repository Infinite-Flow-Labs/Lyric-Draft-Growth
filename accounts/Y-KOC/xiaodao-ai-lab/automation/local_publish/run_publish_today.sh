#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/config.env"

DATE="${1:-$(date +%F)}"
DRY_RUN="${2:-1}"   # 1=dry-run, 0=real

# 1) sync from cloud first
"$DIR/sync_publish_ready.sh" "$DATE"

cd "$LOCAL_AUTOMATION_DIR"

SLOTS=("08:30" "12:00" "19:30")
for i in 1 2 3; do
  SLOT_DIR="./publish_ready/$DATE/slot_0${i}"
  [ -f "$SLOT_DIR/post.txt" ] || { echo "[skip] missing $SLOT_DIR/post.txt"; continue; }
  [ -f "$SLOT_DIR/post.jpg" ] || { echo "[skip] missing $SLOT_DIR/post.jpg"; continue; }

  t="${SLOTS[$((i-1))]}"
  cmd=(python3 -m x_schedule_post.cli
    --dir "$SLOT_DIR"
    --time "$DATE $t"
    --timezone "$TIMEZONE"
    --accounts-csv "./publish_tool/accounts_bitbrowser.csv"
    --account "$BIT_ACCOUNT")

  if [ "$DRY_RUN" = "1" ]; then
    cmd+=(--dry-run)
  fi

  echo "[run] slot_0${i} @ $DATE $t dry_run=$DRY_RUN"
  PYTHONPATH=./publish_tool "${cmd[@]}"

done
