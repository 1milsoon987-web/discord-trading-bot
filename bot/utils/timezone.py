"""Timezone and session-open helpers."""

from __future__ import annotations

from datetime import datetime, time

import pytz

from bot.config import get_settings

# Trading sessions in UTC (approximate open times)
SESSION_OPENS_UTC: dict[str, time] = {
    "asia": time(0, 0),
    "london": time(7, 0),
    "new_york": time(12, 0),
}


def get_local_tz() -> pytz.BaseTzInfo:
    """Return the configured local timezone."""
    return pytz.timezone(get_settings().timezone)


def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=pytz.UTC)


def now_local() -> datetime:
    """Return the current datetime in the configured local timezone."""
    return now_utc().astimezone(get_local_tz())


def utc_time_to_local_str(t: time) -> str:
    """Format a UTC time-of-day as a local-time string `HH:MM`."""
    today_utc = datetime.combine(now_utc().date(), t, tzinfo=pytz.UTC)
    return today_utc.astimezone(get_local_tz()).strftime("%H:%M")
