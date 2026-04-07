import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.db import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Event details
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(500), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_all_day = Column(Boolean, default=False, nullable=False)

    # Google Calendar sync
    google_event_id = Column(String(255), nullable=True, unique=True, index=True)
    google_calendar_id = Column(String(255), nullable=True)
    synced_at = Column(DateTime, nullable=True)

    # Recurrence
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_rule = Column(String(500), nullable=True)  # RFC 5545 RRULE

    # Attendees stored as JSON string
    attendees = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="schedules")

    def __repr__(self) -> str:
        return f"<Schedule id={self.id} title={self.title!r} start={self.start_time}>"
