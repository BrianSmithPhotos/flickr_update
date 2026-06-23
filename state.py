"""JSON manifest of upload state, keyed by filename.

Filenames are unique and stable (sequential camera-assigned numbers), so
keying by name rather than full path lets the same photo be recognized
as already-uploaded regardless of which directory it's scanned from.
"""

import json
from pathlib import Path

MANIFEST_PATH = Path("upload_state.json")


def load(manifest_path: Path = MANIFEST_PATH) -> dict:
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text())


def save(state: dict, manifest_path: Path = MANIFEST_PATH) -> None:
    manifest_path.write_text(json.dumps(state, indent=2, sort_keys=True))


def mark_uploaded(state: dict, file_path: Path, photo_id: str) -> None:
    state[file_path.name] = {"photo_id": photo_id, "status": "uploaded"}


def mark_baseline(state: dict, file_path: Path) -> None:
    """Mark a pre-existing file as not eligible for upload (no photo_id)."""
    state[file_path.name] = {"photo_id": None, "status": "baseline"}


def is_uploaded(state: dict, file_path: Path) -> bool:
    return state.get(file_path.name, {}).get("status") in ("uploaded", "baseline")
