"""Tests for agent tools and agent logic (no real LLM/DB calls)."""
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.agents.tools import (
    make_create_event_tool,
    make_create_task_tool,
    make_find_free_slots_tool,
    make_get_tasks_summary_tool,
    make_list_events_tool,
    make_list_tasks_tool,
)


# ---------------------------------------------------------------------------
# Calendar tools
# ---------------------------------------------------------------------------

class TestListEventsTool:
    def test_returns_events(self):
        mock_cal = MagicMock()
        mock_cal.list_events.return_value = [{"summary": "Meeting", "id": "abc"}]
        tool = make_list_events_tool(mock_cal)
        result = tool.func("{}")
        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["summary"] == "Meeting"

    def test_no_events_returns_message(self):
        mock_cal = MagicMock()
        mock_cal.list_events.return_value = []
        tool = make_list_events_tool(mock_cal)
        result = tool.func("{}")
        assert "No events found" in result

    def test_with_time_range(self):
        mock_cal = MagicMock()
        mock_cal.list_events.return_value = []
        tool = make_list_events_tool(mock_cal)
        payload = json.dumps({"time_min": "2025-01-01T09:00:00", "time_max": "2025-01-01T17:00:00"})
        tool.func(payload)
        call_kwargs = mock_cal.list_events.call_args[1]
        assert call_kwargs["time_min"] == datetime(2025, 1, 1, 9, 0, 0)
        assert call_kwargs["time_max"] == datetime(2025, 1, 1, 17, 0, 0)


class TestCreateEventTool:
    def test_creates_event_successfully(self):
        mock_cal = MagicMock()
        mock_cal.create_event.return_value = {"id": "ev1", "summary": "Standup"}
        tool = make_create_event_tool(mock_cal)
        payload = json.dumps({
            "title": "Standup",
            "start_time": "2025-06-01T10:00:00",
            "end_time": "2025-06-01T10:30:00",
        })
        result = tool.func(payload)
        data = json.loads(result)
        assert data["summary"] == "Standup"

    def test_missing_required_field(self):
        mock_cal = MagicMock()
        tool = make_create_event_tool(mock_cal)
        payload = json.dumps({"title": "Meeting"})  # missing start_time/end_time
        result = tool.func(payload)
        assert "Missing required field" in result

    def test_invalid_json(self):
        mock_cal = MagicMock()
        tool = make_create_event_tool(mock_cal)
        result = tool.func("not-json")
        assert "Invalid JSON input" in result


class TestFindFreeSlotsTool:
    def test_finds_slots(self):
        mock_cal = MagicMock()
        mock_cal.find_free_slots.return_value = [
            {"start": "2025-06-01T09:00:00", "end": "2025-06-01T10:00:00"}
        ]
        tool = make_find_free_slots_tool(mock_cal)
        payload = json.dumps({
            "duration_minutes": 60,
            "date_from": "2025-06-01T08:00:00",
            "date_to": "2025-06-01T18:00:00",
        })
        result = tool.func(payload)
        data = json.loads(result)
        assert len(data) == 1

    def test_no_slots_found(self):
        mock_cal = MagicMock()
        mock_cal.find_free_slots.return_value = []
        tool = make_find_free_slots_tool(mock_cal)
        payload = json.dumps({
            "duration_minutes": 60,
            "date_from": "2025-06-01T08:00:00",
            "date_to": "2025-06-01T18:00:00",
        })
        result = tool.func(payload)
        assert "No free slots" in result


# ---------------------------------------------------------------------------
# Task tools
# ---------------------------------------------------------------------------

class TestCreateTaskTool:
    def test_creates_task(self):
        mock_manager = MagicMock()
        mock_task = MagicMock()
        mock_task.id = uuid.uuid4()
        mock_task.title = "Fix bug"
        mock_task.status = MagicMock(value="pending")
        mock_manager.create_task.return_value = mock_task
        tool = make_create_task_tool(mock_manager)
        payload = json.dumps({
            "user_id": str(uuid.uuid4()),
            "title": "Fix bug",
        })
        result = tool.func(payload)
        data = json.loads(result)
        assert data["title"] == "Fix bug"

    def test_invalid_json_returns_error(self):
        mock_manager = MagicMock()
        tool = make_create_task_tool(mock_manager)
        result = tool.func("bad-json")
        assert "Invalid JSON input" in result


class TestListTasksTool:
    def test_lists_tasks(self):
        mock_manager = MagicMock()
        mock_task = MagicMock()
        mock_task.id = uuid.uuid4()
        mock_task.title = "Write tests"
        mock_task.status = MagicMock(value="pending")
        mock_task.priority = MagicMock(value="medium")
        mock_manager.list_tasks.return_value = ([mock_task], 1)
        tool = make_list_tasks_tool(mock_manager)
        user_id = str(uuid.uuid4())
        result = tool.func(json.dumps({"user_id": user_id}))
        data = json.loads(result)
        assert data["total"] == 1
        assert data["tasks"][0]["title"] == "Write tests"

    def test_missing_user_id(self):
        mock_manager = MagicMock()
        tool = make_list_tasks_tool(mock_manager)
        result = tool.func("{}")
        assert "user_id is required" in result


class TestGetTasksSummaryTool:
    def test_returns_summary(self):
        mock_manager = MagicMock()
        mock_manager.get_tasks_summary.return_value = {
            "total": 5,
            "by_status": {"pending": 3, "completed": 2},
        }
        tool = make_get_tasks_summary_tool(mock_manager)
        user_id = str(uuid.uuid4())
        result = tool.func(json.dumps({"user_id": user_id}))
        data = json.loads(result)
        assert data["total"] == 5
