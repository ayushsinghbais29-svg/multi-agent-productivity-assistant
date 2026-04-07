"""Tests for integration layer (Google Calendar and Task Manager)."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.integrations.google_calendar import GoogleCalendarIntegration
from app.integrations.task_manager import TaskManagerIntegration
from app.models.task import TaskStatus, TaskPriority
from app.schemas.task import TaskCreate, TaskUpdate


# ---------------------------------------------------------------------------
# Google Calendar Integration
# ---------------------------------------------------------------------------

class TestGoogleCalendarIntegration:
    def _make_integration(self):
        integration = GoogleCalendarIntegration()
        integration._service = MagicMock()
        return integration

    def test_list_events_returns_items(self):
        intg = self._make_integration()
        mock_events = {"items": [{"id": "ev1", "summary": "Meeting"}]}
        intg._service.events.return_value.list.return_value.execute.return_value = mock_events
        events = intg.list_events()
        assert len(events) == 1
        assert events[0]["summary"] == "Meeting"

    def test_list_events_http_error_returns_empty(self):
        from googleapiclient.errors import HttpError
        intg = self._make_integration()
        resp = MagicMock()
        resp.status = 403
        resp.reason = "Forbidden"
        intg._service.events.return_value.list.return_value.execute.side_effect = HttpError(resp, b"Forbidden")
        events = intg.list_events()
        assert events == []

    def test_create_event_success(self):
        intg = self._make_integration()
        mock_event = {"id": "new_event_id", "summary": "Standup"}
        intg._service.events.return_value.insert.return_value.execute.return_value = mock_event
        result = intg.create_event(
            title="Standup",
            start_time=datetime(2025, 6, 1, 10, 0),
            end_time=datetime(2025, 6, 1, 10, 30),
        )
        assert result["id"] == "new_event_id"

    def test_create_event_http_error_returns_none(self):
        from googleapiclient.errors import HttpError
        intg = self._make_integration()
        resp = MagicMock()
        resp.status = 500
        resp.reason = "Internal Server Error"
        intg._service.events.return_value.insert.return_value.execute.side_effect = HttpError(resp, b"Error")
        result = intg.create_event(
            title="Standup",
            start_time=datetime(2025, 6, 1, 10, 0),
            end_time=datetime(2025, 6, 1, 10, 30),
        )
        assert result is None

    def test_delete_event_success(self):
        intg = self._make_integration()
        intg._service.events.return_value.delete.return_value.execute.return_value = None
        result = intg.delete_event("ev1")
        assert result is True

    def test_delete_event_http_error_returns_false(self):
        from googleapiclient.errors import HttpError
        intg = self._make_integration()
        resp = MagicMock()
        resp.status = 404
        resp.reason = "Not Found"
        intg._service.events.return_value.delete.return_value.execute.side_effect = HttpError(resp, b"Not Found")
        result = intg.delete_event("ev_missing")
        assert result is False

    def test_find_free_slots_no_busy_events(self):
        intg = self._make_integration()
        mock_events = {"items": []}
        intg._service.events.return_value.list.return_value.execute.return_value = mock_events
        date_from = datetime(2025, 6, 2, 8, 0)
        date_to = datetime(2025, 6, 2, 18, 0)
        slots = intg.find_free_slots(
            duration_minutes=60,
            date_from=date_from,
            date_to=date_to,
            preferred_start=9,
            preferred_end=17,
        )
        assert len(slots) > 0
        # All slots should be within preferred hours
        for slot in slots:
            start = datetime.fromisoformat(slot["start"])
            assert start.hour >= 9

    def test_service_unavailable_returns_empty(self):
        intg = GoogleCalendarIntegration()
        intg._service = None
        # Calling list_events without a service should return []
        events = intg.list_events()
        assert events == []


# ---------------------------------------------------------------------------
# Task Manager Integration
# ---------------------------------------------------------------------------

class TestTaskManagerIntegration:
    def _make_manager(self):
        db = MagicMock()
        manager = TaskManagerIntegration(db=db)
        return manager, db

    def test_create_task(self):
        manager, db = self._make_manager()
        task_data = TaskCreate(
            user_id=uuid.uuid4(),
            title="Write unit tests",
            priority=TaskPriority.high,
        )
        mock_task = MagicMock()
        mock_task.id = uuid.uuid4()
        mock_task.title = "Write unit tests"
        db.add.return_value = None
        db.commit.return_value = None
        db.refresh.side_effect = lambda obj: None

        # Patch Task constructor to return our mock
        with patch("app.integrations.task_manager.Task", return_value=mock_task):
            result = manager.create_task(task_data)

        db.add.assert_called_once_with(mock_task)
        db.commit.assert_called_once()

    def test_get_task_returns_none_if_not_found(self):
        manager, db = self._make_manager()
        db.query.return_value.filter.return_value.first.return_value = None
        result = manager.get_task(uuid.uuid4())
        assert result is None

    def test_delete_task_not_found_returns_false(self):
        manager, db = self._make_manager()
        db.query.return_value.filter.return_value.first.return_value = None
        result = manager.delete_task(uuid.uuid4())
        assert result is False

    def test_delete_task_success(self):
        manager, db = self._make_manager()
        mock_task = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = mock_task
        result = manager.delete_task(uuid.uuid4())
        db.delete.assert_called_once_with(mock_task)
        db.commit.assert_called_once()
        assert result is True

    def test_update_task_not_found_returns_none(self):
        manager, db = self._make_manager()
        db.query.return_value.filter.return_value.first.return_value = None
        result = manager.update_task(uuid.uuid4(), TaskUpdate(title="New title"))
        assert result is None

    def test_get_tasks_summary(self):
        manager, db = self._make_manager()
        mock_task1 = MagicMock()
        mock_task1.status = TaskStatus.pending
        mock_task2 = MagicMock()
        mock_task2.status = TaskStatus.completed
        db.query.return_value.filter.return_value.all.return_value = [mock_task1, mock_task2]
        summary = manager.get_tasks_summary(uuid.uuid4())
        assert summary["total"] == 2
        assert summary["by_status"]["pending"] == 1
        assert summary["by_status"]["completed"] == 1
