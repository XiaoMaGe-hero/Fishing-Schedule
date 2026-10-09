"""Merge the sources into one hourly grid per spot.

No network access and no scoring logic here: this module only reshapes data
and derives tide height, tide phase, wind relative to the shore, and daylight.
Output matches schemas/conditions.schema.json.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from math import cos, pi

from astral import Observer, moon
from astral.sun import sun

from collector.timeutil import NZ, UTC, iso, parse_iso

HOURS = 168
DAYLIGHT_MARGIN = timedelta(minutes=60)
FORECAST_KEYS = ["air_temp_c", "precip_prob_pct", "weather_code",
                 "wind_speed_kmh", "wind_gust_kmh", "wind_dir_deg"]
MARINE_KEYS = ["wave_height_m", "swell_height_m", "sea_temp_c"]


def hour_grid(start: datetime) -> list[datetime]:
    return [start + timedelta(hours=i) for i in range(HOURS)]


# --- tide ---------------------------------------------------------------

def shift_events(events: list[dict], offset_min: int) -> list[dict]:
    """Apply a spot's tide time offset to the reference port's tides."""
    shift = timedelta(minutes=offset_min)
    return [{**e, "time_utc": iso(parse_iso(e["time_utc"]) + shift)} for e in events]


def tide_at(events: list[dict], when: datetime) -> tuple[float | None, str | None]:
    """(estimated height in metres, 'rising' | 'falling') at `when`.

    Half-cosine interpolation between the tide before and the tide after.
    Returns (None, None) when `when` is not between two known tides.
    """
    for before, after in zip(events, events[1:]):
        t1, t2 = parse_iso(before["time_utc"]), parse_iso(after["time_utc"])
        if t1 <= when < t2:
            h1, h2 = before["height_m"], after["height_m"]
            progress = (when - t1) / (t2 - t1)
            height = h1 + (h2 - h1) * (1 - cos(pi * progress)) / 2
            return round(height, 2), "rising" if h2 > h1 else "falling"
    return None, None


# --- wind ---------------------------------------------------------------

def wind_relative(wind_from_deg: float | None, shore_facing_deg: float | None) -> str | None:
    """Wind relative to the shore.

    wind_from_deg is where the wind comes FROM. shore_facing_deg is the
    direction the shore faces, i.e. out to sea. Less than 45 degrees apart:
    the wind blows in from the sea (onshore). More than 135: offshore.
    """
    if wind_from_deg is None or shore_facing_deg is None:
        return None
    angle = abs(wind_from_deg - shore_facing_deg) % 360
    angle = min(angle, 360 - angle)
    if angle < 45:
        return "onshore"
    if angle > 135:
        return "offshore"
    return "cross"


# --- sun and moon -------------------------------------------------------

def sun_times(lat: float, lon: float, local_day: date) -> tuple[datetime, datetime]:
    """(sunrise, sunset) in UTC for a Pacific/Auckland calendar day."""
    observer = Observer(latitude=lat, longitude=lon)
    found: dict[str, datetime] = {}
    # astral may hand back the event of a neighbouring day this far east of
    # Greenwich, so look at the days either side and keep the right one.
    for candidate in (local_day, local_day - timedelta(days=1), local_day + timedelta(days=1)):
        times = sun(observer, date=candidate, tzinfo=NZ)
        for key in ("sunrise", "sunset"):
            if key not in found and times[key].astimezone(NZ).date() == local_day:
                found[key] = times[key].astimezone(UTC)
    return found["sunrise"], found["sunset"]


def moon_fraction(local_day: date) -> float:
    """Fraction of the lunar cycle: 0 = new moon, 0.5 = full moon."""
    return round(min(moon.phase(local_day) / 28.0, 0.999), 3)


def build_days(lat: float, lon: float, grid: list[datetime]) -> tuple[list[dict], list[tuple[datetime, datetime]]]:
    """Per local day: the entries for the "days" list, and the daylight windows."""
    first, last = grid[0].astimezone(NZ).date(), grid[-1].astimezone(NZ).date()
    days, windows = [], []
    day = first - timedelta(days=1)  # one extra day each side for the windows only
    while day <= last + timedelta(days=1):
        sunrise, sunset = sun_times(lat, lon, day)
        windows.append((sunrise - DAYLIGHT_MARGIN, sunset + DAYLIGHT_MARGIN))
        if first <= day <= last:
            days.append({"date_local": day.isoformat(), "sunrise_utc": iso(sunrise),
                         "sunset_utc": iso(sunset), "moon_phase": moon_fraction(day)})
        day += timedelta(days=1)
    return days, windows


# --- the whole file -----------------------------------------------------

def build_conditions(spot: dict, start: datetime, generated_at: datetime,
                     tides: dict | None, forecast: dict | None, marine: dict | None) -> dict:
    """Build conditions/{spot_id}.json for one spot.

    tides / forecast / marine are the sources' own return values, or None
    when a source has never succeeded; missing values become null.
    """
    grid = hour_grid(start)
    offset = spot.get("tide_offset_min")
    events = shift_events(tides["events"], offset or 0) if tides else []
    forecast_rows = (forecast or {}).get("spots", {}).get(spot["id"], {}).get("hourly", {})
    marine_rows = (marine or {}).get("spots", {}).get(spot["id"], {}).get("hourly", {})
    days, windows = build_days(spot["lat"], spot["lon"], grid)

    hourly = []
    for when in grid:
        key = iso(when)
        height, phase = tide_at(events, when)
        f, m = forecast_rows.get(key, {}), marine_rows.get(key, {})
        row = {"time_utc": key, "tide_height_m": height, "tide_phase": phase}
        row.update({k: f.get(k) for k in FORECAST_KEYS})
        row["wind_relative"] = wind_relative(row["wind_dir_deg"], spot.get("shore_facing_deg"))
        row.update({k: m.get(k) for k in MARINE_KEYS})
        row["is_daylight"] = any(lo <= when <= hi for lo, hi in windows)
        hourly.append(row)

    # tides shown with the file: from the last one before the grid to the first one after it
    times = [parse_iso(e["time_utc"]) for e in events]
    lo = max((i for i, t in enumerate(times) if t <= grid[0]), default=0)
    hi = min((i for i, t in enumerate(times) if t >= grid[-1]), default=len(events) - 1)
    return {
        "schema_version": 1,
        "generated_at": iso(generated_at),
        "spot_id": spot["id"],
        "tide_reference": spot.get("tide_reference", "lyttelton"),
        "tide_offset_min": offset or 0,
        "tide_offset_assumed": offset is None,
        "hourly": hourly,
        "tide_events": events[lo:hi + 1],
        "days": days,
    }


def build_river_flow(flow: dict | None, generated_at: datetime, site_id: str, site_name: str) -> dict:
    return {
        "schema_version": 1,
        "generated_at": iso(generated_at),
        "site_id": (flow or {}).get("site_id", site_id),
        "site_name": (flow or {}).get("site_name", site_name),
        "series": (flow or {}).get("series", []),
    }
