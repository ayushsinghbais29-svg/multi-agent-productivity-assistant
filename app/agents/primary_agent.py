"""Primary orchestrator agent that routes requests to sub-agents."""
import json
from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.agents.calendar_agent import CalendarAgent
from app.agents.task_agent import TaskAgent
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

PRIMARY_SYSTEM_PROMPT = """You are a Primary Productivity Assistant Agent.
You coordinate between specialized sub-agents to help users manage their productivity.

Available sub-agents:
1. **Calendar Agent** – manages Google Calendar events, meetings, and time slots
2. **Task Agent** – manages to-do tasks, priorities, deadlines, and task summaries

Your responsibilities:
- Understand the user's intent and route the request to the correct sub-agent
- Coordinate multi-step workflows (e.g., create a task AND schedule a meeting)
- Synthesize responses from multiple agents into a coherent answer
- Handle errors gracefully and provide helpful fallback messages

Always be helpful, concise, and action-oriented.
"""


class PrimaryAgent:
    def __init__(
        self,
        db: Session,
        calendar_credentials: Optional[Dict[str, Any]] = None,
    ):
        self.settings = get_settings()
        self.db = db
        self.calendar_agent = CalendarAgent(credentials_dict=calendar_credentials)
        self.task_agent = TaskAgent(db=db)
        self._agent = None
        self._conversation_history: List = []

    # ------------------------------------------------------------------
    # Internal sub-agent tools exposed to the primary LLM
    # ------------------------------------------------------------------

    def _make_calendar_tool(self) -> Tool:
        def _run(query: str) -> str:
            return self.calendar_agent.run(query, chat_history=self._conversation_history)

        return Tool(
            name="calendar_agent",
            func=_run,
            description=(
                "Delegate calendar-related tasks to the Calendar Agent. "
                "Use this for listing events, creating/updating/deleting calendar events, "
                "or finding free time slots. Input: natural language request."
            ),
        )

    def _make_task_tool(self) -> Tool:
        def _run(query: str) -> str:
            return self.task_agent.run(query, chat_history=self._conversation_history)

        return Tool(
            name="task_agent",
            func=_run,
            description=(
                "Delegate task management to the Task Agent. "
                "Use this for creating tasks, listing tasks, getting task summaries, "
                "or tracking task completion. Input: natural language request."
            ),
        )

    def _build_agent(self):
        tools = [self._make_calendar_tool(), self._make_task_tool()]

        llm = ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
            temperature=0,
        )

        return create_agent(model=llm, tools=tools, system_prompt=PRIMARY_SYSTEM_PROMPT)

    @property
    def agent(self):
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def ask(self, user_input: str) -> Dict[str, Any]:
        """Process a natural language request through the primary agent."""
        try:
            messages = list(self._conversation_history) + [HumanMessage(content=user_input)]
            result = self.agent.invoke({"messages": messages})
            output = "No response generated."
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage):
                    output = msg.content
                    break

            # Maintain conversation context (last 20 turns)
            self._conversation_history.append(HumanMessage(content=user_input))
            self._conversation_history.append(AIMessage(content=output))
            if len(self._conversation_history) > 40:
                self._conversation_history = self._conversation_history[-40:]

            return {"status": "success", "response": output}
        except Exception as exc:  # noqa: BLE001
            logger.error("PrimaryAgent error: %s", exc)
            return {
                "status": "error",
                "response": f"I encountered an error processing your request: {exc}",
            }

    def execute_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a multi-step workflow.

        workflow = {
            "name": "schedule_and_task",
            "steps": [
                {"agent": "task", "action": "Create task: ...", "context": {}},
                {"agent": "calendar", "action": "Schedule meeting: ...", "context": {}},
            ]
        }
        """
        results = []
        errors = []

        for i, step in enumerate(workflow.get("steps", [])):
            agent_name = step.get("agent", "primary")
            action = step.get("action", "")

            logger.info("Workflow step %d/%d: agent=%s", i + 1, len(workflow["steps"]), agent_name)

            try:
                if agent_name == "calendar":
                    output = self.calendar_agent.run(action)
                elif agent_name == "task":
                    output = self.task_agent.run(action)
                else:
                    result = self.ask(action)
                    output = result["response"]

                results.append({"step": i + 1, "agent": agent_name, "output": output})
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Step {i + 1} failed: {exc}"
                logger.error(error_msg)
                errors.append(error_msg)
                results.append({"step": i + 1, "agent": agent_name, "error": str(exc)})

        return {
            "workflow_name": workflow.get("name", "unnamed"),
            "total_steps": len(workflow.get("steps", [])),
            "completed_steps": len(results),
            "results": results,
            "errors": errors,
            "status": "completed" if not errors else "completed_with_errors",
        }

    def clear_history(self):
        """Reset the conversation history."""
        self._conversation_history = []
