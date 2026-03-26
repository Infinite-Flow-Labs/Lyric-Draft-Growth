#!/bin/bash
# Growth Engine Cron Setup
#
# Install: crontab -e, then add the lines below
# Logs: runtime/runs/cron_*.log

ROOT="/home/lyric/growth-engine-pipeline"

# ── Every 4 hours: ingest + topic engine (no writer, just refresh topics) ──
# 0 */4 * * * cd $ROOT && ./run_pipeline.sh --source-dirs "" --run-ingest --skip-review --skip-images --skip-publish >> runtime/runs/cron_ingest.log 2>&1

# ── Every 12 hours: full pipeline with auto-select ──
# 0 8,20 * * * cd $ROOT && ./run_pipeline.sh --source-dirs "runtime/runs/latest/00_ingest/x/items" --skip-review --dry-run >> runtime/runs/cron_full.log 2>&1

# ── Manual: with human review ──
# cd $ROOT && ./run_pipeline.sh --source-dirs "runtime/runs/latest/00_ingest/x/items"
