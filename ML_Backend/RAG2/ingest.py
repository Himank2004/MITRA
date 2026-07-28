"""Manifest-synchronized Chroma indexing for cleaned and chunked books."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil

from langchain_chroma import Chroma

try:
    from .chunker import chunk_documents
    from .cleaners import clean_documents
    from .config import CHROMA_DIR, COLLECTION_NAME, INGEST_BATCH_SIZE, MANIFEST_PATH
    from .embeddings import get_shared_embeddings
    from .loaders import discover_books, load_book
    from .manifest import empty_manifest, load_manifest, save_manifest
    from .utils import hash_file
except ImportError:  # Supports direct execution from the RAG2 directory.
    from chunker import chunk_documents
    from cleaners import clean_documents
    from config import CHROMA_DIR, COLLECTION_NAME, INGEST_BATCH_SIZE, MANIFEST_PATH
    from embeddings import get_shared_embeddings
    from loaders import discover_books, load_book
    from manifest import empty_manifest, load_manifest, save_manifest
    from utils import hash_file


LOGGER = logging.getLogger(__name__)


@dataclass
class IndexResult:
    """Counters describing one exact-corpus synchronization run."""

    books_indexed: int = 0
    chunks_indexed: int = 0
    chunks_deleted: int = 0
    chunks_skipped: int = 0
    total_vectors: int = 0


def sync_index() -> IndexResult:
    """Synchronize Chroma exactly with the current books directory and manifest."""
    manifest = load_manifest()
    manifest_documents: dict[str, dict] = manifest["documents"]
    vector_store = _vector_store()
    result = IndexResult()

    current_books = {str(path.resolve()): path for path in discover_books()}
    for source, entry in list(manifest_documents.items()):
        if source not in current_books:
            result.chunks_deleted += _delete_ids(vector_store, entry.get("chunk_ids", []))
            del manifest_documents[source]

    total_books = len(current_books)
    for book_number, (source, book_path) in enumerate(current_books.items(), start=1):
        try:
            document_hash = hash_file(book_path)
        except OSError:
            LOGGER.exception("Unable to hash book: %s", book_path)
            continue

        previous_entry = manifest_documents.get(source)
        if previous_entry and previous_entry.get("document_hash") == document_hash:
            result.chunks_skipped += previous_entry.get("chunk_count", 0)
            LOGGER.info("Skipping unchanged book %d/%d: %s", book_number, total_books, book_path.name)
            continue

        if previous_entry:
            result.chunks_deleted += _delete_ids(vector_store, previous_entry.get("chunk_ids", []))

        LOGGER.info("Loading and indexing book %d/%d: %s", book_number, total_books, book_path.name)
        loaded = load_book(book_path, file_hash=document_hash)
        chunks = chunk_documents(clean_documents(loaded.documents)).documents
        chunk_ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
        _add_chunks(vector_store, chunks, chunk_ids)
        manifest_documents[source] = {
            "document_hash": document_hash,
            "chunk_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
        }
        result.books_indexed += 1
        result.chunks_indexed += len(chunk_ids)
        save_manifest(manifest)
        LOGGER.info(
            "Indexed %s: %d chunks (%d/%d books complete)",
            book_path.name,
            len(chunk_ids),
            book_number,
            total_books,
        )

    result.chunks_deleted += _delete_orphaned_vectors(vector_store, manifest_documents)
    save_manifest(manifest)
    result.total_vectors = vector_store._collection.count()
    return result


def rebuild_index() -> IndexResult:
    """Remove only the RAG2 index artifacts, then build a fresh complete index."""
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()
    save_manifest(empty_manifest())
    return sync_index()


def _vector_store() -> Chroma:
    """Open the persistent collection using the process-wide embedding instance."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_shared_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def _add_chunks(vector_store: Chroma, chunks: list, chunk_ids: list[str]) -> None:
    """Store chunks in configured batches, preserving all Document metadata."""
    for start in range(0, len(chunks), INGEST_BATCH_SIZE):
        stop = start + INGEST_BATCH_SIZE
        LOGGER.info(
            "Embedding chunks %d-%d of %d",
            start + 1,
            min(stop, len(chunks)),
            len(chunks),
        )
        vector_store.add_documents(chunks[start:stop], ids=chunk_ids[start:stop])


def _delete_ids(vector_store: Chroma, chunk_ids: list[str]) -> int:
    """Delete known chunk IDs in batches and return the requested deletion count."""
    for start in range(0, len(chunk_ids), INGEST_BATCH_SIZE):
        vector_store.delete(ids=chunk_ids[start : start + INGEST_BATCH_SIZE])
    return len(chunk_ids)


def _delete_orphaned_vectors(vector_store: Chroma, manifest_documents: dict[str, dict]) -> int:
    """Remove vectors not represented by the resulting manifest."""
    expected_ids = {
        chunk_id
        for entry in manifest_documents.values()
        for chunk_id in entry.get("chunk_ids", [])
    }
    stored_ids = vector_store.get(include=[]).get("ids", [])
    orphaned_ids = [vector_id for vector_id in stored_ids if vector_id not in expected_ids]
    return _delete_ids(vector_store, orphaned_ids)
