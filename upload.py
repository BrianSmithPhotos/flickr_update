"""Flickr client setup and single-photo upload."""

import os
from pathlib import Path

import flickrapi

# Bound every HTTP request (token check and upload alike). flickrapi defaults to
# timeout=None, which makes requests block forever: on 2026-08-31 a flaky home
# network stalled an upload POST for the full 300s run watchdog. This is a
# requests timeout, so it caps the wait for a single read, not the whole
# transfer - a healthy multi-megabyte upload keeps resetting it.
REQUEST_TIMEOUT = 60  # seconds

# macOS st_flags bit set on online-only placeholders (Google Drive, OneDrive,
# iCloud - all macOS File Provider) whose bytes are not present locally.
# stat() reads this without hydrating; open()/read() would block on hydration
# and can hang indefinitely.
UF_DATALESS = 0x40000000


def is_dataless(file_path: Path) -> bool:
    """True if the file is an online-only placeholder not materialized locally.

    Reading such a file blocks on cloud-sync hydration and has been observed to
    hang for hours, so callers must refuse to upload it rather than open it.
    stat() itself is safe: it returns the flag without triggering a download.
    """
    try:
        return bool(os.stat(file_path).st_flags & UF_DATALESS)
    except OSError:
        # If we can't even stat it, let the normal upload path surface the error.
        return False


def get_client() -> flickrapi.FlickrAPI:
    api_key = os.environ["FLICKR_API_KEY"]
    api_secret = os.environ["FLICKR_API_SECRET"]
    flickr = flickrapi.FlickrAPI(
        api_key, api_secret, format="parsed-json", timeout=REQUEST_TIMEOUT
    )

    if not flickr.token_valid(perms="write"):
        raise RuntimeError(
            "Flickr OAuth token is missing or expired. "
            "Run 'python auth.py' in the project directory to re-authorize."
        )

    return flickr


def upload_photo(flickr: flickrapi.FlickrAPI, file_path: Path) -> str:
    response = flickr.upload(filename=str(file_path), is_public=1, format="etree")
    return response.find("photoid").text
