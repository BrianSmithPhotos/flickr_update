import argparse
import signal
import sys
from pathlib import Path

from flickrapi.exceptions import FlickrError

import scan
import state
import upload

# Stop conditions: error 6 (bandwidth limit), error 98 (bad/expired token).
# Anything else is treated as transient and just skipped for this run.
STOP_CODES = {6, 98}

# Watchdog: a single run must never last longer than this. It exists to keep a
# hung OneDrive read (online-only file that never finishes hydrating) from
# wedging the process forever and, via launchd's no-overlap rule, silently
# suppressing every subsequent scheduled run.
DEFAULT_TIMEOUT = 300  # seconds

# Exit code used for OneDrive/sync anomalies so run_upload.sh can alert on them.
ANOMALY_EXIT = 2


class RunTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise RunTimeout


def run(args) -> None:
    manifest = state.load()

    try:
        images = scan.find_images(args.directory)
    except OSError as e:
        # e.g. [Errno 11] Resource deadlock avoided: a folder under the tree is
        # a OneDrive placeholder that can't be enumerated. Fail loud, not silent.
        print(
            f"ANOMALY: cannot scan {args.directory}: {e}. "
            f"A OneDrive folder may be dehydrated/offline; expected it to be "
            f"fully synced locally."
        )
        sys.exit(ANOMALY_EXIT)

    pending = scan.select_pending(images, manifest, args.limit)

    if not pending:
        print("Nothing to upload.")
        return

    flickr = upload.get_client()

    for file_path in pending:
        if upload.is_dataless(file_path):
            # Don't open it — reading an online-only placeholder can hang for
            # hours. This tree is supposed to be fully local, so treat it as an
            # anomaly worth surfacing rather than silently skipping the photo.
            print(
                f"ANOMALY: {file_path} is online-only (not synced locally); "
                f"OneDrive may have dehydrated Photos2026. Refusing to read it."
            )
            sys.exit(ANOMALY_EXIT)

        try:
            photo_id = upload.upload_photo(flickr, file_path)
        except FlickrError as e:
            if e.code in STOP_CODES:
                print(f"Stopping: {e}")
                sys.exit(1)
            print(f"Skipping {file_path} (transient error: {e})")
            continue

        state.mark_uploaded(manifest, file_path, photo_id)
        state.save(manifest)
        print(f"Uploaded {file_path} -> {photo_id}")


def main():
    parser = argparse.ArgumentParser(description="Upload a batch of images to Flickr.")
    parser.add_argument("directory", type=Path, help="Directory of images to scan")
    parser.add_argument("--limit", type=int, default=3, help="Max photos to upload this run")
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Abort the run after this many seconds (hang watchdog)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(args.timeout)
    try:
        run(args)
    except RunTimeout:
        print(
            f"ANOMALY: run exceeded {args.timeout}s and was aborted. A OneDrive "
            f"read likely hung; check that Photos2026 is fully synced locally."
        )
        sys.exit(ANOMALY_EXIT)
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
