#!/bin/bash
# Cron entry point: upload one paced batch of new photos.
set -uo pipefail
cd "$(dirname "$0")"

set -a
source .env
set +a

PHOTOS_DIR="/Users/bsmi067/OneDrive - Brian Smith Photos/Photos2026"

OUTPUT=$(/Users/bsmi067/.local/bin/uv run python main.py "$PHOTOS_DIR" --limit 3 2>&1)
STATUS=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') $OUTPUT" >> cron.log
exit $STATUS
