#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/config.env"

DATE="${1:-$(date +%F)}"
REMOTE_DIR="$REMOTE_ACCOUNT_ROOT/automation/publish_ready/$DATE/"
LOCAL_DIR="$LOCAL_AUTOMATION_DIR/publish_ready/$DATE/"

mkdir -p "$LOCAL_DIR"
rsync -avz --delete -e "ssh -p ${CLOUD_PORT}" "${CLOUD_USER}@${CLOUD_HOST}:${REMOTE_DIR}" "$LOCAL_DIR"

echo "[ok] synced publish_ready => $LOCAL_DIR"
