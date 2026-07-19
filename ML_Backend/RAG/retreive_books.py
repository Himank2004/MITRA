from langchain_chroma import Chroma
import os
from typing import Tuple, List
import sys

# Ensure ML_Backend root is on path
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from shared_embeddings import get_embeddings

# Absolute path to the ChromaDB directory, resolved relative to this file's
# location so that it works regardless of the cwd when Flask starts.
_RAG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "books_chroma_db",
)

# 1) Shared embedding model (all-mpnet-base-v2, loaded once for the whole process)
embeddings = get_embeddings()

# 2) Load the existing Chroma DB from the local folder
vectordb = Chroma(
    persist_directory=_RAG_DIR,
    collection_name="rag_docs",
    embedding_function=embeddings,
)

# 3) MMR retriever — k=3 final docs selected from fetch_k=12 candidates.
#    lambda_mult=0.6 balances relevance (1.0) vs. diversity (0.0).
retriever = vectordb.as_retriever(
    search_type = "similarity",
    search_kwargs = {"k": 3}
)


def _source_id(doc) -> str:
    """Build a human-readable source identifier from a Document's metadata."""
    meta = doc.metadata or {}
    src = os.path.basename(meta.get("source", ""))
    page = meta.get("page", meta.get("chunk", ""))
    return f"{src}:{page}" if page != "" else (src or "unknown")


def query_retriever(query: str) -> Tuple[str, List[str]]:
    """
    Retrieve relevant passages via MMR search.

    Returns:
        combined_context  -- passages joined by double newline (ready to inject into prompt)
        sources           -- list of source identifiers for storage in the message doc
    """
    docs = retriever.invoke(query)
    combined_context = "\n\n".join(doc.page_content for doc in docs)
    sources = [_source_id(doc) for doc in docs]
    return combined_context, sources


# Example usage
if __name__ == "__main__":
    while True:
        test_query = input("Enter a query (or 'exit' to quit): ")
        if test_query.lower() == "exit":
            break
        context, srcs = query_retriever(test_query)

        if not context:
            print("No documents retrieved.")
        else:
            print(f"Retrieved {len(srcs)} documents.\n")
            for idx, src in enumerate(srcs, start=1):
                print(f"Document {idx}: {src}")
            print("\n--- Combined Context (first 500 chars) ---")
            print(context[:1500])
       
