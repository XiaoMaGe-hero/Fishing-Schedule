"""Explain one score: every rule's input, score, weight and reason.

    python -m scorer.explain --spot new-brighton-pier --time 2026-10-10T04:00:00Z --out out

--time is the start of the hour in UTC, as written in the JSON files.
Add --local to give the time as NZ clock time instead, e.g. --time "2026-10-10 17:00" --local
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scorer import engine

NZ = ZoneInfo("Pacific/Auckland")
# what each rule looks at, so the explanation can show the inputs
INPUTS = {
    "tide": ["tide_height_m", "tide_phase"],
    "wind": ["wind_speed_kmh", "wind_relative", "wind_dir_deg"],
    "wave": ["wave_height_m"],
    "rain": ["precip_prob_pct"],
    "light": ["is_daylight"],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explain the score of one hour.")
    parser.add_argument("--spot", required=True)
    parser.add_argument("--time", required=True)
    parser.add_argument("--local", action="store_true", help="--time is NZ clock time 'YYYY-MM-DD HH:MM'")
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)

    if args.local:
        when = datetime.strptime(args.time, "%Y-%m-%d %H:%M").replace(tzinfo=NZ).astimezone(timezone.utc)
        stamp = when.strftime("%Y-%m-%dT%H:00:00Z")
    else:
        stamp = args.time
    scoring, spots = engine.load_config()
    spot = next((s for s in spots if s["id"] == args.spot), None)
    if spot is None:
        print(f"unknown spot '{args.spot}'; known: {[s['id'] for s in spots]}")
        return 2
    out_dir = Path(args.out)
    conditions = json.loads((out_dir / "conditions" / f"{args.spot}.json").read_text(encoding="utf-8"))
    river = json.loads((out_dir / "river_flow.json").read_text(encoding="utf-8"))["series"]
    rules, vetoes = engine.load_rules()
    breakdown = engine.score_spot(spot, conditions, river, scoring, rules, vetoes)
    hour = next((h for h in breakdown if h["time_utc"] == stamp), None)
    if hour is None:
        print(f"{stamp} is not in the file; it covers {breakdown[0]['time_utc']} .. {breakdown[-1]['time_utc']}")
        return 2
    raw = next(h for h in conditions["hourly"] if h["time_utc"] == stamp)
    local = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(NZ)

    print(f"{args.spot}  {stamp}  ({local:%a %d %b %H:%M} NZ time)  ruleset_version {scoring['ruleset_version']}")
    print(f"{'rule':8} {'score':>6} {'weight':>6}  {'inputs':44} reason")
    total = sum(p["weight"] for p in hour["parts"] if p["score"] is not None)
    for part in hour["parts"]:
        inputs = ", ".join(f"{k}={raw[k]}" for k in INPUTS.get(part["rule"], []))
        score = "skip" if part["score"] is None else f"{part['score']:.3f}"
        print(f"{part['rule']:8} {score:>6} {part['weight']:>6}  {inputs:44} {part['reason']}")
    print(f"weighted score: {hour['score_before_veto']} / 100  (weights in use add up to {total})")
    for message in hour["safety"]:
        print(f"VETO: {message}")
    print(f"final score: {hour['score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
