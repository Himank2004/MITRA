"""Recursive, fault-tolerant loading of PDF and EPUB books into Documents."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub
from langchain_core.documents import Document
from pypdf import PdfReader

try:
    from .config import (
        BOOKS_DIR,
        EPUB_FILE_EXTENSION,
        EPUB_FILE_TYPE,
        HTML_PARSER,
        PDF_FILE_EXTENSION,
        PDF_FILE_TYPE,
        SUPPORTED_FILE_EXTENSIONS,
    )
    from .utils import hash_file
except ImportError:  # Supports ``python test_loader.py`` from this directory.
    from config import (
        BOOKS_DIR,
        EPUB_FILE_EXTENSION,
        EPUB_FILE_TYPE,
        HTML_PARSER,
        PDF_FILE_EXTENSION,
        PDF_FILE_TYPE,
        SUPPORTED_FILE_EXTENSIONS,
    )
    from utils import hash_file


LOGGER = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """Loaded documents and a concise accounting of the loading run."""

    documents: list[Document] = field(default_factory=list)
    total_books: int = 0
    pages_loaded: int = 0
    chapters_loaded: int = 0
    extraction_failures: int = 0


def discover_books(books_dir: Path = BOOKS_DIR) -> list[Path]:
    """Return supported books below ``books_dir``, ordered deterministically."""
    if not books_dir.is_dir():
        LOGGER.error("Books directory does not exist or is not a directory: %s", books_dir)
        return []

    return sorted(
        (
            path
            for path in books_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_FILE_EXTENSIONS
        ),
        key=lambda path: str(path).lower(),
    )


def load_books(books_dir: Path = BOOKS_DIR) -> LoadResult:
    """Load every supported book, logging failed extractions and continuing."""
    result = LoadResult()
    for book_path in discover_books(books_dir):
        _merge_results(result, load_book(book_path))
    return result


def load_book(book_path: Path, file_hash: str | None = None) -> LoadResult:
    """Load one supported book and return its Documents and extraction counts."""
    result = LoadResult(total_books=1)
    try:
        resolved_hash = file_hash or hash_file(book_path)
        if book_path.suffix.lower() == PDF_FILE_EXTENSION:
            _load_pdf(book_path, resolved_hash, result)
        elif book_path.suffix.lower() == EPUB_FILE_EXTENSION:
            _load_epub(book_path, resolved_hash, result)
    except Exception:
        result.extraction_failures += 1
        LOGGER.exception("Failed to load book: %s", book_path)
    return result


def _merge_results(destination: LoadResult, source: LoadResult) -> None:
    """Append one loading result to an aggregate result."""
    destination.documents.extend(source.documents)
    destination.total_books += source.total_books
    destination.pages_loaded += source.pages_loaded
    destination.chapters_loaded += source.chapters_loaded
    destination.extraction_failures += source.extraction_failures


def _base_metadata(book_path: Path, file_hash: str, file_type: str) -> dict[str, str]:
    """Create metadata shared by all extracted units from a book."""
    return {
        "source": str(book_path.resolve()),
        "filename": book_path.name,
        "file_type": file_type,
        "document_id": file_hash,
        "file_hash": file_hash,
    }


def _load_pdf(book_path: Path, file_hash: str, result: LoadResult) -> None:
    """Create exactly one Document for each PDF page."""
    reader = PdfReader(book_path)
    base_metadata = _base_metadata(book_path, file_hash, PDF_FILE_TYPE)
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            result.documents.append(
                Document(
                    page_content=page.extract_text() or "",
                    metadata={**base_metadata, "page_number": page_number},
                )
            )
            result.pages_loaded += 1
        except Exception:
            result.extraction_failures += 1
            LOGGER.exception("Failed to extract page %d from %s", page_number, book_path)


def _load_epub(book_path: Path, file_hash: str, result: LoadResult) -> None:
    """Create exactly one Document for each EPUB chapter in its spine."""
    book = epub.read_epub(str(book_path))
    base_metadata = _base_metadata(book_path, file_hash, EPUB_FILE_TYPE)
    for chapter_number, item in enumerate(_spine_documents(book), start=1):
        try:
            chapter_text = BeautifulSoup(item.get_content(), HTML_PARSER).get_text(" ", strip=True)
            result.documents.append(
                Document(
                    page_content=chapter_text,
                    metadata={**base_metadata, "chapter": chapter_number},
                )
            )
            result.chapters_loaded += 1
        except Exception:
            result.extraction_failures += 1
            LOGGER.exception("Failed to extract chapter %d from %s", chapter_number, book_path)


def _spine_documents(book: epub.EpubBook) -> list[object]:
    """Return reading-order document items, with a safe EPUB fallback."""
    spine_items = [
        book.get_item_with_id(item_id)
        for item_id, _linear in book.spine
    ]
    documents = [item for item in spine_items if item is not None and item.get_type() == ITEM_DOCUMENT]
    if documents:
        return documents
    return list(book.get_items_of_type(ITEM_DOCUMENT))
