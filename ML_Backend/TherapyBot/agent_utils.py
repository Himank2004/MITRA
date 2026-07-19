"""
Agent-specific utility functions for agent_stream.py

Helper functions for JSON cleaning, rate-limit detection, LLM instantiation.
"""

import os
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from constants import RATE_LIMIT_SIGNALS


def is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception looks like a Groq / provider rate-limit or quota error."""
    msg = str(exc).lower()
    return any(sig in msg for sig in RATE_LIMIT_SIGNALS)


def build_llm(provider: str, model_id: str, temperature: float):
    """Instantiate a LangChain chat LLM from a (provider, model_id) pair."""
    if provider == "groq":
        try:
            from langchain_groq import ChatGroq

            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                raise ValueError("GROQ_API_KEY not set — falling back to Gemini")
            return ChatGroq(model=model_id, temperature=temperature, api_key=groq_key)
        except (ImportError, ValueError) as e:
            print(
                f"[TherapyAgent] Groq unavailable ({e}), falling back to gemini-2.5-flash-lite."
            )
            provider, model_id = "google", "gemini-2.5-flash-lite"

    # google
    google_key = os.getenv("GOOGLE_API_KEY")
    if not google_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables.")
    return ChatGoogleGenerativeAI(
        model=model_id, temperature=temperature, google_api_key=google_key
    )


def clean_json_response(response: str) -> str:
    """Extract JSON from markdown code blocks or bare language-hint prefixes if present."""
    response = response.strip()

    # Remove markdown code blocks (```json ... ```)
    if response.startswith("```json"):
        # Find the closing ```
        end_idx = response.rfind("```")
        if end_idx > 0:
            response = response[7:end_idx].strip()  # Remove ```json and closing ```
    elif response.startswith("```"):
        # Generic code block
        end_idx = response.rfind("```")
        if end_idx > 0:
            response = response[3:end_idx].strip()  # Remove ``` and closing ```
    else:
        # Strip bare 'json' language hint that llama/Groq models emit without backticks
        # e.g.  json{\n  "task_name": ...  }
        response = re.sub(r"^json\s*(?=[\[{])", "", response)

    return response.strip()
