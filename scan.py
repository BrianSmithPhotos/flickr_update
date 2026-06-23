"""Directory scanning for candidate images."""

from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}


def find_images(directory: Path) -> list[Path]:
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def select_pending(images: list[Path], state: dict, limit: int) -> list[Path]:
    from state import is_uploaded

    pending = [p for p in images if not is_uploaded(state, p)]
    return pending[:limit]
