"""JSON manifest of upload state, keyed by file path."""

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
    state[str(file_path.resolve())] = {"photo_id": photo_id, "status": "uploaded"}


def is_uploaded(state: dict, file_path: Path) -> bool:
    return state.get(str(file_path.resolve()), {}).get("status") == "uploaded"
