import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ScheduleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_rule: Optional[str] = None
    attendees: Optional[str] = None  # JSON string of attendee list


class ScheduleCreate(ScheduleBase):
    user_id: uuid.UUID
    google_calendar_id: Optional[str] = "primary"


class ScheduleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_all_day: Optional[bool] = None
    is_recurring: Optional[bool] = None
    recurrence_rule: Optional[str] = None
    attendees: Optional[str] = None


class ScheduleRead(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    google_event_id: Optional[str] = None
    google_calendar_id: Optional[str] = None
    synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ScheduleListResponse(BaseModel):
    schedules: List[ScheduleRead]
    total: int


class FindSlotRequest(BaseModel):
    user_id: uuid.UUID
    duration_minutes: int = Field(..., ge=15, le=480)
    date_from: datetime
    date_to: datetime
    preferred_hours_start: int = Field(9, ge=0, le=23)
    preferred_hours_end: int = Field(17, ge=0, le=23)


class FindSlotResponse(BaseModel):
    available_slots: List[dict]
    message: str
