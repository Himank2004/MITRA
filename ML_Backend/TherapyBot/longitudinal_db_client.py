"""
Database client functions for SessionState and UserProfile.

These are called from the Python backend to persist state.
Connect to the Node.js backend via HTTP or direct MongoDB access.
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

# Backend API base URL (or None if using direct MongoDB)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")
USE_HTTP_API = os.getenv("USE_HTTP_API", "false").lower() == "true"


def update_session_state(user_id: str, conversation_id: str, state_data: Dict) -> Dict:
    """
    Update session state for a conversation.

    Args:
        user_id: User ID
        conversation_id: Conversation ID
        state_data: Dict with riskTrend, activeThemes, etc.

    Returns:
        Updated session state
    """

    if USE_HTTP_API:
        return _update_session_state_http(user_id, conversation_id, state_data)
    else:
        return _update_session_state_direct(user_id, conversation_id, state_data)


def _update_session_state_http(
    user_id: str, conversation_id: str, state_data: Dict
) -> Dict:
    """Update via HTTP API call to Node.js backend."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/session-state/update",
            json={"userId": user_id, "conversationId": conversation_id, **state_data},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[db_client] HTTP error: {e}")
        return {"error": str(e)}


def _update_session_state_direct(
    user_id: str, conversation_id: str, state_data: Dict
) -> Dict:
    """Update directly via MongoDB."""
    try:
        from pymongo import MongoClient

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/therapy")
        client = MongoClient(mongo_uri)
        db = client.therapy

        result = db.sessionstates.update_one(
            {"userId": user_id, "conversationId": conversation_id},
            {"$set": state_data, "$currentDate": {"updatedAt": True}},
            upsert=True,
        )

        return {
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted": result.upserted_id,
        }
    except Exception as e:
        print(f"[db_client] Direct DB error: {e}")
        return {"error": str(e)}


def get_session_state(user_id: str, conversation_id: str) -> Optional[Dict]:
    """Retrieve session state from DB."""
    try:
        from pymongo import MongoClient

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/therapy")
        client = MongoClient(mongo_uri)
        db = client.therapy

        return db.sessionstates.find_one(
            {"userId": user_id, "conversationId": conversation_id}
        )
    except Exception as e:
        print(f"[db_client] Error retrieving session state: {e}")
        return None


def get_user_session_states(user_id: str, limit: int = 10) -> List[Dict]:
    """Get recent session states for a user."""
    try:
        from pymongo import MongoClient

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/therapy")
        client = MongoClient(mongo_uri)
        db = client.therapy

        return list(
            db.sessionstates.find({"userId": user_id})
            .sort("createdAt", -1)
            .limit(limit)
        )
    except Exception as e:
        print(f"[db_client] Error retrieving session states: {e}")
        return []


def update_user_profile(user_id: str, profile_data: Dict) -> Dict:
    """
    Update user profile (aggregated from sessions).
    """

    if USE_HTTP_API:
        return _update_user_profile_http(user_id, profile_data)
    else:
        return _update_user_profile_direct(user_id, profile_data)


def _update_user_profile_http(user_id: str, profile_data: Dict) -> Dict:
    """Update via HTTP API."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/user-profile/update",
            json={"userId": user_id, **profile_data},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[db_client] HTTP error: {e}")
        return {"error": str(e)}


def _update_user_profile_direct(user_id: str, profile_data: Dict) -> Dict:
    """Update directly via MongoDB."""
    try:
        from pymongo import MongoClient
        from bson import ObjectId

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/therapy")
        client = MongoClient(mongo_uri)
        db = client.therapy

        # Convert user_id to ObjectId if it is one
        try:
            user_oid = ObjectId(user_id)
        except:
            user_oid = user_id

        result = db.userprofiles.update_one(
            {"userId": user_oid},
            {"$set": profile_data, "$currentDate": {"updatedAt": True}},
            upsert=True,
        )

        return {
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted": result.upserted_id,
        }
    except Exception as e:
        print(f"[db_client] Direct DB error: {e}")
        return {"error": str(e)}


def get_user_profile(user_id: str) -> Optional[Dict]:
    """Retrieve user profile from DB."""
    try:
        from pymongo import MongoClient
        from bson import ObjectId

        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/therapy")
        client = MongoClient(mongo_uri)
        db = client.therapy

        try:
            user_oid = ObjectId(user_id)
        except:
            user_oid = user_id

        return db.userprofiles.find_one({"userId": user_oid})
    except Exception as e:
        print(f"[db_client] Error retrieving user profile: {e}")
        return None
