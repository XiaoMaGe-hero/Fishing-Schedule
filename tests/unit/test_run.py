"""End-to-end collector runs on the real samples, without network."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from collector import run
from collector.timeutil import NZ, parse_iso
from publish import run as publish

from conftest import SAMPLE_NOW, SAMPLE_START, SAMPLES, UTC, replay_fetchers


def load(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_outputs_match_the_schemas(collected):
    out, meta = collected
    assert publish.validate(out) == []
    assert {s["status"] for s in meta["sources"].values()} == {"ok"}
    assert sorted(p.name for p in (out / "conditions").glob("*.json")) == ["new-brighton-pier.json", "southshore.json"]


def test_hours_are_168_consecutive_utc_hours(collected):
    out, _ = collected
    hours = [parse_iso(h["time_utc"]) for h in load(out, "conditions/new-brighton-pier.json")["hourly"]]
    assert hours[0] == datetime(2026, 10, 8, 10, tzinfo=UTC) and len(hours) == 168
    assert all(b - a == timedelta(hours=1) for a, b in zip(hours, hours[1:]))


def test_values_equal_what_open_meteo_returned(collected, spots):
    """Acceptance item 4: air temperature, wind speed, wind direction and sea temperature."""
    out, _ = collected
    raw_f = json.loads((SAMPLES / "open_meteo_forecast.json").read_bytes())
    raw_m = json.loads((SAMPLES / "open_meteo_marine.json").read_bytes())
    for n, spot in enumerate(spots):
        hourly = {h["time_utc"]: h for h in load(out, f"conditions/{spot['id']}.json")["hourly"]}
        for stamp in ("2026-10-08T10:00", "2026-10-10T03:00", "2026-10-14T23:00"):
            i = raw_f[n]["hourly"]["time"].index(stamp)
            row = hourly[stamp + ":00Z"]
            assert row["air_temp_c"] == raw_f[n]["hourly"]["temperature_2m"][i]
            assert row["wind_speed_kmh"] == raw_f[n]["hourly"]["wind_speed_10m"][i]
            assert row["wind_dir_deg"] == raw_f[n]["hourly"]["wind_direction_10m"][i]
            assert row["sea_temp_c"] == raw_m[n]["hourly"]["sea_surface_temperature"][i]


def test_tide_events_equal_the_linz_file(collected):
    """Acceptance item 3: the file's tides for 9 Oct 2026 are 03:52 2.4, 10:05 0.5, 16:15 2.4, 22:30 0.4 (NZDT)."""
    out, _ = collected
    events = {e["time_utc"]: e for e in load(out, "conditions/new-brighton-pier.json")["tide_events"]}
    for local, kind, height in (((3, 52), "high", 2.4), ((10, 5), "low", 0.5), ((16, 15), "high", 2.4), ((22, 30), "low", 0.4)):
        stamp = datetime(2026, 10, 9, *local, tzinfo=NZ).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert events[stamp]["type"] == kind and events[stamp]["height_m"] == height


def test_missing_spot_settings_are_flagged_not_guessed(collected):
    out, _ = collected
    pier, south = load(out, "conditions/new-brighton-pier.json"), load(out, "conditions/southshore.json")
    assert pier["tide_offset_assumed"] is False and south["tide_offset_assumed"] is True
    assert south["tide_offset_min"] == 0
    assert all(h["wind_relative"] is None for h in south["hourly"])          # no shore_facing_deg yet
    assert {h["wind_relative"] for h in pier["hourly"] if h["wind_dir_deg"] is not None} <= {"onshore", "offshore", "cross"}


def test_hours_beyond_the_forecast_are_null_not_dropped(collected):
    """The M0 samples hold 7 days from 00:00 UTC, so the last 10 of our 168 hours have no forecast."""
    out, _ = collected
    hourly = load(out, "conditions/new-brighton-pier.json")["hourly"]
    assert all(h["air_temp_c"] is not None for h in hourly[:158])
    assert all(h["air_temp_c"] is None and h["sea_temp_c"] is None for h in hourly[158:])
    assert all(h["tide_height_m"] is not None for h in hourly)               # tides come from the yearly file


