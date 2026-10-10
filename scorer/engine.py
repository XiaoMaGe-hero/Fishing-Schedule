"""Scoring engine. Pure computation: reads the collector's files, never the network.

Steps (product design, section 6):
  1. for each spot and hour, run every rule: each gives a 0-1 score and a reason;
  2. hour score = weighted average of the rules that ran, scaled to 0-100;
  3. veto rules come first: a vetoed hour scores 0 and carries a safety message;
  4. consecutive hours at or above the threshold are merged into windows;
  5. a window starting within 72 hours is "high" confidence, later ones "low".

Rules and vetoes are found automatically: every .py file in scorer/rules/
(names starting with "_" are ignored) is imported and its @rule / @veto
functions are used. Adding a rule never needs a change here.
"""
from __future__ import annotations

import importlib.util
import json
from math import fsum
from dataclasses import fields
from datetime import timedelta
from pathlib import Path

import yaml

from scorer.api import Context, HourConditions, RuleResult, Spot, parse_utc

ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = Path(__file__).resolve().parent / "rules"
HOUR_FIELDS = [f.name for f in fields(HourConditions)]


def load_rules(rules_dir: Path = RULES_DIR) -> tuple[list, list]:
    """Import every rule file. Returns (rules, vetoes), each sorted by name."""
    rules, vetoes = [], []
    for path in sorted(rules_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"fishing_rules_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for obj in vars(module).values():
            if callable(obj) and getattr(obj, "__module__", None) == module.__name__:
                if hasattr(obj, "_rule_meta"):
                    rules.append(obj)
                if hasattr(obj, "_veto_meta"):
                    vetoes.append(obj)
    names = [r._rule_meta["name"] for r in rules]
    if len(set(names)) != len(names):
        raise ValueError(f"two rules share a name: {sorted(names)}")
    rules.sort(key=lambda r: r._rule_meta["name"])
    vetoes.sort(key=lambda v: v._veto_meta["name"])
    return rules, vetoes


def load_config(config_dir: Path = ROOT / "config") -> tuple[dict, list[dict]]:
    scoring = yaml.safe_load((config_dir / "scoring.yaml").read_text(encoding="utf-8"))
    spots = yaml.safe_load((config_dir / "spots.yaml").read_text(encoding="utf-8"))
    return scoring, spots


def score_hour(hour: HourConditions, spot: Spot, ctx: Context, rules: list, vetoes: list, weights: dict) -> dict:
    """Score one hour. Returns the full breakdown (also used by the explain command)."""
    parts = []
    for fn in rules:
        meta = fn._rule_meta
        weight = weights.get(meta["weight_key"])
        if weight is None:
            raise ValueError(f"rule '{meta['name']}' has no weight '{meta['weight_key']}' in config/scoring.yaml")
        result = fn(hour, spot, ctx)
        if result is None:
            parts.append({"rule": meta["name"], "score": None, "weight": weight,
                          "reason": "skipped: no data or no spot setting for this rule"})
            continue
        if not isinstance(result, RuleResult) or not 0 <= result.score <= 1:
            raise ValueError(f"rule '{meta['name']}' must return a RuleResult with a score from 0 to 1")
        parts.append({"rule": meta["name"], "score": round(result.score, 3), "weight": weight, "reason": result.reason})

    used = [p for p in parts if p["score"] is not None and p["weight"] > 0]
    # fsum, not sum: plain sum() rounds differently on Python 3.12+ than on older versions
    total_weight = fsum(p["weight"] for p in used)
    weighted = fsum(p["score"] * p["weight"] for p in used) / total_weight * 100 if total_weight else 0.0

    safety = [msg for msg in (fn(hour, spot, ctx) for fn in vetoes) if msg]
    return {"time_utc": hour.time_utc, "score": 0.0 if safety else round(weighted, 1),
            "score_before_veto": round(weighted, 1), "vetoed": bool(safety), "safety": safety, "parts": parts}


def score_spot(spot_settings: dict, conditions: dict, river_flow: list, scoring: dict,
               rules: list, vetoes: list) -> list[dict]:
    """Full hourly breakdown for one spot."""
    spot = Spot(id=spot_settings["id"], name=spot_settings.get("name", spot_settings["id"]), settings=spot_settings)
    hours = [HourConditions(**{k: h[k] for k in HOUR_FIELDS}) for h in conditions["hourly"]]
    out = []
    for index, hour in enumerate(hours):
        ctx = Context(index=index, hours=hours, tide_events=conditions["tide_events"], days=conditions["days"],
                      river_flow=river_flow, params=scoring.get("rules", {}))
        out.append(score_hour(hour, spot, ctx, rules, vetoes, scoring["weights"]))
    return out


def build_windows(spot_id: str, breakdown: list[dict], scoring: dict, now_utc: str) -> list[dict]:
    """Merge consecutive good hours into recommended windows, best first."""
    cfg = scoring["window"]
    version = scoring["ruleset_version"]
    horizon = parse_utc(now_utc) + timedelta(hours=cfg["high_confidence_hours"])
    runs, current = [], []
    for hour in breakdown:
        if not hour["vetoed"] and hour["score"] >= cfg["min_score"]:
            current.append(hour)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)

    windows = []
    for run in runs:
        if len(run) < cfg["min_hours"]:
            continue
        start = parse_utc(run[0]["time_utc"])
        end = parse_utc(run[-1]["time_utc"]) + timedelta(hours=1)
        best = max(run, key=lambda h: h["score"])          # its sentences describe the window
        reasons = []
        for i, part in enumerate(best["parts"]):
            scores = [h["parts"][i]["score"] for h in run if h["parts"][i]["score"] is not None]
            reasons.append({"rule": part["rule"],
                            "score": round(fsum(scores) / len(scores), 3) if scores else None,
                            "weight": part["weight"], "reason": part["reason"]})
        windows.append({
            "spot_id": spot_id,
            "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "score": round(fsum(h["score"] for h in run) / len(run), 1),
            "confidence": "high" if start <= horizon else "low",
            "reasons": reasons,
            "ruleset_version": version,
        })
    windows.sort(key=lambda w: (-w["score"], w["start_utc"]))
    return windows


def score_all(out_dir: Path, scoring: dict, spots: list[dict], rules_dir: Path = RULES_DIR) -> dict:
    """Build recommendations.json from the collector's files in out_dir."""
    rules, vetoes = load_rules(rules_dir)
    river_flow = json.loads((out_dir / "river_flow.json").read_text(encoding="utf-8"))["series"]
    result_spots, generated = [], None
    for spot in spots:
        path = out_dir / "conditions" / f"{spot['id']}.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing - run the collector first")
        conditions = json.loads(path.read_text(encoding="utf-8"))
        # "now" is when the conditions were collected, so the same input always gives the same output
        generated = max(generated or "", conditions["generated_at"])
        breakdown = score_spot(spot, conditions, river_flow, scoring, rules, vetoes)
        result_spots.append({
            "spot_id": spot["id"],
            "hourly": [{"time_utc": h["time_utc"], "score": h["score"], "vetoed": h["vetoed"]} for h in breakdown],
            "windows": build_windows(spot["id"], breakdown, scoring, conditions["generated_at"]),
        })
    return {"schema_version": 1, "generated_at": generated, "ruleset_version": scoring["ruleset_version"],
            "spots": result_spots}
