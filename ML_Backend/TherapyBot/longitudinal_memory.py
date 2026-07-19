"""
Longitudinal Memory Coordinator

Manages both:
1. SessionState (updated frequently: every ~5 messages or on risk spike)
2. UserProfile (updated periodically: aggregates from recent sessions)

Provides a simple interface for agent_stream.py to call.
"""

import os
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from session_state_manager import SessionStateManager
from user_profile_manager import UserProfileManager
from longitudinal_db_client import (
    update_session_state,
    get_user_session_states,
    update_user_profile,
    get_user_profile,
)
from constants import DEBUG_FLAGS


class LongitudinalMemoryCoordinator:
    """
    Orchestrates session state and user profile management.
    """

    def __init__(
        self,
        session_update_interval: int = 5,  # Update session state every N messages
        profile_update_interval: int = 5,  # Aggregate into profile every N sessions
        profile_update_hours: int = 24,  # Or at least every N hours
    ):
        self.session_update_interval = session_update_interval
        self.profile_update_interval = profile_update_interval
        self.profile_update_hours = profile_update_hours

        # Debug flags are centralized in constants.DEBUG_FLAGS

        self.session_manager = SessionStateManager()
        self.profile_manager = UserProfileManager()

        # Track message count per conversation
        self._message_counters: Dict[str, int] = {}

        # Track sessions since profile update per user
        self._profile_update_counters: Dict[str, int] = {}

    async def maybe_update_session_state(
        self,
        user_id: str,
        conversation_id: str,
        recent_messages: List[Dict],
        current_emotions: List[str],
        current_risk_level: str,
        risk_confidence: float,
        risk_jump: bool = False,  # True if risk spiked dramatically
    ) -> Optional[Dict]:
        """
        Check if session state should be updated and do so if needed.

        Called after each user message.

        Args:
            user_id, conversation_id: Identifiers
            recent_messages: Last ~15 messages
            current_emotions: Detected emotions
            current_risk_level: Risk level ("NONE", "LOW", "MODERATE", "HIGH", "IMMINENT")
            risk_confidence: Confidence in risk assessment
            risk_jump: True if risk spiked (e.g., LOW→HIGH)

        Returns:
            Updated session state dict if updated, None otherwise
        """

        conv_key = f"{user_id}_{conversation_id}"

        # Increment message counter
        if conv_key not in self._message_counters:
            self._message_counters[conv_key] = 0
        self._message_counters[conv_key] += 1

        should_update = (
            self._message_counters[conv_key] >= self.session_update_interval
            or risk_jump
        )

        if not should_update:
            if DEBUG_FLAGS["session"]:
                print(
                    f"[SessionState] Skip update ({self._message_counters[conv_key]}/{self.session_update_interval} messages)"
                )
            return None

        if DEBUG_FLAGS["session"]:
            trigger = "risk_spike" if risk_jump else "message_interval"
            print(f"[SessionState] Updating (trigger: {trigger})")

        # Update session state
        try:
            session_state = await self.session_manager.update_session_state(
                user_id=user_id,
                conversation_id=conversation_id,
                messages=recent_messages,
                current_emotions=current_emotions,
                current_risk_level=current_risk_level,
                risk_confidence=risk_confidence,
                debug=DEBUG_FLAGS["session"],
            )

            # Reset counter
            self._message_counters[conv_key] = 0

            if DEBUG_FLAGS["session"]:
                print(f"[SessionState] ✓ Updated")
                print(f"  Risk Trend: {session_state.get('riskTrend')}")
                print(
                    f"  Active Themes: {', '.join(session_state.get('activeThemes', []))}"
                )
                print(
                    f"  Warning Signals: {', '.join(session_state.get('activeWarningSignals', []))}"
                )
                print(
                    f"  Staleness: {session_state.get('staleness')} (0=fresh LLM, 1+=fallback)"
                )

            # Maybe trigger profile update
            await self._maybe_update_user_profile(user_id)

            return session_state

        except Exception as e:
            print(f"[SessionState] Error updating: {e}")
            return None

    async def _maybe_update_user_profile(self, user_id: str):
        """
        Check if user profile should be updated based on:
        - Number of sessions since last update
        - Time since last update
        """

        if user_id not in self._profile_update_counters:
            self._profile_update_counters[user_id] = 0
        self._profile_update_counters[user_id] += 1

        try:
            # Get existing profile
            existing_profile = get_user_profile(user_id)

            # Check conditions
            should_update = False

            if not existing_profile:
                should_update = True
                reason = "first_profile"
            elif self._profile_update_counters[user_id] >= self.profile_update_interval:
                should_update = True
                reason = "session_threshold"
            else:
                # Check time-based update
                last_update = existing_profile.get("lastProfileUpdate")
                if last_update:
                    try:
                        from datetime import datetime

                        last_update_dt = datetime.fromisoformat(last_update)
                        hours_since = (
                            datetime.utcnow() - last_update_dt
                        ).total_seconds() / 3600
                        if hours_since >= self.profile_update_hours:
                            should_update = True
                            reason = "time_threshold"
                    except:
                        pass

            if not should_update:
                if DEBUG_FLAGS["session"]:
                    print(
                        f"[UserProfile] Skip update (counter: {self._profile_update_counters[user_id]}/{self.profile_update_interval})"
                    )
                return

            if DEBUG_FLAGS["session"]:
                print(f"[UserProfile] Updating (trigger: {reason})")

            # INCREMENTAL UPDATE: Only process NEW sessions, not all sessions
            # This avoids O(n²) comparison and focuses on what's changed

            if existing_profile and reason != "first_profile":
                # Incremental update: only new sessions since last update
                last_update = existing_profile.get("lastProfileUpdate")

                # Fetch ALL sessions to find which are new
                all_sessions = get_user_session_states(user_id, limit=20)

                # Filter to only sessions created AFTER last profile update
                new_sessions = []
                if last_update:
                    try:
                        from datetime import datetime

                        last_update_dt = datetime.fromisoformat(last_update)
                        for session in all_sessions:
                            created_at = session.get("createdAt")
                            if created_at:
                                session_dt = datetime.fromisoformat(created_at)
                                if session_dt > last_update_dt:
                                    new_sessions.append(session)
                    except:
                        # If date parsing fails, use all sessions
                        new_sessions = all_sessions
                else:
                    new_sessions = all_sessions

                if not new_sessions:
                    if DEBUG_FLAGS["session"]:
                        print(f"[UserProfile] No new sessions since last update")
                    return

                if DEBUG_FLAGS["session"]:
                    print(f"[UserProfile] Merging {len(new_sessions)} new session(s)")

                # Use incremental update
                new_profile = await self.profile_manager.update_profile_incrementally(
                    user_id=user_id,
                    existing_profile=existing_profile,
                    new_session_states=new_sessions,
                    debug=DEBUG_FLAGS["session"],
                )
            else:
                # First profile: aggregate all available sessions
                session_states = get_user_session_states(user_id, limit=20)

                if not session_states:
                    if DEBUG_FLAGS["session"]:
                        print(f"[UserProfile] No session states available")
                    return

                if DEBUG_FLAGS["session"]:
                    print(
                        f"[UserProfile] Creating initial profile from {len(session_states)} session(s)"
                    )

                new_profile = (
                    await self.profile_manager.aggregate_sessions_into_profile(
                        user_id=user_id,
                        session_states=session_states,
                        debug=DEBUG_FLAGS["session"],
                    )
                )

            # Update in DB
            update_user_profile(user_id, new_profile)

            # Reset counter
            self._profile_update_counters[user_id] = 0

            if DEBUG_FLAGS["session"]:
                print(f"[UserProfile] ✓ Updated")
                print(f"  Risk Baseline: {new_profile.get('riskBaseline')}")
                print(f"  Risk Trend: {new_profile.get('riskTrend')}")
                print(
                    f"  Recurring Themes: {len(new_profile.get('recurringThemes', []))}"
                )
                print(
                    f"  Total Sessions Analyzed: {new_profile.get('totalSessionsAnalyzed')}"
                )

        except Exception as e:
            print(f"[UserProfile] Error updating: {e}")

    async def get_session_state(
        self, user_id: str, conversation_id: str
    ) -> Optional[Dict]:
        """Retrieve current session state."""
        from longitudinal_db_client import get_session_state

        return get_session_state(user_id, conversation_id)

    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Retrieve user profile."""
        return get_user_profile(user_id)


# Global singleton instance
_coordinator_instance: Optional[LongitudinalMemoryCoordinator] = None


def get_coordinator() -> LongitudinalMemoryCoordinator:
    """Get or create the coordinator singleton."""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = LongitudinalMemoryCoordinator()
    return _coordinator_instance
