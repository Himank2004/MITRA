"""
StrategyBotv2 — EmoDynamiX-backed strategy predictor.

Replaces the LLM-based StrategyBot with the local RobertaHeterogeneousGraph
checkpoint (EmoDynamiX-v2).  Accepts a list of LangChain messages, converts
them to EmoDynamiX's dialogue format, and returns a single strategy string.

Drop-in async interface compatible with agent_stream.py:
    strategy_task = asyncio.create_task(predict_therapy_strategy(recent_msgs))
    reasoning, strategy = await strategy_task
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
STRATEGY_BOT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(STRATEGY_BOT_DIR, "EmoDynamiX-v2")
CHECKPOINT_PATH = os.path.join(STRATEGY_BOT_DIR, "checkpoint-2600.pth")

# Valid strategy names in the ESConv model vocabulary
VALID_STRATEGIES = {
    "Reflection of feelings",
    "Self-disclosure",
    "Question",
    "Affirmation and Reassurance",
    "Providing Suggestions",
    "Restatement or Paraphrasing",
    "Information",
    "Others",
}


# ---------------------------------------------------------------------------
# Lazy model loader — instantiated once, shared across all requests
# ---------------------------------------------------------------------------
_model = None
_MODEL_UNAVAILABLE = object()  # sentinel: load was attempted but failed


def _load_model():
    global _model
    if _model is not None:
        return _model

    if not os.path.isdir(REPO_DIR):
        raise RuntimeError(
            f"EmoDynamiX-v2 repo not found at {REPO_DIR}. "
            "Clone it: git clone https://github.com/cw-wan/EmoDynamiX-v2"
        )
    if not os.path.isfile(CHECKPOINT_PATH):
        raise RuntimeError(f"Checkpoint not found: {CHECKPOINT_PATH}")

    # Suppress noisy transformers warnings
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

    # Prevent transformers from trying (and failing) to import TensorFlow
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("USE_JAX", "0")

    # Force CPU — prevents "Cannot copy out of meta tensor" on systems where
    # CUDA is visible but the checkpoint was saved with meta-device init.
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    # EmoDynamiX opens 'data/esconv/strategies.json' with a bare relative path
    prev_cwd = os.getcwd()
    print("[StrategyBotv2] Model loading.")
    try:
        if REPO_DIR not in sys.path:
            sys.path.insert(0, REPO_DIR)
        os.chdir(REPO_DIR)
        from EmoDynamiX import EmoDynamiX  # noqa: PLC0415
        _model = EmoDynamiX(dataset="esconv-preprocessed", checkpoint_path=CHECKPOINT_PATH)
    except (NotImplementedError, RuntimeError) as e:
        # Graceful fallback: model cannot load on this device (e.g. meta-tensor
        # error on CPU-only machines with certain PyTorch builds).  Strategy
        # prediction will return a safe default instead of crashing the request.
        print(
            f"[StrategyBotv2] WARNING: model failed to load ({type(e).__name__}: {e}). "
            "Strategy prediction will fall back to 'Question'."
        )
        _model = _MODEL_UNAVAILABLE
    finally:
        os.chdir(prev_cwd)

    if _model is not _MODEL_UNAVAILABLE:
        print("[StrategyBotv2] Model loaded.")
    return _model


# ---------------------------------------------------------------------------
# Message conversion helpers
# ---------------------------------------------------------------------------


def _sanitize_strategy(strategy: str) -> str:
    """Map any unknown/combined strategy string to 'Others'."""
    return strategy if strategy in VALID_STRATEGIES else "Others"


def _extract_user_text(content: str) -> str:
    """
    agent_stream.py sends a bloated message_text as the HumanMessage.
    It embeds the raw query after a 'User Message:' marker followed by
    emotion/strategy metadata lines.  Extract just the clean user utterance.

    Falls back to the full content if the marker is not found (e.g., plain
    messages in tests or direct API calls).
    """
    m = re.search(r"User Message:\s*(.*)", content, re.DOTALL)
    if m:
        raw = m.group(1)
        # Strip trailing metadata lines injected by agent_stream
        raw = re.split(
            r"\n\s*\*\*Detected Emotions|"
            r"\n\s*\*\*Reasoning for strategy|"
            r"\n\s*Use these details",
            raw,
        )[0]
        return raw.strip()
    return content.strip()


def _extract_strategy_from_human_msg(content: str) -> str:
    """
    Recover the strategy that was used for the AI response that followed
    a given HumanMessage.

    agent_stream.py embeds the predicted strategy in the HumanMessage as:
        **Predicted Strategy:** <strategy name>

    The stored value may be:
      - A single strategy:           "Providing Suggestions"
      - A plain comma-sep list:      "Providing Suggestions, Others"
      - A Python list repr (v1):     "['Providing Suggestions', 'Others']"

    In all cases, return the first strategy that appears in VALID_STRATEGIES.
    If none match exactly, return the raw first entry rather than "Others".
    """
    m = re.search(r"\*\*Predicted Strategy:\*\*\s*(.+)", content)
    if not m:
        return "Others"

    raw = m.group(1).strip()

    # 1. Try to extract quoted items from a Python list repr: ['A', 'B']
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", raw)
    if quoted:
        candidates = [s.strip() for s in quoted]
    else:
        # 2. Plain comma-separated string (or single value)
        candidates = [s.strip() for s in raw.split(",")]

    # Return the first candidate that is a known valid strategy
    for c in candidates:
        if c in VALID_STRATEGIES:
            return c

    # No exact match — return raw first entry instead of silently mapping to "Others"
    return candidates[0] if candidates else "Others"


def langchain_to_dialogue(messages) -> List[dict]:
    """
    Convert a list of LangChain HumanMessage / AIMessage objects into the
    [{speaker, text, ?strategy}] format that EmoDynamiX expects.

    HumanMessage handling
    ---------------------
    agent_stream stores the *full* message_text (RAG context, emotion, strategy
    metadata, tool hints) as the HumanMessage content.  We strip all of that
    and keep only the clean user utterance after the 'User Message:' marker.

    AIMessage handling
    ------------------
    The strategy actually used for each AI response is NOT stored separately,
    but it IS recoverable: agent_stream embeds it in the *preceding*
    HumanMessage as '**Predicted Strategy:** <name>'.  We look backwards to
    find that HumanMessage and extract the strategy from it.

    AIMessages that have no text content (pure tool-call messages) are skipped
    because they carry no meaningful therapist utterance for EmoDynamiX.

    SystemMessage / ToolMessage are skipped — not meaningful for strategy.
    """
    from langchain_core.messages import HumanMessage, AIMessage  # local import to avoid circular deps

    turns = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            clean_text = _extract_user_text(str(msg.content))
            turns.append({"speaker": "usr", "text": clean_text})

        elif isinstance(msg, AIMessage):
            # Skip pure tool-call stubs (no actual therapist utterance)
            text = str(msg.content).strip()
            if not text:
                continue

            # Recover the strategy from the nearest preceding HumanMessage
            strategy = "Others"
            for j in range(i - 1, -1, -1):
                if isinstance(messages[j], HumanMessage):
                    strategy = _extract_strategy_from_human_msg(str(messages[j].content))
                    break

            turns.append({"speaker": "sys", "strategy": strategy, "text": text})

        # SystemMessage and ToolMessage are skipped — not meaningful for strategy
    return turns


# ---------------------------------------------------------------------------
# Core prediction
# ---------------------------------------------------------------------------

def predict_strategy_sync(messages) -> str:
    """
    Synchronous prediction.  Returns a single strategy string.

    Parameters
    ----------
    messages : list
        LangChain message objects (HumanMessage / AIMessage) **or** a list of
        pre-built dialogue dicts [{speaker, text, ?strategy}].
    """
    model = _load_model()

    # Model failed to load on this machine — return a sensible default so the
    # rest of the pipeline (emotion, RAG, therapy response) keeps working.
    if model is _MODEL_UNAVAILABLE:
        return "Question"

    # Accept either LangChain messages or pre-built dicts
    if messages and isinstance(messages[0], dict):
        turns = messages
    else:
        turns = langchain_to_dialogue(messages)

    if not turns:
        return "Question"  # safe default for empty input

    # Sanitize any strategy strings that aren't in the model's vocabulary
    sanitized = []
    for t in turns:
        if t["speaker"] == "sys":
            t = {**t, "strategy": _sanitize_strategy(t.get("strategy", "Others"))}
        sanitized.append(t)

    # Run prediction with cwd inside the repo (relative path requirement)
    prev_cwd = os.getcwd()
    try:
        os.chdir(REPO_DIR)
        output = model.predict(sanitized)
    finally:
        os.chdir(prev_cwd)

    return output["next_strategy"]


# ---------------------------------------------------------------------------
# Async wrapper — drop-in replacement for predict_therapy_strategy()
# returns (reasoning: str, strategy: str) to match the existing interface
# ---------------------------------------------------------------------------

async def predict_therapy_strategy(messages) -> Tuple[str, str]:
    """
    Async wrapper around predict_strategy_sync.
    Returns (reasoning, strategy) — reasoning is empty string since
    EmoDynamiX does not produce chain-of-thought text.

    Usage in agent_stream.py (no changes needed):
        strategy_task = asyncio.create_task(predict_therapy_strategy(recent_msgs))
        reasoning, strategy = await strategy_task
    """
    strategy = await asyncio.to_thread(predict_strategy_sync, messages)
    return ("", strategy)


# ---------------------------------------------------------------------------
# Class interface (for use outside agent_stream)
# ---------------------------------------------------------------------------

class StrategyBotV2:
    """
    Object-oriented wrapper.  Call .predict(messages) for synchronous use,
    or await .apredict(messages) for async use.
    """

    def __init__(self):
        # Eagerly load model on construction
        _load_model()

    def predict(self, messages) -> str:
        """Return a single strategy string."""
        return predict_strategy_sync(messages)

    async def apredict(self, messages) -> str:
        return await asyncio.to_thread(predict_strategy_sync, messages)


# ---------------------------------------------------------------------------
# Quick CLI test — simulates the exact message format produced by agent_stream
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from langchain_core.messages import HumanMessage, AIMessage

    # agent_stream wraps each user turn in a large message_text blob.
    # Turn 1: user message with injected metadata (strategy = Question)
    turn1_human = HumanMessage(content="""\
