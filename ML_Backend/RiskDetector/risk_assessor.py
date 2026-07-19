"""
RiskAssessor - Psychological risk assessment for therapy chatbot

Analyzes conversation messages to detect suicide/self-harm risk indicators.
Uses centralized model hierarchy with automatic fallback from GENERAL_MODEL_HIERARCHY.

Usage:
    assessor = RiskAssessor()
    risk = await assessor.assess(["I don't want to wake up"])
    # Returns: {"risk_level": "HIGH", "confidence": 0.91, "signals": [...], "reasoning": "..."}
"""

import asyncio
import json
import os
import sys
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import centralized constants
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from constants import GENERAL_MODEL_HIERARCHY, RATE_LIMIT_SIGNALS, DEBUG_FLAGS

# Configuration
TIMEOUT = 30
MAX_RETRIES = 3
MAX_CONTEXT_LENGTH = 4000  # Safety limit for query size

# Risk level constants
RISK_LEVELS = ["NONE", "LOW", "MODERATE", "HIGH", "IMMINENT"]

# Default response for errors
DEFAULT_RISK_OUTPUT = {
    "risk_level": "LOW",
    "confidence": 0.5,
    "signals": [],
    "reasoning": "Unable to assess - defaulting to conservative LOW risk",
}

# Deterministic safety phrases that override LLM output
IMMINENT_PHRASES = {
    "goodbye",
    "farewell",
    "see you never",
    "have a plan",
    "tonight",
    "this week",
    "when i die",
    "wrote notes",
    "said goodbye",
}

HIGH_PHRASES = {
    "want to die",
    "kill myself",
    "end it all",
    "end it",
    "hang myself",
    "i'm done",
    "don't want to live",
    "take my life",
}

MODERATE_PHRASES = {
    "don't want to wake up",
    "tired of existing",
    "tired of living",
    "wish i wasn't alive",
    "burden",
    "nobody notice",
    "numb",
    "empty",
    "nothing matters",
}


class RiskAssessor:
    """Assess psychological risk from conversation messages using centralized model hierarchy"""

    def __init__(self):
        """Initialize with first model from GENERAL_MODEL_HIERARCHY"""
        self.current_model_idx = 0
        self.llms = {}  # Cache built LLMs by model_id
        self.timeout = TIMEOUT
        self.max_retries = MAX_RETRIES

        # Initialize first model
        alias, provider, model_id = GENERAL_MODEL_HIERARCHY[0]
        self._build_llm(provider, model_id)
        print(f"[RiskAssessor] Initialized with: {alias} ({provider}/{model_id})")

    def _build_llm(self, provider: str, model_id: str):
        """Build LLM for the given provider and model"""
        try:
            if provider == "google":
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
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found")
                self.llms[model_id] = ChatGroq(
                    model=model_id,
                    temperature=0.3,
                    max_tokens=500,
                    api_key=api_key,
                )
            if DEBUG_FLAGS.get("risk"):
                print(f"[RiskAssessor] Built LLM for {provider}/{model_id}")
        except Exception as e:
            if DEBUG_FLAGS.get("risk"):
                print(
                    f"[RiskAssessor] Error building LLM for {provider}/{model_id}: {e}"
                )
            raise

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Detect if error is rate-limit or availability related"""
        err_str = str(exc).lower()
        return any(signal.lower() in err_str for signal in RATE_LIMIT_SIGNALS)

    def _build_system_prompt(self) -> str:
        """System prompt for risk assessment"""
        return """You are a clinical risk assessment AI for a mental health chatbot.
Your job is to analyze conversation messages and assess suicide/self-harm risk.

OUTPUT ONLY valid JSON, no other text.

