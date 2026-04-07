"""Calendar sub-agent: manages Google Calendar interactions."""
from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.agents.tools import (
    make_create_event_tool,
    make_find_free_slots_tool,
    make_list_events_tool,
)
from app.config import get_settings
from app.integrations.google_calendar import GoogleCalendarIntegration
from app.utils.logger import get_logger

logger = get_logger(__name__)

CALENDAR_SYSTEM_PROMPT = """You are a Calendar Management Agent.
Your job is to help users manage their Google Calendar by:
- Listing and searching events
- Creating, updating, and deleting calendar events
- Finding available time slots for meetings
- Scheduling meetings and appointments

Always be precise with dates and times. Confirm details before making changes.
"""


class CalendarAgent:
    def __init__(self, credentials_dict: Optional[Dict[str, Any]] = None):
        self.settings = get_settings()
        self.calendar = GoogleCalendarIntegration(credentials_dict=credentials_dict)
        self._agent = None

    def _build_agent(self):
        tools = [
            make_list_events_tool(self.calendar),
            make_create_event_tool(self.calendar),
            make_find_free_slots_tool(self.calendar),
        ]

        llm = ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
            temperature=0,
        )

        return create_agent(model=llm, tools=tools, system_prompt=CALENDAR_SYSTEM_PROMPT)

    @property
    def agent(self):
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def run(self, user_input: str, chat_history: Optional[List] = None) -> str:
        """Run the calendar agent with the given user input."""
        try:
            messages = list(chat_history or []) + [HumanMessage(content=user_input)]
            result = self.agent.invoke({"messages": messages})
            # Extract last AI message
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage):
                    return msg.content
            return "No response generated."
        except Exception as exc:  # noqa: BLE001
            logger.error("CalendarAgent error: %s", exc)
            return f"Calendar agent encountered an error: {exc}"
