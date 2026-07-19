"""
Theme Deduplicator

Uses semantic similarity (embeddings) to cluster similar themes/triggers.
For example: "financial stress" and "money worries" are similar → merge into one.

This enables the user profile to avoid redundant themes while still capturing diversity.
"""

import numpy as np
from typing import List, Tuple
from shared_embeddings import embed_text


class ThemeDeduplicator:
    """
    Clusters similar themes using cosine similarity on embeddings.

    Default threshold: 0.85 (fairly strict to avoid over-merging)
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def _cosine_similarity(self, a: list, b: list) -> float:
        """Cosine similarity between two embedding vectors."""
        av = np.asarray(a, dtype=np.float32)
        bv = np.asarray(b, dtype=np.float32)

        norm_a = np.linalg.norm(av)
        norm_b = np.linalg.norm(bv)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(av, bv) / (norm_a * norm_b))

    def deduplicate_themes(
        self, new_themes: List[str], existing_themes: List[dict]
    ) -> Tuple[List[dict], List[str]]:
        """
        Merge new themes with existing ones, clustering similar themes.

        Args:
            new_themes: List of theme strings from current session
            existing_themes: List of dicts with {theme, frequency, embedding, ...}

        Returns:
            (merged_themes, new_theme_names_added)
        """

        if not existing_themes:
            # No existing themes → create new entries
            merged = []
            for theme in new_themes:
                embedding = embed_text(theme)
                merged.append(
                    {
                        "theme": theme,
                        "frequency": 1,
                        "embedding": embedding,
                        "lastSeen": None,
                    }
                )
            return merged, new_themes

        merged_themes = list(existing_themes)  # copy
        themes_added = []

        for new_theme in new_themes:
            new_embedding = embed_text(new_theme)
            best_match = None
            best_similarity = 0.0

            # Find most similar existing theme
            for existing in merged_themes:
                sim = self._cosine_similarity(new_embedding, existing["embedding"])
                if sim > best_similarity:
                    best_similarity = sim
                    best_match = existing

            if best_similarity >= self.similarity_threshold and best_match:
                # Merge with existing theme
                best_match["frequency"] += 1
                best_match["lastSeen"] = None  # Will be set by caller
                # Optionally update embedding to running average
                # best_match["embedding"] = (0.7 * np.array(best_match["embedding"]) +
                #                            0.3 * np.array(new_embedding)).tolist()
            else:
                # New theme
                merged_themes.append(
                    {
                        "theme": new_theme,
                        "frequency": 1,
                        "embedding": new_embedding,
                        "lastSeen": None,
                    }
                )
                themes_added.append(new_theme)

        return merged_themes, themes_added

    def cluster_similar_items(
        self, items: List[dict]  # [{item: str, embedding: [float]}, ...]
    ) -> List[List[dict]]:
        """
        Group items into clusters of similar semantic meaning.

        Returns list of clusters (each cluster is a list of items)
        """
        if not items:
            return []

        clusters = []
        used = set()

        for i, item in enumerate(items):
            if i in used:
                continue

            cluster = [item]
            used.add(i)

            for j in range(i + 1, len(items)):
                if j in used:
                    continue

                sim = self._cosine_similarity(item["embedding"], items[j]["embedding"])

                if sim >= self.similarity_threshold:
                    cluster.append(items[j])
                    used.add(j)

            clusters.append(cluster)

        return clusters
