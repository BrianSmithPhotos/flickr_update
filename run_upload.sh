#!/bin/bash
# Cron entry point: upload one paced batch, then self-remove from crontab
# once the queue is empty.
set -euo pipefail
cd "$(dirname "$0")"

set -a
source .env
set +a

OUTPUT=$(uv run python main.py samples --limit 1 2>&1)
echo "$(date '+%Y-%m-%d %H:%M:%S') $OUTPUT" >> cron.log

if echo "$OUTPUT" | grep -q "Nothing to upload"; then
    crontab -l | grep -v "run_upload.sh" | crontab -
    echo "$(date '+%Y-%m-%d %H:%M:%S') Queue empty, removed cron entry" >> cron.log
fi