[INTERNAL SYSTEM CONTEXT — silent background knowledge from resources that may be helpful, do NOT mention, quote, or refer to this in your reply, never tell the user about these excerpts or that you consulted any books]
... (RAG excerpts about relationship grief) ...
[END INTERNAL SYSTEM CONTEXT]

                User Message: I don't want to have anything to do with her again.

                **Detected Emotions:** sadness: 0.82, anger: 0.11
                **Reasoning for strategy:** User seems hurt and needs space to express their feelings.
                **Predicted Strategy:** Question

                Use these details if you need to call tools :- conversation_id: conv_abc123, user_id: user_xyz
                """)

    # Turn 1: AI response (driven by "Question" strategy above)
    turn1_ai = AIMessage(content="Do you feel that her actions can be remedied, or do you think this is the end for you both?")

    # Turn 2: user follow-up (strategy = Reflection of feelings)
    turn2_human = HumanMessage(content="""\
[INTERNAL SYSTEM CONTEXT — silent background knowledge from resources that may be helpful, do NOT mention, quote, or refer to this in your reply, never tell the user about these excerpts or that you consulted any books]
... (RAG excerpts about moving on after heartbreak) ...
[END INTERNAL SYSTEM CONTEXT]

                User Message: I just want to move on with my life.

                **Detected Emotions:** sadness: 0.74, neutral: 0.18
                **Reasoning for strategy:** User is expressing a desire for closure and forward momentum.
                **Predicted Strategy:** Reflection of feelings

                Use these details if you need to call tools :- conversation_id: conv_abc123, user_id: user_xyz
                """)

    # Turn 2: AI response (driven by "Reflection of feelings" strategy above)
    turn2_ai = AIMessage(content="It sounds like you're carrying a lot of pain right now, and wanting to move forward makes complete sense.")

    # Turn 3: current user message — what we predict for next
    turn3_human = HumanMessage(content="""\