def test_one_failing_source_does_not_stop_the_others(collected, spots, monkeypatch):
    """Acceptance item 5."""
    out, _ = collected
    before = load(out, "river_flow.json")
    later = SAMPLE_NOW + timedelta(hours=3)
    monkeypatch.setenv("FISHING_FORCE_FAIL", "ecan_flow")
    meta = run.collect(out, later, replay_fetchers(spots, later, out / "state"), spots)
    assert meta["sources"]["ecan_flow"]["status"] == "failed"
    assert meta["sources"]["ecan_flow"]["last_success_utc"] == "2026-10-08T10:15:00Z"
    assert "forced failure" in meta["sources"]["ecan_flow"]["error"]
    assert {meta["sources"][n]["status"] for n in run.SOURCE_NAMES if n != "ecan_flow"} == {"ok"}
    assert load(out, "river_flow.json")["series"] == before["series"]        # old data kept
    assert load(out, "conditions/southshore.json")["hourly"][0]["time_utc"] == "2026-10-08T13:00:00Z"  # others updated
    assert publish.validate(out) == []


def test_a_source_that_never_worked_gives_nulls_and_valid_files(tmp_path, spots, monkeypatch):
    monkeypatch.setenv("FISHING_FORCE_FAIL", "open_meteo_marine")
    out = tmp_path / "out"
    meta = run.collect(out, SAMPLE_NOW, replay_fetchers(spots, SAMPLE_NOW, out / "state"), spots)
    assert meta["sources"]["open_meteo_marine"] == {
        "status": "failed", "last_success_utc": None, "last_attempt_utc": "2026-10-08T10:15:00Z",
        "error": "RuntimeError: forced failure (FISHING_FORCE_FAIL)"}
    first = load(out, "conditions/new-brighton-pier.json")["hourly"][0]
    assert first["sea_temp_c"] is None and first["air_temp_c"] is not None
    assert publish.validate(out) == []


def test_running_twice_gives_the_same_files(collected, spots):
    out, _ = collected
    first = {p.name: p.read_bytes() for p in out.rglob("*.json")}
    run.collect(out, SAMPLE_NOW, replay_fetchers(spots, SAMPLE_NOW, out / "state"), spots)
    assert first == {p.name: p.read_bytes() for p in out.rglob("*.json")}


@pytest.mark.parametrize("now", [
    datetime(2026, 4, 3, 5, 30, tzinfo=UTC),    # daylight saving ends 5 Apr 2026 03:00 NZDT
    datetime(2026, 9, 25, 5, 30, tzinfo=UTC),   # daylight saving starts 27 Sep 2026 02:00 NZST
])
def test_daylight_saving_change_inside_the_week(tmp_path, spots, now):
    """Acceptance item 8 (the part the design allows as a unit test).

    Tides: the real LINZ 2026 file. Weather: the real M0 samples with their
    timestamps moved so they cover the week around the clock change.
    """
    out = tmp_path / "out"
    shift = now.replace(hour=0, minute=0) - SAMPLE_START
    run.collect(out, now, replay_fetchers(spots, now, out / "state", shift), spots)
    assert publish.validate(out) == []
    doc = load(out, "conditions/new-brighton-pier.json")

    hours = [parse_iso(h["time_utc"]) for h in doc["hourly"]]
    assert len(set(hours)) == 168 and all(b - a == timedelta(hours=1) for a, b in zip(hours, hours[1:]))
    assert all(h["tide_height_m"] is not None and h["air_temp_c"] is not None for h in doc["hourly"][:160])

    days = [d["date_local"] for d in doc["days"]]
    assert len(set(days)) == len(days) == 8 and days == sorted(days)
    local_dates = {h.astimezone(NZ).date().isoformat() for h in hours}
    assert local_dates == set(days)                                           # no local day missing or doubled

    gaps = [parse_iso(b["time_utc"]) - parse_iso(a["time_utc"]) for a, b in zip(doc["tide_events"], doc["tide_events"][1:])]
    assert all(timedelta(hours=5.5) < g < timedelta(hours=7) for g in gaps)
    # daylight must follow the real sun, whatever the clocks do
    for hour in doc["hourly"]:
        local = parse_iso(hour["time_utc"]).astimezone(NZ)
        if 11 <= local.hour <= 14:
            assert hour["is_daylight"] is True
        if local.hour in (0, 1, 2, 3):
            assert hour["is_daylight"] is False
