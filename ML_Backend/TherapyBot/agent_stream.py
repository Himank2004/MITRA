# import os
# import asyncio
# import sys
# import threading

# # Points to the parent directory containing EmotionBot, StrategyBot, TherapyBot
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, BASE_DIR)
# from dotenv import load_dotenv
# from langchain_core.prompts import PromptTemplate
# from langchain_core.runnables.history import RunnableWithMessageHistory
# from langchain_core.prompts import (
#     ChatPromptTemplate,
#     MessagesPlaceholder,
#     SystemMessagePromptTemplate,
#     HumanMessagePromptTemplate,
#     AIMessagePromptTemplate,
# )
# from langchain_core.chat_history import BaseChatMessageHistory
# from pydantic import BaseModel, Field
# from typing import List
# from langchain_core.runnables import (
#     RunnableLambda,
#     ConfigurableFieldSpec,
#     RunnablePassthrough,
# )
# from langchain_core.messages import BaseMessage

# # from langchain.agents import AgentType
# from langchain.agents import create_agent
# from langchain.messages import SystemMessage, HumanMessage, AIMessage
# from RAG2.retriever import query_retriever
# from EmotionBot.bot import emotion_detection

# # Import from parent ML_Backend/constants.py (avoiding circular import)
# import importlib.util

# spec = importlib.util.spec_from_file_location(
#     "ml_backend_constants", os.path.join(BASE_DIR, "constants.py")
# )
# constants_module = importlib.util.module_from_spec(spec)
# spec.loader.exec_module(constants_module)
# MODEL_HIERARCHY = constants_module.THERAPY_MODEL_HIERARCHY
# DEBUG_FLAGS = constants_module.DEBUG_FLAGS
# RATE_LIMIT_SIGNALS = constants_module.RATE_LIMIT_SIGNALS

# from agent_utils import is_rate_limit_error, build_llm, clean_json_response
# from agent_tools import save_memory_to_db, create_therapy_task

# # ---------------------------------------------------------------------------
# # Strategy bot version — set STRATEGY_BOT_VERSION=1 in .env to use the
# # LLM-based v1 (gemini-2.5-flash-lite -> llama-3.1-8b-instant fallback).
# # Default is 2 (local EmoDynamiX model, no network needed).
# # ---------------------------------------------------------------------------
# _STRATEGY_BOT_VERSION = int(os.getenv("STRATEGY_BOT_VERSION", "2"))
# if _STRATEGY_BOT_VERSION == 1:
#     from StrategyBot.bot import predict_therapy_strategy

#     _load_strategy_model = None  # v1 has no model warm-up
#     print(f"[TherapyAgent] Using StrategyBot v1 (LLM-based)")
# else:
#     from StrategyBot.StrategyBotv2 import (
#         predict_therapy_strategy,
#         _load_model as _load_strategy_model,
#     )

#     print("[TherapyAgent] Using StrategyBot v2 (EmoDynamiX local model).")

# # Risk Assessment and Policy Injection
# from RiskDetector import RiskAssessor, PolicyInjector

# from MemoryBot.bot import MemoryBot
# from TherapyBot.utils import (
#     _extract_config_dict,
#     is_probably_json,
#     system_prompt,
#     user_prompt,
#     pet_prompt,
#     chat_prompt,
# )
# from TaskBot.bot import Taskbot
# from TaskBot.utils import Task
# import json
# from langgraph.checkpoint.memory import InMemorySaver
# from langchain_core.runnables import RunnableConfig

# # from langchain_core.runnables import get_current_config
# from typing import Optional, Any, Dict

# load_dotenv()

# # (Debug flags are now centralized in constants.DEBUG_FLAGS — modify them there)


# # Module-level TaskBot instance (will be initialized by TherapyAgent)
# _taskbot_instance: Optional[Taskbot] = None


# def set_taskbot_instance(taskbot: Taskbot):
#     """Set the shared TaskBot instance for use in tools."""
#     global _taskbot_instance
#     _taskbot_instance = taskbot


# def get_taskbot_instance() -> Taskbot:
#     """Get the shared TaskBot instance, creating one if it doesn't exist."""
#     global _taskbot_instance
#     if _taskbot_instance is None:
#         _taskbot_instance = Taskbot()
#     return _taskbot_instance


# def _stream_content_to_text(content: Any) -> str:
#     """Return displayable text from either legacy or structured LLM content."""
#     if isinstance(content, str):
#         return content
#     if not isinstance(content, list):
#         return ""

#     text_parts: list[str] = []
#     for block in content:
#         if isinstance(block, str):
#             text_parts.append(block)
#         elif isinstance(block, dict):
#             text = block.get("text")
#             if isinstance(text, str):
#                 text_parts.append(text)
#     return "".join(text_parts)


# # try making tool runnable? or maybe by customstate or just prompt bs


# # --------------------- CHATBOT ---------------------


# class TherapyAgent:
#     def __init__(
#         self,
#         retry_count: int = 1,
#     ):
#         self.retry_count = retry_count

#         # Debug flags are centralized in constants.DEBUG_FLAGS — modify them there for global control

#         alias, primary_provider, primary_model_id = MODEL_HIERARCHY[0]
#         print(f"[TherapyAgent] Model hierarchy ({len(MODEL_HIERARCHY)} levels):")
#         for i, (a, p, m) in enumerate(MODEL_HIERARCHY):
#             print(f"  [{i}] {a} — {p}/{m}")

#         self.conversation_llm = build_llm(
#             primary_provider, primary_model_id, temperature=0.7
#         )
#         # Initialize TaskBot instance and share it with tools
#         self.taskbot = Taskbot()
#         set_taskbot_instance(self.taskbot)
#         # Initialize RiskAssessor for safety monitoring
#         self.risk_assessor = RiskAssessor()
#         # Prompt setup

#         self.system_prompt_template = SystemMessagePromptTemplate.from_template(
#             system_prompt.template
#         )
#         self.user_prompt_template = HumanMessagePromptTemplate.from_template(
#             user_prompt.template
#         )
#         pet_prompt_template = AIMessagePromptTemplate.from_template(pet_prompt.template)
#         self.prompt = ChatPromptTemplate.from_messages(
#             [
#                 self.system_prompt_template,
#                 MessagesPlaceholder(variable_name="history"),
#                 (
#                     "user",
#                     """[INTERNAL SYSTEM CONTEXT — do NOT mention, quote, or reveal to user]
# {context}
# [END INTERNAL SYSTEM CONTEXT]

# {input}
# **Detected Emotions:** {emotion_result}
# **Reasoning for strategy:** {reasoning_for_strategy}
# **Predicted Strategy:** {strategy_result}""",
#                 ),
#             ]
#         )

#         chat_history_checkpointer = InMemorySaver()
#         # Initialize agent for tool calling
#         self.agent = create_agent(
#             tools=[save_memory_to_db, create_therapy_task],
#             model=self.conversation_llm,
#             system_prompt=system_prompt.template,
#             checkpointer=chat_history_checkpointer,
#             debug=False,
#         )
#         self.agent.checkpointer.storage.clear()

#         # Agent cache — additional hierarchy agents are built lazily on rate-limit
#         self._agent_cache: dict[int, Any] = {0: self.agent}

