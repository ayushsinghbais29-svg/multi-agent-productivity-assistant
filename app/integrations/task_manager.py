import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus, TaskPriority
from app.schemas.task import TaskCreate, TaskUpdate
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TaskManagerIntegration:
    """Database-backed task management."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_task(self, task_data: TaskCreate) -> Task:
        task = Task(
            user_id=task_data.user_id,
            title=task_data.title,
            description=task_data.description,
            priority=task_data.priority,
            due_date=task_data.due_date,
            reminder_at=task_data.reminder_at,
            is_recurring=task_data.is_recurring,
            recurrence_pattern=task_data.recurrence_pattern,
            tags=task_data.tags,
            estimated_minutes=task_data.estimated_minutes,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        logger.info("Created task %s: %s", task.id, task.title)
        return task

    def get_task(self, task_id: uuid.UUID) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def list_tasks(
        self,
        user_id: uuid.UUID,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Task], int]:
        query = self.db.query(Task).filter(Task.user_id == user_id)
        if status:
            query = query.filter(Task.status == status)
        if priority:
            query = query.filter(Task.priority == priority)
        total = query.count()
        tasks = query.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return tasks, total

    def update_task(self, task_id: uuid.UUID, update_data: TaskUpdate) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task:
            logger.warning("Task %s not found for update.", task_id)
            return None

        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)

        # Auto-set completed_at when status changes to completed
        if update_data.status == TaskStatus.completed and not task.completed_at:
            task.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(task)
        logger.info("Updated task %s", task_id)
        return task

    def delete_task(self, task_id: uuid.UUID) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        self.db.delete(task)
        self.db.commit()
        logger.info("Deleted task %s", task_id)
        return True

    def get_overdue_tasks(self, user_id: uuid.UUID) -> List[Task]:
        now = datetime.utcnow()
        return (
            self.db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.due_date < now,
                Task.status.notin_([TaskStatus.completed, TaskStatus.cancelled]),
            )
            .all()
        )

    def get_tasks_summary(self, user_id: uuid.UUID) -> Dict[str, Any]:
        tasks = self.db.query(Task).filter(Task.user_id == user_id).all()
        summary: Dict[str, int] = {s.value: 0 for s in TaskStatus}
        for task in tasks:
            summary[task.status.value] += 1
        return {
            "total": len(tasks),
            "by_status": summary,
        }
