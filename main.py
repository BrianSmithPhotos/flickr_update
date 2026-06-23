import argparse
import sys
from pathlib import Path

from flickrapi.exceptions import FlickrError

import scan
import state
import upload

# Stop conditions: error 6 (bandwidth limit), error 98 (bad/expired token).
# Anything else is treated as transient and just skipped for this run.
STOP_CODES = {6, 98}


def main():
    parser = argparse.ArgumentParser(description="Upload a batch of images to Flickr.")
    parser.add_argument("directory", type=Path, help="Directory of images to scan")
    parser.add_argument("--limit", type=int, default=3, help="Max photos to upload this run")
    args = parser.parse_args()

    manifest = state.load()
    images = scan.find_images(args.directory)
    pending = scan.select_pending(images, manifest, args.limit)

    if not pending:
        print("Nothing to upload.")
        return

    flickr = upload.get_client()

    for file_path in pending:
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


if __name__ == "__main__":
    main()
