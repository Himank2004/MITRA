# from langchain_chroma import Chroma
# import os
# from typing import Tuple, List
# import sys

# # Ensure ML_Backend root is on path
# _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# if _BASE not in sys.path:
#     sys.path.insert(0, _BASE)

# from shared_embeddings import get_embeddings

# # Absolute path to the ChromaDB directory, resolved relative to this file's
# # location so that it works regardless of the cwd when Flask starts.
# _RAG_DIR = os.path.join(
#     os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
#     "books_chroma_db",
# )

# # 1) Shared embedding model (all-mpnet-base-v2, loaded once for the whole process)
# embeddings = get_embeddings()

# # 2) Load the existing Chroma DB from the local folder
# vectordb = Chroma(
#     persist_directory=_RAG_DIR,
#     collection_name="rag_docs",
#     embedding_function=embeddings,
# )

# # 3) MMR retriever — k=3 final docs selected from fetch_k=12 candidates.
# #    lambda_mult=0.6 balances relevance (1.0) vs. diversity (0.0).
# retriever = vectordb.as_retriever(
#     search_type = "similarity",
#     search_kwargs = {"k": 3}
# )


# def _source_id(doc) -> str:
#     """Build a human-readable source identifier from a Document's metadata."""
#     meta = doc.metadata or {}
#     src = os.path.basename(meta.get("source", ""))
#     page = meta.get("page", meta.get("chunk", ""))
#     return f"{src}:{page}" if page != "" else (src or "unknown")


# def query_retriever(query: str) -> Tuple[str, List[str]]:
#     """
#     Retrieve relevant passages via MMR search.

#     Returns:
#         combined_context  -- passages joined by double newline (ready to inject into prompt)
#         sources           -- list of source identifiers for storage in the message doc
#     """
#     docs = retriever.invoke(query)
#     combined_context = "\n\n".join(doc.page_content for doc in docs)
#     sources = [_source_id(doc) for doc in docs]
#     return combined_context, sources


# # Example usage
# if __name__ == "__main__":
#     while True:
#         test_query = input("Enter a query (or 'exit' to quit): ")
#         if test_query.lower() == "exit":
#             break
#         context, srcs = query_retriever(test_query)

#         if not context:
#             print("No documents retrieved.")
#         else:
#             print(f"Retrieved {len(srcs)} documents.\n")
#             for idx, src in enumerate(srcs, start=1):
#                 print(f"Document {idx}: {src}")
#             print("\n--- Combined Context (first 500 chars) ---")
#             print(context[:1500])
       
import hashlib
import json
import os
import re
import sys
from typing import Dict, List, Tuple

import torch
from langchain_chroma import Chroma
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

# Ensure ML_Backend root is importable.
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from shared_embeddings import get_embeddings

_RAG_DIR = os.path.join(_BASE, "books_chroma_db")
_COLLECTION_NAME = "rag_docs"

# Retrieval settings
DENSE_K = 20        # Semantic-search candidates
BM25_K = 20         # Keyword-search candidates
FUSION_K = 20       # Candidates passed to reranker
FINAL_K = 3         # Passages returned to the bot
RRF_K = 60          # Reciprocal Rank Fusion constant

embeddings = get_embeddings()

vectordb = Chroma(
    persist_directory=_RAG_DIR,
    collection_name=_COLLECTION_NAME,
    embedding_function=embeddings,
)

_reranker = None
_bm25 = None
_bm25_docs: List[Document] = []


def _tokenize(text: str) -> List[str]:
    """Simple, deterministic tokenizer for BM25 keyword retrieval."""
    return re.findall(r"\b\w+\b", text.lower())


