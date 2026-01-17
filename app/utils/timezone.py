"""
Timezone utilities for MamaStoria Comics
Handles conversion between UTC and Asia/Jakarta timezone
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Jakarta timezone (WIB = UTC+7)
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


def get_jakarta_now() -> datetime:
    """
    Get current datetime in Jakarta timezone
    
    Returns:
        datetime: Current time in Asia/Jakarta timezone
    """
    return datetime.now(JAKARTA_TZ)


def utc_to_jakarta(utc_dt: datetime) -> datetime:
    """
    Convert UTC datetime to Jakarta timezone
    
    Args:
        utc_dt: datetime object in UTC (can be naive or aware)
    
    Returns:
        datetime: datetime in Asia/Jakarta timezone
    """
    if utc_dt is None:
        return None
    
    # If naive, assume UTC
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    
    # Convert to Jakarta time
    return utc_dt.astimezone(JAKARTA_TZ)


def jakarta_to_utc(jakarta_dt: datetime) -> datetime:
    """
    Convert Jakarta datetime to UTC
    
    Args:
        jakarta_dt: datetime object in Jakarta timezone
    
    Returns:
        datetime: datetime in UTC timezone
    """
    if jakarta_dt is None:
        return None
    
    # If naive, assume Jakarta time
    if jakarta_dt.tzinfo is None:
        jakarta_dt = jakarta_dt.replace(tzinfo=JAKARTA_TZ)
    
    # Convert to UTC
    return jakarta_dt.astimezone(timezone.utc)


def get_jakarta_start_of_day(date: datetime = None) -> datetime:
    """
    Get start of day (00:00:00) in Jakarta timezone
    
    Args:
        date: specific date (defaults to today)
    
    Returns:
        datetime: Start of day in Jakarta timezone
    """
    if date is None:
        date = get_jakarta_now()
    
    # Ensure it's in Jakarta timezone
    if date.tzinfo is None:
        date = date.replace(tzinfo=JAKARTA_TZ)
    else:
        date = date.astimezone(JAKARTA_TZ)
    
    # Set to midnight
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def format_jakarta_time(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S WIB") -> str:
    """
    Format datetime as Jakarta time string
    
    Args:
        dt: datetime object (UTC or Jakarta)
        fmt: format string (default includes WIB suffix)
    
    Returns:
        str: Formatted time string in Jakarta timezone
    """
    if dt is None:
        return None
    
    jakarta_dt = utc_to_jakarta(dt) if dt.tzinfo == timezone.utc else dt
    return jakarta_dt.strftime(fmt)


def get_hours_since_jakarta_midnight() -> float:
    """
    Get hours elapsed since midnight Jakarta time
    Useful for "Today" filters in dashboards
    
    Returns:
        float: Hours since midnight (e.g., 15.5 for 3:30 PM)
    """
    now = get_jakarta_now()
    start_of_day = get_jakarta_start_of_day(now)
    diff = now - start_of_day
    return diff.total_seconds() / 3600
