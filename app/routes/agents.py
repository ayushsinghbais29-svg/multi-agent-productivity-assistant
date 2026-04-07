import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.primary_agent import PrimaryAgent
from app.database.db import get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Agents & Workflows"])


# ------------------------------------------------------------------
# Request / Response schemas (inline, agent-specific)
# ------------------------------------------------------------------

class AskRequest(BaseModel):
    user_input: str = Field(..., min_length=1, description="Natural language query")
    user_id: Optional[uuid.UUID] = None
    context: Optional[Dict[str, Any]] = None


class AskResponse(BaseModel):
    status: str
    response: str


class WorkflowStep(BaseModel):
    agent: str = Field(..., description="'calendar', 'task', or 'primary'")
    action: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None


class WorkflowRequest(BaseModel):
    name: str = Field(..., min_length=1)
    steps: List[WorkflowStep] = Field(..., min_length=1)
    user_id: Optional[uuid.UUID] = None


class WorkflowResponse(BaseModel):
    workflow_name: str
    total_steps: int
    completed_steps: int
    results: List[Dict[str, Any]]
    errors: List[str]
    status: str


# ------------------------------------------------------------------
# Route helpers
# ------------------------------------------------------------------

_agent_cache: Dict[str, PrimaryAgent] = {}


def get_primary_agent(db: Session = Depends(get_db)) -> PrimaryAgent:
    """Return a PrimaryAgent instance (one per process for simplicity)."""
    key = "default"
    if key not in _agent_cache:
        _agent_cache[key] = PrimaryAgent(db=db)
    else:
        # Refresh DB session reference
        _agent_cache[key].db = db
        _agent_cache[key].task_agent.task_manager.db = db
    return _agent_cache[key]


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/agents/ask", response_model=AskResponse)
def ask_agent(
    request: AskRequest,
    agent: PrimaryAgent = Depends(get_primary_agent),
):
    """Send a natural language query to the primary agent."""
    result = agent.ask(request.user_input)
    return AskResponse(status=result["status"], response=result["response"])


@router.post("/workflows/execute", response_model=WorkflowResponse)
def execute_workflow(
    request: WorkflowRequest,
    agent: PrimaryAgent = Depends(get_primary_agent),
):
    """Execute a multi-step workflow through the primary agent."""
    workflow_dict = {
        "name": request.name,
        "steps": [s.model_dump() for s in request.steps],
    }
    result = agent.execute_workflow(workflow_dict)
    return WorkflowResponse(**result)


@router.post("/agents/reset")
def reset_agent_history(agent: PrimaryAgent = Depends(get_primary_agent)):
    """Clear the agent's conversation history."""
    agent.clear_history()
    return {"message": "Conversation history cleared."}
