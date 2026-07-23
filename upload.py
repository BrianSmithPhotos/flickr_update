"""Flickr client setup and single-photo upload."""

import os
from pathlib import Path

import flickrapi

# macOS st_flags bit set on online-only placeholders (OneDrive/iCloud Files
# On-Demand) whose bytes are not present locally. stat() reads this without
# hydrating; open()/read() would block on hydration and can hang indefinitely.
UF_DATALESS = 0x40000000


def is_dataless(file_path: Path) -> bool:
    """True if the file is an online-only placeholder not materialized locally.

    Reading such a file blocks on OneDrive hydration and has been observed to
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
    flickr = flickrapi.FlickrAPI(api_key, api_secret, format="parsed-json")

    if not flickr.token_valid(perms="write"):
        raise RuntimeError(
            "Flickr OAuth token is missing or expired. "
            "Run 'python auth.py' in the project directory to re-authorize."
        )

    return flickr


def upload_photo(flickr: flickrapi.FlickrAPI, file_path: Path) -> str:
    response = flickr.upload(filename=str(file_path), is_public=1, format="etree")
    return response.find("photoid").text
