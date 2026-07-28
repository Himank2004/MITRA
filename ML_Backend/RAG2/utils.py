"""Small, shared utilities for the document-loading layer."""

from pathlib import Path
import hashlib

try:
    from .config import FILE_HASH_ALGORITHM, FILE_HASH_READ_SIZE
except ImportError:  # Supports ``python test_loader.py`` from this directory.
    from config import FILE_HASH_ALGORITHM, FILE_HASH_READ_SIZE


def hash_file(file_path: Path) -> str:
    """Return a deterministic hash for ``file_path`` without loading it all at once."""
    digest = hashlib.new(FILE_HASH_ALGORITHM)
    with file_path.open("rb") as source_file:
        while chunk := source_file.read(FILE_HASH_READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
