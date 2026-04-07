from datetime import datetime
from typing import Optional


def validate_date_range(start: datetime, end: datetime) -> bool:
    """Return True if start is strictly before end."""
    return start < end


def validate_future_date(dt: datetime, allow_past: bool = False) -> bool:
    """Return True if the datetime is in the future (or allow_past is set)."""
    if allow_past:
        return True
    return dt > datetime.utcnow()


def sanitize_string(value: Optional[str], max_length: int = 500) -> Optional[str]:
    """Strip whitespace and truncate to max_length."""
    if value is None:
        return None
    return value.strip()[:max_length]
