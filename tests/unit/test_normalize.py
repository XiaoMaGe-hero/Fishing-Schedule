"""Derived values: tide curve, wind relative to shore, daylight, moon."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from collector import normalize
from collector.timeutil import NZ, UTC


EVENTS = [
    {"time_utc": "2026-10-08T08:00:00Z", "type": "low", "height_m": 0.5},
    {"time_utc": "2026-10-08T14:00:00Z", "type": "high", "height_m": 2.5},
    {"time_utc": "2026-10-08T20:00:00Z", "type": "low", "height_m": 0.5},
]


def at(hour, minute=0):
    return datetime(2026, 10, 8, hour, minute, tzinfo=UTC)


def test_tide_curve_hits_the_official_points_and_the_midpoint():
    assert normalize.tide_at(EVENTS, at(8)) == (0.5, "rising")
    assert normalize.tide_at(EVENTS, at(11)) == (1.5, "rising")     # halfway in time = halfway in height
    assert normalize.tide_at(EVENTS, at(14)) == (2.5, "falling")
    assert normalize.tide_at(EVENTS, at(17)) == (1.5, "falling")
    quarter, _ = normalize.tide_at(EVENTS, at(9, 30))
    assert 0.5 < quarter < 1.0                                       # cosine: slow near the turn


def test_tide_outside_known_tides_is_null():
    assert normalize.tide_at(EVENTS, at(7)) == (None, None)
    assert normalize.tide_at(EVENTS, at(20)) == (None, None)
    assert normalize.tide_at([], at(12)) == (None, None)


def test_tide_offset_moves_the_events():
    shifted = normalize.shift_events(EVENTS, 45)
    assert shifted[0]["time_utc"] == "2026-10-08T08:45:00Z" and shifted[0]["height_m"] == 0.5


@pytest.mark.parametrize("wind_from, shore, expected", [
    (90, 90, "onshore"),      # shore faces east, wind from the east: blowing in from the sea
    (60, 90, "onshore"),
    (46, 90, "onshore"),      # 44 degrees apart
    (45, 90, "cross"),        # exactly 45 apart is no longer onshore
    (0, 90, "cross"),
    (225, 90, "cross"),       # exactly 135 apart is still cross
    (226, 90, "offshore"),
    (270, 90, "offshore"),
    (350, 10, "onshore"),     # wraps through north
    (190, 10, "offshore"),
    (None, 90, None),
    (90, None, None),
])
def test_wind_relative(wind_from, shore, expected):
    assert normalize.wind_relative(wind_from, shore) == expected


def test_sun_times_belong_to_the_local_day():
    for day in (date(2026, 10, 8), date(2026, 6, 21), date(2026, 12, 21), date(2026, 4, 5), date(2026, 9, 27)):
        sunrise, sunset = normalize.sun_times(-43.507, 172.733, day)
        assert sunrise.astimezone(NZ).date() == day and sunset.astimezone(NZ).date() == day
        assert sunrise < sunset
    sunrise, sunset = normalize.sun_times(-43.507, 172.733, date(2026, 10, 8))
    assert 6 <= sunrise.astimezone(NZ).hour <= 7 and 19 <= sunset.astimezone(NZ).hour <= 20
    midwinter = normalize.sun_times(-43.507, 172.733, date(2026, 6, 21))
    assert midwinter[1] - midwinter[0] < timedelta(hours=9, minutes=30)


def test_moon_fraction_matches_known_moons():
    new, full = normalize.moon_fraction(date(2026, 10, 11)), normalize.moon_fraction(date(2026, 10, 26))
    assert new < 0.06 or new > 0.94          # new moon 10-11 Oct 2026
    assert 0.44 < full < 0.56                # full moon 26 Oct 2026
    assert all(0 <= normalize.moon_fraction(date(2026, 1, 1) + timedelta(days=d)) < 1 for d in range(365))
