"""JSON manifest of upload state, keyed by filename.

Filenames are the primary key, but they are NOT reliably stable: a photo may be
renamed in Finder after export (e.g. to add a location token) without changing
its bytes. So each entry also stores a SHA-256 of the file's contents, and a
content match is treated as "already handled" even when the filename differs.
This prevents a pure rename from being re-uploaded as a duplicate, while still
letting genuinely different files that share a leading sequence number (e.g. the
straight-from-ORF JPG and a separate edit/crop) upload as distinct photos.
"""

import hashlib
import json
from pathlib import Path

MANIFEST_PATH = Path("upload_state.json")


def load(manifest_path: Path = MANIFEST_PATH) -> dict:
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def save(state: dict, manifest_path: Path = MANIFEST_PATH) -> None:
    manifest_path.write_text(json.dumps(state, indent=2, sort_keys=True))


def file_hash(file_path: Path) -> str:
    """SHA-256 of the file's bytes, streamed so large images don't load fully.

    Callers must confirm the file is materialized (not a dataless placeholder)
    before calling — reading an online-only file can hang indefinitely.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mark_uploaded(state: dict, file_path: Path, photo_id: str, digest: str | None = None) -> None:
    state[file_path.name] = {"photo_id": photo_id, "status": "uploaded", "hash": digest}


def mark_baseline(state: dict, file_path: Path, digest: str | None = None) -> None:
    """Mark a file as not eligible for upload (no photo_id).

    Used both for pre-existing files and for rename-duplicates of photos that
    are already on Flickr.
    """
    state[file_path.name] = {"photo_id": None, "status": "baseline", "hash": digest}


def is_uploaded(state: dict, file_path: Path) -> bool:
    """True if this filename is already handled (uploaded or baselined)."""
    return state.get(file_path.name, {}).get("status") in ("uploaded", "baseline")


def known_hashes(state: dict) -> dict:
    """Map of content-hash -> the filename it was first recorded under, for
    detecting renamed duplicates by content."""
    return {v["hash"]: name for name, v in state.items() if v.get("hash")}
