"""Each source parses its real M0 sample correctly."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from collector.sources import ecan_flow, linz_tides, open_meteo
from collector.timeutil import parse_iso

from conftest import SAMPLES, UTC, no_network


def linz_events():
    return linz_tides.parse((SAMPLES / "linz_lyttelton_2026.csv").read_text(encoding="utf-8-sig"))


def test_linz_whole_year_parses():
    events = linz_events()
    assert len(events) == 1410
    times = [e["time_utc"] for e in events]
    assert times == sorted(times) and len(set(times)) == len(times)


def test_linz_times_are_nz_clock_time_converted_to_utc():
    # File row for 8 Oct 2026 (daylight time, UTC+13): 02:59 2.4, 09:10 0.5, 15:25 2.4, 21:39 0.5
    by_time = {e["time_utc"]: e for e in linz_events()}
    assert by_time["2026-10-07T13:59:00Z"] == {"time_utc": "2026-10-07T13:59:00Z", "type": "high", "height_m": 2.4}
    assert by_time["2026-10-07T20:10:00Z"]["type"] == "low"
    assert by_time["2026-10-08T08:39:00Z"]["height_m"] == 0.5
    # File row for 1 Jul 2026 (standard time, UTC+12) must shift by 12 h, not 13
    july = [e for e in linz_events() if e["time_utc"].startswith("2026-06-30T1") or e["time_utc"].startswith("2026-07-01")]
    raw_first = (SAMPLES / "linz_lyttelton_2026.csv").read_text(encoding="utf-8-sig").splitlines()
    row = next(r for r in raw_first if r.startswith("1,We,7,2026"))
    hh, mm = row.split(",")[4].split(":")
    expected = datetime(2026, 7, 1, int(hh), int(mm), tzinfo=UTC) - timedelta(hours=12)
    assert any(parse_iso(e["time_utc"]) == expected for e in july)


def test_linz_high_and_low_alternate():
    types = [e["type"] for e in linz_events()]
    assert all(a != b for a, b in zip(types, types[1:]))


def test_linz_no_jump_across_daylight_saving_changes():
    """Real rows around 5 Apr and 27 Sep 2026: every tide-to-tide gap stays near 6.2 h."""
    events = linz_events()
    for day in ("2026-04-04", "2026-04-05", "2026-09-26", "2026-09-27"):
        idx = [i for i, e in enumerate(events) if e["time_utc"].startswith(day)]
        for i in range(idx[0] - 1, idx[-1] + 1):
            gap = parse_iso(events[i + 1]["time_utc"]) - parse_iso(events[i]["time_utc"])
            assert timedelta(hours=5.5) < gap < timedelta(hours=7), (day, events[i], gap)


def test_linz_fetch_uses_the_file_in_the_repo(tmp_path):
    start = datetime(2026, 10, 8, 10, tzinfo=UTC)
    result = linz_tides.fetch("lyttelton", start, start + timedelta(hours=168), tmp_path, get=no_network)
    times = [parse_iso(e["time_utc"]) for e in result["events"]]
    assert times[0] < start and times[-1] > start + timedelta(hours=168)


def test_linz_fetch_downloads_next_year_once_and_keeps_it(tmp_path):
    calls = []

    def fake_linz(url):
        calls.append(url)
        # stand-in body: the real 2026 file with the year relabelled; only the download path is under test
        return (SAMPLES / "linz_lyttelton_2026.csv").read_text(encoding="utf-8-sig").replace(",2026,", ",2027,").encode()

    start = datetime(2026, 12, 28, tzinfo=UTC)
    for _ in range(2):
        linz_tides.fetch("lyttelton", start, start + timedelta(hours=168), tmp_path, get=fake_linz)
    assert calls == ["https://static.charts.linz.govt.nz/tide-tables/maj-ports/csv/Lyttelton%202027.csv"]
    assert (tmp_path / "linz" / "lyttelton_2027.csv").exists()


def test_open_meteo_values_are_passed_through_unchanged(spots):
    for sample, fields in (("open_meteo_forecast.json", open_meteo.FORECAST_FIELDS),
                           ("open_meteo_marine.json", open_meteo.MARINE_FIELDS)):
        body = (SAMPLES / sample).read_bytes()
        parsed = open_meteo.parse(body, spots, fields)
        raw = json.loads(body)
        for spot, loc in zip(spots, raw):
            rows = parsed["spots"][spot["id"]]["hourly"]
            assert len(rows) == len(loc["hourly"]["time"]) == 168
            for i in (0, 37, 167):
                row = rows[loc["hourly"]["time"][i] + ":00Z"]
                for ours, theirs in fields.items():
                    assert row[ours] == loc["hourly"][theirs][i]


def test_open_meteo_request_urls(spots):
    seen = []

    def capture(url):
        seen.append(url)
        raise RuntimeError("stop after building the URL")

    for fn in (open_meteo.fetch_forecast, open_meteo.fetch_marine):
        try:
            fn(spots, get=capture)
        except RuntimeError:
            pass
    assert "latitude=-43.507,-43.558" in seen[0] and "timezone=GMT" in seen[0]
    assert "forecast_days=8" in seen[0] and "wind_speed_unit=kmh" in seen[0]
    assert seen[1].startswith("https://marine-api.open-meteo.com/v1/marine?")
    assert "sea_surface_temperature" in seen[1]


def test_ecan_times_are_nz_standard_time_converted_to_utc():
    text = (SAMPLES / "ecan_flow_66401_1week.csv").read_text(encoding="utf-8-sig")
    flow = ecan_flow.parse(text)
    first_row = text.splitlines()[1].split(",")          # e.g. 66401,1/10/2026 11:25:00 PM,99.451
    local = datetime.strptime(first_row[1], "%d/%m/%Y %I:%M:%S %p")
    assert parse_iso(flow["series"][0]["time_utc"]) == local.replace(tzinfo=UTC) - timedelta(hours=12)
    assert flow["series"][0]["flow_m3s"] == float(first_row[2])
    assert flow["site_id"] == "66401" and len(flow["series"]) == len(text.splitlines()) - 1
    steps = {parse_iso(b["time_utc"]) - parse_iso(a["time_utc"]) for a, b in zip(flow["series"], flow["series"][1:])}
    assert steps == {timedelta(minutes=5)}
