"""Asset synchronization for Pagecraft builds."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_assets(project_root: str, assets_dir: str, output_dir: str, previous: dict[str, str] | None = None) -> dict[str, list[str] | dict[str, str]]:
    """Mirror project assets into output while retaining a safe source manifest.

    Assets are deliberately copied at the output root to preserve v0.1 behavior.
    ``previous`` maps relative output paths to source hashes and allows files that
    disappeared from ``assets/`` to be removed on the next build.
    """
    source = Path(project_root) / assets_dir
    destination = Path(output_dir)
    previous = previous or {}
    current: dict[str, str] = {}
    copied: list[str] = []
    skipped: list[str] = []

    if source.is_dir():
        for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
            relative = source_file.relative_to(source).as_posix()
            digest = _hash(source_file)
            current[relative] = digest
            destination_file = destination / relative
            if previous.get(relative) == digest and destination_file.exists():
                skipped.append(str(destination_file))
                continue
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)
            copied.append(str(destination_file))

    removed: list[str] = []
    for relative in sorted(set(previous) - set(current)):
        stale = destination / relative
        if stale.is_file():
            stale.unlink()
            removed.append(str(stale))
        # Prune only empty parents underneath the output directory.
        parent = stale.parent
        while parent != destination and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent

    return {"hashes": current, "copied": copied, "skipped": skipped, "removed": removed}


# Backwards-compatible public helper retained for v0.1 callers.
def copy_assets(project_root: str, assets_dir: str, output_dir: str) -> list[str]:
    return list(sync_assets(project_root, assets_dir, output_dir).get("copied", []))
