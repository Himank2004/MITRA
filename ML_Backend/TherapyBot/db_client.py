"""
MongoDB client for TherapyBot ML Backend.
Connects directly to MongoDB to persist conversations, messages, tasks, and memories
without going through the Node backend API.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/therapy_app")

_client: Optional[MongoClient] = None


def get_db():
    """Return the MongoDB database, creating the client once."""
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            _client.admin.command("ping")
            logger.info("[DB] Connected to MongoDB at %s", MONGO_URI)
        except ConnectionFailure as exc:
            logger.error("[DB] Could not connect to MongoDB: %s", exc)
            raise

    # Extract DB name from the URI  (last path segment, strip query string)
    db_name = MONGO_URI.rstrip("/").split("/")[-1].split("?")[0] or "therapy_app"
    return _client[db_name]


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def ensure_conversation(user_id: str, conversation_id: str, first_message: str = "") -> str:
    """
    Update lastMessageAt / title on an existing Conversation document.
    The conversation is always pre-created by the Node backend (POST /api/conversations)
    before the first message is sent, so we never upsert here.
    Returns conversation_id unchanged.
    """
    try:
        db = get_db()
        from bson import ObjectId
        now = datetime.now(timezone.utc)

        max_title_len = 50
        title = (
            first_message[:max_title_len] + "…"
            if len(first_message) > max_title_len
            else first_message or "New Conversation"
        )

        try:
            oid = ObjectId(conversation_id)
        except Exception:
            logger.error("[DB] Invalid conversation_id '%s'", conversation_id)
            return conversation_id

        db.conversations.update_one(
            {"_id": oid},
            {
                "$set": {
                    "lastMessageAt": now,
                    "updatedAt": now,
                },
            },
        )
        return conversation_id
    except PyMongoError as exc:
        logger.error("[DB] ensure_conversation error: %s", exc)
        return conversation_id


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def save_message(
    conversation_id: str,
    role: str,
    content: str,
    emotion: list = None,
    strategy_used: list = None,
    strategy_reasoning: str = "",
    tool_calls: dict = None,
    rag_sources: list = None,
):
    """Persist a single chat message."""
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        db.messages.insert_one(
            {
                "conversationId": conversation_id,
                "role": role,
                "content": content,
                "emotion": emotion or [],
                "strategyUsed": strategy_used or [],
                "strategyReasoning": strategy_reasoning or "",
                "toolCalls": tool_calls or {},
                "ragSources": rag_sources or [],
                "createdAt": now,
                "updatedAt": now,
            }
        )
    except PyMongoError as exc:
        logger.error("[DB] save_message error: %s", exc)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def save_task(user_id: str, conversation_id: str, task_data: dict):
    """Persist an AI-created therapy task."""
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        # Store userId as ObjectId so it matches the Mongoose schema
        try:
            uid = ObjectId(user_id)
        except Exception:
            uid = user_id
        db.tasks.insert_one(
            {
                "userId": uid,
                "conversationId": conversation_id,
                "taskName": task_data.get("task_name", "Therapy Task"),
                "description": task_data.get("description", ""),
                "reasonForCreation": task_data.get("reason_for_creation", ""),
                "taskType": task_data.get("task_type", "checkmark"),
                "difficulty": task_data.get("difficulty", "easy"),
                "progress": 0,
                "totalCount": task_data.get("total_count", None),
                # Support both 'recurring' and 'recurring_hours' keys from TaskBot output
                "recurringHours": task_data.get("recurring", task_data.get("recurring_hours", 0)),
                "nextDueAt": None,
                "createdBy": "companion",
                "completed": False,
                "completedAt": None,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        logger.info("[DB] Task saved for user %s", user_id)
    except PyMongoError as exc:
        logger.error("[DB] save_task error: %s", exc)


def get_user_tasks(user_id: str) -> list:
    """
    Return the user's active (non-completed) tasks as a list of Task-compatible dicts
    (snake_case keys matching TaskBot's Task model).
    Queries by both string and ObjectId userId to handle historical data.
    """
    try:
        db = get_db()
        # Build a filter that matches userId stored as either string or ObjectId
        try:
            oid = ObjectId(user_id)
            uid_filter = {"$or": [{"userId": user_id}, {"userId": oid}]}
        except Exception:
            uid_filter = {"userId": user_id}
        docs = list(
            db.tasks.find(
                {"$and": [uid_filter, {"completed": False}]},
                {"_id": 0, "taskName": 1, "description": 1, "taskType": 1,
                 "reasonForCreation": 1, "difficulty": 1, "recurringHours": 1,
                 "progress": 1, "totalCount": 1},
            ).sort("createdAt", -1).limit(20)
        )
        # Map camelCase DB fields → snake_case Task model fields
        tasks = []
        for d in docs:
            tasks.append({
                "task_name": d.get("taskName", ""),
                "task_type": d.get("taskType", "checkmark"),
                "reason_for_task_creation": d.get("reasonForCreation", ""),
                "description": d.get("description", ""),
                "difficulty": d.get("difficulty", "easy"),
                "recurring": d.get("recurringHours", 0),
                "completed": d.get("progress", 0),
                "total_count": d.get("totalCount"),
            })
        return tasks
    except PyMongoError as exc:
        logger.error("[DB] get_user_tasks error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

def save_memory(user_id: str, conversation_id: str, content: str, memory_type: str = "info", embedding: list = None):
    """Persist an AI-captured user memory, storing a pre-computed embedding if supplied."""
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        try:
            uid = ObjectId(user_id)
        except Exception:
            uid = user_id
        db.memories.insert_one(
            {
                "userId": uid,
                "conversationId": conversation_id,
                "memoryType": memory_type,
                "content": content,
                "embedding": embedding or [],
                "createdAt": now,
                "updatedAt": now,
            }
        )
        logger.info("[DB] Memory (%s) saved for user %s", memory_type, user_id)
    except PyMongoError as exc:
        logger.error("[DB] save_memory error: %s", exc)


def get_memories_for_user(user_id: str) -> Tuple[List[dict], List[dict]]:
    """
    Return (instruct_memories, info_memories) for a user.
    - instruct_memories: ALL behaviour-instruction memories (returned always)
    - info_memories:     ALL factual memories with _id + embedding so caller
                         can rank by relevance and backfill missing embeddings.
    """
    try:
        db = get_db()
        try:
            oid = ObjectId(user_id)
            uid_filter = {"$or": [{"userId": user_id}, {"userId": oid}]}
        except Exception:
            uid_filter = {"userId": user_id}

        instruct_docs = list(
            db.memories.find(
                {**uid_filter, "memoryType": "instruct"},
                {"_id": 0, "content": 1},
            ).sort("createdAt", 1)
        )
        info_docs = list(
            db.memories.find(
                {**uid_filter, "memoryType": "info"},
                {"_id": 1, "content": 1, "embedding": 1},
            ).sort("createdAt", -1).limit(100)
        )
        return instruct_docs, info_docs
    except PyMongoError as exc:
        logger.error("[DB] get_memories_for_user error: %s", exc)
        return [], []


def update_memory_embedding(memory_id, embedding: list):
    """Backfill the embedding field for an existing memory document."""
    try:
        db = get_db()
        db.memories.update_one(
            {"_id": memory_id},
            {"$set": {"embedding": embedding, "updatedAt": datetime.now(timezone.utc)}},
        )
    except PyMongoError as exc:
        logger.error("[DB] update_memory_embedding error: %s", exc)


def get_conversation_messages(conversation_id: str, limit: int = 20) -> List[dict]:
    """
    Return the last `limit` messages for a conversation, in chronological order.
    Each dict has 'role' and 'content' keys.
    """
    try:
        db = get_db()
        docs = list(
            db.messages.find(
                {"conversationId": conversation_id},
                {"_id": 0, "role": 1, "content": 1, "createdAt": 1},
            ).sort("createdAt", -1).limit(limit)
        )
        # Reverse to get chronological order (oldest first)
        docs.reverse()
        return [{"role": d["role"], "content": d["content"]} for d in docs]
    except PyMongoError as exc:
        logger.error("[DB] get_conversation_messages error: %s", exc)
        return []
