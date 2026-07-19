"""
Centralized constants for all LLM-based components.

This file defines model hierarchies, error signals, and debug flags
used across TherapyBot, StrategyBot, RiskDetector, TaskBot, and SessionStateManager.

Each component has its own hierarchy optimized for its use case.
"""

# ═════════════════════════════════════════════════════════════════════════════
# MODEL HIERARCHIES — Component-specific model fallback order
# ═════════════════════════════════════════════════════════════════════════════

# STRATEGY BOT: Optimized for strategy classification
# Uses efficient models with Llama primary, Gemma (Google) fallback
STRATEGY_MODEL_HIERARCHY: list[tuple[str, str, str]] = [
    ("Llama 3.3 70B", "groq", "llama-3.3-70b-versatile"),
    ("Gemma 4 31B", "google", "gemma-4-31b-it"),
    ("Gemma 4 26B A4B", "google", "gemma-4-26b-a4b-it"),
    ("Llama 3.1 8B", "groq", "llama-3.1-8b-instant"),
]

# GENERAL MODEL HIERARCHY: Risk, Task, SessionState
# Uses efficient models: Gemma (Google) primary, Llama fallback
GENERAL_MODEL_HIERARCHY: list[tuple[str, str, str]] = [
    ("Gemma 4 31B", "google", "gemma-4-31b-it"),
    ("Llama 3.3 70B", "groq", "llama-3.3-70b-versatile"),
    ("Gemma 4 26B A4B", "google", "gemma-4-26b-a4b-it"),
    ("Llama 3.1 8B", "groq", "llama-3.1-8b-instant"),
]

# THERAPY BOT: Advanced conversation with Google and fallback models
# Uses premium Google models with Groq fallback for resilience
THERAPY_MODEL_HIERARCHY: list[tuple[str, str, str]] = [
    ("Gemini 2.5 Flash", "google", "gemini-2.5-flash"),
    # ("Gemini 3 Flash", "google", "gemini-3.1-flash"),
    ("Gemini 2.5 Flash Lite", "google", "gemini-2.5-flash-lite"),
    # ("Gemini 3.1 Flash Lite", "google", "gemini-3.1-flash-lite"),
    ("Llama 3.3 70B", "groq", "llama-3.3-70b-versatile"),
    ("openai/gpt-oss-120b", "groq", "openai/gpt-oss-120b"),
    ("Llama 3.1 8B", "groq", "llama-3.1-8b-instant"),
]

# ═════════════════════════════════════════════════════════════════════════════
# ERROR SIGNALS — Triggers model fallback across all components
# ═════════════════════════════════════════════════════════════════════════════

RATE_LIMIT_SIGNALS = [
    "rate_limit",
    "rate limit",
    "429",
    "too many requests",
    "request too large",
    "tokens per minute",
    "requests per minute",
    "quota exceeded",
    "resource_exhausted",
    "404",
    "not found",
    "is not found",
    "not supported",
    "model_not_found",
    "unavailable",
]

# ═════════════════════════════════════════════════════════════════════════════
# DEBUG FLAGS — Centralized control for all debug output across the system
# ═════════════════════════════════════════════════════════════════════════════

DEBUG_FLAGS = {
    "memory": False,  # Memory retrieval and creation (LongitudinalMemory)
    "risk": True,  # Risk assessment (RiskDetector)
    "session": True,  # SessionState/UserProfile updates
    "task": True,  # Task creation via TaskBot
    "agent": False,  # Agent streaming and token-level debugging (TherapyBot)
    "checkpoint": False,  # Agent checkpoint debugging (TherapyBot)
    "strategy": True,  # Strategy prediction (StrategyBot)
}
