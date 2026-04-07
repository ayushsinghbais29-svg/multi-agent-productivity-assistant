"""Task sub-agent: manages task creation, updates, and queries."""
from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.agents.tools import (
    make_create_task_tool,
    make_get_tasks_summary_tool,
    make_list_tasks_tool,
)
from app.config import get_settings
from app.integrations.task_manager import TaskManagerIntegration
from app.utils.logger import get_logger

logger = get_logger(__name__)

TASK_SYSTEM_PROMPT = """You are a Task Management Agent.
Your job is to help users manage their tasks by:
- Creating new tasks with appropriate priorities and deadlines
- Listing and filtering tasks
- Providing summaries and status updates
- Identifying overdue or high-priority tasks

Always ask for clarification if task details are ambiguous.
Suggest appropriate priorities based on context.
"""


class TaskAgent:
    def __init__(self, db: Session):
        self.settings = get_settings()
        self.task_manager = TaskManagerIntegration(db=db)
        self._agent = None

    def _build_agent(self):
        tools = [
            make_create_task_tool(self.task_manager),
            make_list_tasks_tool(self.task_manager),
            make_get_tasks_summary_tool(self.task_manager),
        ]

        llm = ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
            temperature=0,
        )

        return create_agent(model=llm, tools=tools, system_prompt=TASK_SYSTEM_PROMPT)

    @property
    def agent(self):
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def run(self, user_input: str, chat_history: Optional[List] = None) -> str:
        """Run the task agent with the given user input."""
        try:
            messages = list(chat_history or []) + [HumanMessage(content=user_input)]
            result = self.agent.invoke({"messages": messages})
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage):
                    return msg.content
            return "No response generated."
        except Exception as exc:  # noqa: BLE001
            logger.error("TaskAgent error: %s", exc)
            return f"Task agent encountered an error: {exc}"
