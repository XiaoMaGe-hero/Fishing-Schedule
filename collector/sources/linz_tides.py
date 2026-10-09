"""LINZ tide predictions (yearly CSV per port).

File facts, confirmed in M0 (docs/m0-report.md 2.1):
  * 3 header lines, then one row per day:
    day, weekday, month, year, then up to 4 x (HH:MM, height in metres);
  * times are NZ clock time, already adjusted for daylight saving;
  * the file does not say which tides are high and which are low.

Public entry point: fetch(). It returns times in UTC.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from collector.http import http_get
from collector.timeutil import NZ, UTC, iso

URL = "https://static.charts.linz.govt.nz/tide-tables/maj-ports/csv/{port}%20{year}.csv"
PORT_FILE_NAMES = {"lyttelton": "Lyttelton"}
REPO_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "linz"
HEADER_LINES = 3
TYPICAL_GAP = timedelta(hours=6, minutes=12)  # high tide to the next low tide


def _to_utc(local: datetime, previous_utc: datetime | None) -> datetime:
    """NZ clock time -> UTC.

    On the night daylight saving ends, 02:00-02:59 happens twice. For such a
    time, pick the reading that sits closest to one tide gap after the
    previous tide.
    """
    first = local.replace(tzinfo=NZ, fold=0).astimezone(UTC)
    second = local.replace(tzinfo=NZ, fold=1).astimezone(UTC)
    if first == second or previous_utc is None:
        return first
    expected = previous_utc + TYPICAL_GAP
    return min((first, second), key=lambda t: abs(t - expected))


def parse(text: str) -> list[dict]:
    """Parse one yearly file into [{"time_utc", "type", "height_m"}], in time order."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    raw: list[tuple[datetime, float]] = []
    for row in lines[HEADER_LINES:]:
        cells = [c.strip() for c in row.split(",")]
        day, month, year = int(cells[0]), int(cells[2]), int(cells[3])
        pairs = cells[4:]
        for i in range(0, len(pairs) - 1, 2):
            if not pairs[i]:
                continue  # some days have only three tides
            hh, mm = pairs[i].split(":")
            raw.append((datetime(year, month, day, int(hh), int(mm)), float(pairs[i + 1])))
    raw.sort()

    events: list[dict] = []
    previous: datetime | None = None
    for i, (local, height) in enumerate(raw):
        utc = _to_utc(local, previous)
        neighbour = raw[i + 1][1] if i + 1 < len(raw) else raw[i - 1][1]
        events.append({"time_utc": iso(utc), "type": "high" if height > neighbour else "low",
                       "height_m": height})
        previous = utc
    return events


def _load_year(port: str, year: int, state_dir: Path, get) -> str:
    """Yearly file from the state folder, else the repo, else LINZ (then kept in state)."""
    name = f"{port}_{year}.csv"
    for folder in (state_dir / "linz", REPO_DATA_DIR):
        path = folder / name
        if path.exists():
            return path.read_text(encoding="utf-8-sig")
    body = get(URL.format(port=PORT_FILE_NAMES[port], year=year))
    target = state_dir / "linz" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return body.decode("utf-8-sig")


def fetch(port: str, start: datetime, end: datetime, state_dir: Path, get=http_get) -> dict:
    """Tides for `port` covering start..end (UTC), with two days of margin each side.

    Returns {"port": ..., "events": [{"time_utc", "type", "height_m"}, ...]}.
    A file for next year is downloaded the first time the range reaches into it.
    """
    lo, hi = start - timedelta(days=2), end + timedelta(days=2)
    years = sorted({lo.astimezone(NZ).year, hi.astimezone(NZ).year})
    events: list[dict] = []
    for year in years:
        events.extend(parse(_load_year(port, year, state_dir, get)))
    events.sort(key=lambda e: e["time_utc"])
    return {"port": port, "events": [e for e in events if iso(lo) <= e["time_utc"] <= iso(hi)]}
