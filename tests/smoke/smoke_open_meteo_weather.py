"""M0 smoke test: Open-Meteo Forecast API (air temperature, rain, wind).

Checks that every field the design needs is returned for both spots and
covers 7 days. Makes exactly one request (both spots in one call).
"""
from __future__ import annotations

from _common import finish, http_get, save_sample
from _open_meteo import as_list, build_url, describe
from _spots import SPOTS

BASE = "https://api.open-meteo.com/v1/forecast"
HOURLY = ["temperature_2m", "precipitation_probability", "weather_code",
          "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m"]


def main() -> None:
    url = build_url(BASE, SPOTS, HOURLY, {"wind_speed_unit": "kmh"})
    status, _, body = http_get(url)
    if status != 200:
        print(body[:500].decode("utf-8", "replace"))
        finish(False, f"Open-Meteo forecast request failed (HTTP {status})")
    save_sample("open_meteo_forecast.json", body)

    problems = []
    for spot, loc in zip(SPOTS, as_list(body)):
        counts = describe(spot["id"], spot, loc, HOURLY)
        hours = len(loc.get("hourly", {}).get("time", []))
        if hours < 7 * 24:
            problems.append(f"{spot['id']}: only {hours} hours")
        for var, n in counts.items():
            if n < hours:
                problems.append(f"{spot['id']}: {var} has {hours - n} null/missing hours")

    print("\nNote: forecast_days=7 starts at 00:00 UTC today, so it reaches less than")
    print("7 x 24 h ahead of 'now'. M1 may need forecast_days=8 to cover a full 7 days ahead.")
    finish(not problems, "all fields present for 7 days at both spots" if not problems
           else "; ".join(problems))


if __name__ == "__main__":
    main()
