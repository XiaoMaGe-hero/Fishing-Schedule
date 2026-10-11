"""M4 acceptance check: the fishing record, seen from outside the website.

    python3 tests/acceptance/check_m4.py <label>

Uses only the public (anon) key, exactly like a stranger on the internet would:
  item 1   tries to add a record and to upload a file without signing in - both must be refused
  item 2   tries to create a new account - must be refused
  items 5-7  compares the snapshots saved in every record with the history table
  item 8   downloads every photo and measures it
  item 9   looks for photo files that no record points to

Prints a report and saves it to tests/acceptance/output/<label>.txt.
Uses the same .env file as check_m1.py (SUPABASE_URL, SUPABASE_ANON_KEY).

If a "must be refused" attempt is NOT refused, the script says so and tells you what it
left behind (a test record or a test account) so you can remove it in the Supabase dashboard.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_m1  # noqa: E402  (settings, parse)
from collector.timeutil import NZ  # noqa: E402

UTC = timezone.utc
PHOTO_BUCKET = "record-photos"
MAX_EDGE = 1600
CONDITION_FIELDS = ["tide_height_m", "tide_phase", "air_temp_c", "precip_prob_pct", "weather_code", "wind_speed_kmh",
                    "wind_gust_kmh", "wind_dir_deg", "wind_relative", "wave_height_m", "swell_height_m", "sea_temp_c",
                    "is_daylight", "river_flow_m3s"]
verdicts: list[tuple[str, bool | None, str]] = []


def record(item: str, ok: bool | None, text: str) -> None:
    verdicts.append((item, ok, text))
    print(f"  => {'PASS' if ok else 'INFO' if ok is None else 'FAIL'}: {text}")


def call(method: str, url: str, headers: dict | None = None, body: bytes | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": "LiangsFishingSchedule-acceptance/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def nz(stamp: str) -> str:
    return check_m1.parse(stamp).astimezone(NZ).strftime("%a %d %b %Y %H:%M")


def short(body: bytes) -> str:
    return body.decode("utf-8", "replace").strip().replace("\n", " ")[:200]


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """Width and height from a JPEG's own header."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if 0xD0 <= marker <= 0xD9 or marker == 0x01:
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + length
    return None


def trip_hours(started: str, ended: str) -> list[datetime]:
    start = check_m1.parse(started).astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    end = check_m1.parse(ended).astimezone(UTC)
    hours = []
    while start < end:
        hours.append(start)
        start += timedelta(hours=1)
    return hours


def same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 1e-9
    return a == b


