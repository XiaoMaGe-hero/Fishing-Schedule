"""M1 acceptance check: look at what is actually published and compare it with the sources.

    python3 tests/acceptance/check_m1.py <label>

Reads the public files from the Supabase bucket, the row count of
conditions_hourly, the LINZ file in this repo, and Open-Meteo directly.
Prints a report and saves it to tests/acceptance/output/<label>.txt so
runs can be compared (before / after a repeat run, a forced failure, ...).

Settings come from the environment or from a .env file in the project root:
    SUPABASE_URL        https://<project>.supabase.co   (not a secret)
    SUPABASE_ANON_KEY   the "anon public" key           (public by design; needed only for the row count)
Never put the service_role key in .env - this script does not need it.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from collector.sources import linz_tides, open_meteo  # noqa: E402
from collector.timeutil import NZ  # noqa: E402

import yaml  # noqa: E402

UTC = timezone.utc
BUCKET = os.environ.get("SUPABASE_BUCKET", "fishing-data")
SOURCES = ["linz_tides", "open_meteo_forecast", "open_meteo_marine", "ecan_flow"]
COMPARE = {"air_temp_c": "forecast", "wind_speed_kmh": "forecast", "wind_dir_deg": "forecast", "sea_temp_c": "marine"}
verdicts: list[tuple[str, bool | None, str]] = []


def settings() -> tuple[str, str | None]:
    env = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    if "SUPABASE_URL" not in env:
        raise SystemExit("SUPABASE_URL is not set (environment or .env file)")
    parts = urlsplit(env["SUPABASE_URL"].strip())
    return f"{parts.scheme}://{parts.netloc}", env.get("SUPABASE_ANON_KEY")


def get(url: str, headers: dict | None = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "LiangsFishingSchedule-acceptance/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def record(item: str, ok: bool | None, text: str) -> None:
    verdicts.append((item, ok, text))
    print(f"  => {'PASS' if ok else 'INFO' if ok is None else 'FAIL'}: {text}")


def parse(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def is_utc(text) -> bool:
    try:
        parse(text)
        return True
    except (TypeError, ValueError):
        return False


def check(fetch=get, now: datetime | None = None) -> None:
    base, anon_key = settings()
    now = now or datetime.now(UTC)
    public = f"{base}/storage/v1/object/public/{BUCKET}/"
    spots = yaml.safe_load((ROOT / "config" / "spots.yaml").read_text(encoding="utf-8"))
    print(f"checked at {now:%Y-%m-%dT%H:%M:%SZ}  bucket: {BUCKET}")

    # the bucket is behind a CDN; a changing query string makes sure we see the newest file
    bust = f"?t={int(now.timestamp())}"
    docs: dict[str, dict] = {}
    print("\n[published files]")
    for name in [f"conditions/{s['id']}.json" for s in spots] + ["river_flow.json", "meta.json"]:
        status, _, body = fetch(public + name + bust)
        if status != 200:
            print(f"  {name}: HTTP {status}")
            continue
        docs[name] = json.loads(body)
        print(f"  {name}: generated_at {docs[name].get('generated_at')}, {len(body)} bytes")
    if len(docs) != len(spots) + 2:
        record("files", False, "not every published file could be read; stopping")
        return

    print("\n[item 2] coverage: every spot, 168 hours")
    problems = []
    for spot in spots:
        doc = docs[f"conditions/{spot['id']}.json"]
        hours = [parse(h["time_utc"]) for h in doc["hourly"]]
        consecutive = all(b - a == timedelta(hours=1) for a, b in zip(hours, hours[1:]))
        nulls = {k: sum(1 for h in doc["hourly"] if h[k] is None) for k in doc["hourly"][0] if k != "time_utc"}
        nulls = {k: v for k, v in nulls.items() if v}
        print(f"  {spot['id']}: {len(hours)} hours {doc['hourly'][0]['time_utc']} .. {doc['hourly'][-1]['time_utc']}, "
              f"consecutive={consecutive}, null counts={nulls or 'none'}")
        if len(hours) != 168 or not consecutive:
            problems.append(spot["id"])
    record("2", not problems, "both spots have 168 consecutive hours" if not problems else f"bad coverage: {problems}")

    print("\n[item 3] tides against the official LINZ file")
    year_now = now.year
    official = {}
    for year in (year_now, year_now + 1):
        path = ROOT / "collector" / "data" / "linz" / f"lyttelton_{year}.csv"
        if path.exists():
            official.update({e["time_utc"]: e for e in linz_tides.parse(path.read_text(encoding="utf-8-sig"))})
    spot0 = next((s for s in spots if not s.get("tide_offset_min")), spots[0])
    events = docs[f"conditions/{spot0['id']}.json"]["tide_events"]
    mismatches = [e for e in events if official.get(e["time_utc"], {}).get("height_m") != e["height_m"]
                  or official[e["time_utc"]]["type"] != e["type"]]
    # Shown in NZ clock time next to the untouched rows of the LINZ file, so the
    # match can also be checked by eye, independently of our own parser.
    shown_days = set()
    for e in events[2:6]:
        local = parse(e["time_utc"]).astimezone(NZ)
        shown_days.add((local.day, local.month, local.year))
        print(f"  published {e['time_utc']} = {local:%d %b %H:%M} NZ time, {e['type']:4} {e['height_m']} m")
    raw_path = ROOT / "collector" / "data" / "linz" / f"lyttelton_{year_now}.csv"
    if raw_path.exists():
        for row in raw_path.read_text(encoding="utf-8-sig").splitlines()[3:]:
            cells = row.split(",")
            if (int(cells[0]), int(cells[2]), int(cells[3])) in shown_days:
                print(f"  LINZ file row:  {row}")
    record("3", not mismatches, f"{spot0['id']}: all {len(events)} published tides equal the LINZ file to the minute"
           if not mismatches else f"{len(mismatches)} tides differ from the LINZ file, first: {mismatches[0]}")

    print("\n[item 4] three hours against Open-Meteo asked directly right now")
    direct = {}
    for kind, base_url, fields, extra in (("forecast", open_meteo.FORECAST_URL, open_meteo.FORECAST_FIELDS, {"wind_speed_unit": "kmh"}),
                                          ("marine", open_meteo.MARINE_URL, open_meteo.MARINE_FIELDS, {})):
        status, _, body = fetch(open_meteo._url(base_url, spots, fields, extra))
        direct[kind] = open_meteo.parse(body, spots, fields) if status == 200 else None
        print(f"  Open-Meteo {kind}: HTTP {status}")
    diffs, compared = [], 0
    if all(direct.values()):
        for spot in spots:
            hourly = docs[f"conditions/{spot['id']}.json"]["hourly"]
            for index in (2, 60, 150):
                stamp = hourly[index]["time_utc"]
                for field, kind in COMPARE.items():
                    theirs = direct[kind]["spots"][spot["id"]]["hourly"].get(stamp, {}).get(field)
                    ours = hourly[index][field]
                    compared += 1
                    mark = "==" if ours == theirs else "!="
                    if ours != theirs:
                        diffs.append((spot["id"], stamp, field, ours, theirs))
                    print(f"  {spot['id']:18} {stamp} {field:15} published {ours!s:>6} {mark} direct {theirs}")
        generated = docs[f"conditions/{spots[0]['id']}.json"]["generated_at"]
        age_min = (now - parse(generated)).total_seconds() / 60
        if diffs:
            record("4", False, f"{len(diffs)} of {compared} values differ. The published file is {age_min:.0f} min old; "
                               "Open-Meteo refreshes its forecast through the day, so run this right after a Collect run")
        else:
            record("4", True, f"all {compared} values equal (published file is {age_min:.0f} min old)")
    else:
        record("4", False, "Open-Meteo could not be reached")

    print("\n[item 5 / state of sources] meta.json and river flow")
    meta = docs["meta.json"]["sources"]
    for name in SOURCES:
        s = meta[name]
        print(f"  {name:20} {s['status']:6} last_success {s['last_success_utc']} last_attempt {s['last_attempt_utc']} error={s['error']}")
    series = docs["river_flow.json"]["series"]
    print(f"  river_flow.json: {len(series)} points, {series[0]['time_utc'] if series else None} .. {series[-1]['time_utc'] if series else None}")
    failed = [n for n in SOURCES if meta[n]["status"] == "failed"]
    record("5", None, f"failed sources: {failed or 'none'}")

    print("\n[item 6] rows in conditions_hourly")
    if anon_key:
        headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}", "Prefer": "count=exact"}
        rest = f"{base}/rest/v1/conditions_hourly"
        status, hdrs, _ = fetch(rest + "?select=spot_id&limit=1", headers)
        total = hdrs.get("Content-Range", hdrs.get("content-range", "?/?")).split("/")[-1]
        _, _, first = fetch(rest + "?select=time_utc&order=time_utc.asc&limit=1", headers)
        _, _, last = fetch(rest + "?select=time_utc,updated_at&order=time_utc.desc&limit=1", headers)
        print(f"  HTTP {status}; total rows: {total}; earliest {first.decode()[:80]}; latest {last.decode()[:120]}")
        record("6", None, f"row count = {total}")
    else:
        record("6", None, "SUPABASE_ANON_KEY not set, row count skipped")

    print("\n[item 8] every time field is UTC")
    bad = []
    for name, doc in docs.items():
        stack = [doc]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.endswith("_utc") or key == "generated_at":
                        if value is not None and not is_utc(value):
                            bad.append((name, key, value))
                    else:
                        stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)
    record("8", not bad, "all time fields are UTC ISO strings ending in Z" if not bad else f"non-UTC values: {bad[:3]}")

    print("\n[summary]")
    for item, ok, text in verdicts:
        print(f"  item {item:5} {'PASS' if ok else 'INFO' if ok is None else 'FAIL'}  {text}")


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    buffer = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, text):
            sys.__stdout__.write(text)
            return buffer.write(text)

    with redirect_stdout(Tee()):
        print(f"M1 acceptance check - label: {label}")
        check()
    out = ROOT / "tests" / "acceptance" / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.txt").write_text(buffer.getvalue(), encoding="utf-8")
    print(f"\nsaved to tests/acceptance/output/{label}.txt")
    return 0 if all(ok is not False for _, ok, _ in verdicts) else 1


if __name__ == "__main__":
    sys.exit(main())
