"""Read and atomically write the RAG2 index manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .config import MANIFEST_JSON_INDENT, MANIFEST_PATH, MANIFEST_VERSION
except ImportError:  # Supports direct execution from the RAG2 directory.
    from config import MANIFEST_JSON_INDENT, MANIFEST_PATH, MANIFEST_VERSION


def empty_manifest() -> dict[str, Any]:
    """Return the base manifest structure."""
    return {"version": MANIFEST_VERSION, "documents": {}}


def load_manifest(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Load a manifest, treating a missing or invalid file as empty."""
    if not manifest_path.is_file():
        return empty_manifest()
    try:
        with manifest_path.open(encoding="utf-8") as manifest_file:
            manifest = json.load(manifest_file)
    except (OSError, json.JSONDecodeError):
        return empty_manifest()
    if manifest.get("version") != MANIFEST_VERSION or not isinstance(manifest.get("documents"), dict):
        return empty_manifest()
    return manifest


def save_manifest(manifest: dict[str, Any], manifest_path: Path = MANIFEST_PATH) -> None:
    """Atomically persist a manifest so interrupted writes cannot corrupt it."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(f"{manifest_path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=False, indent=MANIFEST_JSON_INDENT)
        manifest_file.write("\n")
    temporary_path.replace(manifest_path)
