import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.integrations.task_manager import TaskManagerIntegration
from app.models.task import TaskStatus, TaskPriority
from app.schemas.task import TaskCreate, TaskListResponse, TaskRead, TaskUpdate

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


def get_task_manager(db: Session = Depends(get_db)) -> TaskManagerIntegration:
    return TaskManagerIntegration(db=db)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    user_id: uuid.UUID = Query(..., description="User UUID"),
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    tasks, total = manager.list_tasks(
        user_id=user_id, status=status, priority=priority, page=page, page_size=page_size
    )
    return TaskListResponse(tasks=tasks, total=total, page=page, page_size=page_size)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    task_data: TaskCreate,
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    return manager.create_task(task_data)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID,
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    update_data: TaskUpdate,
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    task = manager.update_task(task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID,
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    deleted = manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/user/{user_id}/summary")
def get_task_summary(
    user_id: uuid.UUID,
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    return manager.get_tasks_summary(user_id)


@router.get("/user/{user_id}/overdue", response_model=list[TaskRead])
def get_overdue_tasks(
    user_id: uuid.UUID,
    manager: TaskManagerIntegration = Depends(get_task_manager),
):
    return manager.get_overdue_tasks(user_id)