#         # MemoryBot — retrieves user memories from MongoDB
#         self.memory_bot = MemoryBot(top_k=5)

#         # Pre-warm StrategyBot v2 model in background (v1 has no local model to warm up)
#         if _load_strategy_model is not None:
#             threading.Thread(
#                 target=_load_strategy_model, daemon=True, name="strategy-bot-warmup"
#             ).start()
#             print("[TherapyAgent] StrategyBot v2 warm-up started in background.")
#         else:
#             print(
#                 "[TherapyAgent] StrategyBot v1 selected — no local model warm-up needed."
#             )

#         print("Agent initialized.\n")

#     def _get_agent(self, idx: int):
#         """Return the agent for the given MODEL_HIERARCHY index, building it lazily."""
#         if idx not in self._agent_cache:
#             alias, provider, model_id = MODEL_HIERARCHY[idx]
#             print(
#                 f"[TherapyAgent] Building agent [{idx}] '{alias}' ({provider}/{model_id})"
#             )
#             llm = build_llm(provider, model_id, temperature=0.7)
#             checkpointer = InMemorySaver()
#             agent = create_agent(
#                 tools=[save_memory_to_db, create_therapy_task],
#                 model=llm,
#                 system_prompt=system_prompt.template,
#                 checkpointer=checkpointer,
#                 debug=False,
#             )
#             self._agent_cache[idx] = agent
#         return self._agent_cache[idx]

#     async def chat(self, query: str, conversation_id: str, user_id: str):
#         thread_id = conversation_id

#         # retrieve full or partial history (from checkpointer)
#         config = RunnableConfig(
#             configurable={
#                 "thread_id": thread_id,
#                 "user_id": user_id,
#             }
#         )
#         checkpoint = self.agent.checkpointer.get(config)

#         # --- Cross-session history: seed from MongoDB when checkpointer is cold ---
#         history_context = ""
#         if checkpoint is None:
#             try:
#                 from TherapyBot.db_client import get_conversation_messages
#             except ImportError:
#                 from db_client import get_conversation_messages
#             try:
#                 past_msgs = get_conversation_messages(conversation_id, limit=14)
#                 if past_msgs:
#                     lines = []
#                     for m in past_msgs:
#                         role_label = "User" if m["role"] == "user" else "Companion"
#                         lines.append(f"{role_label}: {m['content'][:400]}")
#                     history_context = "\n".join(lines)
#                     print(
#                         f"[TherapyAgent] Seeded {len(past_msgs)} messages from DB "
#                         f"for conversation {conversation_id}"
#                     )
#             except Exception as e:
#                 print(f"[TherapyAgent] Could not load conversation history: {e}")

#         state = (
#             checkpoint.checkpoint.get("state", {})
#             if checkpoint and hasattr(checkpoint, "checkpoint")
#             else {}
#         )

#         messages = state.get("messages", []) if isinstance(state, dict) else []

#         recent_msgs = messages[-8:]

#         # add new message
#         recent_msgs.append(HumanMessage(content=query))

#         # concurrent async tasks (RAG, emotion, strategy, memories, risk assessment run in parallel)
#         rag_docs_task = asyncio.create_task(asyncio.to_thread(query_retriever, query))
#         emotion_task = asyncio.create_task(emotion_detection(query))
#         strategy_task = asyncio.create_task(predict_therapy_strategy(recent_msgs))
#         memory_task = asyncio.create_task(
#             asyncio.to_thread(self.memory_bot.retrieve_memories, user_id, query)
#         )
#         # Collect recent messages for risk assessment
#         recent_text = [
#             m.content if hasattr(m, "content") else str(m) for m in recent_msgs
#         ]
#         risk_task = asyncio.create_task(self.risk_assessor.assess(recent_text))

#         emotion_result, strategy_result, rag_result, memory_result, risk_result = (
#             await asyncio.gather(
#                 emotion_task, strategy_task, rag_docs_task, memory_task, risk_task
#             )
#         )
#         combined_context, rag_sources = rag_result  # (str, List[str])
#         instruct_context, info_context = memory_result
#         memory_block = self.memory_bot.format_for_prompt(instruct_context, info_context)

#         reasoning, strategy_list = strategy_result

#         # Inject risk policy into message packet
#         risk_policy = PolicyInjector.get_policy_block(
#             PolicyInjector.determine_mode(risk_result)
#         )
#         risk_mode = PolicyInjector.determine_mode(risk_result)

#         # Debug: Risk assessment results
#         if DEBUG_FLAGS["risk"]:
#             print(f"\n[RISK ASSESSMENT]")
#             print(f"  Level: {risk_result.get('risk_level')}")
#             print(f"  Confidence: {risk_result.get('confidence'):.2%}")
#             print(f"  Mode: {risk_mode}")
#             signals = risk_result.get("signals", [])
#             if signals:
#                 print(f"  Signals Detected: {', '.join(signals)}")
#             else:
#                 print(f"  Signals Detected: None")
#             if risk_policy:
#                 print(f"  Policy Injected: Yes")
#             else:
#                 print(f"  Policy Injected: No")
#             print()

#         response = ""
#         tool_events: list = []  # accumulate tool calls made this turn
#         attempts, successful, last_exception = 0, False, None
#         current_idx = 0  # current position in MODEL_HIERARCHY

#         while attempts < self.retry_count and not successful:
#             active_agent = self._get_agent(current_idx)
#             try:
#                 # Combine all retrieved info into a single user message string
#                 message_text = f"""
# [INTERNAL SYSTEM CONTEXT — silent background knowledge from resources that may be helpful, do NOT mention, quote, or refer to this in your reply, never tell the user about these excerpts or that you consulted any books]
# {combined_context}
# [END INTERNAL SYSTEM CONTEXT]
# {f'''
# [PREVIOUS CONVERSATION HISTORY — context from a prior session, do NOT reference that you are reading logs]
# {history_context}
# [END PREVIOUS CONVERSATION HISTORY]
# ''' if history_context else ''}{f'''
# [USER MEMORY]
# {memory_block}
# [END USER MEMORY]
# ''' if memory_block else ''}{f'''
# [SAFETY ASSESSMENT]
# Risk Level: {risk_result.get('risk_level')} (confidence: {risk_result.get('confidence'):.2f})
# Mode: {risk_mode}
# {risk_policy if risk_policy else ''}
# [END SAFETY ASSESSMENT]
# ''' if risk_policy else ''}
#                 User Message: {query}

#                 **Detected Emotions:** {emotion_result}
#                 **Reasoning for strategy:** {reasoning}
#                 **Predicted Strategy:** {strategy_list}

#                 Use these details if you need to call tools :- conversation_id: {conversation_id}, user_id: {user_id}
#                 """

#                 inside_json_block = False  # suppress ``` fenced blocks

#                 pre_tool_buffer: list[str] = []
#                 tool_call_detected: bool = False
#                 seen_tool_result: bool = False

#                 async for token, metadata in active_agent.astream(
#                     {"messages": [{"role": "user", "content": message_text}]},
#                     stream_mode="messages",
#                     config=config,
#                 ):
#                     if DEBUG_FLAGS["agent"]:
#                         token_type = type(token).__name__
#                         print(f"[TOKEN DEBUG] Received token type: {token_type}")

