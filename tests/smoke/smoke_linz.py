"""M0 smoke test: LINZ tide predictions for Lyttelton (yearly CSV).

Answers unknowns 1 and 2 of M0:
  1. What is the CSV layout?
  2. Are the times already adjusted for daylight saving?

Makes exactly one request.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from _common import finish, http_get, save_sample

NZ = ZoneInfo("Pacific/Auckland")
NZST = timezone(timedelta(hours=12))  # fixed offset, no daylight saving
YEAR = datetime.now(NZ).year
URL = f"https://static.charts.linz.govt.nz/tide-tables/maj-ports/csv/Lyttelton%20{YEAR}.csv"
HEADER_LINES = 3


def parse(text: str) -> tuple[list[str], list[tuple[datetime, float]], int]:
    """Return (header lines, [(naive local datetime, height_m)], number of day rows)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    header, rows = lines[:HEADER_LINES], lines[HEADER_LINES:]
    events: list[tuple[datetime, float]] = []
    for row in rows:
        cells = [c.strip() for c in row.split(",")]
        day, month, year = int(cells[0]), int(cells[2]), int(cells[3])
        pairs = cells[4:]
        for i in range(0, len(pairs) - 1, 2):
            if not pairs[i]:
                continue  # days with only three tides leave the last pair empty
            hh, mm = pairs[i].split(":")
            events.append((datetime(year, month, day, int(hh), int(mm)), float(pairs[i + 1])))
    events.sort()
    return header, events, len(rows)


def tide_type(events: list[tuple[datetime, float]], i: int) -> str:
    """The CSV does not label high/low; infer it from the neighbouring tide."""
    j = i + 1 if i + 1 < len(events) else i - 1
    return "high" if events[i][1] > events[j][1] else "low"


def dst_transitions(year: int) -> list[datetime]:
    """UTC instants in `year` where the Pacific/Auckland UTC offset changes."""
    out = []
    t = datetime(year, 1, 1, tzinfo=timezone.utc)
    prev = t.astimezone(NZ).utcoffset()
    while t.year == year:
        t += timedelta(hours=1)
        cur = t.astimezone(NZ).utcoffset()
        if cur != prev:
            out.append(t)
            prev = cur
    return out


def spanning_gap(utc_times: list[datetime], instant: datetime) -> tuple[float, float]:
    """(gap in hours between the two tides either side of `instant`,
    mean gap of the 4 tide-to-tide gaps before and the 4 after)."""
    k = next(i for i, t in enumerate(utc_times) if t > instant)
    gaps = [(utc_times[i + 1] - utc_times[i]).total_seconds() / 3600 for i in range(len(utc_times) - 1)]
    span = gaps[k - 1]
    around = gaps[max(0, k - 5):k - 1] + gaps[k:k + 4]
    return span, mean(around)


def main() -> None:
    status, _, body = http_get(URL)
    if status != 200:
        finish(False, f"LINZ CSV download failed (HTTP {status})")
    save_sample(f"linz_lyttelton_{YEAR}.csv", body)
    text = body.decode("utf-8-sig")

    print("\n--- First 6 raw lines ---")
    for ln in text.splitlines()[:6]:
        print(repr(ln))

    header, events, n_days = parse(text)
    print("\n--- Layout ---")
    print(f"header lines: {HEADER_LINES}; day rows: {n_days}; tide events: {len(events)}")
    print("row layout: day, weekday, month, year, then up to 4 x (HH:MM, height_m)")
    print(f"time basis stated in file header: {header[2]!r}")

    # Interpretation A: times are NZ civil time (already daylight-adjusted).
    # Interpretation B: times are NZ Standard Time all year (UTC+12).
    utc_a = [dt.replace(tzinfo=NZ).astimezone(timezone.utc) for dt, _ in events]
    utc_b = [dt.replace(tzinfo=NZST).astimezone(timezone.utc) for dt, _ in events]

    today = datetime.now(NZ).date()
    print(f"\n--- Tides for today, {today} (Pacific/Auckland) ---")
    todays = [i for i, (dt, _) in enumerate(events) if dt.date() == today]
    for i in todays:
        dt, h = events[i]
        print(f"{dt:%H:%M} as printed in file  {tide_type(events, i):4}  {h:.1f} m   "
              f"-> UTC if civil time: {utc_a[i]:%Y-%m-%d %H:%M}Z")
    print("Compare these with today's Lyttelton tides on the LINZ website / tide table PDF.")

    print("\n--- Daylight saving check ---")
    print("Tides are ~6.2 h apart. If the file is read with the wrong time basis, the gap")
    print("between the two tides either side of a clock change is off by one hour.")
    verdicts = []
    for instant in dst_transitions(YEAR):
        local = instant.astimezone(NZ)
        span_a, around_a = spanning_gap(utc_a, instant)
        span_b, around_b = spanning_gap(utc_b, instant)
        print(f"clock change at {local:%Y-%m-%d %H:%M %Z}:")
        print(f"  A (file = civil time, daylight-adjusted): gap {span_a:.2f} h, neighbours avg {around_a:.2f} h")
        print(f"  B (file = NZ Standard Time all year):     gap {span_b:.2f} h, neighbours avg {around_b:.2f} h")
        verdicts.append("A" if abs(span_a - around_a) < abs(span_b - around_b) else "B")
    if not verdicts:
        finish(False, "no clock change found in this year; cannot decide the time basis")
    if len(set(verdicts)) != 1:
        finish(False, f"time basis inconclusive, per-transition verdicts: {verdicts}")
    basis = ("civil time, ALREADY adjusted for daylight saving" if verdicts[0] == "A"
             else "NZ Standard Time all year, NOT adjusted for daylight saving")
    print(f"CONCLUSION: file times are {basis}.")

    ok = n_days >= 365 and len(todays) >= 3
    finish(ok, f"{n_days} day rows, {len(events)} tides, {len(todays)} today; times are {basis}")


if __name__ == "__main__":
    main()