def _doc_key(doc: Document) -> str:
    """Create a stable key used to merge dense and BM25 results."""
    metadata = json.dumps(doc.metadata or {}, sort_keys=True, default=str)
    content = f"{doc.page_content}\n{metadata}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_bm25_index() -> None:
    """Build an in-memory BM25 index from the persisted Chroma documents."""
    global _bm25, _bm25_docs

    result = vectordb.get(include=["documents", "metadatas"])
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    _bm25_docs = [
        Document(page_content=text, metadata=metadata or {})
        for text, metadata in zip(documents, metadatas)
        if text and text.strip()
    ]

    if not _bm25_docs:
        _bm25 = None
        return

    corpus = [_tokenize(doc.page_content) for doc in _bm25_docs]
    _bm25 = BM25Okapi(corpus)


def _get_reranker() -> CrossEncoder:
    """Load the cross-encoder only when the first query needs it."""
    global _reranker

    if _reranker is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _reranker = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
            device=device,
            max_length=512,
        )

    return _reranker


def _bm25_search(query: str, k: int) -> List[Document]:
    """Return the best keyword matches."""
    if _bm25 is None:
        _load_bm25_index()

    if _bm25 is None:
        return []

    scores = _bm25.get_scores(_tokenize(query))
    best_indices = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )[:k]

    return [
        _bm25_docs[index]
        for index in best_indices
        if scores[index] > 0
    ]


def _rrf_merge(
    dense_docs: List[Document],
    keyword_docs: List[Document],
    k: int = RRF_K,
) -> List[Document]:
    """Merge rankings without comparing dense and BM25 score scales."""
    scores: Dict[str, float] = {}
    docs_by_key: Dict[str, Document] = {}

    for ranked_docs in (dense_docs, keyword_docs):
        for rank, doc in enumerate(ranked_docs, start=1):
            key = _doc_key(doc)
            docs_by_key[key] = doc
            scores[key] = scores.get(key, 0.0) + (1.0 / (k + rank))

    return [
        docs_by_key[key]
        for key in sorted(scores, key=scores.get, reverse=True)
    ]


def _rerank(query: str, docs: List[Document], k: int) -> List[Document]:
    """Use a cross-encoder to select the most relevant final passages."""
    if not docs:
        return []

    try:
        reranker = _get_reranker()
        pairs = [(query, doc.page_content) for doc in docs]
        scores = reranker.predict(pairs)

        ranked = sorted(
            zip(docs, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [doc for doc, _ in ranked[:k]]

    except Exception as error:
        # RAG should remain available if model loading or reranking fails.
        print(f"[RAG] Reranking failed; returning fused results: {error}")
        return docs[:k]


def _source_id(doc: Document) -> str:
    meta = doc.metadata or {}
    src = os.path.basename(meta.get("source", ""))
    page = meta.get("page", meta.get("chunk", ""))
    return f"{src}:{page}" if page != "" else (src or "unknown")


def query_retriever(query: str) -> Tuple[str, List[str]]:
    """
    Hybrid retrieval pipeline:

    1. Chroma dense semantic search
    2. BM25 keyword search
    3. Reciprocal Rank Fusion
    4. Cross-encoder reranking
    """
    if not query or not query.strip():
        return "", []

    try:
        dense_docs = vectordb.similarity_search(query, k=DENSE_K)
    except Exception as error:
        print(f"[RAG] Dense retrieval failed: {error}")
        dense_docs = []

    try:
        keyword_docs = _bm25_search(query, k=BM25_K)
    except Exception as error:
        print(f"[RAG] BM25 retrieval failed: {error}")
        keyword_docs = []

    fused_docs = _rrf_merge(dense_docs, keyword_docs)[:FUSION_K]
    final_docs = _rerank(query, fused_docs, k=FINAL_K)

    context = "\n\n".join(doc.page_content for doc in final_docs)
    sources = [_source_id(doc) for doc in final_docs]
    return context, sources


if __name__ == "__main__":
    while True:
        query = input("Enter a query (or 'exit' to quit): ").strip()
        if query.lower() == "exit":
            break

        context, sources = query_retriever(query)
        print(f"\nRetrieved {len(sources)} passages: {sources}\n")
        print(context[:1500])