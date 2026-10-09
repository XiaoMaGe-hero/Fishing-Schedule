"""Collector entry point.

    python -m collector.run --out out

Fetches every source, then writes
    out/conditions/<spot_id>.json, out/river_flow.json, out/meta.json
and keeps each source's last good result in out/state/.

One source failing never stops the others: its last good result from
out/state/ is used instead, and meta.json records the failure.

Test hooks (used only for acceptance tests, never in normal runs):
    FISHING_FORCE_FAIL=<source name>   make that source fail
    FISHING_BREAK_OUTPUT=1             write a conditions file that breaks the schema
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from collector import normalize
from collector.sources import ecan_flow, linz_tides, open_meteo
from collector.timeutil import UTC, floor_hour, iso

ROOT = Path(__file__).resolve().parent.parent
SOURCE_NAMES = ["linz_tides", "open_meteo_forecast", "open_meteo_marine", "ecan_flow"]


def load_spots(path: Path = ROOT / "config" / "spots.yaml") -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def fetchers(spots: list[dict], start: datetime, state_dir: Path) -> dict:
    """source name -> function that fetches it. Tests replace this."""
    end = start + timedelta(hours=normalize.HOURS)
    ports = sorted({s.get("tide_reference", "lyttelton") for s in spots})
    if len(ports) != 1:
        raise ValueError(f"only one tide reference port is supported for now, got {ports}")
    return {
        "linz_tides": lambda: linz_tides.fetch(ports[0], start, end, state_dir),
        "open_meteo_forecast": lambda: open_meteo.fetch_forecast(spots),
        "open_meteo_marine": lambda: open_meteo.fetch_marine(spots),
        "ecan_flow": lambda: ecan_flow.fetch(),
    }


def _read_state(state_dir: Path, name: str) -> dict | None:
    path = state_dir / f"{name}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def collect(out_dir: Path, now: datetime | None = None, fetch_map: dict | None = None,
            spots: list[dict] | None = None) -> dict:
    """Run one collection. Returns the meta.json content."""
    now = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    start = floor_hour(now)
    spots = spots if spots is not None else load_spots()
    state_dir = out_dir / "state"
    fetch_map = fetch_map or fetchers(spots, start, state_dir)
    force_fail = os.environ.get("FISHING_FORCE_FAIL", "")

    data, sources_meta = {}, {}
    for name in SOURCE_NAMES:
        previous = _read_state(state_dir, name)
        try:
            if name == force_fail:
                raise RuntimeError("forced failure (FISHING_FORCE_FAIL)")
            data[name] = fetch_map[name]()
            _write_json(state_dir / f"{name}.json", {"fetched_at": iso(now), "data": data[name]})
            sources_meta[name] = {"status": "ok", "last_success_utc": iso(now),
                                  "last_attempt_utc": iso(now), "error": None}
            print(f"[ok]     {name}")
        except Exception as exc:  # any failure of one source must not stop the others
            data[name] = previous["data"] if previous else None
            sources_meta[name] = {"status": "failed",
                                  "last_success_utc": previous["fetched_at"] if previous else None,
                                  "last_attempt_utc": iso(now),
                                  "error": f"{type(exc).__name__}: {exc}"[:300]}
            kept = f"using data from {previous['fetched_at']}" if previous else "no earlier data to fall back on"
            print(f"[FAILED] {name}: {sources_meta[name]['error']} ({kept})")

    for spot in spots:
        conditions = normalize.build_conditions(
            spot, start, now, data["linz_tides"], data["open_meteo_forecast"], data["open_meteo_marine"])
        if os.environ.get("FISHING_BREAK_OUTPUT"):
            del conditions["spot_id"]
        _write_json(out_dir / "conditions" / f"{spot['id']}.json", conditions)
    _write_json(out_dir / "river_flow.json", normalize.build_river_flow(
        data["ecan_flow"], now, ecan_flow.SITE_ID, ecan_flow.SITE_NAME))
    meta = {"schema_version": 1, "generated_at": iso(now), "sources": sources_meta}
    _write_json(out_dir / "meta.json", meta)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect fishing conditions.")
    parser.add_argument("--out", default="out", help="output folder (default: out)")
    args = parser.parse_args()
    meta = collect(Path(args.out))
    failed = [n for n, s in meta["sources"].items() if s["status"] == "failed"]
    print(f"wrote {args.out}/ - {len(SOURCE_NAMES) - len(failed)} of {len(SOURCE_NAMES)} sources ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
