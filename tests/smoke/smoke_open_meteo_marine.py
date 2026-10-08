"""M0 smoke test: Open-Meteo Marine API (sea temperature, waves, swell).

Answers unknown 3 of M0: do the two spot coordinates return data, or do
they fall on land cells? If a spot returns nothing, one extra request tries
an open-sea point nearby. At most two requests.
"""
from __future__ import annotations

from _common import finish, http_get, save_sample
from _open_meteo import as_list, build_url, describe
from _spots import OFFSHORE_FALLBACK, SPOTS

BASE = "https://marine-api.open-meteo.com/v1/marine"
HOURLY = ["wave_height", "swell_wave_height", "sea_surface_temperature"]


def main() -> None:
    status, _, body = http_get(build_url(BASE, SPOTS, HOURLY))
    if status != 200:
        print(body[:500].decode("utf-8", "replace"))
        finish(False, f"Open-Meteo marine request failed (HTTP {status})")
    save_sample("open_meteo_marine.json", body)

    notes, empty_spots = [], []
    for spot, loc in zip(SPOTS, as_list(body)):
        counts = describe(spot["id"], spot, loc, HOURLY)
        hours = len(loc.get("hourly", {}).get("time", []))
        empty = [v for v, n in counts.items() if n == 0]
        partial = [f"{v} ({hours - n} null)" for v, n in counts.items() if 0 < n < hours]
        if empty:
            empty_spots.append(spot)
            notes.append(f"{spot['id']}: NO data for {', '.join(empty)}")
        elif partial:
            notes.append(f"{spot['id']}: partly null: {', '.join(partial)}")
        else:
            notes.append(f"{spot['id']}: all three fields non-null for {hours} h")

    ok = not empty_spots
    if empty_spots:
        print("\n--- Retrying empty spots with open-sea fallback coordinates ---")
        points = [OFFSHORE_FALLBACK[s["id"]] for s in empty_spots]
        status, _, body = http_get(build_url(BASE, points, HOURLY))
        if status == 200:
            save_sample("open_meteo_marine_fallback.json", body)
            ok = True
            for spot, point, loc in zip(empty_spots, points, as_list(body)):
                counts = describe(f"{spot['id']} fallback", point, loc, HOURLY)
                if any(n == 0 for n in counts.values()):
                    ok = False
                    notes.append(f"{spot['id']}: fallback ({point['lat']}, {point['lon']}) is ALSO empty")
                else:
                    notes.append(f"{spot['id']}: fallback ({point['lat']}, {point['lon']}) returns data")
        else:
            notes.append(f"fallback request failed (HTTP {status})")

    finish(ok, "; ".join(notes))


if __name__ == "__main__":
    main()
