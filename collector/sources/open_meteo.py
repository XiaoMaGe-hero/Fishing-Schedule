"""Open-Meteo: weather forecast and marine forecast.

API facts, confirmed in M0 (docs/m0-report.md 2.2 and 2.3):
  * no key needed; several spots go in one request;
  * with timezone=GMT the times are UTC, written as '2026-10-08T00:00';
  * units already match our contract (deg C, %, km/h, degrees, metres).

Public entry points: fetch_forecast() and fetch_marine(). Values are passed
through exactly as Open-Meteo returns them.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode

from collector.http import http_get

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
# 8 days from 00:00 UTC today always covers the 168 hours that start now.
FORECAST_DAYS = 8

# our field name -> Open-Meteo variable
FORECAST_FIELDS = {
    "air_temp_c": "temperature_2m",
    "precip_prob_pct": "precipitation_probability",
    "weather_code": "weather_code",
    "wind_speed_kmh": "wind_speed_10m",
    "wind_gust_kmh": "wind_gusts_10m",
    "wind_dir_deg": "wind_direction_10m",
}
MARINE_FIELDS = {
    "wave_height_m": "wave_height",
    "swell_height_m": "swell_wave_height",
    "sea_temp_c": "sea_surface_temperature",
}


def _url(base: str, spots: list[dict], fields: dict, extra: dict) -> str:
    params = {
        "latitude": ",".join(str(s["lat"]) for s in spots),
        "longitude": ",".join(str(s["lon"]) for s in spots),
        "hourly": ",".join(fields.values()),
        "timezone": "GMT",
        "forecast_days": FORECAST_DAYS,
        **extra,
    }
    return base + "?" + urlencode(params, safe=",")


def parse(body: bytes, spots: list[dict], fields: dict) -> dict:
    """Open-Meteo response -> {"spots": {spot_id: {"hourly": {time_utc: {field: value}}}}}."""
    data = json.loads(body)
    locations = data if isinstance(data, list) else [data]  # one spot comes back as an object
    if len(locations) != len(spots):
        raise ValueError(f"asked for {len(spots)} locations, got {len(locations)}")
    out = {}
    for spot, loc in zip(spots, locations):
        if loc.get("utc_offset_seconds") != 0:
            raise ValueError("Open-Meteo did not answer in UTC")
        hourly = loc["hourly"]
        rows = {}
        for i, t in enumerate(hourly["time"]):
            rows[t + ":00Z"] = {ours: hourly[theirs][i] for ours, theirs in fields.items()}
        out[spot["id"]] = {"grid_lat": loc.get("latitude"), "grid_lon": loc.get("longitude"), "hourly": rows}
    return {"spots": out}


def fetch_forecast(spots: list[dict], get=http_get) -> dict:
    body = get(_url(FORECAST_URL, spots, FORECAST_FIELDS, {"wind_speed_unit": "kmh"}))
    return parse(body, spots, FORECAST_FIELDS)


def fetch_marine(spots: list[dict], get=http_get) -> dict:
    body = get(_url(MARINE_URL, spots, MARINE_FIELDS, {}))
    return parse(body, spots, MARINE_FIELDS)
