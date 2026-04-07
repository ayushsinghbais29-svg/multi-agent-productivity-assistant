"""Tests for FastAPI routes using TestClient with an in-memory SQLite DB."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite DB for tests (StaticPool ensures a single shared connection
# so that all requests within a test see the same in-memory state)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def sample_user(reset_db):
    """Create a user directly in DB and return its UUID."""
    from app.models.user import User
    db = TestingSessionLocal()
    user = User(email="test@example.com", full_name="Test User")
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()
    return uid


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoints:
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Task routes
# ---------------------------------------------------------------------------

class TestTaskRoutes:
    def test_create_task(self, sample_user):
        payload = {
            "user_id": str(sample_user),
            "title": "Write documentation",
            "priority": "high",
        }
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Write documentation"
        assert data["status"] == "pending"
        assert data["priority"] == "high"

    def test_list_tasks_empty(self, sample_user):
        response = client.get(f"/api/v1/tasks?user_id={sample_user}")
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_list_tasks_after_create(self, sample_user):
        payload = {"user_id": str(sample_user), "title": "Task 1"}
        client.post("/api/v1/tasks", json=payload)
        response = client.get(f"/api/v1/tasks?user_id={sample_user}")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_get_task_by_id(self, sample_user):
        create_resp = client.post("/api/v1/tasks", json={"user_id": str(sample_user), "title": "Test task"})
        task_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test task"

    def test_get_task_not_found(self):
        response = client.get(f"/api/v1/tasks/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_update_task_status(self, sample_user):
        create_resp = client.post("/api/v1/tasks", json={"user_id": str(sample_user), "title": "Update me"})
        task_id = create_resp.json()["id"]
        update_resp = client.patch(f"/api/v1/tasks/{task_id}", json={"status": "completed"})
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "completed"

    def test_delete_task(self, sample_user):
        create_resp = client.post("/api/v1/tasks", json={"user_id": str(sample_user), "title": "Delete me"})
        task_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/v1/tasks/{task_id}")
        assert del_resp.status_code == 204
        get_resp = client.get(f"/api/v1/tasks/{task_id}")
        assert get_resp.status_code == 404

    def test_delete_task_not_found(self):
        response = client.delete(f"/api/v1/tasks/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_task_summary(self, sample_user):
        client.post("/api/v1/tasks", json={"user_id": str(sample_user), "title": "T1"})
        client.post("/api/v1/tasks", json={"user_id": str(sample_user), "title": "T2"})
        response = client.get(f"/api/v1/tasks/user/{sample_user}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["by_status"]["pending"] == 2

    def test_create_task_missing_title_fails(self, sample_user):
        payload = {"user_id": str(sample_user)}
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Schedule routes
# ---------------------------------------------------------------------------

class TestScheduleRoutes:
    def test_list_schedules_empty(self, sample_user):
        response = client.get(f"/api/v1/schedules?user_id={sample_user}")
        assert response.status_code == 200
        data = response.json()
        assert data["schedules"] == []
        assert data["total"] == 0

    def test_create_schedule(self, sample_user):
        payload = {
            "user_id": str(sample_user),
            "title": "Team Sync",
            "start_time": "2025-06-01T10:00:00",
            "end_time": "2025-06-01T11:00:00",
        }
        response = client.post("/api/v1/schedules", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Team Sync"

    def test_create_schedule_invalid_range(self, sample_user):
        payload = {
            "user_id": str(sample_user),
            "title": "Bad Event",
            "start_time": "2025-06-01T12:00:00",
            "end_time": "2025-06-01T10:00:00",  # end before start
        }
        response = client.post("/api/v1/schedules", json=payload)
        assert response.status_code == 400

    def test_get_schedule_by_id(self, sample_user):
        payload = {
            "user_id": str(sample_user),
            "title": "Review",
            "start_time": "2025-07-01T14:00:00",
            "end_time": "2025-07-01T15:00:00",
        }
        create_resp = client.post("/api/v1/schedules", json=payload)
        schedule_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/schedules/{schedule_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Review"

    def test_get_schedule_not_found(self):
        response = client.get(f"/api/v1/schedules/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_delete_schedule(self, sample_user):
        payload = {
            "user_id": str(sample_user),
            "title": "To delete",
            "start_time": "2025-08-01T09:00:00",
            "end_time": "2025-08-01T10:00:00",
        }
        create_resp = client.post("/api/v1/schedules", json=payload)
        schedule_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/v1/schedules/{schedule_id}")
        assert del_resp.status_code == 204

    def test_find_slot_invalid_range(self, sample_user):
        payload = {
            "user_id": str(sample_user),
            "duration_minutes": 60,
            "date_from": "2025-06-01T18:00:00",
            "date_to": "2025-06-01T09:00:00",  # to before from
        }
        response = client.post("/api/v1/schedules/find-slot", json=payload)
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Agent routes (mocked LLM)
# ---------------------------------------------------------------------------

class TestAgentRoutes:
    @patch("app.agents.primary_agent.PrimaryAgent.ask")
    def test_ask_agent(self, mock_ask):
        mock_ask.return_value = {"status": "success", "response": "Here are your tasks."}
        response = client.post("/api/v1/agents/ask", json={"user_input": "What are my tasks?"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "tasks" in data["response"]

    @patch("app.agents.primary_agent.PrimaryAgent.execute_workflow")
    def test_execute_workflow(self, mock_workflow):
        mock_workflow.return_value = {
            "workflow_name": "test_workflow",
            "total_steps": 1,
            "completed_steps": 1,
            "results": [{"step": 1, "agent": "task", "output": "done"}],
            "errors": [],
            "status": "completed",
        }
        payload = {
            "name": "test_workflow",
            "steps": [{"agent": "task", "action": "Create a task: Buy milk"}],
        }
        response = client.post("/api/v1/workflows/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["total_steps"] == 1

    @patch("app.agents.primary_agent.PrimaryAgent.clear_history")
    def test_reset_agent(self, mock_reset):
        response = client.post("/api/v1/agents/reset")
        assert response.status_code == 200
        mock_reset.assert_called_once()

    def test_ask_agent_empty_input(self):
        response = client.post("/api/v1/agents/ask", json={"user_input": ""})
        assert response.status_code == 422