RISK LEVELS:
- NONE: Normal emotional distress, no risk indicators
- LOW: Sadness, burnout, mild hopelessness (no SI)
- MODERATE: Passive SI (wish wasn't alive), hopelessness, numbness, withdrawal
- HIGH: Active SI (want to die), escalation, severe hopelessness
- IMMINENT: Intent, planning, goodbye language, temporal urgency

DETECT SIGNALS (extract all that apply):
hopelessness, passive_suicidal_ideation, active_suicidal_ideation,
self_hatred, emotional_numbness, social_isolation, burden_language,
temporal_urgency, goodbye_language, dissociation, emotional_escalation,
dependency_on_chatbot

OUTPUT JSON:
{
  "risk_level": "NONE|LOW|MODERATE|HIGH|IMMINENT",
  "confidence": 0.0-1.0,
  "signals": ["detected", "signals"],
  "reasoning": "brief explanation"
}"""

    async def assess(
        self,
        messages: List[str],
        memory_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assess psychological risk from conversation

        Args:
            messages: List of conversation messages
            memory_summary: Optional context (trends, history, etc)

        Returns:
            Risk assessment dict with risk_level, confidence, signals, reasoning
        """
        try:
            # Format context safely
            context = self._format_context_safe(messages, memory_summary)

            # Query LLM with hierarchy and retries
            result = await self._query_with_hierarchy(context)

            # Apply deterministic overrides for safety
            result = self._apply_overrides(result, messages)

            return result

        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return DEFAULT_RISK_OUTPUT

    def assess_sync(
        self,
        messages: List[str],
        memory_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper - use when async not available"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.assess(messages, memory_summary))
        finally:
            loop.close()

    def _format_context_safe(
        self, messages: List[str], memory_summary: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format messages and memory into context with size limiting"""

        # Build context with messages
        context_lines = ["Conversation:"]
        messages_str = ""

        for i, msg in enumerate(messages, 1):
            line = f"{i}. {msg}"
            messages_str += line + "\n"

        # Add memory if provided
        memory_str = ""
        if memory_summary:
            memory_str = "\nContext:\n"
            for key, value in memory_summary.items():
                memory_str += f"- {key}: {value}\n"

        full_context = messages_str + memory_str

        # Truncate if too long (keep recent messages, memory summary)
        if len(full_context) > MAX_CONTEXT_LENGTH:
            # Keep last N messages to fit within limit
            available = MAX_CONTEXT_LENGTH - len(memory_str) - 500

            # Work backwards from recent messages
            msg_list = messages[::-1]  # Reverse to get recent first
            kept_msgs = []
            char_count = 0

            for msg in msg_list:
                msg_line = f"- {msg}\n"
                if char_count + len(msg_line) < available:
                    kept_msgs.append(msg)
                    char_count += len(msg_line)
                else:
                    break

            kept_msgs = kept_msgs[::-1]  # Reverse back to original order
            context = "Recent messages:\n" + "\n".join(
                f"{i}. {msg}" for i, msg in enumerate(kept_msgs, 1)
            )
        else:
            context = full_context

        return context

    async def _query_with_hierarchy(self, prompt: str) -> Dict[str, Any]:
        """Query with model hierarchy and automatic fallback"""
        last_exception = None
        max_attempts = len(GENERAL_MODEL_HIERARCHY)
        models_tried = set()  # Track which models we've tried to avoid infinite loops

        while len(models_tried) < max_attempts:
            if self.current_model_idx >= len(GENERAL_MODEL_HIERARCHY):
                # Safety check: reset to next valid index
                self.current_model_idx = min(self.current_model_idx + 1, len(GENERAL_MODEL_HIERARCHY) - 1)
            
            if self.current_model_idx in models_tried:
                # We've looped back to a model we already tried, move to next
                self.current_model_idx += 1
                if self.current_model_idx >= len(GENERAL_MODEL_HIERARCHY):
                    break
                continue
            
            alias, provider, model_id = GENERAL_MODEL_HIERARCHY[self.current_model_idx]
            models_tried.add(self.current_model_idx)

            try:
                # Build or get cached LLM for this model
                if model_id not in self.llms:
                    self._build_llm(provider, model_id)

                llm = self.llms[model_id]

                if DEBUG_FLAGS.get("risk"):
                    print(
                        f"[RiskAssessor] Trying model [{self.current_model_idx}]: {alias} ({provider}/{model_id})"
                    )

                result = await self._call_llm_with_timeout(llm, prompt)
                return self._validate_output(result)

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Log the actual error for debugging
                if DEBUG_FLAGS.get("risk"):
                    print(f"[RiskAssessor] Error from {alias}: {type(e).__name__}: {e}")

                # Try to fallback to next model
                if self.current_model_idx < len(GENERAL_MODEL_HIERARCHY) - 1:
                    self.current_model_idx += 1
                    next_alias = GENERAL_MODEL_HIERARCHY[self.current_model_idx][0]
                    logger.warning(
                        f"[RiskAssessor] Error on {alias} ({type(e).__name__}) — switching to {next_alias}"
                    )
                else:
                    # No more models to try
                    logger.error(
                        f"[RiskAssessor] All {len(GENERAL_MODEL_HIERARCHY)} models exhausted."
                    )
                    logger.error(f"[RiskAssessor] Last error: {last_exception}")
                    # Return sensible default on complete failure
                    return DEFAULT_RISK_OUTPUT

        return DEFAULT_RISK_OUTPUT

    async def _call_llm_with_timeout(self, llm, prompt: str) -> Dict[str, Any]:
        """Call LLM with timeout"""
        loop = asyncio.get_event_loop()

        return await asyncio.wait_for(
            loop.run_in_executor(None, self._call_llm_sync, llm, prompt),
            timeout=self.timeout,
        )

    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from response, handling markdown code fences.
        
        Handles formats like:
        - ```json {...} ```
        - ``` {...} ```
        - Raw JSON {...}
        """
        # Try to extract from markdown code fence (```json ... ```)
        if "```json" in response_text:
            try:
                json_part = response_text.split("```json")[1]
                json_part = json_part.split("```")[0].strip()
                if json_part:
                    return json_part
            except (IndexError, ValueError):
                pass
        
        # Try to extract from generic code fence (``` ... ```)
        if "```" in response_text:
            try:
                parts = response_text.split("```")
                # Look for a part that starts with { (likely JSON)
                for part in parts:
                    stripped = part.strip()
                    if stripped.startswith("{"):
                        return stripped
                # If no { found, try the middle part (between first ``` markers)
                if len(parts) >= 3:
                    middle = parts[1].strip()
                    if middle:
                        return middle
            except (IndexError, ValueError):
                pass
        
        # Try to extract JSON object directly from the text
        # Find first { and last } 
        first_brace = response_text.find('{')
        last_brace = response_text.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_part = response_text[first_brace:last_brace+1]
            if json_part.strip():
                return json_part
        
        # Return original if no extraction worked
        return response_text.strip()

    def _call_llm_sync(self, llm, prompt: str) -> Dict[str, Any]:
        """Synchronous call to LLM"""

        # Build messages
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=prompt),
        ]

        # Invoke LLM
        response = llm.invoke(messages)
        
        # Handle multiple response formats
        if isinstance(response.content, list):
            response_text = ""
            # Try to find JSON-containing block (works for both dict and string blocks)
            for block in response.content:
                if isinstance(block, dict):
                    # Extended thinking format: {'type': 'text', 'text': '...'}
                    if block.get('type') == 'text':
                        response_text = block.get('text', '')
                        break
                elif isinstance(block, str):
                    # Direct string format (Gemma 4 26B A4B)
                    response_text = block
                    break
            
            if not response_text:
                # Fallback: look through all blocks for text content
                text_blocks = []
                for block in response.content:
                    if isinstance(block, dict):
                        # Try to extract text from dict blocks
                        text_value = block.get('text', '')
                        if not text_value:
                            text_value = block.get('thinking', '')
                        if text_value:
                            text_blocks.append(text_value)
                    elif isinstance(block, str):
                        text_blocks.append(block)
                
                if text_blocks:
                    response_text = '\n'.join(text_blocks)
        else:
            # Standard string response
            response_text = response.content.strip()

        # Extract JSON from markdown or raw text
        response_text = self._extract_json_from_response(response_text)

        if not response_text or not response_text.strip():
            if DEBUG_FLAGS.get("risk"):
                print(f"[RiskAssessor] Warning: Empty response after extraction")
            raise ValueError("No valid JSON response from model")

        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            if DEBUG_FLAGS.get("risk"):
                print(f"[RiskAssessor] JSON parse error: {e}")
                print(f"[RiskAssessor] Response text (first 200 chars): {response_text[:200]}")
            raise

        return result

    def _validate_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize LLM output"""

        # Handle both "signals" and "signals_detected" field names
        if "signals_detected" in result and "signals" not in result:
            result["signals"] = result.pop("signals_detected")

        # Ensure required fields exist
        if "risk_level" not in result:
            result["risk_level"] = "NONE"
        if "confidence" not in result:
            result["confidence"] = 0.5
        if "signals" not in result:
            result["signals"] = []
        if "reasoning" not in result:
            result["reasoning"] = ""

        # Validate risk level
        result["risk_level"] = result["risk_level"].upper()
        if result["risk_level"] not in RISK_LEVELS:
            result["risk_level"] = "LOW"

        # Clamp confidence 0-1
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

        # Ensure signals is list
        if not isinstance(result["signals"], list):
            result["signals"] = []

        result["signals"] = [str(s).lower() for s in result["signals"]]

        return result

    def _apply_overrides(
        self, llm_result: Dict[str, Any], messages: List[str]
    ) -> Dict[str, Any]:
        """Apply deterministic safety overrides to LLM result"""

        # Combine all messages for phrase checking
        all_text = " ".join(messages).lower()

        # Check for imminent phrases (highest priority)
        imminent_matches = sum(1 for phrase in IMMINENT_PHRASES if phrase in all_text)

        # Check for high phrases
        high_matches = sum(1 for phrase in HIGH_PHRASES if phrase in all_text)

        # Check for moderate phrases
        moderate_matches = sum(1 for phrase in MODERATE_PHRASES if phrase in all_text)

        # Confidence threshold for override
        OVERRIDE_CONFIDENCE = 0.90

        # Apply overrides with confidence threshold
        if imminent_matches > 0:
            # Multiple imminent phrases = strong signal
            if llm_result["confidence"] < OVERRIDE_CONFIDENCE:
                llm_result["risk_level"] = "IMMINENT"
                llm_result["confidence"] = min(
                    1.0, llm_result["confidence"] + (imminent_matches * 0.1)
                )
                if "override_imminent" not in llm_result["reasoning"]:
                    llm_result["reasoning"] += " [Imminent phrase override]"

        elif high_matches > 0:
            if llm_result["risk_level"] in ["NONE", "LOW", "MODERATE"]:
                llm_result["risk_level"] = "HIGH"
                llm_result["confidence"] = min(1.0, max(llm_result["confidence"], 0.90))
                if "override_high" not in llm_result["reasoning"]:
                    llm_result["reasoning"] += " [High phrase override]"

        elif moderate_matches > 0:
            if llm_result["risk_level"] in ["NONE", "LOW"]:
                llm_result["risk_level"] = "MODERATE"
                llm_result["confidence"] = min(1.0, max(llm_result["confidence"], 0.85))
                if "override_moderate" not in llm_result["reasoning"]:
                    llm_result["reasoning"] += " [Moderate phrase override]"

        return llm_result
