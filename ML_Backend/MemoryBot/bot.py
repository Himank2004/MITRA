"""
MemoryBot - retrieves user memories from MongoDB.

Two kinds of memory are stored:
  - "instruct"  -> explicit user behavioural preferences
                   ALL instruct memories are ALWAYS returned.
  - "info"      -> factual/biographical memories
                   Top-k returned ranked by semantic similarity to the current query.

Embeddings are stored in MongoDB using the shared all-mpnet-base-v2 model.
If a memory has an empty embedding field (legacy entries), MemoryBot computes
and backfills it on first access.
"""

from __future__ import annotations

import os
import sys
import numpy as np
from typing import Tuple, List, Optional

# Ensure ML_Backend root is on path when run standalone
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _cosine_similarity(a: list, b: list) -> float:
    """Cosine similarity between two normalised embedding vectors."""
    av, bv = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    norm_a = np.linalg.norm(av)
    norm_b = np.linalg.norm(bv)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(av, bv) / (norm_a * norm_b))


class MemoryBot:
    """
    Retrieves user memories from MongoDB and formats them for injection into the
    agent system context.

    Usage
    -----
    bot = MemoryBot(top_k=5)
    instruct_text, info_text = bot.retrieve_memories(user_id, query)
    """

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def retrieve_memories(
        self,
        user_id: str,
        query: str,
        top_k: Optional[int] = None,
    ) -> Tuple[str, str]:
        """
        Returns
        -------
        instruct_context : str
            All instruct-type memories formatted as a bullet list.
        info_context : str
            Top-k info-type memories most semantically relevant to query,
            formatted as a bullet list.
        """
        k = top_k if top_k is not None else self.top_k

        try:
            from TherapyBot.db_client import get_memories_for_user, update_memory_embedding
        except ImportError:
            try:
                from db_client import get_memories_for_user, update_memory_embedding
            except ImportError as e:
                print(f"[MemoryBot] Cannot import db_client: {e}")
                return "", ""

        try:
            instruct_mems, info_mems = get_memories_for_user(user_id)
        except Exception as e:
            print(f"[MemoryBot] DB error while fetching memories: {e}")
            return "", ""

        # instruct memories (all of them, always - no embedding needed)
        instruct_lines = [
            m["content"] for m in instruct_mems if m.get("content", "").strip()
        ]
        instruct_context = "\n".join(f"- {line}" for line in instruct_lines)

        if not info_mems:
            return instruct_context, ""

        # Separate docs that have stored embeddings from those that don't
        have_emb: list = []   # docs with non-empty embedding list
        need_emb: list = []   # docs with empty/missing embedding
        for m in info_mems:
            if m.get("content", "").strip():
                if m.get("embedding"):
                    have_emb.append(m)
                else:
                    need_emb.append(m)

        if not have_emb and not need_emb:
            return instruct_context, ""

        # Backfill missing embeddings using shared model
        if need_emb:
            try:
                from shared_embeddings import embed_texts
                texts_to_embed = [m["content"] for m in need_emb]
                new_embs = embed_texts(texts_to_embed)
                for mem, emb in zip(need_emb, new_embs):
                    mem["embedding"] = emb
                    try:
                        update_memory_embedding(mem["_id"], emb)
                    except Exception as e:
                        print(f"[MemoryBot] Backfill DB write failed for {mem['_id']}: {e}")
                print(f"[MemoryBot] Backfilled embeddings for {len(need_emb)} memories.")
                have_emb.extend(need_emb)
            except Exception as e:
                print(f"[MemoryBot] Backfill embedding error - using recency order: {e}")
                top_contents = [m["content"] for m in (have_emb + need_emb)][:k]
                info_context = "\n".join(f"- {c}" for c in top_contents)
                return instruct_context, info_context

        # Rank all docs by cosine similarity to the query using stored embeddings
        try:
            from shared_embeddings import embed_text
            query_emb = embed_text(query)
            scored = sorted(
                have_emb,
                key=lambda m: _cosine_similarity(query_emb, m["embedding"]),
                reverse=True,
            )
            top_contents = [m["content"] for m in scored[:k]]
        except Exception as e:
            print(f"[MemoryBot] Similarity ranking error - using recency order: {e}")
            top_contents = [m["content"] for m in have_emb][:k]

        info_context = "\n".join(f"- {c}" for c in top_contents)
        return instruct_context, info_context

    def format_for_prompt(self, instruct_context: str, info_context: str) -> str:
        """
        Produce a single formatted block ready to be injected into the
        agent's message_text as silent background context.
        Returns an empty string if both contexts are empty.
        """
        parts: List[str] = []
        if instruct_context.strip():
            parts.append(
                "[USER PREFERENCES & INSTRUCTIONS - always follow these]\n"
                + instruct_context
            )
        if info_context.strip():
            parts.append(
                "[RELEVANT FACTS ABOUT THIS USER - use to personalise, do NOT parrot back]\n"
                + info_context
            )
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    bot = MemoryBot(top_k=3)
    uid = input("User ID: ").strip()
    q   = input("Query  : ").strip()
    ins, inf = bot.retrieve_memories(uid, q)
    print("\n--- INSTRUCT ---")
    print(ins or "(none)")
    print("\n--- INFO ---")
    print(inf or "(none)")
    print("\n--- FORMATTED ---")
    print(bot.format_for_prompt(ins, inf) or "(empty)")
