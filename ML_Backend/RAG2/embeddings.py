"""Access to MITRA's process-wide shared embedding model."""

from __future__ import annotations

import sys

try:
    from .config import ML_BACKEND_DIR
except ImportError:  # Supports direct execution from the RAG2 directory.
    from config import ML_BACKEND_DIR


def get_shared_embeddings():
    """Return the existing shared model instead of creating a second instance."""
    backend_directory = str(ML_BACKEND_DIR)
    if backend_directory not in sys.path:
        sys.path.insert(0, backend_directory)
    from shared_embeddings import get_embeddings

    return get_embeddings()
