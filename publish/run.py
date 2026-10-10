"""Publish step: the only part of the pipeline that talks to Supabase.

    python -m publish.run due --min-minutes 170   # scheduled runs: is it time to collect again?
    python -m publish.run pull --out out      # before collector: fetch last run's state
    python -m publish.run push --out out      # after collector: validate, upload, write history
    python -m publish.run push --out out --dry-run   # validate only, no network

`push` validates every output file against schemas/ first. If any file is
invalid nothing is uploaded, so the files already online stay as they are,
and the command exits with an error.

Needs these environment variables (not for --dry-run):
    SUPABASE_URL           https://<project>.supabase.co
    SUPABASE_SERVICE_KEY   the service_role key - a secret, never commit it
    SUPABASE_BUCKET        optional, default "fishing-data"

No collecting and no scoring logic lives here: scores are copied from
recommendations.json exactly as the scorer wrote them.
"""
from __future__ import annotations

import argparse
import json
from math import fsum
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
STATE_FILES = ["linz_tides.json", "open_meteo_forecast.json", "open_meteo_marine.json", "ecan_flow.json"]
CONDITION_COLUMNS = ["tide_height_m", "tide_phase", "air_temp_c", "precip_prob_pct", "weather_code",
                     "wind_speed_kmh", "wind_gust_kmh", "wind_dir_deg", "wind_relative",
                     "wave_height_m", "swell_height_m", "sea_temp_c", "is_daylight"]
FLOW_BACKFILL_HOURS = 12  # past hours whose measured flow is refreshed on each run
TIMEOUT_S = 60
UTC = timezone.utc


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


# --- validation -----------------------------------------------------------

def output_files(out_dir: Path) -> list[tuple[Path, str, str]]:
    """(local path, path in the bucket, schema name) for every public output file."""
    files = [(p, f"conditions/{p.name}", "conditions") for p in sorted((out_dir / "conditions").glob("*.json"))]
    files.append((out_dir / "river_flow.json", "river_flow.json", "river_flow"))
    files.append((out_dir / "meta.json", "meta.json", "meta"))
    if (out_dir / "recommendations.json").exists():      # written by the scorer (from M2 on)
        files.append((out_dir / "recommendations.json", "recommendations.json", "recommendations"))
    return files


