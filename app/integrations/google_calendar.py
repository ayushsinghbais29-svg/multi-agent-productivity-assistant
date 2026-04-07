import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarIntegration:
    """Wrapper around the Google Calendar API."""

    def __init__(self, credentials_dict: Optional[Dict[str, Any]] = None):
        self.settings = get_settings()
        self._service = None
        self._credentials_dict = credentials_dict

    def _get_credentials(self) -> Optional[Credentials]:
        if self._credentials_dict:
            return Credentials.from_authorized_user_info(self._credentials_dict, SCOPES)
        return None

    def _build_service(self):
        credentials = self._get_credentials()
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if credentials:
            self._service = build("calendar", "v3", credentials=credentials)
        else:
            logger.warning("No Google credentials available; service not built.")

    @property
    def service(self):
        if self._service is None:
            self._build_service()
        return self._service

    # ------------------------------------------------------------------
    # Event CRUD
    # ------------------------------------------------------------------

    def list_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """List calendar events within an optional time range."""
        if self.service is None:
            logger.error("Google Calendar service is not available.")
            return []
        try:
            params: Dict[str, Any] = {
                "calendarId": calendar_id,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": max_results,
            }
            if time_min:
                params["timeMin"] = time_min.isoformat() + "Z"
            if time_max:
                params["timeMax"] = time_max.isoformat() + "Z"

            result = self.service.events().list(**params).execute()
            return result.get("items", [])
        except HttpError as exc:
            logger.error("Failed to list events: %s", exc)
            return []

    def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
        calendar_id: str = "primary",
    ) -> Optional[Dict[str, Any]]:
        """Create a new calendar event."""
        if self.service is None:
            logger.error("Google Calendar service is not available.")
            return None
        try:
            event_body: Dict[str, Any] = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
            }
            if attendees:
                event_body["attendees"] = [{"email": e} for e in attendees]

            created = self.service.events().insert(calendarId=calendar_id, body=event_body).execute()
            logger.info("Created event %s: %s", created.get("id"), title)
            return created
        except HttpError as exc:
            logger.error("Failed to create event: %s", exc)
            return None

    def update_event(
        self,
        event_id: str,
        updates: Dict[str, Any],
        calendar_id: str = "primary",
    ) -> Optional[Dict[str, Any]]:
        """Update an existing calendar event."""
        if self.service is None:
            logger.error("Google Calendar service is not available.")
            return None
        try:
            existing = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            existing.update(updates)
            updated = (
                self.service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=existing)
                .execute()
            )
            logger.info("Updated event %s", event_id)
            return updated
        except HttpError as exc:
            logger.error("Failed to update event %s: %s", event_id, exc)
            return None

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> bool:
        """Delete a calendar event by its ID."""
        if self.service is None:
            logger.error("Google Calendar service is not available.")
            return False
        try:
            self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            logger.info("Deleted event %s", event_id)
            return True
        except HttpError as exc:
            logger.error("Failed to delete event %s: %s", event_id, exc)
            return False

    def find_free_slots(
        self,
        duration_minutes: int,
        date_from: datetime,
        date_to: datetime,
        preferred_start: int = 9,
        preferred_end: int = 17,
        calendar_id: str = "primary",
    ) -> List[Dict[str, Any]]:
        """Return a list of free time slots of the given duration."""
        busy_events = self.list_events(
            calendar_id=calendar_id,
            time_min=date_from,
            time_max=date_to,
        )

        # Build list of busy periods
        busy: List[tuple] = []
        for ev in busy_events:
            start_raw = ev.get("start", {}).get("dateTime")
            end_raw = ev.get("end", {}).get("dateTime")
            if start_raw and end_raw:
                busy.append(
                    (
                        datetime.fromisoformat(start_raw.rstrip("Z")),
                        datetime.fromisoformat(end_raw.rstrip("Z")),
                    )
                )
        busy.sort(key=lambda x: x[0])

        slots: List[Dict[str, Any]] = []
        candidate = date_from.replace(
            hour=preferred_start, minute=0, second=0, microsecond=0
        )

        while candidate + timedelta(minutes=duration_minutes) <= date_to:
            slot_end = candidate + timedelta(minutes=duration_minutes)

            # Check working hours
            if candidate.hour >= preferred_start and slot_end.hour <= preferred_end:
                overlap = any(
                    not (slot_end <= b_start or candidate >= b_end)
                    for b_start, b_end in busy
                )
                if not overlap:
                    slots.append({"start": candidate.isoformat(), "end": slot_end.isoformat()})
                    if len(slots) >= 10:
                        break

            candidate += timedelta(minutes=30)

        return slots
