"""Metadata-preserving text chunking for cleaned LangChain Documents."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from .config import (
        CHUNK_ID_HASH_ALGORITHM,
        CHUNK_OVERLAP,
        CHUNK_SEPARATORS,
        CHUNK_SIZE,
        TEXT_EXTRACTION_ENCODING,
    )
except ImportError:  # Supports direct execution from the RAG2 directory.
    from config import (
        CHUNK_ID_HASH_ALGORITHM,
        CHUNK_OVERLAP,
        CHUNK_SEPARATORS,
        CHUNK_SIZE,
        TEXT_EXTRACTION_ENCODING,
    )


@dataclass
class ChunkResult:
    """Chunked Documents and the summary statistics for the run."""

    documents: list[Document] = field(default_factory=list)

    @property
    def total_chunks(self) -> int:
        return len(self.documents)

    @property
    def average_chunk_size(self) -> float:
        if not self.documents:
            return 0.0
        return sum(len(document.page_content) for document in self.documents) / self.total_chunks

    @property
    def largest_chunk_size(self) -> int:
        return max((len(document.page_content) for document in self.documents), default=0)

    @property
    def smallest_chunk_size(self) -> int:
        return min((len(document.page_content) for document in self.documents), default=0)


def chunk_documents(documents: list[Document]) -> ChunkResult:
    """Split cleaned documents and add deterministic identifiers to every chunk."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=list(CHUNK_SEPARATORS),
    )
    chunks: list[Document] = []
    for document in documents:
        for chunk_index, chunk_text in enumerate(splitter.split_text(document.page_content)):
            metadata = dict(document.metadata)
            metadata["chunk_index"] = chunk_index
            metadata["chunk_id"] = _chunk_id(document.metadata, chunk_index, chunk_text)
            chunks.append(Document(page_content=chunk_text, metadata=metadata))
    return ChunkResult(documents=chunks)


def _chunk_id(source_metadata: dict, chunk_index: int, chunk_text: str) -> str:
    """Build a stable chunk ID from source identity, position, and chunk content."""
    source_id = str(source_metadata.get("document_id", ""))
    page_or_chapter = str(
        source_metadata.get("page_number", source_metadata.get("chapter", ""))
    )
    identifier = "|".join((source_id, page_or_chapter, str(chunk_index), chunk_text))
    return hashlib.new(
        CHUNK_ID_HASH_ALGORITHM, identifier.encode(TEXT_EXTRACTION_ENCODING)
    ).hexdigest()
