#!/bin/bash
# Setup x-schedule-post venv
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -e . 2>/dev/null || .venv/bin/pip install anyio httpx
echo "Setup complete. Use: $(pwd)/.venv/bin/python $(pwd)/x_schedule_post/cli.py"
