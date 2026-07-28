"""
Shared embedding model singleton for the entire ML_Backend.

All modules (RAG2, MemoryBot, etc.) import from here so the model is
loaded exactly once per process.

Model: sentence-transformers/all-mpnet-base-v2  (768-dim, normalised)
"""

from __future__ import annotations
from typing import Optional

from RAG2.config import EMBEDDING_MODEL

_embeddings = None


def get_embeddings():
    """
    Return the shared HuggingFace embeddings instance, loading it once lazily.
    Thread-safe in practice: Flask/asyncio workers all live in the same process,
    and Python's GIL ensures only one thread runs the init block.
    """
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        import torch

        print(f"[SharedEmbeddings] Loading {EMBEDDING_MODEL} …")
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[SharedEmbeddings] Model ready.")
    return _embeddings


def embed_text(text: str) -> list[float]:
    """Embed a single string and return a normalised float list."""
    return get_embeddings().embed_query(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings and return a list of normalised float lists."""
    return get_embeddings().embed_documents(texts)