#                     # -------------------------------
#                     # 1. Skip tool call / function call messages
#                     # -------------------------------
#                     if hasattr(token, "additional_kwargs"):
#                         if "function_call" in token.additional_kwargs:
#                             if DEBUG_FLAGS["agent"]:
#                                 print(
#                                     "[TOKEN DEBUG] Filtered: Function call detected in additional_kwargs"
#                                 )
#                             continue

#                     # -------------------------------
#                     # 2. Capture + skip tool call metadata
#                     # -------------------------------
#                     if getattr(token, "tool_calls", None):
#                         for tc in token.tool_calls:
#                             if tc.get("name"):  # only complete (non-chunk) entries
#                                 tool_events.append(
#                                     {
#                                         "name": tc.get("name"),
#                                         "args": tc.get("args", {}),
#                                         "id": tc.get("id"),
#                                     }
#                                 )
#                         # Discard any preamble text buffered before this tool call
#                         tool_call_detected = True
#                         pre_tool_buffer.clear()
#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 f"[TOKEN DEBUG] Captured tool_calls: {token.tool_calls}"
#                             )
#                         continue

#                     if getattr(token, "tool_call_chunks", None):
#                         # Also discard preamble on partial tool call chunks
#                         tool_call_detected = True
#                         pre_tool_buffer.clear()
#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 f"[TOKEN DEBUG] Filtered: tool_call_chunks found: {token.tool_call_chunks}"
#                             )
#                         continue

#                     # -------------------------------
#                     # 3. Capture tool result + skip from stream
#                     # -------------------------------
#                     if hasattr(token, "tool_call_id") and getattr(
#                         token, "tool_call_id", None
#                     ):
#                         tc_id = token.tool_call_id
#                         tc_content = getattr(token, "content", "")
#                         for ev in tool_events:
#                             if ev.get("id") == tc_id:
#                                 ev["result"] = tc_content
#                         seen_tool_result = (
#                             True  # next AI text = final response, stream it
#                         )
#                         if DEBUG_FLAGS["agent"]:
#                             print(f"[TOKEN DEBUG] Captured tool result id={tc_id}")
#                         continue

#                     if getattr(token, "name", None) and getattr(
#                         token, "tool_call_id", None
#                     ):
#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 "[TOKEN DEBUG] Filtered: token has name and tool_call_id"
#                             )
#                         continue

#                     # -------------------------------
#                     # 4. Extract text
#                     # -------------------------------
#                     text = _stream_content_to_text(getattr(token, "content", None))

#                     if DEBUG_FLAGS["agent"]:
#                         print(
#                             f"[TOKEN DEBUG] Extracted text: {repr(text[:100])} (length: {len(text)})"
#                         )

#                     # -------------------------------
#                     # 5. Skip empty text
#                     # -------------------------------
#                     if not text.strip():
#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 "[TOKEN DEBUG] Filtered: Empty or whitespace-only text"
#                             )
#                         continue

#                     # -------------------------------
#                     # 6. JSON BLOCK SUPPRESSION LOGIC
#                     # -------------------------------

#                     # Detect the start of a ``` fenced block
#                     if text.strip().startswith("```") or text.strip().endswith("```"):
#                         inside_json_block = not inside_json_block

#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 f"[TOKEN DEBUG] JSON block toggle. Now inside_json_block={inside_json_block}"
#                             )

#                         # Do NOT stream this fence line
#                         continue

#                     # If inside JSON block → suppress EVERYTHING
#                     if inside_json_block:
#                         if DEBUG_FLAGS["agent"]:
#                             print("[TOKEN DEBUG] Filtered: inside JSON fenced block")
#                         continue

#                     # # -------------------------------
#                     # # 7. Skip JSON-like fragments (brace chunks)
#                     # # -------------------------------
#                     # if is_probably_json(text):
#                     #     if self.agent_debug:
#                     #         print("[TOKEN DEBUG] Filtered: Detected as JSON/markdown artifact")
#                     #     continue

#                     # -------------------------------
#                     # 8. FINALLY: yield valid assistant text
#                     # -------------------------------
#                     if seen_tool_result:
#                         # Text after a tool result = the real final response → stream live
#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 f"[TOKEN DEBUG] YIELDING (post-tool): {repr(text[:50])}..."
#                             )
#                         yield text
#                         response += text
#                     else:
#                         # Text before any tool result → might be silent reasoning/preamble
#                         # Buffer it; discard if a tool call fires, flush at end if not
#                         if DEBUG_FLAGS["agent"]:
#                             print(
#                                 f"[TOKEN DEBUG] BUFFERING (pre-tool): {repr(text[:50])}..."
#                             )
#                         pre_tool_buffer.append(text)

#                 # Flush buffer for normal (no-tool-call) turns
#                 if pre_tool_buffer and not tool_call_detected:
#                     buffered = "".join(pre_tool_buffer)
#                     if DEBUG_FLAGS["agent"]:
#                         print(
#                             f"[TOKEN DEBUG] FLUSHING buffer ({len(buffered)} chars, no tool call)"
#                         )
#                     yield buffered
#                     response += buffered
#                 elif pre_tool_buffer and tool_call_detected:
#                     if DEBUG_FLAGS["agent"]:
#                         print(
#                             f"[TOKEN DEBUG] DISCARDING buffer ({len(pre_tool_buffer)} chunks) — tool call was made"
#                         )

#                 # async for event in self.agent.astream(
#                 #     {"messages": [{"role": "user", "content": message_text}]},
#                 #     config=config,
#                 #     stream_mode="updates",
#                 # ):
#                 #     print(event)

#                 successful = True

#             except Exception as e:
#                 last_exception = e
#                 # Rate-limit → advance to the next model in the hierarchy
#                 if is_rate_limit_error(e) and current_idx < len(MODEL_HIERARCHY) - 1:
#                     next_idx = current_idx + 1
#                     next_alias = MODEL_HIERARCHY[next_idx][0]
#                     print(
#                         f"[TherapyAgent] Rate-limit on '{MODEL_HIERARCHY[current_idx][0]}' — "
#                         f"switching to '{next_alias}'."
#                     )
#                     print(f"[TherapyAgent] Original error: {e}")
#                     # Copy checkpointer history so next agent has context
#                     try:
#                         next_agent = self._get_agent(next_idx)
#                         next_agent.checkpointer.storage = dict(
#                             self._get_agent(current_idx).checkpointer.storage
#                         )
#                     except Exception:
#                         pass
#                     current_idx = next_idx
#                 else:
#                     attempts += 1
#                     print(f"Error on attempt {attempts}: {e}")
#                     await asyncio.sleep(2**attempts)
#         if DEBUG_FLAGS["checkpoint"]:
#             self.debug_agent(user_id, conversation_id)
#         if not successful:
#             raise Exception("Failed after retries.") from last_exception

#         # Yield metadata so app.py can persist the turn and forward tool events
#         yield {
#             "__metadata__": {
#                 "emotions": emotion_result,
#                 "strategies": strategy_list,
#                 "strategy_reasoning": reasoning,
#                 "tool_events": tool_events,
#                 "rag_sources": rag_sources,
#                 "risk_assessment": {
#                     "risk_level": risk_result.get("risk_level"),
#                     "confidence": risk_result.get("confidence"),
#                     "signals": risk_result.get("signals", []),
#                     "risk_mode": risk_mode,
#                 },
#             }
#         }

