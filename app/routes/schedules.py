import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.integrations.google_calendar import GoogleCalendarIntegration
from app.models.schedule import Schedule
from app.schemas.schedule import (
    FindSlotRequest,
    FindSlotResponse,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleRead,
    ScheduleUpdate,
)
from app.utils.logger import get_logger
from app.utils.validators import validate_date_range

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/schedules", tags=["Schedules"])


def get_calendar(db: Session = Depends(get_db)) -> GoogleCalendarIntegration:
    # In production, credentials would be fetched per user from the DB.
    return GoogleCalendarIntegration()


@router.get("", response_model=ScheduleListResponse)
def list_schedules(
    user_id: uuid.UUID = Query(...),
    time_min: Optional[datetime] = Query(None),
    time_max: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Schedule).filter(Schedule.user_id == user_id)
    if time_min:
        query = query.filter(Schedule.start_time >= time_min)
    if time_max:
        query = query.filter(Schedule.end_time <= time_max)
    schedules = query.order_by(Schedule.start_time).all()
    return ScheduleListResponse(schedules=schedules, total=len(schedules))


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule_data: ScheduleCreate,
    db: Session = Depends(get_db),
    calendar: GoogleCalendarIntegration = Depends(get_calendar),
):
    if not validate_date_range(schedule_data.start_time, schedule_data.end_time):
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    # Persist locally
    schedule = Schedule(
        user_id=schedule_data.user_id,
        title=schedule_data.title,
        description=schedule_data.description,
        location=schedule_data.location,
        start_time=schedule_data.start_time,
        end_time=schedule_data.end_time,
        is_all_day=schedule_data.is_all_day,
        is_recurring=schedule_data.is_recurring,
        recurrence_rule=schedule_data.recurrence_rule,
        attendees=schedule_data.attendees,
        google_calendar_id=schedule_data.google_calendar_id,
    )

    # Optionally sync with Google Calendar
    if calendar.service:
        attendees_list = None
        if schedule_data.attendees:
            import json
            try:
                attendees_list = json.loads(schedule_data.attendees)
            except Exception:
                pass

        gcal_event = calendar.create_event(
            title=schedule_data.title,
            start_time=schedule_data.start_time,
            end_time=schedule_data.end_time,
            description=schedule_data.description or "",
            location=schedule_data.location or "",
            attendees=attendees_list,
        )
        if gcal_event:
            schedule.google_event_id = gcal_event.get("id")
            schedule.synced_at = datetime.utcnow()

    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: uuid.UUID, db: Session = Depends(get_db)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: uuid.UUID,
    update_data: ScheduleUpdate,
    db: Session = Depends(get_db),
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(schedule, field, value)

    if update_data.start_time and update_data.end_time:
        if not validate_date_range(update_data.start_time, update_data.end_time):
            raise HTTPException(status_code=400, detail="start_time must be before end_time")

    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: uuid.UUID,
    db: Session = Depends(get_db),
    calendar: GoogleCalendarIntegration = Depends(get_calendar),
):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.google_event_id and calendar.service:
        calendar.delete_event(schedule.google_event_id)

    db.delete(schedule)
    db.commit()


@router.post("/find-slot", response_model=FindSlotResponse)
def find_available_slot(
    request: FindSlotRequest,
    calendar: GoogleCalendarIntegration = Depends(get_calendar),
):
    if not validate_date_range(request.date_from, request.date_to):
        raise HTTPException(status_code=400, detail="date_from must be before date_to")

    slots = calendar.find_free_slots(
        duration_minutes=request.duration_minutes,
        date_from=request.date_from,
        date_to=request.date_to,
        preferred_start=request.preferred_hours_start,
        preferred_end=request.preferred_hours_end,
    )

    if not slots:
        return FindSlotResponse(
            available_slots=[],
            message="No available slots found in the specified range.",
        )

    return FindSlotResponse(
        available_slots=slots,
        message=f"Found {len(slots)} available slot(s).",
    )
