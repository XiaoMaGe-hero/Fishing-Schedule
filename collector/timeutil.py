"""Time helpers. Everything inside the project is UTC; only sources convert."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
NZ = ZoneInfo("Pacific/Auckland")
NZST = timezone(timedelta(hours=12))  # NZ Standard Time, no daylight saving


def iso(dt: datetime) -> str:
    """UTC datetime -> '2026-10-08T08:00:00Z'."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    """'2026-10-08T08:00:00Z' -> aware UTC datetime."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def floor_hour(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
