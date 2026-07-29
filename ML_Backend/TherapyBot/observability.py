"""Privacy-preserving LangSmith instrumentation for TherapyBot.

Tracing is opt-in: set ``LANGSMITH_TRACING=true`` and ``LANGSMITH_API_KEY``.
Inputs and outputs are hidden by default because this service processes highly
sensitive mental-health conversations and long-term memories.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

# Keep the safe default while allowing an explicit deployment-level override.
os.environ.setdefault("LANGSMITH_HIDE_INPUTS", "true")
os.environ.setdefault("LANGSMITH_HIDE_OUTPUTS", "true")

try:
    from langsmith import get_current_run_tree, traceable

    LANGSMITH_AVAILABLE = True
except ImportError:  # Lets the API keep working before dependencies are installed.
    LANGSMITH_AVAILABLE = False

    def get_current_run_tree():
        return None

    _F = TypeVar("_F", bound=Callable[..., Any])

    def traceable(*_args: Any, **_kwargs: Any):
        def decorator(function: _F) -> _F:
            return function

        return decorator


def tracing_enabled() -> bool:
    """Return whether this process can submit traces to LangSmith."""
    return LANGSMITH_AVAILABLE and os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(
        os.getenv("LANGSMITH_API_KEY")
    )


def hash_identifier(value: Any) -> str:
    """Create a stable, non-reversible identifier for trace correlation."""
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def add_metadata(**metadata: Any) -> None:
    """Attach only caller-approved, non-content metadata to the active span."""
    run_tree = get_current_run_tree()
    if run_tree is None:
        return
    try:
        run_tree.add_metadata(metadata)
    except AttributeError:
        # Compatibility with SDK releases that expose the mutable mapping only.
        run_tree.metadata.update(metadata)
    except Exception:
        logger.debug("Could not attach LangSmith span metadata", exc_info=True)


def redact_inputs(_inputs: dict[str, Any]) -> dict[str, Any]:
    """Never send raw prompts, query text, memory, or IDs from custom spans."""
    return {}


def redact_outputs(_outputs: Any) -> dict[str, Any]:
    """Never send model responses or retrieved content from custom spans."""
    return {}


def trace_failure() -> None:
    """Mark the active span as failed before allowing the original error to raise."""
    add_metadata(status="error")

