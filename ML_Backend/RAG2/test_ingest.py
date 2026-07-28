"""Completely rebuild the persistent RAG2 index and print its summary."""

import logging

try:
    from .config import LOG_FORMAT, LOG_LEVEL
    from .ingest import rebuild_index
except ImportError:  # Supports ``python test_ingest.py`` from this directory.
    from config import LOG_FORMAT, LOG_LEVEL
    from ingest import rebuild_index


def main() -> None:
    """Rebuild from scratch and print the required index counts."""
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    result = rebuild_index()
    print(f"Books indexed: {result.books_indexed}")
    print(f"Chunks indexed: {result.chunks_indexed}")
    print(f"Chunks deleted: {result.chunks_deleted}")
    print(f"Chunks skipped: {result.chunks_skipped}")
    print(f"Total vectors: {result.total_vectors}")


if __name__ == "__main__":
    main()