#     # ── Journal reflection: skips emotion/RAG/strategy detection ────────────
#     async def chat_with_journal_context(
#         self,
#         journal_title: str,
#         journal_content: str,
#         conversation_id: str,
#         user_id: str,
#         task_context: str = "",
#     ):
#         """Start a reflection conversation seeded with a journal entry.

#         Emotion detection, RAG retrieval, and strategy prediction are all skipped;
#         strategy is hard-wired to 'Others'.  Memories are still retrieved so the
#         companion can personalise the opening response.  The stream contract is
#         identical to ``chat()``.
#         """
#         thread_id = conversation_id
#         config = RunnableConfig(
#             configurable={"thread_id": thread_id, "user_id": user_id}
#         )

#         # Retrieve user memories (skip emotion / RAG / strategy)
#         memory_result = await asyncio.to_thread(
#             self.memory_bot.retrieve_memories, user_id, journal_content[:300]
#         )
#         instruct_context, info_context = memory_result
#         memory_block = self.memory_bot.format_for_prompt(instruct_context, info_context)

#         emotion_result = "Neutral"
#         reasoning = "Journal reflection — open-ended exploration."
#         strategy_list = ["Others"]
#         rag_sources: list = []

#         task_section = (
#             f"\n[Linked Task]\n{task_context}\n" if task_context.strip() else ""
#         )

#         message_text = f"""[JOURNAL REFLECTION — the user has shared a personal journal entry and would like to reflect on it with you.  Read it carefully and open a warm, non-judgmental conversation.  Do NOT summarise the entry back to the user verbatim; instead invite them to explore their feelings at their own pace.]

# Journal Title: {journal_title or "(untitled)"}
# ---
# {journal_content}
# ---
# {task_section}{f'''
# [USER MEMORY]
# {memory_block}
# [END USER MEMORY]
# ''' if memory_block else ''}
# User message: I'd like to reflect on what I just wrote in my journal.

# **Detected Emotions:** {emotion_result}
# **Reasoning for strategy:** {reasoning}
# **Predicted Strategy:** {strategy_list}

# Use these details if you need to call tools :- conversation_id: {conversation_id}, user_id: {user_id}
# """

#         response = ""
#         tool_events: list = []
#         attempts, successful, last_exception = 0, False, None
#         current_idx = 0

#         while attempts < self.retry_count and not successful:
#             active_agent = self._get_agent(current_idx)
#             try:
#                 pre_tool_buffer: list[str] = []
#                 tool_call_detected: bool = False
#                 seen_tool_result: bool = False
#                 inside_json_block: bool = False

#                 async for token, metadata in active_agent.astream(
#                     {"messages": [{"role": "user", "content": message_text}]},
#                     stream_mode="messages",
#                     config=config,
#                 ):
#                     if hasattr(token, "additional_kwargs"):
#                         if "function_call" in token.additional_kwargs:
#                             continue

#                     if getattr(token, "tool_calls", None):
#                         for tc in token.tool_calls:
#                             if tc.get("name"):
#                                 tool_events.append(
#                                     {
#                                         "name": tc.get("name"),
#                                         "args": tc.get("args", {}),
#                                         "id": tc.get("id"),
#                                     }
#                                 )
#                         tool_call_detected = True
#                         pre_tool_buffer.clear()
#                         continue

#                     if getattr(token, "tool_call_chunks", None):
#                         tool_call_detected = True
#                         pre_tool_buffer.clear()
#                         continue

#                     if hasattr(token, "tool_call_id") and getattr(
#                         token, "tool_call_id", None
#                     ):
#                         tc_id = token.tool_call_id
#                         tc_content = getattr(token, "content", "")
#                         for ev in tool_events:
#                             if ev.get("id") == tc_id:
#                                 ev["result"] = tc_content
#                         seen_tool_result = True
#                         continue

#                     if getattr(token, "name", None) and getattr(
#                         token, "tool_call_id", None
#                     ):
#                         continue

#                     text = _stream_content_to_text(getattr(token, "content", None))
#                     if not text.strip():
#                         continue

#                     if text.strip().startswith("```") or text.strip().endswith("```"):
#                         inside_json_block = not inside_json_block
#                         continue
#                     if inside_json_block:
#                         continue

#                     if seen_tool_result:
#                         yield text
#                         response += text
#                     else:
#                         pre_tool_buffer.append(text)

#                 if pre_tool_buffer and not tool_call_detected:
#                     buffered = "".join(pre_tool_buffer)
#                     yield buffered
#                     response += buffered

#                 successful = True

#             except Exception as e:
#                 last_exception = e
#                 if is_rate_limit_error(e) and current_idx < len(MODEL_HIERARCHY) - 1:
#                     next_idx = current_idx + 1
#                     print(
#                         f"[TherapyAgent] Rate-limit on '{MODEL_HIERARCHY[current_idx][0]}' — "
#                         f"switching to '{MODEL_HIERARCHY[next_idx][0]}'."
#                     )
#                     try:
#                         next_agent = self._get_agent(next_idx)
#                         next_agent.checkpointer.storage = dict(
#                             self._get_agent(current_idx).checkpointer.storage
#                         )
#                     except Exception:
#                         pass
#                     current_idx = next_idx
#                 else:
#                     attempts += 1
#                     await asyncio.sleep(2**attempts)

#         if not successful:
#             raise Exception("Failed after retries.") from last_exception

#         yield {
#             "__metadata__": {
#                 "emotions": emotion_result,
#                 "strategies": strategy_list,
#                 "strategy_reasoning": "",
#                 "tool_events": tool_events,
#                 "rag_sources": rag_sources,
#             }
#         }

#     def debug_agent(self, user_id: str, conversation_id: str):
#         thread_id = conversation_id
#         config = RunnableConfig(
#             configurable={"thread_id": thread_id, "user_id": user_id}
#         )
#         checkpoints = self.agent.checkpointer.list(config)
#         print(f"\n\n--- Agent Debug for Thread: {thread_id} ---")
#         try:
#             for i, checkpoint in enumerate(checkpoints):
#                 print(f"\n[Checkpoint {i}]")
#                 print(f"  Timestamp: {checkpoint.checkpoint.get('ts')}")
#                 print(f"  Thread TS: {checkpoint.checkpoint.get('thread_ts')}")
#                 state = checkpoint.checkpoint.get("checkpoint", {}).get("state")
#                 if state:
#                     print(f"  State Messages: {state.get('messages')}")
#                 else:
#                     print("  State: (Empty)")
#         except Exception as e:
#             print(f"Error while debugging checkpoints: {e}")

#         print("--- End Agent Debug ---")


# # --------------------- TEST ---------------------
# if __name__ == "__main__":

#     async def main():
#         bot = TherapyAgent()

#         while True:
#             query = input("\n>> User: ")
#             if query.lower() == "exit":
#                 break
#             print(">> Pet: ")
#             response = ""
#             async for res in bot.chat(query, "test-conversation-id", "test-user-id"):
#                 response += res
#                 print(res, end="")