def validate(out_dir: Path) -> list[str]:
    """Return a list of problems; empty means every output file is valid."""
    problems = []
    files = output_files(out_dir)
    if not any(schema == "conditions" for _, _, schema in files):
        problems.append("no conditions/*.json files found")
    for path, remote, schema_name in files:
        if not path.exists():
            problems.append(f"{remote}: file is missing")
            continue
        schema = json.loads((SCHEMA_DIR / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"{remote}: not valid JSON ({exc})")
            continue
        for error in list(Draft202012Validator(schema).iter_errors(data))[:5]:
            where = "/".join(str(p) for p in error.absolute_path) or "(top level)"
            problems.append(f"{remote}: {where}: {error.message[:160]}")
    return problems


# --- history table rows ---------------------------------------------------

def hourly_flow_means(out_dir: Path) -> dict[str, float]:
    """Mean measured flow per hour: {hour start as UTC ISO: m3/s}."""
    series = json.loads((out_dir / "river_flow.json").read_text(encoding="utf-8"))["series"]
    buckets: dict[str, list[float]] = {}
    for point in series:
        if point["flow_m3s"] is not None:
            buckets.setdefault(point["time_utc"][:13] + ":00:00Z", []).append(point["flow_m3s"])
    return {hour: round(fsum(v) / len(v), 3) for hour, v in buckets.items()}


def hourly_scores(out_dir: Path) -> tuple[dict | None, int | None]:
    """({(spot_id, hour): score}, ruleset_version) from recommendations.json, or (None, None) if there is none."""
    path = out_dir / "recommendations.json"
    if not path.exists():
        return None, None
    doc = json.loads(path.read_text(encoding="utf-8"))
    scores = {(spot["spot_id"], hour["time_utc"]): hour["score"] for spot in doc["spots"] for hour in spot["hourly"]}
    return scores, doc["ruleset_version"]


def history_rows(out_dir: Path, now: datetime) -> tuple[list[dict], list[dict]]:
    """Rows for conditions_hourly.

    Returns (full rows for hours that have not finished, flow-only updates for
    recent past hours). Past hours keep the forecast they already hold.
    """
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    flow = hourly_flow_means(out_dir)
    stamp = _iso(now)
    scores, ruleset_version = hourly_scores(out_dir)
    full_rows = []
    for path in sorted((out_dir / "conditions").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for hour in doc["hourly"]:
            if _parse(hour["time_utc"]) < current_hour:
                continue
            row = {"spot_id": doc["spot_id"], "time_utc": hour["time_utc"]}
            row.update({c: hour[c] for c in CONDITION_COLUMNS})
            row["river_flow_m3s"] = flow.get(hour["time_utc"])
            if scores is not None:               # without scorer output the score columns are left untouched
                row["score"] = scores.get((doc["spot_id"], hour["time_utc"]))
                row["ruleset_version"] = ruleset_version
            row["updated_at"] = stamp
            full_rows.append(row)
    flow_updates = []
    for back in range(1, FLOW_BACKFILL_HOURS + 1):
        key = _iso(current_hour - timedelta(hours=back))
        if key in flow:
            flow_updates.append({"time_utc": key, "river_flow_m3s": flow[key], "updated_at": stamp})
    return full_rows, flow_updates


# --- Supabase -------------------------------------------------------------

def project_base_url(value: str) -> str:
    """Reduce whatever was pasted as SUPABASE_URL to 'https://<project>.supabase.co'.

    The Supabase dashboard also shows the address with '/rest/v1/' on the end.
    With that suffix every request lands on the database API instead of the
    storage API and fails with HTTP 404 PGRST125, so any path is dropped here.
    """
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise SystemExit("SUPABASE_URL must look like https://<project>.supabase.co")
    return f"{parts.scheme}://{parts.netloc}"


class Supabase:
    def __init__(self) -> None:
        try:
            self.url = project_base_url(os.environ["SUPABASE_URL"])
            self.key = os.environ["SUPABASE_SERVICE_KEY"].strip()
        except KeyError as exc:
            raise SystemExit(f"environment variable {exc} is not set") from None
        if not self.key:
            raise SystemExit("SUPABASE_SERVICE_KEY is empty")
        self.bucket = os.environ.get("SUPABASE_BUCKET", "fishing-data")

    def _request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None) -> tuple[int, bytes]:
        req = urllib.request.Request(self.url + path, data=body, method=method, headers={
            "Authorization": f"Bearer {self.key}", "apikey": self.key, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def download(self, remote: str) -> bytes | None:
        status, body = self._request("GET", f"/storage/v1/object/{self.bucket}/{quote(remote)}")
        return body if status == 200 else None

    def list(self, prefix: str) -> list[str]:
        status, body = self._request("POST", f"/storage/v1/object/list/{self.bucket}",
                                     json.dumps({"prefix": prefix, "limit": 100}).encode(),
                                     {"Content-Type": "application/json"})
        if status != 200:
            # An existing bucket answers 200 even when the folder is empty, so anything
            # else means the URL, the key or the bucket name is wrong. Stop here rather
            # than run on without the previous state.
            raise RuntimeError(f"cannot list bucket '{self.bucket}': HTTP {status} {body[:200]!r}")
        return [item["name"] for item in json.loads(body)]

    def upload(self, remote: str, body: bytes, content_type: str) -> None:
        status, answer = self._request("POST", f"/storage/v1/object/{self.bucket}/{quote(remote)}", body, {
            "Content-Type": content_type, "x-upsert": "true", "cache-control": "max-age=300"})
        if status not in (200, 201):
            raise RuntimeError(f"upload of {remote} failed: HTTP {status} {answer[:200]!r}")

    def upsert_rows(self, rows: list[dict]) -> None:
        for i in range(0, len(rows), 500):
            status, answer = self._request(
                "POST", "/rest/v1/conditions_hourly?on_conflict=spot_id,time_utc",
                json.dumps(rows[i:i + 500]).encode(),
                {"Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})
            if status not in (200, 201, 204):
                raise RuntimeError(f"writing conditions_hourly failed: HTTP {status} {answer[:300]!r}")

    def update_flow(self, update: dict) -> None:
        when = quote(update["time_utc"], safe="")
        status, answer = self._request(
            "PATCH", f"/rest/v1/conditions_hourly?time_utc=eq.{when}",
            json.dumps({"river_flow_m3s": update["river_flow_m3s"], "updated_at": update["updated_at"]}).encode(),
            {"Content-Type": "application/json", "Prefer": "return=minimal"})
        if status not in (200, 204):
            raise RuntimeError(f"updating river flow failed: HTTP {status} {answer[:300]!r}")


# --- commands -------------------------------------------------------------

def is_due(last_generated_at: str | None, now: datetime, min_minutes: int) -> tuple[bool, str]:
    """Should a scheduled run collect now? (decision, explanation)

    GitHub starts scheduled workflows late and silently drops many of them, so
    the workflow is triggered every hour and this check keeps the real pace at
    about one collection every 3 hours (and the load on the data sources low).
    """
    if last_generated_at is None:
        return True, "nothing has been published yet"
    age = (now - _parse(last_generated_at)).total_seconds() / 60
    if age >= min_minutes:
        return True, f"last published {age:.0f} min ago (at least {min_minutes} min)"
    return False, f"last published only {age:.0f} min ago (less than {min_minutes} min) - skipping this run"


def due(client: Supabase, min_minutes: int, force: bool, now: datetime | None = None) -> int:
    """Print the decision; inside GitHub Actions also expose it as the step output `run`."""
    if force:
        decision, why = True, "started by hand - always runs"
    else:
        body = client.download("meta.json")
        last = json.loads(body).get("generated_at") if body else None
        decision, why = is_due(last, (now or datetime.now(UTC)).astimezone(UTC), min_minutes)
    print(f"due: {'collect' if decision else 'skip'} - {why}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"run={'true' if decision else 'false'}\n")
    return 0


def pull(out_dir: Path, client: Supabase) -> int:
    """Download the previous run's state so a failing source can fall back on it."""
    state_dir = out_dir / "state"
    remotes = [f"state/{name}" for name in STATE_FILES]
    remotes += [f"state/linz/{name}" for name in client.list("state/linz/")]
    got = 0
    for remote in remotes:
        body = client.download(remote)
        if body is None:
            continue
        target = out_dir / remote
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        got += 1
    state_dir.mkdir(parents=True, exist_ok=True)
    print(f"pull: {got} state file(s) downloaded (none is normal on the very first run)")
    return 0


def push(out_dir: Path, client: Supabase | None, now: datetime | None = None) -> int:
    problems = validate(out_dir)
    if problems:
        print("push: output does NOT match the schemas - nothing was uploaded:")
        for problem in problems:
            print("  " + problem)
        return 1
    files = output_files(out_dir)
    print(f"push: {len(files)} output files are valid")
    if client is None:
        print("push: --dry-run, stopping before any upload")
        return 0

    for path, remote, _ in files:
        client.upload(remote, path.read_bytes(), "application/json")
    state = [p for p in sorted((out_dir / "state").rglob("*")) if p.is_file()]
    for path in state:
        client.upload(path.relative_to(out_dir).as_posix(), path.read_bytes(),
                      "application/json" if path.suffix == ".json" else "text/csv")
    print(f"push: uploaded {len(files)} output files and {len(state)} state files to bucket '{client.bucket}'")

    full_rows, flow_updates = history_rows(out_dir, (now or datetime.now(UTC)).astimezone(UTC))
    client.upsert_rows(full_rows)
    for update in flow_updates:
        client.update_flow(update)
    print(f"push: conditions_hourly - {len(full_rows)} rows written, "
          f"river flow refreshed for {len(flow_updates)} past hour(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish collector output to Supabase.")
    parser.add_argument("command", choices=["due", "pull", "push"])
    parser.add_argument("--min-minutes", type=int, default=170, help="due: shortest gap between two collections")
    parser.add_argument("--force", action="store_true", help="due: always answer 'collect'")
    parser.add_argument("--out", default="out", help="output folder (default: out)")
    parser.add_argument("--dry-run", action="store_true", help="push: validate only, no network")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    if args.command == "due":
        return due(Supabase(), args.min_minutes, args.force)
    if args.command == "pull":
        return pull(out_dir, Supabase())
    return push(out_dir, None if args.dry_run else Supabase())


if __name__ == "__main__":
    sys.exit(main())
