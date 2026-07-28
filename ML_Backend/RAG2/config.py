"""Central configuration for the RAG2 pipeline.

All RAG tunables and filesystem locations belong in this module.  Pipeline
modules should import values from here instead of defining local settings.
"""

from pathlib import Path


# Filesystem locations
RAG_DIR = Path(__file__).resolve().parent
ML_BACKEND_DIR = RAG_DIR.parent
BOOKS_DIR = (RAG_DIR / ".." / "Books").resolve()
CHROMA_DIR = RAG_DIR / "chroma_db"
MANIFEST_PATH = RAG_DIR / "manifest.json"

# Vector database
COLLECTION_NAME = "mental_health_books"
MANIFEST_VERSION = 1
MANIFEST_JSON_INDENT = 2

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"

# Chunking
CHUNK_SIZE = 1_000
CHUNK_OVERLAP = 200
CHUNK_SEPARATORS = ("\n\n", "\n", ". ", " ", "")
CHUNK_ID_HASH_ALGORITHM = "sha256"

# Text cleaning
MAX_CONSECUTIVE_BLANK_LINES = 2

# Ingestion and retrieval
INGEST_BATCH_SIZE = 8
RETRIEVAL_TOP_K = 5
RETRIEVAL_SIMILARITY_THRESHOLD = 0.35
RETRIEVAL_RETURN_LOW_CONFIDENCE_FALLBACK = True

# Supported source files
PDF_FILE_EXTENSION = ".pdf"
EPUB_FILE_EXTENSION = ".epub"
SUPPORTED_FILE_EXTENSIONS = frozenset({PDF_FILE_EXTENSION, EPUB_FILE_EXTENSION})
PDF_FILE_TYPE = "pdf"
EPUB_FILE_TYPE = "epub"

# Loading
FILE_HASH_ALGORITHM = "sha256"
FILE_HASH_READ_SIZE = 1_048_576
TEXT_EXTRACTION_ENCODING = "utf-8"
HTML_PARSER = "html.parser"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
