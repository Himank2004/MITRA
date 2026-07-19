"""
User Profile Manager

Aggregates session states into a long-term user profile WITHOUT LLM.
Uses deterministic logic and statistical aggregation.

Periodically updates (not every message) based on:
- Sessions since last update
- Significant time elapsed
- Scheduled background job
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import Counter
import numpy as np
from theme_deduplicator import ThemeDeduplicator
from shared_embeddings import embed_text


class UserProfileManager:
    """
    Builds and updates user profile from session states.

    NO LLM - purely statistical/semantic similarity based.
    """

    def __init__(self, theme_similarity_threshold: float = 0.75):
        self.deduplicator = ThemeDeduplicator(
            similarity_threshold=theme_similarity_threshold
        )

    async def aggregate_sessions_into_profile(
        self, user_id: str, session_states: List[Dict], debug: bool = False
    ) -> Dict:
        """
        Aggregate multiple session states into a user profile.

        Args:
            user_id: User ID
            session_states: List of session state dicts from DB
                Each has: activeThemes, activeWarningSignals, whatHelpedThisSession, riskTrend
            debug: Print debug info

        Returns:
            user_profile dict ready for DB update
        """

        if debug:
            print(
                f"[UserProfileManager] Aggregating {len(session_states)} sessions for user {user_id}"
            )

        # 1. Extract recurring themes (most common across sessions)
        recurring_themes = self._aggregate_themes(
            session_states, field="activeThemes", debug=debug
        )

        # 2. Extract common triggers (warning signals that recur)
        common_triggers = self._aggregate_triggers(
            session_states, field="activeWarningSignals", debug=debug
        )

        # 3. Extract helpful approaches (what worked most often)
        known_helpful_approaches = self._aggregate_helpful_approaches(
            session_states, debug=debug
        )

        # 4. Determine support style (inferred from patterns)
        preferred_support_style = self._infer_support_style(session_states, debug=debug)

        # 5. Calculate risk baseline
        risk_baseline, risk_trend = self._calculate_risk_baseline(
            session_states, debug=debug
        )

        # 6. Calculate stats
        stats = self._calculate_stats(session_states)

        profile = {
            "userId": user_id,
            "recurringThemes": recurring_themes,
            "commonTriggers": common_triggers,
            "preferredSupportStyle": preferred_support_style,
            "knownHelpfulApproaches": known_helpful_approaches,
            "riskBaseline": risk_baseline,
            "riskTrend": risk_trend,
            "lastProfileUpdate": datetime.utcnow().isoformat(),
            "sessionsSinceLastUpdate": 0,
            "totalSessionsAnalyzed": len(session_states),
            "stats": stats,
        }

        if debug:
            print(f"[UserProfileManager] Profile aggregated:")
            print(f"  - Recurring themes: {len(recurring_themes)}")
            print(f"  - Common triggers: {len(common_triggers)}")
            print(f"  - Helpful approaches: {len(known_helpful_approaches)}")
            print(f"  - Risk baseline: {risk_baseline}")

        return profile

    def _aggregate_themes(
        self,
        session_states: List[Dict],
        field: str = "activeThemes",
        debug: bool = False,
    ) -> List[Dict]:
        """
        Extract recurring themes, deduplicated by semantic similarity.
        """

        # Collect all themes across sessions
        all_themes = []
        for session in session_states:
            themes = session.get(field, [])
            all_themes.extend(themes)

        if not all_themes:
            return []

        # Count frequency
        theme_counts = Counter(all_themes)

        # Create theme objects
        theme_objects = []
        for theme, count in theme_counts.most_common():
            try:
                embedding = embed_text(theme)
                theme_objects.append(
                    {
                        "theme": theme,
                        "frequency": count,
                        "embedding": embedding,
                        "lastSeen": None,
                    }
                )
            except Exception as e:
                if debug:
                    print(f"[UserProfileManager] Embedding error for '{theme}': {e}")

        # Deduplicate similar themes
        if debug:
            print(f"[UserProfileManager] Before dedup: {len(theme_objects)} themes")

        deduped, _ = self.deduplicator.deduplicate_themes([], theme_objects)

        if debug:
            print(f"[UserProfileManager] After dedup: {len(deduped)} themes")

        # Sort by frequency
        deduped.sort(key=lambda x: x["frequency"], reverse=True)

        return deduped[:5]  # Keep top 5

    def _aggregate_triggers(
        self,
        session_states: List[Dict],
        field: str = "activeWarningSignals",
        debug: bool = False,
    ) -> List[Dict]:
        """
        Extract common triggers (warning signals/stressors that recur).
        """

        all_triggers = []
        for session in session_states:
            triggers = session.get(field, [])
            all_triggers.extend(triggers)

        if not all_triggers:
            return []

        trigger_counts = Counter(all_triggers)

        trigger_objects = []
        for trigger, count in trigger_counts.most_common():
            try:
                embedding = embed_text(trigger)
                trigger_objects.append(
                    {
                        "trigger": trigger,
                        "frequency": count,
                        "embedding": embedding,
                        "lastSeen": None,
                    }
                )
            except Exception as e:
                if debug:
                    print(
                        f"[UserProfileManager] Embedding error for trigger '{trigger}': {e}"
                    )

        trigger_objects.sort(key=lambda x: x["frequency"], reverse=True)
        return trigger_objects[:4]  # Keep top 4

    def _aggregate_helpful_approaches(
        self, session_states: List[Dict], debug: bool = False
    ) -> List[Dict]:
        """
        Extract approaches that helped, ranked by frequency and recency.
        """

        all_approaches = []
        for session in session_states:
            approaches = session.get("whatHelpedThisSession", [])
            all_approaches.extend(approaches)

        if not all_approaches:
            return []

        approach_counts = Counter(all_approaches)

        approaches_list = []
        for approach, count in approach_counts.most_common():
            # Effectiveness: assume higher frequency = higher effectiveness
            # Scale: 1-10 based on how many sessions used it
            effectiveness = min(10, 3 + count)  # 3-13, capped at 10

            approaches_list.append(
                {
                    "approach": approach,
                    "effectiveness": effectiveness,
                    "frequency": count,
                    "lastUsed": None,
                }
            )

        approaches_list.sort(key=lambda x: x["effectiveness"], reverse=True)
        return approaches_list[:5]  # Keep top 5

    def _infer_support_style(
        self, session_states: List[Dict], debug: bool = False
    ) -> List[str]:
        """
        Infer user's preferred support style from patterns.

        Returns: ["slow_pacing", "few_questions", "direct_advice", "exploration", etc.]
        """

        # For now, return empty - this would need more sophisticated analysis
        # Could infer from:
        # - Response latency (slow_pacing vs fast engagement)
        # - Question frequency in helpful sessions
        # - Feedback patterns

        # Placeholder: start with empty
        return []

    def _calculate_momentum_score(self, session_states: List[Dict]) -> float:
        """
        Calculate momentum-based trend score using EWMA (Exponential Weighted Moving Average).
        Recent sessions weighted MORE heavily than older ones, but not extremely.

        Converts riskTrend to numeric: worsening=-1, volatile=-0.5, stable=0, improving=+1
        Then applies exponential weights where recent index has higher weight.

        Returns: momentum_score in range [-1, 1]
            -1: strong declining trend (recent sessions getting worse)
            0: neutral/stable
            +1: strong improving trend (recent sessions getting better)
        """
        if not session_states:
            return 0.0

        n = len(session_states)
        alpha = 0.7  # Smoothing factor (0.7 = moderate recency weighting, less extreme)

        # Convert trends to numeric values
        trend_map = {
            "worsening": -1.0,
            "volatile": -0.5,
            "stable": 0.0,
            "improving": 1.0,
        }

        # Extract and convert
        trend_values = []
        for s in session_states:
            trend = s.get("riskTrend", "stable")
            trend_values.append(trend_map.get(trend, 0.0))

        # Calculate EWMA (exponential weights increase toward recent)
        # More recent sessions have higher weights, but not extremely
        ewma = 0.0
        weight_sum = 0.0
        for i in range(n):
            # Exponential weight: older sessions (low i) have lower weight
            weight = alpha ** (n - 1 - i)
            ewma += trend_values[i] * weight
            weight_sum += weight

        momentum = ewma / weight_sum if weight_sum > 0 else 0.0
        return float(np.clip(momentum, -1.0, 1.0))

    def _calculate_risk_baseline(
        self, session_states: List[Dict], debug: bool = False
    ) -> tuple[str, str]:
        """
        Calculate baseline risk level and trend from session history.

        Uses PERCENTAGE THRESHOLDS to avoid over-classifying on single sessions.
        Risk baseline requires RECURRING PATTERNS, not isolated incidents.
        Risk trend uses MOMENTUM scoring (EWMA) to weight recent sessions more heavily.

        Example: Hopelessness in 1 session out of 20 = not HIGH risk.
                 Hopelessness in 5+ sessions (20%+) = concerning.

        Returns: (risk_baseline, risk_trend)
            risk_baseline: "LOW", "MODERATE", "MODERATE-HIGH", "HIGH"
            risk_trend: "improving", "stable", "declining"
        """

        if not session_states:
            return "LOW", "stable"

        # Calculate momentum-based trend (weights recent sessions more)
        momentum_score = self._calculate_momentum_score(session_states)

        if momentum_score > 0.3:
            overall_trend = "improving"
        elif momentum_score < -0.3:
            overall_trend = "declining"
        else:
            overall_trend = "stable"

        # Determine baseline from warning signals
        # CRITICAL: Use frequency thresholds, not just presence
        all_warnings = []
        for session in session_states:
            all_warnings.extend(session.get("activeWarningSignals", []))

        high_risk_keywords = [
            "suicidal",
            "self_harm",
            "hopelessness",
            "severe_isolation",
        ]

        # Count how many HIGH-RISK warnings appear frequently
        total_sessions = len(session_states)
        warning_counts = Counter(all_warnings)

        high_risk_signal_count = 0
        for warning, count in warning_counts.items():
            if any(kw in warning.lower() for kw in high_risk_keywords):
                # Only count as HIGH if appears in 20%+ of sessions
                if count / total_sessions >= 0.2:  # 20% threshold
                    high_risk_signal_count += 1

        if high_risk_signal_count > 0:
            baseline = "HIGH"
        elif momentum_score < -0.3:
            # Declining trend correlates with elevated baseline
            baseline = "MODERATE-HIGH"
        elif momentum_score < 0.0:
            # Slight decline warrants moderate attention
            baseline = "MODERATE"
        else:
            baseline = "LOW"

        if debug:
            print(
                f"[UserProfileManager] Risk baseline: {baseline}, trend: {overall_trend}"
            )
            print(f"[UserProfileManager] Momentum score: {momentum_score:.2f}")

        return baseline, overall_trend

    async def update_profile_incrementally(
        self,
        user_id: str,
        existing_profile: Dict,
        new_session_states: List[Dict],
        debug: bool = False,
    ) -> Dict:
        """
        Update existing profile with NEW sessions only (not full re-aggregation).

        This is more efficient than re-processing all sessions each time.
        Only compares new sessions against existing profile data.

        Args:
            user_id: User ID
            existing_profile: Current profile from DB
            new_session_states: Only NEW sessions since last profile update
            debug: Print debug info

        Returns:
            Updated profile dict
        """
        if debug:
            print(
                f"[UserProfileManager] Incrementally updating profile with {len(new_session_states)} new sessions"
            )

        # Merge existing themes with new themes from new sessions
        existing_themes = existing_profile.get("recurringThemes", [])
        new_themes = self._aggregate_themes(
            new_session_states, field="activeThemes", debug=False
        )

        # Deduplicate: match new themes to existing by similarity
        merged_themes = self._merge_theme_lists(existing_themes, new_themes)

        # Similar for triggers
        existing_triggers = existing_profile.get("commonTriggers", [])
        new_triggers = self._aggregate_triggers(
            new_session_states, field="activeWarningSignals", debug=False
        )
        merged_triggers = self._merge_trigger_lists(existing_triggers, new_triggers)

        # Merge helpful approaches
        existing_approaches = existing_profile.get("knownHelpfulApproaches", [])
        new_approaches = self._aggregate_helpful_approaches(
            new_session_states, debug=False
        )
        merged_approaches = self._merge_approach_lists(
            existing_approaches, new_approaches
        )

        # Recalculate risk using combined history
        # Fetch all sessions needed for accurate risk calculation
        from longitudinal_db_client import get_user_session_states

        all_recent = get_user_session_states(user_id, limit=20)

        risk_baseline, risk_trend = self._calculate_risk_baseline(
            all_recent if all_recent else new_session_states, debug=debug
        )

        # Update stats
        existing_stats = existing_profile.get("stats", {})
        new_stats = self._calculate_stats(
            all_recent if all_recent else new_session_states
        )

        # Accumulate totals
        new_stats["totalConversations"] = (
            existing_stats.get("totalConversations", 0)
            + new_stats["totalConversations"]
        )
        new_stats["totalMessages"] = (
            existing_stats.get("totalMessages", 0) + new_stats["totalMessages"]
        )

        # Updated profile
        profile = {
            "userId": user_id,
            "recurringThemes": merged_themes,
            "commonTriggers": merged_triggers,
            "preferredSupportStyle": existing_profile.get("preferredSupportStyle", []),
            "knownHelpfulApproaches": merged_approaches,
            "riskBaseline": risk_baseline,
            "riskTrend": risk_trend,
            "lastProfileUpdate": datetime.utcnow().isoformat(),
            "sessionsSinceLastUpdate": 0,
            "totalSessionsAnalyzed": new_stats["totalConversations"],
            "stats": new_stats,
        }

        if debug:
            print(f"[UserProfileManager] Profile incrementally updated")
            print(f"  - Merged themes: {len(merged_themes)}")
            print(f"  - Risk baseline: {risk_baseline}, trend: {risk_trend}")

        return profile

    def _merge_theme_lists(
        self, existing_themes: List[Dict], new_themes: List[Dict]
    ) -> List[Dict]:
        """
        Merge new themes into existing theme list, deduplicating by similarity.
        Updates frequencies for matching themes.
        """
        merged = existing_themes.copy()

        for new_theme in new_themes:
            # Check if similar theme exists
            matched = False
            for existing in merged:
                # Compare embeddings
                if "embedding" in new_theme and "embedding" in existing:
                    sim = self.deduplicator._cosine_similarity(
                        new_theme["embedding"], existing["embedding"]
                    )
                    if sim >= 0.75:
                        # Merge: update frequency and lastSeen
                        existing["frequency"] += new_theme["frequency"]
                        existing["lastSeen"] = new_theme["lastSeen"]
                        matched = True
                        break

            if not matched:
                # New theme, add it
                merged.append(new_theme)

        # Re-sort by frequency, keep top 5
        merged.sort(key=lambda x: x["frequency"], reverse=True)
        return merged[:5]

    def _merge_trigger_lists(
        self, existing_triggers: List[Dict], new_triggers: List[Dict]
    ) -> List[Dict]:
        """
        Merge new triggers into existing trigger list, deduplicating by similarity.
        """
        merged = existing_triggers.copy()

        for new_trigger in new_triggers:
            matched = False
            for existing in merged:
                if "embedding" in new_trigger and "embedding" in existing:
                    sim = self.deduplicator._cosine_similarity(
                        new_trigger["embedding"], existing["embedding"]
                    )
                    if sim >= 0.75:
                        existing["frequency"] += new_trigger["frequency"]
                        matched = True
                        break

            if not matched:
                merged.append(new_trigger)

        merged.sort(key=lambda x: x["frequency"], reverse=True)
        return merged[:4]

    def _merge_approach_lists(
        self, existing_approaches: List[Dict], new_approaches: List[Dict]
    ) -> List[Dict]:
        """
        Merge new approaches into existing approach list.
        Updates frequency and effectiveness.
        """
        merged = existing_approaches.copy()

        for new_approach in new_approaches:
            # Find by name match
            matched = False
            for existing in merged:
                if existing["approach"].lower() == new_approach["approach"].lower():
                    existing["frequency"] += new_approach["frequency"]
                    existing["lastUsed"] = new_approach["lastUsed"]
                    # Recalculate effectiveness: 3 + frequency, capped at 10
                    existing["effectiveness"] = min(10, 3 + existing["frequency"])
                    matched = True
                    break

            if not matched:
                merged.append(new_approach)

        merged.sort(key=lambda x: x["effectiveness"], reverse=True)
        return merged[:5]

    def _calculate_stats(self, session_states: List[Dict]) -> Dict:
        """Calculate summary statistics."""

        total_msgs = sum(s.get("messageCount", 0) for s in session_states)

        # Convert risk level enums to numeric values for averaging
        risk_level_to_numeric = {
            "NONE": 0,
            "LOW": 1,
            "MODERATE": 2,
            "MODERATE-HIGH": 2.5,
            "HIGH": 3,
            "IMMINENT": 4,
        }

        risk_levels = [
            risk_level_to_numeric.get(s.get("lastRiskLevel", "NONE"), 0)
            for s in session_states
            if s.get("lastRiskLevel")
        ]

        avg_risk = np.mean(risk_levels) if risk_levels else 0

        return {
            "totalConversations": len(session_states),
            "totalMessages": total_msgs,
            "averageRiskLevel": float(avg_risk),
        }