#     asyncio.run(main())















"""TherapyAgent streaming orchestration module.

This file coordinates the main therapy chatbot pipeline. It combines:
- conversation history,
- retrieval-augmented generation (RAG),
- emotion detection,
- strategy prediction,
- memory retrieval,
- risk assessment,
- tool calling,
- model fallback,
- and streamed response delivery.

The comments are intentionally detailed so the purpose of each major line,
block, and control-flow decision is easier to understand while studying.
"""
import os
import asyncio
import sys
import threading

# Resolve the project root so sibling packages such as EmotionBot, StrategyBot,
# TherapyBot, TaskBot, and MemoryBot can be imported reliably.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
)
from langchain_core.chat_history import BaseChatMessageHistory
from pydantic import BaseModel, Field
from typing import List
from langchain_core.runnables import (
    RunnableLambda,
    ConfigurableFieldSpec,
    RunnablePassthrough,
)
from langchain_core.messages import BaseMessage

# from langchain.agents import AgentType
from langchain.agents import create_agent
from langchain.messages import SystemMessage, HumanMessage, AIMessage
from RAG2.retriever import query_retriever
from EmotionBot.bot import emotion_detection

# Import from parent ML_Backend/constants.py (avoiding circular import)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "ml_backend_constants", os.path.join(BASE_DIR, "constants.py")
)
constants_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(constants_module)
MODEL_HIERARCHY = constants_module.THERAPY_MODEL_HIERARCHY
DEBUG_FLAGS = constants_module.DEBUG_FLAGS
RATE_LIMIT_SIGNALS = constants_module.RATE_LIMIT_SIGNALS

from agent_utils import is_rate_limit_error, build_llm, clean_json_response
from agent_tools import save_memory_to_db, create_therapy_task

# ---------------------------------------------------------------------------
# Strategy bot version — set STRATEGY_BOT_VERSION=1 in .env to use the
# LLM-based v1 (gemini-2.5-flash-lite -> llama-3.1-8b-instant fallback).
# Default is 2 (local EmoDynamiX model, no network needed).
# ---------------------------------------------------------------------------
_STRATEGY_BOT_VERSION = int(os.getenv("STRATEGY_BOT_VERSION", "2"))
if _STRATEGY_BOT_VERSION == 1:
    from StrategyBot.bot import predict_therapy_strategy

    _load_strategy_model = None  # v1 has no model warm-up
    print(f"[TherapyAgent] Using StrategyBot v1 (LLM-based)")
else:
    from StrategyBot.StrategyBotv2 import (
        predict_therapy_strategy,
        _load_model as _load_strategy_model,
    )

    print("[TherapyAgent] Using StrategyBot v2 (EmoDynamiX local model).")

# Risk Assessment and Policy Injection
from RiskDetector import RiskAssessor, PolicyInjector

from MemoryBot.bot import MemoryBot
from TherapyBot.utils import (
    _extract_config_dict,
    is_probably_json,
    system_prompt,
    user_prompt,
    pet_prompt,
    chat_prompt,
)
from TaskBot.bot import Taskbot
from TaskBot.utils import Task
import json
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.runnables import RunnableConfig

# from langchain_core.runnables import get_current_config
from typing import Optional, Any, Dict

# Load API keys and configuration values from the project's .env file.
load_dotenv()

# (Debug flags are now centralized in constants.DEBUG_FLAGS — modify them there)


# Module-level TaskBot instance (will be initialized by TherapyAgent)
_taskbot_instance: Optional[Taskbot] = None


def set_taskbot_instance(taskbot: Taskbot):
    """Set the shared TaskBot instance for use in tools."""
    global _taskbot_instance
    _taskbot_instance = taskbot


def get_taskbot_instance() -> Taskbot:
    """Get the shared TaskBot instance, creating one if it doesn't exist."""
    global _taskbot_instance
    if _taskbot_instance is None:
        _taskbot_instance = Taskbot()
    return _taskbot_instance


def _stream_content_to_text(content: Any) -> str:
    """Return displayable text from either legacy or structured LLM content."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text")
            if isinstance(text, str):
                text_parts.append(text)
    return "".join(text_parts)


# The helper functions and class below implement the chatbot runtime.
# They prepare context, call supporting models/tools, and stream the final answer.


# --------------------- MAIN CHATBOT IMPLEMENTATION ---------------------


# Main orchestrator responsible for building the agent and handling conversations.
class TherapyAgent:
    def __init__(
        self,
        retry_count: int = 1,
    ):
        # Store how many non-rate-limit failures should be retried.
        self.retry_count = retry_count

        # Debug flags are centralized in constants.DEBUG_FLAGS — modify them there for global control

        alias, primary_provider, primary_model_id = MODEL_HIERARCHY[0]
        print(f"[TherapyAgent] Model hierarchy ({len(MODEL_HIERARCHY)} levels):")
        for i, (a, p, m) in enumerate(MODEL_HIERARCHY):
            print(f"  [{i}] {a} — {p}/{m}")

        # Build the primary conversational model from the first hierarchy entry.
        self.conversation_llm = build_llm(
            primary_provider, primary_model_id, temperature=0.7
        )
        # Initialize TaskBot instance and share it with tools
        # Create one TaskBot and share it with tool functions to avoid repeated setup.
        self.taskbot = Taskbot()
        set_taskbot_instance(self.taskbot)
        # Initialize RiskAssessor for safety monitoring
        # Create the safety classifier used to choose an appropriate response policy.
        self.risk_assessor = RiskAssessor()
        # Prompt setup

        self.system_prompt_template = SystemMessagePromptTemplate.from_template(
            system_prompt.template
        )
        self.user_prompt_template = HumanMessagePromptTemplate.from_template(
            user_prompt.template
        )
        pet_prompt_template = AIMessagePromptTemplate.from_template(pet_prompt.template)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                self.system_prompt_template,
                MessagesPlaceholder(variable_name="history"),
                (
                    "user",
                    """[INTERNAL SYSTEM CONTEXT — do NOT mention, quote, or reveal to user]
{context}
[END INTERNAL SYSTEM CONTEXT]

