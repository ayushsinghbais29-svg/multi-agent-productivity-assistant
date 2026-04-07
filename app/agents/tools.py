"""
LangChain tool definitions for the multi-agent system.
Each tool wraps a specific capability that agents can invoke.
"""
import json
from datetime import datetime
from typing import Any, Optional

from langchain_core.tools import Tool

from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Tool factory helpers
# ---------------------------------------------------------------------------

def make_list_events_tool(calendar_integration) -> Tool:
    def _run(query: str) -> str:
        """Parse a JSON query with optional time_min/time_max keys."""
        try:
            params = json.loads(query) if query.strip().startswith("{") else {}
        except json.JSONDecodeError:
            params = {}

        time_min = None
        time_max = None
        if "time_min" in params:
            time_min = datetime.fromisoformat(params["time_min"])
        if "time_max" in params:
            time_max = datetime.fromisoformat(params["time_max"])

        events = calendar_integration.list_events(time_min=time_min, time_max=time_max)
        if not events:
            return "No events found."
        return json.dumps(events, default=str)

    return Tool(
        name="list_calendar_events",
        func=_run,
        description=(
            "List Google Calendar events. Input: JSON with optional keys "
            "'time_min' and 'time_max' (ISO 8601 strings). "
            "Returns a JSON array of event objects."
        ),
    )


def make_create_event_tool(calendar_integration) -> Tool:
    def _run(query: str) -> str:
        """Expect JSON: {title, start_time, end_time, description?, location?, attendees?}."""
        try:
            params = json.loads(query)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON input: {exc}"

        required = ["title", "start_time", "end_time"]
        for field in required:
            if field not in params:
                return f"Missing required field: {field}"

        event = calendar_integration.create_event(
            title=params["title"],
            start_time=datetime.fromisoformat(params["start_time"]),
            end_time=datetime.fromisoformat(params["end_time"]),
            description=params.get("description", ""),
            location=params.get("location", ""),
            attendees=params.get("attendees"),
        )
        if event:
            return json.dumps(event, default=str)
        return "Failed to create event."

    return Tool(
        name="create_calendar_event",
        func=_run,
        description=(
            "Create a new Google Calendar event. "
            "Input: JSON with keys 'title', 'start_time', 'end_time' (ISO 8601), "
            "and optional 'description', 'location', 'attendees' (list of emails)."
        ),
    )


def make_find_free_slots_tool(calendar_integration) -> Tool:
    def _run(query: str) -> str:
        """Expect JSON: {duration_minutes, date_from, date_to, preferred_start?, preferred_end?}."""
        try:
            params = json.loads(query)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON input: {exc}"

        slots = calendar_integration.find_free_slots(
            duration_minutes=int(params.get("duration_minutes", 60)),
            date_from=datetime.fromisoformat(params["date_from"]),
            date_to=datetime.fromisoformat(params["date_to"]),
            preferred_start=int(params.get("preferred_start", 9)),
            preferred_end=int(params.get("preferred_end", 17)),
        )
        if not slots:
            return "No free slots found in the given range."
        return json.dumps(slots)

    return Tool(
        name="find_free_slots",
        func=_run,
        description=(
            "Find available time slots in Google Calendar. "
            "Input: JSON with keys 'duration_minutes', 'date_from', 'date_to' (ISO 8601), "
            "and optional 'preferred_start' / 'preferred_end' (hour integers, default 9/17)."
        ),
    )


def make_create_task_tool(task_manager) -> Tool:
    def _run(query: str) -> str:
        """Expect JSON: {user_id, title, description?, priority?, due_date?}."""
        try:
            params = json.loads(query)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON input: {exc}"

        from app.schemas.task import TaskCreate
        try:
            task_data = TaskCreate(**params)
            task = task_manager.create_task(task_data)
            return json.dumps({"id": str(task.id), "title": task.title, "status": task.status.value})
        except Exception as exc:  # noqa: BLE001
            return f"Failed to create task: {exc}"

    return Tool(
        name="create_task",
        func=_run,
        description=(
            "Create a new task. "
            "Input: JSON with keys 'user_id' (UUID), 'title', and optional "
            "'description', 'priority' (low/medium/high/urgent), 'due_date' (ISO 8601)."
        ),
    )


def make_list_tasks_tool(task_manager) -> Tool:
    def _run(query: str) -> str:
        """Expect JSON: {user_id, status?, priority?}."""
        try:
            params = json.loads(query) if query.strip().startswith("{") else {}
        except json.JSONDecodeError:
            params = {}

        import uuid as _uuid
        user_id = _uuid.UUID(params["user_id"]) if "user_id" in params else None
        if not user_id:
            return "user_id is required."

        tasks, total = task_manager.list_tasks(user_id=user_id)
        result = [{"id": str(t.id), "title": t.title, "status": t.status.value, "priority": t.priority.value} for t in tasks]
        return json.dumps({"tasks": result, "total": total})

    return Tool(
        name="list_tasks",
        func=_run,
        description=(
            "List tasks for a user. "
            "Input: JSON with key 'user_id' (UUID), and optional 'status', 'priority' filters."
        ),
    )


def make_get_tasks_summary_tool(task_manager) -> Tool:
    def _run(query: str) -> str:
        """Expect JSON: {user_id}."""
        try:
            params = json.loads(query)
        except json.JSONDecodeError:
            return "Invalid JSON input."

        import uuid as _uuid
        user_id = _uuid.UUID(params["user_id"])
        summary = task_manager.get_tasks_summary(user_id)
        return json.dumps(summary)

    return Tool(
        name="get_tasks_summary",
        func=_run,
        description=(
            "Get a summary of a user's tasks by status. "
            "Input: JSON with key 'user_id' (UUID)."
        ),
    )
