"""Shared fixtures. Tests never touch the network: they replay the real
responses saved by the M0 smoke tests (tests/smoke/samples/)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from collector import run  # noqa: E402
from collector.sources import ecan_flow, linz_tides, open_meteo  # noqa: E402

SAMPLES = ROOT / "tests" / "smoke" / "samples"
UTC = timezone.utc
# The M0 samples were fetched on 2026-10-08 and start at 00:00 UTC that day.
SAMPLE_NOW = datetime(2026, 10, 8, 10, 15, tzinfo=UTC)
SAMPLE_START = datetime(2026, 10, 8, 0, 0, tzinfo=UTC)


def no_network(url):  # passed as `get` where a download must not happen
    raise AssertionError(f"unexpected network request: {url}")


def shifted_open_meteo(name: str, shift: timedelta) -> bytes:
    """A real Open-Meteo sample with only its timestamps moved by `shift`."""
    data = json.loads((SAMPLES / name).read_bytes())
    for loc in data:
        loc["hourly"]["time"] = [
            (datetime.strptime(t, "%Y-%m-%dT%H:%M") + shift).strftime("%Y-%m-%dT%H:%M")
            for t in loc["hourly"]["time"]]
    return json.dumps(data).encode()


def replay_fetchers(spots, now, state_dir, shift=timedelta(0)):
    """Same shape as run.fetchers(), but every source reads a saved real response."""
    start = now.replace(minute=0, second=0, microsecond=0)
    return {
        "linz_tides": lambda: linz_tides.fetch("lyttelton", start, start + timedelta(hours=168),
                                               state_dir, get=no_network),
        "open_meteo_forecast": lambda: open_meteo.parse(
            shifted_open_meteo("open_meteo_forecast.json", shift), spots, open_meteo.FORECAST_FIELDS),
        "open_meteo_marine": lambda: open_meteo.parse(
            shifted_open_meteo("open_meteo_marine.json", shift), spots, open_meteo.MARINE_FIELDS),
        "ecan_flow": lambda: ecan_flow.parse(
            (SAMPLES / "ecan_flow_66401_1week.csv").read_text(encoding="utf-8-sig")),
    }


@pytest.fixture
def spots():
    return run.load_spots()


@pytest.fixture
def collected(tmp_path, spots):
    """One full collector run on the real samples. Returns (out_dir, meta)."""
    out = tmp_path / "out"
    meta = run.collect(out, SAMPLE_NOW, replay_fetchers(spots, SAMPLE_NOW, out / "state"), spots)
    return out, meta
