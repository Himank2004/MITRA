"""Text cleaning that preserves meaningful Unicode and paragraph boundaries."""

from __future__ import annotations

import re

from langchain_core.documents import Document

try:
    from .config import MAX_CONSECUTIVE_BLANK_LINES
except ImportError:  # Supports direct execution from the RAG2 directory.
    from config import MAX_CONSECUTIVE_BLANK_LINES


SURROGATE_CHARACTERS = re.compile(r"[\ud800-\udfff]")
REPEATED_HORIZONTAL_WHITESPACE = re.compile(r"[\t ]+")
EXCESSIVE_BLANK_LINES = re.compile(r"\n(?:[\t ]*\n){2,}")


def clean_text(text: str) -> str:
    """Remove extraction artifacts without removing Unicode or paragraph breaks."""
    without_surrogates = SURROGATE_CHARACTERS.sub("", text)
    without_null_bytes = without_surrogates.replace("\x00", "")
    normalized_newlines = without_null_bytes.replace("\r\n", "\n").replace("\r", "\n")
    normalized_spaces = REPEATED_HORIZONTAL_WHITESPACE.sub(" ", normalized_newlines)
    return EXCESSIVE_BLANK_LINES.sub("\n" * MAX_CONSECUTIVE_BLANK_LINES, normalized_spaces)


def clean_documents(documents: list[Document]) -> list[Document]:
    """Clean documents and omit empty pages or chapters after cleaning."""
    cleaned_documents: list[Document] = []
    for document in documents:
        cleaned_text = clean_text(document.page_content)
        if not cleaned_text.strip():
            continue
        cleaned_documents.append(
            Document(page_content=cleaned_text, metadata=dict(document.metadata))
        )
    return cleaned_documents
