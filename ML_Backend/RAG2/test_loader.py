"""Run the document loader and print a concise extraction report."""

import logging

try:
    from .config import LOG_FORMAT, LOG_LEVEL
    from .loaders import load_books
except ImportError:  # Supports ``python test_loader.py`` from this directory.
    from config import LOG_FORMAT, LOG_LEVEL
    from loaders import load_books


def main() -> None:
    """Load the configured books directory and print required summary counts."""
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    result = load_books()
    print(f"total books: {result.total_books}")
    print(f"pages loaded: {result.pages_loaded}")
    print(f"chapters loaded: {result.chapters_loaded}")
    print(f"extraction failures: {result.extraction_failures}")


if __name__ == "__main__":
    main()
