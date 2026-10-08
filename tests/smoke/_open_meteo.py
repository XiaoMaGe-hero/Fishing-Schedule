"""Helpers shared by the two Open-Meteo smoke tests."""
from __future__ import annotations

import json
from math import asin, cos, radians, sin, sqrt
from urllib.parse import urlencode


def build_url(base: str, points: list[dict], hourly: list[str], extra: dict | None = None) -> str:
    params = {
        "latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points),
        "hourly": ",".join(hourly),
        "timezone": "GMT",
        "forecast_days": 7,
    }
    params.update(extra or {})
    return base + "?" + urlencode(params, safe=",")


def as_list(body: bytes) -> list[dict]:
    """Open-Meteo returns an object for one location and a list for several."""
    data = json.loads(body)
    return data if isinstance(data, list) else [data]


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def describe(label: str, requested: dict, loc: dict, hourly: list[str]) -> dict[str, int]:
    """Print one location's response; return {variable: number of non-null values}."""
    h = loc.get("hourly", {})
    times = h.get("time", [])
    print(f"\n[{label}] requested ({requested['lat']}, {requested['lon']})")
    print(f"  grid cell returned: ({loc.get('latitude')}, {loc.get('longitude')}), "
          f"{km_between(requested['lat'], requested['lon'], loc.get('latitude', 0), loc.get('longitude', 0)):.1f} km away, "
          f"elevation {loc.get('elevation')} m")
    print(f"  timezone: {loc.get('timezone')} (utc_offset_seconds={loc.get('utc_offset_seconds')})")
    print(f"  hours: {len(times)}  from {times[0] if times else None} to {times[-1] if times else None}")
    non_null = {}
    for var in hourly:
        values = h.get(var)
        if values is None:
            print(f"  {var}: MISSING from response")
            non_null[var] = 0
            continue
        good = [v for v in values if v is not None]
        non_null[var] = len(good)
        print(f"  {var} [{loc.get('hourly_units', {}).get(var)}]: {len(good)}/{len(values)} non-null, "
              f"first 3 = {values[:3]}")
    return non_null
