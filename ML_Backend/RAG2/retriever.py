"""Semantic-only retrieval from the persisted RAG2 Chroma collection."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document

try:
    from .config import (
        CHROMA_DIR,
        COLLECTION_NAME,
        RETRIEVAL_SIMILARITY_THRESHOLD,
        RETRIEVAL_TOP_K,
    )
    from .embeddings import get_shared_embeddings
except ImportError:  # Supports ``python retriever.py "query"`` from RAG2.
    from config import (
        CHROMA_DIR,
        COLLECTION_NAME,
        RETRIEVAL_SIMILARITY_THRESHOLD,
        RETRIEVAL_TOP_K,
    )
    from embeddings import get_shared_embeddings


NO_RELEVANT_CONTEXT = "No relevant context found."


@dataclass(frozen=True)
class RetrievedChunk:
    """A retrieved chunk paired with Chroma's normalized relevance score."""

    document: Document
    similarity_score: float


def retrieve(query: str) -> list[RetrievedChunk] | str:
    """Return up to five semantically relevant chunks, or a no-context message."""
    if not query.strip() or not CHROMA_DIR.is_dir():
        return NO_RELEVANT_CONTEXT

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_shared_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )
    scored_documents = vector_store.similarity_search_with_relevance_scores(
        query,
        k=RETRIEVAL_TOP_K,
    )
    results = [
        RetrievedChunk(document=document, similarity_score=score)
        for document, score in scored_documents
        if score >= RETRIEVAL_SIMILARITY_THRESHOLD
    ]
    return results or NO_RELEVANT_CONTEXT


def print_retrieval(query: str) -> None:
    """Run semantic retrieval and print its source, location, score, and text."""
    results = retrieve(query)
    if isinstance(results, str):
        print(results)
        return

    for result in results:
        metadata = result.document.metadata
        page = metadata.get("page_number", metadata.get("chapter", "N/A"))
        print(f"source: {metadata.get('source', 'Unknown')}")
        print(f"page: {page}")
        print(f"similarity score: {result.similarity_score:.4f}")
        print("chunk text:")
        print(result.document.page_content)
        print()


def main() -> None:
    """Accept one user query and print the semantic retrieval results."""
    parser = argparse.ArgumentParser(description="Query the RAG2 Chroma index.")
    parser.add_argument("query", help="The text to retrieve context for.")
    arguments = parser.parse_args()
    print_retrieval(arguments.query)


if __name__ == "__main__":
    main()
