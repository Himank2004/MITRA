# import mongodb
import time
import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Points to the parent directory containing EmotionBot, StrategyBot, TherapyBot
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Import centralized constants
from constants import GENERAL_MODEL_HIERARCHY, RATE_LIMIT_SIGNALS, DEBUG_FLAGS

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain.messages import HumanMessage
import json
from typing import List
from TaskBot.utils import Task, Journey, JourneySchema, json_task
from langchain_core.prompts import PromptTemplate
from TaskBot.prompts import (
    create_task_prompt,
    journey_prompt_template,
    task_difficulty_prompt,
)


class Taskbot:
    def __init__(
        self,
        retry_count: int = 3,
        use_rag: bool = False,
    ):
        """Initialize TaskBot with first model from GENERAL_MODEL_HIERARCHY"""
        self.create_task_prompt = create_task_prompt
        self.journey_prompt_template = journey_prompt_template
        self.task_difficulty_prompt = task_difficulty_prompt
        self.retry_count = retry_count
        self.use_rag = use_rag
        self.current_model_idx = 0
        self.llms = {}  # Cache built LLMs by model_id

        # Build first model from hierarchy
        alias, provider, model_id = GENERAL_MODEL_HIERARCHY[0]
        self._build_llm(provider, model_id)
        print(f"[Taskbot] Initialized with: {alias} ({provider}/{model_id})")

    def _build_llm(self, provider: str, model_id: str):
        """Build LLM for the given provider and model"""
        try:
            if provider == "google":
                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not found")
                self.llms[model_id] = ChatGoogleGenerativeAI(
                    model=model_id,
                    temperature=0.7,
                    max_output_tokens=4096,
                    google_api_key=api_key,
                )
            else:  # groq
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found")
                self.llms[model_id] = ChatGroq(
                    model=model_id,
                    temperature=0.7,
                    max_tokens=4096,
                    api_key=api_key,
                )
            if DEBUG_FLAGS.get("task"):
                print(f"[Taskbot] Built LLM for {provider}/{model_id}")
        except Exception as e:
            if DEBUG_FLAGS.get("task"):
                print(f"[Taskbot] Error building LLM for {provider}/{model_id}: {e}")
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

    async def _invoke_with_fallback(self, prompt_template, **input_data):
        """Invoke chain with model hierarchy fallback"""
        last_exception = None
        attempts = 0
        max_attempts = len(GENERAL_MODEL_HIERARCHY)

        while attempts < max_attempts:
            alias, provider, model_id = GENERAL_MODEL_HIERARCHY[self.current_model_idx]

            try:
                llm = self._get_current_llm()
                llm_chain = prompt_template | llm

                if DEBUG_FLAGS.get("task"):
                    print(
                        f"[Taskbot] Trying model [{self.current_model_idx}]: {alias} ({provider}/{model_id})"
                    )

                result = await asyncio.to_thread(llm_chain.invoke, input_data)

                if DEBUG_FLAGS.get("task"):
                    print(f"[Taskbot] Success with {alias}")

                return result.content.strip()

            except Exception as e:
                last_exception = e

                # Check if this is a rate-limit/availability error warranting fallback
                if (
                    self._is_rate_limit_error(e)
                    and self.current_model_idx < len(GENERAL_MODEL_HIERARCHY) - 1
                ):
                    self.current_model_idx += 1
                    next_alias = GENERAL_MODEL_HIERARCHY[self.current_model_idx][0]
                    print(f"[Taskbot] Error on {alias} — switching to {next_alias}")
                    print(f"[Taskbot] Original error: {e}")
                else:
                    attempts += 1
                    print(
                        f"[Taskbot] Error on attempt {attempts}/{max_attempts}: {str(e)}"
                    )
                    if attempts < max_attempts:
                        await asyncio.sleep(2**attempts)  # Exponential backoff
                    else:
                        print(
                            f"[Taskbot] All {len(GENERAL_MODEL_HIERARCHY)} models exhausted."
                        )
                        raise Exception(
                            f"API call failed after exhausting all models."
                        ) from last_exception

        raise Exception(
            f"API call failed after exhausting model hierarchy."
        ) from last_exception

    async def create_task(self, reason, tasks: List[Task]):
        # tasks may be Task Pydantic objects or plain dicts (from db_client.get_user_tasks)
        tasks_json = json.dumps(
            [
                task.model_dump() if hasattr(task, "model_dump") else task
                for task in tasks
            ],
            ensure_ascii=False,
            indent=2,
        )

        # Optional RAG enrichment — retrieve therapy book excerpts relevant to the task goal
        if self.use_rag:
            try:
                from RAG.retreive_books import query_retriever

                rag_context, _ = await asyncio.to_thread(
                    query_retriever, f"Tasks for: {reason}"
                )
                if rag_context:
                    reason = (
                        f"[Therapeutic reference material — use silently to inform task design]\n"
                        f"{rag_context}\n"
                        f"[End reference material]\n\n"
                        f"{reason}"
                    )
            except Exception as rag_err:
                print(f"[TaskBot] RAG lookup failed (non-fatal): {rag_err}")

        # Use centralized fallback mechanism
        return await self._invoke_with_fallback(
            self.create_task_prompt, reason=reason, tasks_json=tasks_json
        )

    async def process_task_into_journey(self, new_task: Task, journeys: List[Journey]):
        tasks_json = json.dumps(new_task.model_dump(), ensure_ascii=False, indent=2)
        journeys_json = json.dumps(
            [j.model_dump() for j in journeys], ensure_ascii=False, indent=2
        )

        # Use centralized fallback mechanism
        return await self._invoke_with_fallback(
            self.journey_prompt_template,
            new_task=tasks_json,
            journeys_json=journeys_json,
        )

    async def change_task_difficulty(self, reason, task: Task):
        task_json = json.dumps(task.model_dump(), ensure_ascii=False, indent=2)

        # Use centralized fallback mechanism
        return await self._invoke_with_fallback(
            self.task_difficulty_prompt, reason=reason, task=task_json
        )


async def __main__():
    model = Taskbot(use_rag=False)
    tasks = [
        json_task(
            task_name="Morning Gratitude",
            task_type="checkmark",
            reason="Alice needs to reaffirm their love for themself",
            description="Mark your morning gratitude as complete",
            difficulty="easy",
            completed=True,
        ),
        json_task(
            task_name="Meditation for 10 minutes",
            task_type="slider",
            reason="Alice struggles with overthinking",
            description="Meditate for at least 10 minutes",
            completed=30,
            difficulty="easy",
        ),
    ]
    result = await model.create_task(
        "To help User get used to rejections and failures.", tasks
    )
    print("Result 1:", result)


if __name__ == "__main__":
    asyncio.run(__main__())
