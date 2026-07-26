#!/bin/bash
# Cron entry point: upload one paced batch of new photos.
set -uo pipefail
cd "$(dirname "$0")"

set -a
source .env
set +a

# PHOTOS_DIR comes from .env (gitignored) rather than being hardcoded here:
# the path embeds the local username and the Google account name, and this
# repo is public.
#
# Both failures below are silent-killers — uploads would just stop, or the scan
# would find nothing and cheerfully report "Nothing to upload." forever — so
# they get the same log line and desktop notification as a runtime failure.
fail() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> cron.log
    /usr/bin/osascript -e "display notification \"${1//\"/\\\"}\" with title \"Flickr upload misconfigured\"" >/dev/null 2>&1
    exit 1
}
[ -n "${PHOTOS_DIR:-}" ] || fail "PHOTOS_DIR not set — add it to .env (see .env.example)"
[ -d "$PHOTOS_DIR" ] || fail "PHOTOS_DIR does not exist: $PHOTOS_DIR"

# Absolute path, not bare `uv`: launchd runs with a minimal PATH that doesn't
# include ~/.local/bin. $HOME rather than a literal home directory keeps the
# local username out of this public repo; under `set -u` an unset HOME errors
# loudly rather than silently invoking the wrong binary.
OUTPUT=$("$HOME/.local/bin/uv" run python main.py "$PHOTOS_DIR" --limit 3 2>&1)
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