[INTERNAL SYSTEM CONTEXT — silent background knowledge from resources that may be helpful, do NOT mention, quote, or refer to this in your reply, never tell the user about these excerpts or that you consulted any books]
... (RAG excerpts about trust and love after loss) ...
[END INTERNAL SYSTEM CONTEXT]

                User Message: I don't think I can love her again.

                **Detected Emotions:** sadness: 0.79, disgust: 0.09
                **Reasoning for strategy:** User is expressing hopelessness about the relationship.
                **Predicted Strategy:** Affirmation and Reassurance

                Use these details if you need to call tools :- conversation_id: conv_abc123, user_id: user_xyz
                """)

    recent_msgs = [turn1_human, turn1_ai, turn2_human, turn2_ai, turn3_human]

    async def main():
        reasoning, strategy = await predict_therapy_strategy(recent_msgs)
        print(f"Predicted : {strategy}")
        print(f"Expected  : Affirmation and Reassurance")
        print()
        # Also show what langchain_to_dialogue extracted, for debugging
        print("--- Dialogue fed to EmoDynamiX ---")
        for turn in langchain_to_dialogue(recent_msgs):
            strat = f"  [strategy={turn['strategy']}]" if turn["speaker"] == "sys" else ""
            print(f"  [{turn['speaker']}]{strat} {turn['text'][:80]}")

    asyncio.run(main())
