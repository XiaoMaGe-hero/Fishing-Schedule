"""M2 acceptance check: look at the published recommendations and re-derive them.

    python3 tests/acceptance/check_m2.py <label>

Reads the published files from the Supabase bucket and a few rows of
conditions_hourly, then scores the published conditions again on this
computer with the rules in this folder and compares the two results.
Prints a report and saves it to tests/acceptance/output/<label>.txt.

Uses the same .env file as check_m1.py (SUPABASE_URL, SUPABASE_ANON_KEY).
Run it right after a Collect run that used the current rules.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_m1  # noqa: E402  (settings, get, parse)
from collector.timeutil import NZ  # noqa: E402
from scorer import engine, version  # noqa: E402

UTC = timezone.utc
verdicts: list[tuple[str, bool | None, str]] = []


def record(item: str, ok: bool | None, text: str) -> None:
    verdicts.append((item, ok, text))
    print(f"  => {'PASS' if ok else 'INFO' if ok is None else 'FAIL'}: {text}")


def nz(stamp: str) -> str:
    return check_m1.parse(stamp).astimezone(NZ).strftime("%a %d %b %H:%M")


def check(fetch=check_m1.get, now: datetime | None = None) -> None:
    base, anon_key = check_m1.settings()
    now = now or datetime.now(UTC)
    public = f"{base}/storage/v1/object/public/{check_m1.BUCKET}/"
    bust = f"?t={int(now.timestamp())}"
    scoring, spots = engine.load_config()
    print(f"checked at {now:%Y-%m-%dT%H:%M:%SZ}  local ruleset_version {scoring['ruleset_version']}  "
          f"({version.check() or 'rules and lock file agree'})")

    docs = {}
    print("\n[published files]")
    for name in [f"conditions/{s['id']}.json" for s in spots] + ["river_flow.json", "recommendations.json"]:
        status, _, body = fetch(public + name + bust)
        if status != 200:
            print(f"  {name}: HTTP {status}")
            continue
        docs[name] = json.loads(body)
        print(f"  {name}: generated_at {docs[name].get('generated_at')}, {len(body)} bytes")
    if len(docs) != len(spots) + 2:
        record("files", False, "not every published file could be read; stopping")
        return
    rec = docs["recommendations.json"]

    print("\n[item 1] coverage and version")
    problems = []
    if rec["ruleset_version"] != scoring["ruleset_version"]:
        problems.append(f"published ruleset_version {rec['ruleset_version']} != local {scoring['ruleset_version']} "
                        "(run this after a Collect run that used the pushed rules)")
    for spot in spots:
        entry = next((s for s in rec["spots"] if s["spot_id"] == spot["id"]), None)
        cond_hours = [h["time_utc"] for h in docs[f"conditions/{spot['id']}.json"]["hourly"]]
        if entry is None or [h["time_utc"] for h in entry["hourly"]] != cond_hours:
            problems.append(f"{spot['id']}: hourly scores do not line up with the conditions file")
            continue
        vetoed = sum(h["vetoed"] for h in entry["hourly"])
        print(f"  {spot['id']}: {len(entry['hourly'])} hourly scores, {vetoed} vetoed, {len(entry['windows'])} windows")
    record("1", not problems, "both spots: 168 hourly scores matching the conditions hours, current ruleset_version"
           if not problems else "; ".join(problems))

    print("\n[item 4] every window lists every rule with a score and a sentence; best windows shown")
    rule_names = sorted(r._rule_meta["name"] for r in engine.load_rules()[0])
    bad = []
    for entry in rec["spots"]:
        scores = [w["score"] for w in entry["windows"]]
        if scores != sorted(scores, reverse=True):
            bad.append(f"{entry['spot_id']}: windows are not sorted best first")
        for w in entry["windows"]:
            hours = (check_m1.parse(w["end_utc"]) - check_m1.parse(w["start_utc"])) / timedelta(hours=1)
            if sorted(r["rule"] for r in w["reasons"]) != rule_names or not all(r["reason"] for r in w["reasons"]):
                bad.append(f"{entry['spot_id']} {w['start_utc']}: reasons incomplete")
            if hours < 1.5:
                bad.append(f"{entry['spot_id']} {w['start_utc']}: only {hours} h long")
        for w in entry["windows"][:2]:
            print(f"  {entry['spot_id']}: {nz(w['start_utc'])} - {nz(w['end_utc'])[-5:]}  score {w['score']}  {w['confidence']}")
            for r in w["reasons"]:
                print(f"      {r['rule']:6} {r['score']!s:>6} x{r['weight']}  {r['reason']}")
    record("4", not bad, f"all windows carry {len(rule_names)} rules ({', '.join(rule_names)}) with reasons, sorted best first"
           if not bad else "; ".join(bad[:3]))

    print("\n[item 6] vetoed hours")
    bad, shown = [], 0
    for spot in spots:
        entry = next(s for s in rec["spots"] if s["spot_id"] == spot["id"])
        cond = {h["time_utc"]: h for h in docs[f"conditions/{spot['id']}.json"]["hourly"]}
        for h in entry["hourly"]:
            c = cond[h["time_utc"]]
            over = ((c["wind_gust_kmh"] is not None and spot.get("max_gust_kmh") is not None and c["wind_gust_kmh"] > spot["max_gust_kmh"])
                    or (c["wave_height_m"] is not None and spot.get("max_wave_m") is not None and c["wave_height_m"] > spot["max_wave_m"])
                    or (not c["is_daylight"] and not spot.get("allow_night")))
            if over != h["vetoed"] or (h["vetoed"] and h["score"] != 0):
                bad.append((spot["id"], h["time_utc"]))
            if over and c["is_daylight"] and shown < 3:
                shown += 1
                print(f"  {spot['id']} {nz(h['time_utc'])}: gust {c['wind_gust_kmh']} km/h, wave {c['wave_height_m']} m -> vetoed, score {h['score']}")
        in_window = set()
        for w in entry["windows"]:
            t = check_m1.parse(w["start_utc"])
            while t < check_m1.parse(w["end_utc"]):
                in_window.add(t.strftime("%Y-%m-%dT%H:%M:%SZ"))
                t += timedelta(hours=1)
        if any(h["vetoed"] for h in entry["hourly"] if h["time_utc"] in in_window):
            bad.append((spot["id"], "vetoed hour inside a window"))
    record("6", not bad, "every hour over a gust / wave limit or at night is vetoed with score 0, no other hour is, "
                         "and no vetoed hour is inside a window" if not bad else f"mismatch at {bad[:3]}")

    print("\n[item 7] confidence")
    limit = check_m1.parse(rec["generated_at"]) + timedelta(hours=scoring["window"]["high_confidence_hours"])
    wrong = [(e["spot_id"], w["start_utc"]) for e in rec["spots"] for w in e["windows"]
             if w["confidence"] != ("high" if check_m1.parse(w["start_utc"]) <= limit else "low")]
    counts = {c: sum(1 for e in rec["spots"] for w in e["windows"] if w["confidence"] == c) for c in ("high", "low")}
    record("7", not wrong, f"{counts['high']} windows 'high' (start within 72 h of {rec['generated_at']}), {counts['low']} 'low'"
           if not wrong else f"wrong confidence at {wrong[:3]}")

    print("\n[item 8] scoring the published conditions again on this computer")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "conditions").mkdir()
        for spot in spots:
            (out / "conditions" / f"{spot['id']}.json").write_text(json.dumps(docs[f"conditions/{spot['id']}.json"]), encoding="utf-8")
        (out / "river_flow.json").write_text(json.dumps(docs["river_flow.json"]), encoding="utf-8")
        again = engine.score_all(out, scoring, spots)
        again2 = engine.score_all(out, scoring, spots)
    same = json.dumps(again, sort_keys=True) == json.dumps(rec, sort_keys=True)
    record("8", same and again == again2, "recomputed here twice: identical to each other and to the published file"
           if same else "recomputed result differs from the published file (different rules pushed, or a different Python?)")

    print("\n[history table] scores in conditions_hourly")
    if anon_key:
        headers = {"apikey": anon_key, "Authorization": f"Bearer {anon_key}", "Prefer": "count=exact"}
        rest = f"{base}/rest/v1/conditions_hourly"
        _, hdrs, _ = fetch(rest + "?select=spot_id&score=not.is.null&limit=1", headers)
        scored_rows = hdrs.get("Content-Range", hdrs.get("content-range", "?/?")).split("/")[-1]
        entry = rec["spots"][0]
        # a recommended hour if there is one (a non-zero score says more than a vetoed 0)
        start = entry["windows"][0]["start_utc"] if entry["windows"] else entry["hourly"][5]["time_utc"]
        hour = next(h for h in entry["hourly"] if h["time_utc"] == start)
        _, _, body = fetch(rest + f"?select=score,ruleset_version&spot_id=eq.{entry['spot_id']}"
                                  f"&time_utc=eq.{quote(hour['time_utc'], safe='')}", headers)
        rows = json.loads(body) if body else []
        print(f"  rows with a score: {scored_rows}; {entry['spot_id']} {hour['time_utc']}: table {rows} vs file score {hour['score']}")
        ok = bool(rows) and rows[0]["score"] == hour["score"] and rows[0]["ruleset_version"] == rec["ruleset_version"]
        record("table", ok, "the table holds the same score and ruleset_version as the published file" if ok
               else "the table row does not match the published file (was the file re-published since?)")
    else:
        record("table", None, "SUPABASE_ANON_KEY not set, table check skipped")

    print("\n[summary]")
    for item, ok, text in verdicts:
        print(f"  item {item:5} {'PASS' if ok else 'INFO' if ok is None else 'FAIL'}  {text}")


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "m2-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    buffer = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, text):
            sys.__stdout__.write(text)
            return buffer.write(text)

    with redirect_stdout(Tee()):
        print(f"M2 acceptance check - label: {label}")
        check()
    out = ROOT / "tests" / "acceptance" / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.txt").write_text(buffer.getvalue(), encoding="utf-8")
    print(f"\nsaved to tests/acceptance/output/{label}.txt")
    return 0 if all(ok is not False for _, ok, _ in verdicts) else 1


if __name__ == "__main__":
    sys.exit(main())