def check(call=call, now: datetime | None = None) -> None:
    base, anon = check_m1.settings()
    if not anon:
        raise SystemExit("SUPABASE_ANON_KEY is not set (environment or .env file)")
    now = now or datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    key = {"apikey": anon, "Authorization": f"Bearer {anon}"}
    as_json = {**key, "Content-Type": "application/json"}
    rest = f"{base}/rest/v1"
    print(f"checked at {now:%Y-%m-%dT%H:%M:%SZ}")

    print("\n[records] reading the list without signing in")
    status, body = call("GET", f"{rest}/records?select=*&order=started_at.desc", key)
    if status != 200:
        record("10", False, f"the record list could not be read without signing in: HTTP {status} {short(body)}")
        return
    records = json.loads(body)
    record("10", None, f"{len(records)} records can be read without signing in (that no edit buttons show must be checked on the page)")

    print("\n[item 1] writing without signing in")
    probe = {"spot_id": "acceptance-test", "started_at": "2000-01-01T00:00:00Z", "ended_at": "2000-01-01T01:00:00Z",
             "outcome": "blank", "notes": f"ACCEPTANCE TEST {stamp} - delete me"}
    status, body = call("POST", f"{rest}/records", as_json, json.dumps(probe).encode())
    print(f"  add a record: HTTP {status} {short(body)}")
    refused_insert = status in (401, 403)
    if not refused_insert:
        print(f"  !! a test record may have been added (notes start with 'ACCEPTANCE TEST {stamp}'). Delete it in the Supabase table editor.")
    refused_update = True
    if records:
        target = records[0]
        status, body = call("PATCH", f"{rest}/records?id=eq.{target['id']}", {**as_json, "Prefer": "return=representation"},
                            json.dumps({"updated_at": target["updated_at"]}).encode())  # writes the value it already has
        changed = json.loads(body) if status == 200 and body.strip() else []
        refused_update = not changed
        print(f"  change a record (harmless: sets updated_at to its current value): HTTP {status}, rows changed: {len(changed) if isinstance(changed, list) else changed}")
    else:
        print("  change a record: skipped, there is no record to try it on")
    path = f"acceptance-test/{stamp}.txt"
    status, body = call("POST", f"{base}/storage/v1/object/{PHOTO_BUCKET}/{path}", {**key, "Content-Type": "text/plain"}, b"acceptance test")
    print(f"  upload a file: HTTP {status} {short(body)}")
    there, _ = call("GET", f"{base}/storage/v1/object/public/{PHOTO_BUCKET}/{path}")
    refused_upload = status != 200 and there != 200
    if not refused_upload:
        print(f"  !! the file {PHOTO_BUCKET}/{path} may have been stored. Delete it in the Supabase storage page.")
    record("1", refused_insert and refused_update and refused_upload,
           f"add refused: {refused_insert}; change refused: {refused_update}; upload refused: {refused_upload} "
           "(deleting is not attempted: a delete that got through could not be undone)")

    print("\n[item 2] creating an account")
    email = f"acceptance-test-{stamp.lower()}@example.com"
    status, body = call("POST", f"{base}/auth/v1/signup", {"apikey": anon, "Content-Type": "application/json"},
                        json.dumps({"email": email, "password": f"Test-{stamp}-x9!"}).encode())
    print(f"  sign up as {email}: HTTP {status} {short(body)}")
    closed = status >= 400 and status != 429
    if status == 429:
        record("2", None, "Supabase limited the request rate, so this could not be checked; run again later")
    else:
        if not closed:
            print(f"  !! an account {email} may have been created. Delete it under Authentication > Users.")
        record("2", closed, "new sign-ups are refused" if closed else "a new account could be created - sign-ups are still open")

    print("\n[items 5-7] snapshots against the history table")
    with_snapshot = backfilled = without = 0
    ok5 = ok6 = ok7 = True
    for r in records:
        hours = trip_hours(r["started_at"], r["ended_at"])
        lo, hi = quote(hours[0].isoformat()), quote(hours[-1].isoformat())
        status, body = call("GET", f"{rest}/conditions_hourly?select=*&spot_id=eq.{quote(r['spot_id'])}"
                                   f"&time_utc=gte.{lo}&time_utc=lte.{hi}&order=time_utc", key)
        history = {check_m1.parse(h["time_utc"]).astimezone(UTC): h for h in (json.loads(body) if status == 200 else [])}
        snap, score = r.get("conditions_snapshot"), r.get("score_snapshot")
        late_h = (check_m1.parse(r["created_at"]) - check_m1.parse(r["ended_at"])).total_seconds() / 3600
        print(f"  {r['id'][:8]}  {nz(r['started_at'])} to {nz(r['ended_at'])[-5:]} NZ  {r['spot_id']}  {r['outcome']}  "
              f"saved {late_h:.1f} h after the trip ended  photos {len(r.get('photos') or [])}")
        if not snap:
            without += 1
            fine = not history
            ok7 &= fine
            print(f"    no snapshot; the history table has {len(history)} of the {len(hours)} hours"
                  + ("" if fine else "  <- the history HAS data, so the snapshot should not be empty"))
            continue
        with_snapshot += 1
        got = {check_m1.parse(h["time_utc"]).astimezone(UTC): h for h in snap}
        missing = [h for h in hours if h in history and h not in got]
        extra = [h for h in got if h not in hours]
        diffs = []
        for hour, entry in got.items():
            row = history.get(hour)
            if row is None:
                diffs.append(f"{hour:%d %H:%M}Z is not in the history table")
                continue
            diffs += [f"{hour:%d %H:%M}Z {f}: record {entry.get(f)!r}, history {row.get(f)!r}"
                      for f in CONDITION_FIELDS if not same(entry.get(f), row.get(f))]
        score_hours = {check_m1.parse(h["time_utc"]).astimezone(UTC): h for h in (score or {}).get("hours", [])}
        for hour, entry in score_hours.items():
            row = history.get(hour, {})
            if not same(entry.get("score"), row.get("score")):
                diffs.append(f"{hour:%d %H:%M}Z score: record {entry.get('score')!r}, history {row.get('score')!r}")
        complete = not missing and not extra and bool(score) and score.get("ruleset_version") is not None \
            and "mean_score" in score and len(score_hours) > 0
        ok5 &= complete
        print(f"    snapshot has {len(got)} hours (trip touches {len(hours)}, history has {len(history)}); "
              f"score {score.get('mean_score') if score else None}, ruleset_version {score.get('ruleset_version') if score else None}"
              + ("" if complete else "  <- incomplete"))
        for d in diffs[:12]:
            print(f"      differs: {d}")
        if len(diffs) > 12:
            print(f"      ... and {len(diffs) - 12} more")
        if late_h >= 24:
            backfilled += 1
            ok6 &= not diffs and complete
        elif diffs:
            print("      (a trip saved soon after it ended can differ: the river flow of the last hours is filled in later,"
                  " and hours still ahead at saving time get newer forecasts)")
    record("5", (ok5 if with_snapshot else None),
           f"{with_snapshot} records carry a snapshot" + (", each with every available hour, a score and a ruleset_version" if ok5 and with_snapshot else ""))
    record("6", (ok6 if backfilled else None),
           f"{backfilled} records were saved a day or more after the trip" + (" and match the history table exactly" if ok6 and backfilled else ""))
    record("7", (ok7 if without else None),
           f"{without} records have no snapshot" + (", and the history table has nothing for those hours either" if ok7 and without else ""))

    print("\n[item 8] photo sizes")
    count, too_big, unreadable = 0, [], []
    for r in records:
        for p in r.get("photos") or []:
            status, body = call("GET", f"{base}/storage/v1/object/public/{PHOTO_BUCKET}/{quote(p)}")
            size = jpeg_size(body) if status == 200 else None
            count += 1
            print(f"  {p}: HTTP {status}, {len(body)} bytes, {f'{size[0]}x{size[1]}' if size else 'size not readable'}")
            if size is None:
                unreadable.append(p)
            elif max(size) > MAX_EDGE:
                too_big.append(p)
    record("8", (not too_big and not unreadable) if count else None,
           f"{count} photos; longer side over {MAX_EDGE}px: {len(too_big)}; unreadable: {len(unreadable)}")

    print("\n[item 9] photo files without a record")
    def listing(prefix: str) -> list[dict]:
        status, body = call("POST", f"{base}/storage/v1/object/list/{PHOTO_BUCKET}", as_json,
                            json.dumps({"prefix": prefix, "limit": 1000, "offset": 0}).encode())
        return json.loads(body) if status == 200 else []
    referenced = {p for r in records for p in (r.get("photos") or [])}
    stored = set()
    for folder in listing(""):
        if folder.get("id") is None:  # a folder
            stored |= {f"{folder['name']}/{f['name']}" for f in listing(folder["name"] + "/") if f.get("id")}
        else:
            stored.add(folder["name"])
    orphans, lost = sorted(stored - referenced), sorted(referenced - stored)
    for p in orphans:
        print(f"  stored but not used by any record: {p}")
    for p in lost:
        print(f"  used by a record but not in storage: {p}")
    record("9", not orphans and not lost,
           f"{len(stored)} files in storage, {len(referenced)} used by records, {len(orphans)} left over, {len(lost)} missing "
           "(that edit and delete work must be done on the page first)")

    print("\nsummary")
    for item, ok, text in verdicts:
        print(f"  item {item:5} {'PASS' if ok else 'INFO' if ok is None else 'FAIL'}  {text}")


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "m4-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    buffer = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, text):
            sys.__stdout__.write(text)
            return buffer.write(text)

    with redirect_stdout(Tee()):
        print(f"M4 acceptance check - label: {label}")
        check()
    out = ROOT / "tests" / "acceptance" / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.txt").write_text(buffer.getvalue(), encoding="utf-8")
    print(f"\nsaved to tests/acceptance/output/{label}.txt")
    return 0 if all(ok is not False for _, ok, _ in verdicts) else 1


if __name__ == "__main__":
    sys.exit(main())
