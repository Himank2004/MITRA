"""
Session State Manager

Updates session state based on conversation turns.
Called every ~5 messages or when risk spikes.

Uses centralized model hierarchy to extract:
- risk_trend
- active_themes
- active_warning_signals
- what_helped_this_session (only when genuinely effective)
"""

import os
import sys
import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from shared_embeddings import embed_text

# Import centralized constants
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from constants import GENERAL_MODEL_HIERARCHY, RATE_LIMIT_SIGNALS, DEBUG_FLAGS


class SessionStateManager:
    """
    Maintains and updates real-time session state using centralized model hierarchy.

    Triggers:
    - Every 5 user messages
    - When risk_level jumps dramatically (e.g., MODERATE → IMMINENT)
    - At end of conversation
    """

    def __init__(self):
        """Initialize with first model from GENERAL_MODEL_HIERARCHY"""
        self.current_model_idx = 0
        self.llms = {}  # Cache built LLMs by model_id
        self.extraction_prompt = """
You are analyzing a therapy conversation snippet to extract real-time session state.

[CONVERSATION SNIPPET]
{messages}
[END SNIPPET]

Extract the following from the snippet ONLY if clearly present:

1. **risk_trend**: Is the user's risk level within this session "stable", "worsening", "improving", or "volatile"?
   Only change this if you see clear trajectory WITHIN THIS SESSION.
   
2. **active_themes**: What are 2-4 main psychological themes active RIGHT NOW?
   Examples: "perfectionism", "loneliness", "burnout", "social_anxiety"
   Be specific. Avoid generic labels like "stress" or "sadness".
   
3. **active_warning_signals**: Any concerning patterns or red flags?
   Examples: "hopelessness", "isolation_deepening", "suicidal_ideation"
   Only list if explicitly or clearly present.
   
4. **what_helped_this_session**: What techniques/approaches visibly helped the user?
   Only include if user gave explicit feedback like:
   - "that helped"
   - "I feel calmer now"
   - "that makes sense"
   Examples: "grounding technique", "gentle reflection", "validation", "humor"
   Be conservative - only include if clear.

Return ONLY valid JSON:
{{
  "risk_trend": "stable" | "worsening" | "improving" | "volatile",
  "active_themes": ["theme1", "theme2"],
  "active_warning_signals": [],
  "what_helped_this_session": ["approach1"]
}}
"""
        # Initialize first model from hierarchy
        alias, provider, model_id = GENERAL_MODEL_HIERARCHY[0]
        self._build_llm(provider, model_id)
        if DEBUG_FLAGS.get("session"):
            print(
                f"[SessionStateManager] Initialized with: {alias} ({provider}/{model_id})"
            )

    def _build_llm(self, provider: str, model_id: str):
        """Build LLM for the given provider and model"""
        try:
            if provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI

                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not found")
                self.llms[model_id] = ChatGoogleGenerativeAI(
                    model=model_id,
                    temperature=0.3,
                    max_output_tokens=500,
                    google_api_key=api_key,
                )
            else:  # groq
                from langchain_groq import ChatGroq

                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found")
                self.llms[model_id] = ChatGroq(
                    model=model_id,
                    temperature=0.3,
                    max_tokens=500,
                    api_key=api_key,
                )
            if DEBUG_FLAGS.get("session"):
                print(f"[SessionStateManager] Built LLM for {provider}/{model_id}")
        except Exception as e:
            if DEBUG_FLAGS.get("session"):
                print(
                    f"[SessionStateManager] Error building LLM for {provider}/{model_id}: {e}"
                )
            raise

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Detect if error is rate-limit or availability related"""
        err_str = str(exc).lower()
        return any(signal.lower() in err_str for signal in RATE_LIMIT_SIGNALS)

    def _get_current_llm(self):
        """Get current LLM or build it if needed"""
        alias, provider, model_id = GENERAL_MODEL_HIERARCHY[self.current_model_idx]
        if model_id not in self.llms:
            self._build_llm(provider, model_id)
        return self.llms[model_id]

    async def extract_session_state(
        self,
        messages: List[Dict],
        current_emotions: List[str],
        current_risk_level: str,
        debug: bool = False,
    ) -> Dict:
        """
        Analyze recent messages to extract session state with hierarchy fallback.

        Args:
            messages: Recent conversation messages (last 10-15)
            current_emotions: Detected emotions from current turn
            current_risk_level: Risk level ("NONE", "LOW", "MODERATE", "HIGH", "IMMINENT")
            debug: Print debug info

        Returns:
            {
                "risk_trend": "stable" | "worsening" | "improving" | "volatile",
                "active_themes": [...],
                "active_warning_signals": [...],
                "what_helped_this_session": [...]
            }
        """

        # Format messages for LLM
        msg_text = self._format_messages(messages)

        if debug or DEBUG_FLAGS.get("session"):
            print(
                f"[SessionStateManager] Extracting state from {len(messages)} messages"
            )

        last_exception = None
        attempts = 0
        max_attempts = len(GENERAL_MODEL_HIERARCHY)

        while attempts < max_attempts:
            alias, provider, model_id = GENERAL_MODEL_HIERARCHY[self.current_model_idx]

            try:
                from langchain_core.messages import HumanMessage

                llm = self._get_current_llm()

                if DEBUG_FLAGS.get("session"):
                    print(
                        f"[SessionStateManager] Trying model [{self.current_model_idx}]: {alias} ({provider}/{model_id})"
                    )

                prompt = self.extraction_prompt.format(messages=msg_text)
                response = llm.invoke([HumanMessage(content=prompt)])

                # Parse JSON response
                response_text = response.content.strip()

                # Extract JSON if wrapped in markdown
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()

                state = json.loads(response_text)

                if DEBUG_FLAGS.get("session"):
                    print(f"[SessionStateManager] Success with {alias}")
                    print(f"[SessionStateManager] Extracted state: {state}")

                return state

            except Exception as e:
                last_exception = e

                # Check if this is a rate-limit/availability error warranting fallback
                if (
                    self._is_rate_limit_error(e)
                    and self.current_model_idx < len(GENERAL_MODEL_HIERARCHY) - 1
                ):
                    self.current_model_idx += 1
                    next_alias = GENERAL_MODEL_HIERARCHY[self.current_model_idx][0]
                    print(
                        f"[SessionStateManager] Error on {alias} — switching to {next_alias}"
                    )
                    print(f"[SessionStateManager] Original error: {e}")
                else:
                    attempts += 1
                    if debug or DEBUG_FLAGS.get("session"):
                        print(
                            f"[SessionStateManager] Error on attempt {attempts}/{max_attempts}: {e}"
                        )
                    if attempts < max_attempts:
                        await asyncio.sleep(2**attempts)
                    else:
                        if debug or DEBUG_FLAGS.get("session"):
                            print(
                                f"[SessionStateManager] All {len(GENERAL_MODEL_HIERARCHY)} models exhausted."
                            )
                        break

        # Fallback: return neutral state
        if debug or DEBUG_FLAGS.get("session"):
            print(
                f"[SessionStateManager] Using neutral fallback state due to: {last_exception}"
            )

        return {
            "risk_trend": "stable",
            "active_themes": current_emotions or [],
            "active_warning_signals": [],
            "what_helped_this_session": [],
        }

    def _format_messages(self, messages: List[Dict]) -> str:
        """Format messages for LLM consumption."""
        lines = []
        for msg in messages[-15:]:  # Last 15 messages
            role = "User" if msg.get("role") == "user" else "Companion"
            content = msg.get("content", "")[:300]  # Truncate long messages
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    async def update_session_state(
        self,
        user_id: str,
        conversation_id: str,
        messages: List[Dict],
        current_emotions: List[str],
        current_risk_level: str,
        risk_confidence: float,
        debug: bool = False,
    ) -> Dict:
        """
        Update session state in database.

        On LLM failure, falls back to previous state if it exists.
        Adds 'staleness' metric so agent knows confidence level.

        Returns updated session state.
        """

        # Try to extract state from LLM
        extracted = await self.extract_session_state(
            messages, current_emotions, current_risk_level, debug=debug
        )

        try:
            from longitudinal_db_client import update_session_state, get_session_state

            # If extraction failed (has only fallback values), try to fetch previous state
            is_extraction_fallback = (
                extracted.get("risk_trend") == "stable"
                and not extracted.get("active_themes")
                and not extracted.get("active_warning_signals")
            )

            if is_extraction_fallback:
                previous_state = get_session_state(user_id, conversation_id)
                if previous_state:
                    if debug:
                        print(
                            f"[SessionStateManager] LLM failed, using previous state with increased staleness"
                        )
                    # Use previous state but mark it as stale
                    extracted = {
                        "risk_trend": previous_state.get("riskTrend", "stable"),
                        "active_themes": previous_state.get("activeThemes", []),
                        "active_warning_signals": previous_state.get(
                            "activeWarningSignals", []
                        ),
                        "what_helped_this_session": previous_state.get(
                            "whatHelpedThisSession", []
                        ),
                    }
                    staleness = previous_state.get("staleness", 0) + 1
                else:
                    staleness = 0
            else:
                # Fresh extraction succeeded
                staleness = 0

            # Build update payload
            update_data = {
                "userId": user_id,
                "conversationId": conversation_id,
                "riskTrend": extracted.get("risk_trend", "stable"),
                "activeThemes": extracted.get("active_themes", []),
                "activeWarningSignals": extracted.get("active_warning_signals", []),
                "whatHelpedThisSession": extracted.get("what_helped_this_session", []),
                "messageCount": len(messages),
                "lastDetectedEmotions": current_emotions,
                "lastRiskLevel": current_risk_level,
                "lastRiskConfidence": risk_confidence,
                "staleness": staleness,  # 0=fresh, 1=one update old, 2+=very old
                "updatedAt": datetime.utcnow().isoformat(),
            }

            result = update_session_state(user_id, conversation_id, update_data)

            if debug:
                print(
                    f"[SessionStateManager] Updated session state (staleness={staleness}): {result}"
                )

            return update_data

        except Exception as e:
            if debug:
                print(f"[SessionStateManager] DB error: {e}")
            return extracted
