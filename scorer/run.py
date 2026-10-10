"""Scorer entry point.

    python -m scorer.run --out out

Reads out/conditions/*.json and out/river_flow.json (written by the
collector) plus config/, and writes out/recommendations.json.
Stops with an error if the rules changed without a new ruleset_version.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scorer import engine, version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score fishing conditions.")
    parser.add_argument("--out", default="out", help="folder holding the collector output (default: out)")
    args = parser.parse_args(argv)

    problem = version.check()
    if problem:
        print("scorer: " + problem)
        return 1
    scoring, spots = engine.load_config()
    result = engine.score_all(Path(args.out), scoring, spots)
    path = Path(args.out) / "recommendations.json"
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for spot in result["spots"]:
        best = spot["windows"][0] if spot["windows"] else None
        summary = f"best {best['start_utc']} score {best['score']}" if best else "no window reaches the threshold"
        print(f"scorer: {spot['spot_id']}: {len(spot['windows'])} window(s), {summary}")
    print(f"scorer: wrote {path} (ruleset_version {result['ruleset_version']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