{input}
**Detected Emotions:** {emotion_result}
**Reasoning for strategy:** {reasoning_for_strategy}
**Predicted Strategy:** {strategy_result}""",
                ),
            ]
        )

        chat_history_checkpointer = InMemorySaver()
        # Initialize agent for tool calling
        # Build the LangChain/LangGraph agent that can call memory and task tools.
        self.agent = create_agent(
            tools=[save_memory_to_db, create_therapy_task],
            model=self.conversation_llm,
            system_prompt=system_prompt.template,
            checkpointer=chat_history_checkpointer,
            debug=False,
        )
        self.agent.checkpointer.storage.clear()

        # Agent cache — additional hierarchy agents are built lazily on rate-limit
        self._agent_cache: dict[int, Any] = {0: self.agent}

        # MemoryBot — retrieves user memories from MongoDB
        # Retrieve up to five relevant long-term memories for each user query.
        self.memory_bot = MemoryBot(top_k=5)

        # Pre-warm StrategyBot v2 model in background (v1 has no local model to warm up)
        if _load_strategy_model is not None:
            threading.Thread(
                target=_load_strategy_model, daemon=True, name="strategy-bot-warmup"
            ).start()
            print("[TherapyAgent] StrategyBot v2 warm-up started in background.")
        else:
            print(
                "[TherapyAgent] StrategyBot v1 selected — no local model warm-up needed."
            )

        print("Agent initialized.\n")

    def _get_agent(self, idx: int):
        """Return the agent for the given MODEL_HIERARCHY index, building it lazily."""
        if idx not in self._agent_cache:
            alias, provider, model_id = MODEL_HIERARCHY[idx]
            print(
                f"[TherapyAgent] Building agent [{idx}] '{alias}' ({provider}/{model_id})"
            )
            llm = build_llm(provider, model_id, temperature=0.7)
            checkpointer = InMemorySaver()
            agent = create_agent(
                tools=[save_memory_to_db, create_therapy_task],
                model=llm,
                system_prompt=system_prompt.template,
                checkpointer=checkpointer,
                debug=False,
            )
            self._agent_cache[idx] = agent
        return self._agent_cache[idx]

    async def chat(self, query: str, conversation_id: str, user_id: str):
        """Process one user message and stream text chunks plus final metadata."""
        # LangGraph uses thread_id to keep checkpoints isolated per conversation.
        thread_id = conversation_id

        # retrieve full or partial history (from checkpointer)
        # Pass conversation- and user-scoped values to the agent and its tools.
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "user_id": user_id,
            }
        )
        # Read the latest in-memory checkpoint, if this conversation is already warm.
        checkpoint = self.agent.checkpointer.get(config)

        # --- Cross-session history: seed from MongoDB when checkpointer is cold ---
        history_context = ""
        if checkpoint is None:
            try:
                from TherapyBot.db_client import get_conversation_messages
            except ImportError:
                from db_client import get_conversation_messages
            try:
                past_msgs = get_conversation_messages(conversation_id, limit=14)
                if past_msgs:
                    lines = []
                    for m in past_msgs:
                        role_label = "User" if m["role"] == "user" else "Companion"
                        lines.append(f"{role_label}: {m['content'][:400]}")
                    history_context = "\n".join(lines)
                    print(
                        f"[TherapyAgent] Seeded {len(past_msgs)} messages from DB "
                        f"for conversation {conversation_id}"
                    )
            except Exception as e:
                print(f"[TherapyAgent] Could not load conversation history: {e}")

        state = (
            checkpoint.checkpoint.get("state", {})
            if checkpoint and hasattr(checkpoint, "checkpoint")
            else {}
        )

        messages = state.get("messages", []) if isinstance(state, dict) else []

        recent_msgs = messages[-8:]

        # add new message
        # Add the current user message so strategy and risk models see fresh context.
        recent_msgs.append(HumanMessage(content=query))

        # concurrent async tasks (RAG, emotion, strategy, memories, risk assessment run in parallel)
        # Run blocking RAG retrieval in a worker thread so it does not block the event loop.
        rag_docs_task = asyncio.create_task(asyncio.to_thread(query_retriever, query))
        # Detect the emotional tone of the current message concurrently.
        emotion_task = asyncio.create_task(emotion_detection(query))
        # Predict which therapeutic strategy is most suitable for the recent dialogue.
        strategy_task = asyncio.create_task(predict_therapy_strategy(recent_msgs))
        # Fetch relevant long-term memories without blocking other analysis tasks.
        memory_task = asyncio.create_task(
            asyncio.to_thread(self.memory_bot.retrieve_memories, user_id, query)
        )
        # Collect recent messages for risk assessment
        recent_text = [
            m.content if hasattr(m, "content") else str(m) for m in recent_msgs
        ]
        # Assess safety risk using the recent conversation text.
        risk_task = asyncio.create_task(self.risk_assessor.assess(recent_text))

        emotion_result, strategy_result, rag_result, memory_result, risk_result = (
            await asyncio.gather(
                emotion_task, strategy_task, rag_docs_task, memory_task, risk_task
            )
        )
        combined_context, rag_sources = rag_result  # (str, List[str])
        instruct_context, info_context = memory_result
        memory_block = self.memory_bot.format_for_prompt(instruct_context, info_context)

        reasoning, strategy_list = strategy_result

        # Inject risk policy into message packet
        risk_policy = PolicyInjector.get_policy_block(
            PolicyInjector.determine_mode(risk_result)
        )
        risk_mode = PolicyInjector.determine_mode(risk_result)

        # Debug: Risk assessment results
        if DEBUG_FLAGS["risk"]:
            print(f"\n[RISK ASSESSMENT]")
            print(f"  Level: {risk_result.get('risk_level')}")
            print(f"  Confidence: {risk_result.get('confidence'):.2%}")
            # print(f"  Rag: {rag_docs_task.result()[1] if rag_docs_task.done() else 'N/A'}")
            print(f"  Mode: {risk_mode}")
            signals = risk_result.get("signals", [])
            if signals:
                print(f"  Signals Detected: {', '.join(signals)}")
            else:
                print(f"  Signals Detected: None")
            if risk_policy:
                print(f"  Policy Injected: Yes")
            else:
                print(f"  Policy Injected: No")
            print()

        response = ""
        tool_events: list = []  # accumulate tool calls made this turn
        attempts, successful, last_exception = 0, False, None
        current_idx = 0  # current position in MODEL_HIERARCHY

        # Keep trying until the request succeeds or the configured retry budget is exhausted.
        while attempts < self.retry_count and not successful:
            active_agent = self._get_agent(current_idx)
            try:
                # Combine all retrieved info into a single user message string
                message_text = f"""
                    [INTERNAL SYSTEM CONTEXT — silent background knowledge from resources that may be helpful, do NOT mention, quote, or refer to this in your reply, never tell the user about these excerpts or that you consulted any books]
                    {combined_context}
                    [END INTERNAL SYSTEM CONTEXT]
                    {f'''
                    [PREVIOUS CONVERSATION HISTORY — context from a prior session, do NOT reference that you are reading logs]
                    {history_context}
                    [END PREVIOUS CONVERSATION HISTORY]
                    ''' if history_context else ''}{f'''
                    [USER MEMORY]
                    {memory_block}
                    [END USER MEMORY]
                    ''' if memory_block else ''}{f'''
                    [SAFETY ASSESSMENT]
                    Risk Level: {risk_result.get('risk_level')} (confidence: {risk_result.get('confidence'):.2f})
                    Mode: {risk_mode}
                    {risk_policy if risk_policy else ''}
                    [END SAFETY ASSESSMENT]
                    ''' if risk_policy else ''}
                User Message: {query}

                **Detected Emotions:** {emotion_result}
                **Reasoning for strategy:** {reasoning}
                **Predicted Strategy:** {strategy_list}

                Use these details if you need to call tools :- conversation_id: {conversation_id}, user_id: {user_id}
                """

                inside_json_block = False  # suppress ``` fenced blocks

                pre_tool_buffer: list[str] = []
                tool_call_detected: bool = False
                seen_tool_result: bool = False

                # Stream model/tool events incrementally instead of waiting for a full response.
                async for token, metadata in active_agent.astream(
                    {"messages": [{"role": "user", "content": message_text}]},
                    stream_mode="messages",
                    config=config,
                ):
                    if DEBUG_FLAGS["agent"]:
                        token_type = type(token).__name__
                        print(f"[TOKEN DEBUG] Received token type: {token_type}")

                    # -------------------------------
                    # 1. Skip tool call / function call messages
                    # -------------------------------
                    if hasattr(token, "additional_kwargs"):
                        if "function_call" in token.additional_kwargs:
                            if DEBUG_FLAGS["agent"]:
                                print(
                                    "[TOKEN DEBUG] Filtered: Function call detected in additional_kwargs"
                                )
                            continue

                    # -------------------------------
                    # 2. Capture + skip tool call metadata
                    # -------------------------------
                    if getattr(token, "tool_calls", None):
                        for tc in token.tool_calls:
                            if tc.get("name"):  # only complete (non-chunk) entries
                                tool_events.append(
                                    {
                                        "name": tc.get("name"),
                                        "args": tc.get("args", {}),
                                        "id": tc.get("id"),
                                    }
                                )
                        # Discard any preamble text buffered before this tool call
                        tool_call_detected = True
                        pre_tool_buffer.clear()
                        if DEBUG_FLAGS["agent"]:
                            print(
                                f"[TOKEN DEBUG] Captured tool_calls: {token.tool_calls}"
                            )
                        continue

                    if getattr(token, "tool_call_chunks", None):
                        # Also discard preamble on partial tool call chunks
                        tool_call_detected = True
                        pre_tool_buffer.clear()
                        if DEBUG_FLAGS["agent"]:
                            print(
                                f"[TOKEN DEBUG] Filtered: tool_call_chunks found: {token.tool_call_chunks}"
                            )
                        continue

                    # -------------------------------
                    # 3. Capture tool result + skip from stream
                    # -------------------------------
                    if hasattr(token, "tool_call_id") and getattr(
                        token, "tool_call_id", None
                    ):
                        tc_id = token.tool_call_id
                        tc_content = getattr(token, "content", "")
                        for ev in tool_events:
                            if ev.get("id") == tc_id:
                                ev["result"] = tc_content
                        seen_tool_result = (
                            True  # next AI text = final response, stream it
                        )
                        if DEBUG_FLAGS["agent"]:
                            print(f"[TOKEN DEBUG] Captured tool result id={tc_id}")
                        continue

                    if getattr(token, "name", None) and getattr(
                        token, "tool_call_id", None
                    ):
                        if DEBUG_FLAGS["agent"]:
                            print(
                                "[TOKEN DEBUG] Filtered: token has name and tool_call_id"
                            )
                        continue

                    # -------------------------------
                    # 4. Extract text
                    # -------------------------------
                    text = _stream_content_to_text(getattr(token, "content", None))

                    if DEBUG_FLAGS["agent"]:
                        print(
                            f"[TOKEN DEBUG] Extracted text: {repr(text[:100])} (length: {len(text)})"
                        )

                    # -------------------------------
                    # 5. Skip empty text
                    # -------------------------------
                    if not text.strip():
                        if DEBUG_FLAGS["agent"]:
                            print(
                                "[TOKEN DEBUG] Filtered: Empty or whitespace-only text"
                            )
                        continue

                    # -------------------------------
                    # 6. JSON BLOCK SUPPRESSION LOGIC
                    # -------------------------------

                    # Detect the start of a ``` fenced block
                    if text.strip().startswith("```") or text.strip().endswith("```"):
                        inside_json_block = not inside_json_block

                        if DEBUG_FLAGS["agent"]:
                            print(
                                f"[TOKEN DEBUG] JSON block toggle. Now inside_json_block={inside_json_block}"
                            )

                        # Do NOT stream this fence line
                        continue

                    # If inside JSON block → suppress EVERYTHING
                    if inside_json_block:
                        if DEBUG_FLAGS["agent"]:
                            print("[TOKEN DEBUG] Filtered: inside JSON fenced block")
                        continue

                    # # -------------------------------
                    # # 7. Skip JSON-like fragments (brace chunks)
                    # # -------------------------------
                    # if is_probably_json(text):
                    #     if self.agent_debug:
                    #         print("[TOKEN DEBUG] Filtered: Detected as JSON/markdown artifact")
                    #     continue

                    # -------------------------------
                    # 8. FINALLY: yield valid assistant text
                    # -------------------------------
                    if seen_tool_result:
                        # Text after a tool result = the real final response → stream live
                        if DEBUG_FLAGS["agent"]:
                            print(
                                f"[TOKEN DEBUG] YIELDING (post-tool): {repr(text[:50])}..."
                            )
                        yield text
                        response += text
                    else:
                        # Text before any tool result → might be silent reasoning/preamble
                        # Buffer it; discard if a tool call fires, flush at end if not
                        if DEBUG_FLAGS["agent"]:
                            print(
                                f"[TOKEN DEBUG] BUFFERING (pre-tool): {repr(text[:50])}..."
                            )
                        pre_tool_buffer.append(text)

                # Flush buffer for normal (no-tool-call) turns
                if pre_tool_buffer and not tool_call_detected:
                    buffered = "".join(pre_tool_buffer)
                    if DEBUG_FLAGS["agent"]:
                        print(
                            f"[TOKEN DEBUG] FLUSHING buffer ({len(buffered)} chars, no tool call)"
                        )
                    yield buffered
                    response += buffered
                elif pre_tool_buffer and tool_call_detected:
                    if DEBUG_FLAGS["agent"]:
                        print(
                            f"[TOKEN DEBUG] DISCARDING buffer ({len(pre_tool_buffer)} chunks) — tool call was made"
                        )

                # async for event in self.agent.astream(
                #     {"messages": [{"role": "user", "content": message_text}]},
                #     config=config,
                #     stream_mode="updates",
                # ):
                #     print(event)

                # Reaching this point means streaming completed without raising an exception.
                successful = True

            except Exception as e:
                last_exception = e
                # Rate-limit → advance to the next model in the hierarchy
                if is_rate_limit_error(e) and current_idx < len(MODEL_HIERARCHY) - 1:
                    next_idx = current_idx + 1
                    next_alias = MODEL_HIERARCHY[next_idx][0]
                    print(
                        f"[TherapyAgent] Rate-limit on '{MODEL_HIERARCHY[current_idx][0]}' — "
                        f"switching to '{next_alias}'."
                    )
                    print(f"[TherapyAgent] Original error: {e}")
                    # Copy checkpointer history so next agent has context
                    try:
                        next_agent = self._get_agent(next_idx)
                        next_agent.checkpointer.storage = dict(
                            self._get_agent(current_idx).checkpointer.storage
                        )
                    except Exception:
                        pass
                    current_idx = next_idx
                else:
                    attempts += 1
                    print(f"Error on attempt {attempts}: {e}")
                    await asyncio.sleep(2**attempts)
        if DEBUG_FLAGS["checkpoint"]:
            self.debug_agent(user_id, conversation_id)
        if not successful:
            raise Exception("Failed after retries.") from last_exception

        # Yield metadata so app.py can persist the turn and forward tool events
        # Send non-text metadata last so the caller can persist analytics and tool traces.
        yield {
            "__metadata__": {
                "emotions": emotion_result,
                "strategies": strategy_list,
                "strategy_reasoning": reasoning,
                "tool_events": tool_events,
                "rag_sources": rag_sources,
                "risk_assessment": {
                    "risk_level": risk_result.get("risk_level"),
                    "confidence": risk_result.get("confidence"),
                    "signals": risk_result.get("signals", []),
                    "risk_mode": risk_mode,
                },
            }
        }

    # ── Journal reflection: skips emotion/RAG/strategy detection ────────────
    async def chat_with_journal_context(
        self,
        journal_title: str,
        journal_content: str,
        conversation_id: str,
        user_id: str,
        task_context: str = "",
    ):
        """Start a reflection conversation seeded with a journal entry.

        Emotion detection, RAG retrieval, and strategy prediction are all skipped;
        strategy is hard-wired to 'Others'.  Memories are still retrieved so the
        companion can personalise the opening response.  The stream contract is
        identical to ``chat()``.
        """
        thread_id = conversation_id
        config = RunnableConfig(
            configurable={"thread_id": thread_id, "user_id": user_id}
        )

        # Retrieve user memories (skip emotion / RAG / strategy)
        memory_result = await asyncio.to_thread(
            self.memory_bot.retrieve_memories, user_id, journal_content[:300]
        )
        instruct_context, info_context = memory_result
        memory_block = self.memory_bot.format_for_prompt(instruct_context, info_context)

        emotion_result = "Neutral"
        reasoning = "Journal reflection — open-ended exploration."
        strategy_list = ["Others"]
        rag_sources: list = []

        task_section = (
            f"\n[Linked Task]\n{task_context}\n" if task_context.strip() else ""
        )

        message_text = f"""[JOURNAL REFLECTION — the user has shared a personal journal entry and would like to reflect on it with you.  Read it carefully and open a warm, non-judgmental conversation.  Do NOT summarise the entry back to the user verbatim; instead invite them to explore their feelings at their own pace.]

        Journal Title: {journal_title or "(untitled)"}
        ---
        {journal_content}
        ---
        {task_section}{f'''
        [USER MEMORY]
        {memory_block}
        [END USER MEMORY]
        ''' if memory_block else ''}
        User message: I'd like to reflect on what I just wrote in my journal.

        **Detected Emotions:** {emotion_result}
        **Reasoning for strategy:** {reasoning}
        **Predicted Strategy:** {strategy_list}

        Use these details if you need to call tools :- conversation_id: {conversation_id}, user_id: {user_id}
        """

        response = ""
        tool_events: list = []
        attempts, successful, last_exception = 0, False, None
        current_idx = 0

        while attempts < self.retry_count and not successful:
            active_agent = self._get_agent(current_idx)
            try:
                pre_tool_buffer: list[str] = []
                tool_call_detected: bool = False
                seen_tool_result: bool = False
                inside_json_block: bool = False

                async for token, metadata in active_agent.astream(
                    {"messages": [{"role": "user", "content": message_text}]},
                    stream_mode="messages",
                    config=config,
                ):
                    if hasattr(token, "additional_kwargs"):
                        if "function_call" in token.additional_kwargs:
                            continue

                    if getattr(token, "tool_calls", None):
                        for tc in token.tool_calls:
                            if tc.get("name"):
                                tool_events.append(
                                    {
                                        "name": tc.get("name"),
                                        "args": tc.get("args", {}),
                                        "id": tc.get("id"),
                                    }
                                )
                        tool_call_detected = True
                        pre_tool_buffer.clear()
                        continue

                    if getattr(token, "tool_call_chunks", None):
                        tool_call_detected = True
                        pre_tool_buffer.clear()
                        continue

                    if hasattr(token, "tool_call_id") and getattr(
                        token, "tool_call_id", None
                    ):
                        tc_id = token.tool_call_id
                        tc_content = getattr(token, "content", "")
                        for ev in tool_events:
                            if ev.get("id") == tc_id:
                                ev["result"] = tc_content
                        seen_tool_result = True
                        continue

                    if getattr(token, "name", None) and getattr(
                        token, "tool_call_id", None
                    ):
                        continue

                    text = _stream_content_to_text(getattr(token, "content", None))
                    if not text.strip():
                        continue

                    if text.strip().startswith("```") or text.strip().endswith("```"):
                        inside_json_block = not inside_json_block
                        continue
                    if inside_json_block:
                        continue

                    if seen_tool_result:
                        yield text
                        response += text
                    else:
                        pre_tool_buffer.append(text)

                if pre_tool_buffer and not tool_call_detected:
                    buffered = "".join(pre_tool_buffer)
                    yield buffered
                    response += buffered

                successful = True

            except Exception as e:
                last_exception = e
                if is_rate_limit_error(e) and current_idx < len(MODEL_HIERARCHY) - 1:
                    next_idx = current_idx + 1
                    print(
                        f"[TherapyAgent] Rate-limit on '{MODEL_HIERARCHY[current_idx][0]}' — "
                        f"switching to '{MODEL_HIERARCHY[next_idx][0]}'."
                    )
                    try:
                        next_agent = self._get_agent(next_idx)
                        next_agent.checkpointer.storage = dict(
                            self._get_agent(current_idx).checkpointer.storage
                        )
                    except Exception:
                        pass
                    current_idx = next_idx
                else:
                    attempts += 1
                    await asyncio.sleep(2**attempts)

        if not successful:
            raise Exception("Failed after retries.") from last_exception

        yield {
            "__metadata__": {
                "emotions": emotion_result,
                "strategies": strategy_list,
                "strategy_reasoning": "",
                "tool_events": tool_events,
                "rag_sources": rag_sources,
            }
        }

    def debug_agent(self, user_id: str, conversation_id: str):
        """Print stored checkpoints for diagnosing conversation-state issues."""
        thread_id = conversation_id
        config = RunnableConfig(
            configurable={"thread_id": thread_id, "user_id": user_id}
        )
        checkpoints = self.agent.checkpointer.list(config)
        print(f"\n\n--- Agent Debug for Thread: {thread_id} ---")
        try:
            for i, checkpoint in enumerate(checkpoints):
                print(f"\n[Checkpoint {i}]")
                print(f"  Timestamp: {checkpoint.checkpoint.get('ts')}")
                print(f"  Thread TS: {checkpoint.checkpoint.get('thread_ts')}")
                state = checkpoint.checkpoint.get("checkpoint", {}).get("state")
                if state:
                    print(f"  State Messages: {state.get('messages')}")
                else:
                    print("  State: (Empty)")
        except Exception as e:
            print(f"Error while debugging checkpoints: {e}")

        print("--- End Agent Debug ---")


# --------------------- LOCAL MANUAL TEST RUNNER ---------------------
if __name__ == "__main__":

    # This block runs only when executing this file directly, not when importing it.

    async def main():
        bot = TherapyAgent()

        while True:
            query = input("\n>> User: ")
            if query.lower() == "exit":
                break
            print(">> Pet: ")
            response = ""
            async for res in bot.chat(query, "test-conversation-id", "test-user-id"):
                response += res
                print(res, end="")

    asyncio.run(main())
