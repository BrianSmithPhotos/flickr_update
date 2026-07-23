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

# Surface any non-clean exit (anomaly, stop condition, crash) as a desktop
# notification. cron.log alone is silent — the OneDrive hang went unnoticed for
# hours precisely because nothing told us. The last output line is the reason.
if [ "$STATUS" -ne 0 ]; then
    MSG=$(printf '%s' "$OUTPUT" | tail -n 1)
    /usr/bin/osascript -e "display notification \"${MSG//\"/\\\"}\" with title \"Flickr upload failed (exit $STATUS)\"" >/dev/null 2>&1
fi

exit $STATUS
