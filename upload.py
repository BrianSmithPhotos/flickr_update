"""Flickr client setup and single-photo upload."""

import os
from pathlib import Path

import flickrapi


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
