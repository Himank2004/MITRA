"""
TaskBot quality tests — 5 clinical scenarios.

Run from /home/himanshu/ML/Therapy/ML_Backend:
    python3 -m TaskBot.quality_tests

Tweak MODEL and USE_RAG below to compare outputs across configurations.

Supported MODEL values:
    "llama-8b"   — Groq llama-3.1-8b-instant    (default, fast)
    "llama-70b"  — Groq llama-3.1-70b-versatile  (higher quality, slower)
    "llama-4-scout" — Groq Llama 4 Scout ~120B MoE (high quality)
    "gemma-27b"  — Google gemma-3-27b-it          (Google API)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from TaskBot.bot import Taskbot
from TaskBot.utils import json_task

# ── configuration ────────────────────────────────────────────────────────────
# Change these two constants to test different setups.
MODEL   = "llama-8b"   # "llama-8b" | "llama-70b" | "gemma-27b"
USE_RAG = True         # True to enrich each task prompt with book excerpts

# ── colour helpers (graceful fallback if stdout is not a tty) ───────────────
_BOLD   = "\033[1m"
_CYAN   = "\033[96m"
_YELLOW = "\033[93m"
_GREEN  = "\033[92m"
_RESET  = "\033[0m"


def _header(index: int, title: str, reason: str) -> None:
    print(f"\n{'─' * 70}")
    print(f"{_BOLD}{_CYAN}🥇  Test {index} — {title}{_RESET}")
    # print(f"{_YELLOW}Model :{_RESET} {MODEL}   {_YELLOW}RAG:{_RESET} {USE_RAG}")
    print(f"{_YELLOW}Reason:{_RESET} {reason}")
    print(f"{'─' * 70}")


def _print_result(raw: str) -> None:
    """Pretty-print the LLM output; fall back to raw text if JSON parsing fails."""
    try:
        parsed = json.loads(raw)
        print(f"{_GREEN}Output (parsed):{_RESET}")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(f"{_YELLOW}Output (raw — not valid JSON):{_RESET}")
        print(raw)


# ── test definitions ─────────────────────────────────────────────────────────

TESTS = [
    # ── Test 1: Severe Apathy ───────────────────────────────────────────────
    {
        "title": "Severe Apathy",
        "reason": "User feels nothing matters and lacks energy for basic self-care.",
        "existing_tasks": [
            json_task(
                task_name="Drink a glass of water",
                task_type="checkmark",
                reason="Encourage the smallest possible act of self-care",
                description="Drink one full glass of water when you wake up.",
                difficulty="easy",
                completed=False,
            ),
        ],
    },
    # ── Test 2: Anger + Regret ──────────────────────────────────────────────
    {
        "title": "Anger + Regret",
        "reason": "User lashed out at someone they care about and feels ashamed.",
        "existing_tasks": [
            json_task(
                task_name="Anger Temp-Check",
                task_type="slider",
                reason="Track intensity of anger episodes throughout the day",
                description="Rate your anger level (0-10) three times today.",
                difficulty="easy",
                completed=0.0,
            ),
        ],
    },
    # ── Test 3: Avoidance Loop ──────────────────────────────────────────────
    {
        "title": "Avoidance Loop",
        "reason": "User keeps avoiding a task, which increases anxiety.",
        "existing_tasks": [
            json_task(
                task_name="2-Minute Start Rule",
                task_type="checkmark",
                reason="Lower the activation energy to begin the avoided task",
                description="Open the avoided task and work on it for just 2 minutes.",
                difficulty="easy",
                completed=False,
            ),
            json_task(
                task_name="Anxiety Log",
                task_type="discrete",
                reason="Build awareness of avoidance triggers",
                description="Write down what you were avoiding and what feeling arose.",
                difficulty="easy",
                completed=1,
                total_count=7,
            ),
        ],
    },
    # ── Test 4: Rejection Exposure ──────────────────────────────────────────
    {
        "title": "Rejection Exposure",
        "reason": "User wants to become less sensitive to rejection.",
        "existing_tasks": [
            json_task(
                task_name="Low-Stakes Ask",
                task_type="discrete",
                reason="Practice making small requests where refusal is acceptable",
                description="Ask a barista, colleague, or stranger for a small, harmless favour.",
                difficulty="easy",
                completed=2,
                total_count=5,
            ),
            json_task(
                task_name="Rejection Journal",
                task_type="checkmark",
                reason="Reframe rejection as data, not verdict",
                description="After a rejection, write one neutral observation about it.",
                difficulty="easy",
                completed=True,
            ),
        ],
    },
    # ── Test 5: Overthinking Spiral ─────────────────────────────────────────
    {
        "title": "Overthinking Spiral",
        "reason": "User cannot stop analyzing past conversations.",
        "existing_tasks": [
            json_task(
                task_name="Worry Window",
                task_type="checkmark",
                reason="Contain rumination to a scheduled 10-minute block",
                description="Set a 10-minute timer and allow yourself to think; then close the loop.",
                difficulty="easy",
                completed=False,
            ),
            json_task(
                task_name="Grounding 5-4-3-2-1",
                task_type="checkmark",
                reason="Interrupt the overthinking loop with a sensory exercise",
                description="Name 5 things you see, 4 you hear, 3 you can touch, 2 you smell, 1 you taste.",
                difficulty="easy",
                completed=False,
            ),
        ],
    },
]


# ── runner ───────────────────────────────────────────────────────────────────

async def run_tests() -> None:
    bot = Taskbot(model=MODEL, use_rag=USE_RAG)

    for i, test in enumerate(TESTS, start=1):
        _header(i, test["title"], test["reason"])
        try:
            result = await bot.create_task(test["reason"], test["existing_tasks"])
            _print_result(result)
        except Exception as exc:
            print(f"\033[91mERROR on Test {i}:\033[0m {exc}")

    print(f"\n{'─' * 70}")
    print(f"{_BOLD}All tests complete.{_RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
