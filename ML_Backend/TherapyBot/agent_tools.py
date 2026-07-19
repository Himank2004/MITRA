"""
Tool functions for TherapyAgent.

These are LangChain tools that the agent can call during conversations.
"""

import json
from langchain_core.tools import tool
from constants import DEBUG_FLAGS


@tool("save_memory_to_db")
def save_memory_to_db(
    memory: str,
    conversation_id: str,
    user_id: str,
    memory_type: str = "info",
):
    """Persist a piece of information about the user that should be remembered across sessions.

    Call this when the user reveals something lasting and personal, for example:
    - biographical facts (name, age, occupation, family situation)
    - recurring struggles or diagnoses they have mentioned
    - strong preferences or dislikes they have expressed
    - goals they have shared

    Use memory_type="instruct" for explicit preferences about how the assistant should behave
    (e.g. "user prefers short replies", "user does not want homework tasks").
    Use memory_type="info" (default) for all factual or biographical memories.

    Do NOT call this for transient feelings or one-off statements that are not worth keeping
    long-term.
    """
    if DEBUG_FLAGS["memory"]:
        print(
            f"[DB MEMORY SAVE] User: {user_id}, type={memory_type}, conv: {conversation_id}"
        )
        print(f"[DB MEMORY SAVE] Content: {memory[:200]}...")

    # Compute embedding before saving so it's stored immediately
    embedding = []
    try:
        from shared_embeddings import embed_text

        embedding = embed_text(memory)
        if DEBUG_FLAGS["memory"]:
            print(f"[DB MEMORY SAVE] Embedding computed ({len(embedding)}-dim)")
    except Exception as e:
        if DEBUG_FLAGS["memory"]:
            print(f"[DB MEMORY SAVE] Embedding error (saving without): {e}")

    try:
        from db_client import save_memory

        save_memory(
            user_id,
            conversation_id,
            memory,
            memory_type=memory_type,
            embedding=embedding,
        )
    except Exception as e:
        if DEBUG_FLAGS["memory"]:
            print(f"[DB MEMORY SAVE] DB error: {e}")

    return {
        "status": "success",
        "memory": memory,
        "memory_type": memory_type,
        "user_id": user_id,
        "conversation_id": conversation_id,
    }


@tool("create_therapy_task")
async def create_therapy_task(
    reason_for_task_creation: str, conversation_id: str, user_id: str
):
    """Create a therapy-related task for the user, based on the given reason.
    Make sure to provide a detailed description of the problem of multiple sentences and the user's needs in the reason_for_task_creation, so TaskBot can generate a clear, relevant and personalized task.
    This tool uses TaskBot to generate personalized therapy tasks that avoid redundancy
    and are tailored to the user's needs."""

    # Import here to avoid circular imports
    from agent_stream import get_taskbot_instance
    from agent_utils import clean_json_response

    if DEBUG_FLAGS["task"]:
        print(
            f"[THERAPY TASK] New Task Creation Started for User {user_id}, Conversation {conversation_id}"
        )
        print(f"[THERAPY TASK] Reason: {reason_for_task_creation}")

    # Get shared TaskBot instance
    taskbot = get_taskbot_instance()

    # Fetch existing tasks so TaskBot can avoid redundancy and calibrate difficulty
    try:
        from db_client import get_user_tasks

        existing_tasks = get_user_tasks(user_id)
    except Exception as e:
        if DEBUG_FLAGS["task"]:
            print(f"[THERAPY TASK] Could not fetch existing tasks: {e}")
        existing_tasks = []

    try:
        # Call TaskBot to create the task
        task_json_result = await taskbot.create_task(
            reason_for_task_creation, existing_tasks
        )

        # Clean the response (remove markdown code blocks if present)
        cleaned_json = clean_json_response(task_json_result)

        # Parse the JSON response from TaskBot
        try:
            task_data = json.loads(cleaned_json)

            # Handle both single task and list of tasks
            if isinstance(task_data, dict) and "task" in task_data:
                # Extract the task from the wrapper
                task_data = task_data["task"]
            elif (
                isinstance(task_data, list)
                and len(task_data) > 0
                and isinstance(task_data[0], dict)
                and "task" in task_data[0]
            ):
                # Handle list of tasks wrapped in task key
                task_data = [
                    item["task"] if isinstance(item, dict) and "task" in item else item
                    for item in task_data
                ]

        except json.JSONDecodeError as e:
            if DEBUG_FLAGS["task"]:
                print(f"[THERAPY TASK] JSON Parse Error: {e}")
                print(f"[THERAPY TASK] Raw response: {cleaned_json[:500]}")
            # If parsing fails, return the cleaned string
            task_data = {"raw_response": cleaned_json}

        if DEBUG_FLAGS["task"]:
            print(f"[THERAPY TASK] Task Created Successfully")
            print(
                f"[THERAPY TASK] Task Data: {json.dumps(task_data, indent=2)[:300]}..."
            )

        # Persist task(s) to MongoDB
        try:
            from db_client import save_task

            if isinstance(task_data, dict):
                save_task(user_id, conversation_id, task_data)
            elif isinstance(task_data, list):
                for td in task_data:
                    if isinstance(td, dict):
                        save_task(user_id, conversation_id, td)
        except Exception as e:
            if DEBUG_FLAGS["task"]:
                print(f"[THERAPY TASK] DB save error: {e}")

        # Format a user-friendly response string instead of returning raw dict
        # This prevents the agent from echoing the entire JSON structure
        if isinstance(task_data, dict):
            task_name = task_data.get("task_name", "A therapy task")
            task_description = task_data.get("description", "")
            task_type = task_data.get("task_type", "")
            difficulty = task_data.get("difficulty", "")

            # Create a concise, natural description for the agent to use
            response_text = f"Task created: '{task_name}'. {task_description}"
            if difficulty:
                response_text += f" (Difficulty: {difficulty})"
        elif isinstance(task_data, list) and len(task_data) > 0:
            # Handle multiple tasks
            task_names = [
                t.get("task_name", "task") if isinstance(t, dict) else str(t)
                for t in task_data
            ]
            response_text = f"Created {len(task_data)} tasks: {', '.join(task_names)}"
        else:
            response_text = "Task created successfully."

        # Store full task data for potential later use (e.g., saving to DB)
        # You can access this via a getter function if needed
        if DEBUG_FLAGS["task"]:
            if not hasattr(create_therapy_task, "_task_store"):
                create_therapy_task._task_store = {}
            create_therapy_task._task_store[f"{user_id}_{conversation_id}"] = {
                "status": "success",
                "created_task": task_data,
                "reason_for_task_creation": reason_for_task_creation,
            }

        return response_text
    except Exception as e:
        if DEBUG_FLAGS["task"]:
            print(f"[THERAPY TASK] Error creating task: {str(e)}")
        return f"Error creating task: {str(e)}"
