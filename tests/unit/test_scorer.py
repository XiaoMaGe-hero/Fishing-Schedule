"""Scoring engine: the nine acceptance items of M2, on real collected data replayed from the M0 samples."""
from __future__ import annotations

import json
import shutil
from math import fsum
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from publish import run as publish
from scorer import engine, version
from scorer.api import Context, HourConditions, RuleResult, Spot, parse_utc

from conftest import ROOT, SAMPLE_NOW

CURRENT_VERSION = yaml.safe_load((ROOT / "config" / "scoring.yaml").read_text(encoding="utf-8"))["ruleset_version"]


@pytest.fixture
def config():
    return engine.load_config()


@pytest.fixture
def scored(collected, config):
    out, _ = collected
    scoring, spots = config
    result = engine.score_all(out, scoring, spots)
    (out / "recommendations.json").write_text(json.dumps(result), encoding="utf-8")
    return out, result


def spot_result(result, spot_id):
    return next(s for s in result["spots"] if s["spot_id"] == spot_id)


def make_hour(**changes):
    base = dict(time_utc="2026-10-10T01:00:00Z", tide_height_m=1.5, tide_phase="rising", air_temp_c=15.0,
                precip_prob_pct=10, weather_code=1, wind_speed_kmh=12.0, wind_gust_kmh=20.0, wind_dir_deg=270,
                wind_relative="offshore", wave_height_m=0.6, swell_height_m=0.4, sea_temp_c=13.0, is_daylight=True)
    base.update(changes)
    return HourConditions(**base)


def make_ctx(hour, params):
    return Context(index=0, hours=[hour],
                   tide_events=[{"time_utc": "2026-10-10T01:30:00Z", "type": "high", "height_m": 2.4},
                                {"time_utc": "2026-10-10T07:40:00Z", "type": "low", "height_m": 0.5}],
                   days=[{"date_local": "2026-10-10", "sunrise_utc": "2026-10-09T17:47:00Z",
                          "sunset_utc": "2026-10-10T06:46:00Z", "moon_phase": 0.0}],
                   river_flow=[], params=params)


PIER = Spot("new-brighton-pier", "New Brighton Pier",
            {"id": "new-brighton-pier", "allow_night": False, "best_tide_window_min": [-120, 120],
             "max_gust_kmh": 45, "max_wave_m": 2.0})


# --- item 1: schema and coverage -------------------------------------------

def test_output_matches_schema_and_covers_both_spots_for_7_days(scored):
    out, result = scored
    assert publish.validate(out) == []
    assert [s["spot_id"] for s in result["spots"]] == ["new-brighton-pier", "southshore"]
    for spot in result["spots"]:
        conditions = json.loads((out / "conditions" / f"{spot['spot_id']}.json").read_text())
        assert [h["time_utc"] for h in spot["hourly"]] == [h["time_utc"] for h in conditions["hourly"]]
        assert len(spot["hourly"]) == 168
        scores = [w["score"] for w in spot["windows"]]
        assert scores == sorted(scores, reverse=True) and scores, "windows are listed best first"
        for window in spot["windows"]:
            length = parse_utc(window["end_utc"]) - parse_utc(window["start_utc"])
            assert length >= timedelta(hours=1.5)


def test_window_score_is_the_mean_of_its_hours(scored):
    _, result = scored
    spot = spot_result(result, "new-brighton-pier")
    by_time = {h["time_utc"]: h for h in spot["hourly"]}
    for window in spot["windows"]:
        hours, t = [], parse_utc(window["start_utc"])
        while t < parse_utc(window["end_utc"]):
            hours.append(by_time[t.strftime("%Y-%m-%dT%H:%M:%SZ")])
            t += timedelta(hours=1)
        assert all(h["score"] >= 60 and not h["vetoed"] for h in hours)
        assert window["score"] == round(fsum(h["score"] for h in hours) / len(hours), 1)


# --- item 2: changing a weight moves the scores as expected ----------------

def test_raising_a_weight_pulls_scores_towards_that_rule(collected, config):
    out, _ = collected
    scoring, spots = config
    rules, vetoes = engine.load_rules()
    conditions = json.loads((out / "conditions" / "new-brighton-pier.json").read_text())
    before = engine.score_spot(spots[0], conditions, [], scoring, rules, vetoes)
    heavier = json.loads(json.dumps(scoring))
    heavier["weights"]["rain"] = scoring["weights"]["rain"] * 10
    after = engine.score_spot(spots[0], conditions, [], heavier, rules, vetoes)
    moved = 0
    for b, a in zip(before, after):
        rain = next(p["score"] for p in b["parts"] if p["rule"] == "rain")
        if rain is None:
            continue                       # the samples have no forecast for the last hours of the week
        rain *= 100
        if abs(rain - b["score_before_veto"]) > 0.2:
            assert abs(rain - a["score_before_veto"]) < abs(rain - b["score_before_veto"])
            moved += 1
    assert moved > 100


# --- item 3: a new rule file needs no engine change ------------------------

NEW_RULE = '''
from scorer.api import RuleResult, rule

@rule(name="warm_sea", weight_key="warm_sea")
def warm_sea(hour, spot, ctx):
    if hour.sea_temp_c is None:
        return None
    return RuleResult(1.0 if hour.sea_temp_c >= 13 else 0.2, f"sea {hour.sea_temp_c} C")
'''


def test_a_new_rule_file_is_picked_up_without_touching_the_engine(collected, config, tmp_path):
    out, _ = collected
    scoring, spots = config
    rules_dir = tmp_path / "rules"
    shutil.copytree(engine.RULES_DIR, rules_dir)
    (rules_dir / "warm_sea.py").write_text(NEW_RULE, encoding="utf-8")
    scoring = json.loads(json.dumps(scoring))
    scoring["weights"]["warm_sea"] = 2
    result = engine.score_all(out, scoring, spots, rules_dir=rules_dir)
    windows = spot_result(result, "new-brighton-pier")["windows"]
    assert all("warm_sea" in [r["rule"] for r in w["reasons"]] for w in windows)
    reasons = [r["reason"] for w in windows for r in w["reasons"] if r["rule"] == "warm_sea"]
    assert any(reason.startswith("sea ") for reason in reasons)


def test_a_rule_without_a_weight_is_reported_clearly(collected, config, tmp_path):
    out, _ = collected
    scoring, spots = config
    rules_dir = tmp_path / "rules"
    shutil.copytree(engine.RULES_DIR, rules_dir)
    (rules_dir / "warm_sea.py").write_text(NEW_RULE, encoding="utf-8")
    with pytest.raises(ValueError, match="warm_sea.*scoring.yaml"):
        engine.score_all(out, scoring, spots, rules_dir=rules_dir)


# --- item 4: every window carries every rule's score and reason -------------

def test_every_window_lists_all_rules_with_score_and_reason(scored):
    _, result = scored
    for spot in result["spots"]:
        for window in spot["windows"]:
            assert [r["rule"] for r in window["reasons"]] == ["light", "rain", "tide", "wave", "wind"]
            assert all(r["reason"] and r["weight"] > 0 for r in window["reasons"])
            assert window["ruleset_version"] == result["ruleset_version"] == CURRENT_VERSION


# --- item 5: a missing spot setting skips only what depends on it -----------

def test_no_shore_direction_skips_the_direction_part_only(config):
    scoring, _ = config
    rules, vetoes = engine.load_rules()
    known = make_hour(wind_relative="cross")
    unknown = make_hour(wind_relative=None)
    a = engine.score_hour(known, PIER, make_ctx(known, scoring["rules"]), rules, vetoes, scoring["weights"])
    b = engine.score_hour(unknown, PIER, make_ctx(unknown, scoring["rules"]), rules, vetoes, scoring["weights"])
    wind = next(p for p in b["parts"] if p["rule"] == "wind")
    assert "direction not scored" in wind["reason"] and "shore direction is not set" in wind["reason"]
    assert b["score"] == a["score"]            # same as a neutral, cross-shore wind: not dragged down


def test_a_skipped_rule_hands_its_weight_to_the_others(config):
    scoring, _ = config
    rules, vetoes = engine.load_rules()
    no_limit = Spot("x", "X", {"id": "x", "allow_night": False, "best_tide_window_min": [-120, 120],
                               "max_gust_kmh": 45, "max_wave_m": None})
    hour = make_hour()
    result = engine.score_hour(hour, no_limit, make_ctx(hour, scoring["rules"]), rules, vetoes, scoring["weights"])
    wave = next(p for p in result["parts"] if p["rule"] == "wave")
    assert wave["score"] is None and wave["reason"].startswith("skipped")
    used = [p for p in result["parts"] if p["score"] is not None]
    expected = fsum(p["score"] * p["weight"] for p in used) / fsum(p["weight"] for p in used) * 100
    assert result["score"] == round(expected, 1)


def test_southshore_is_scored_despite_its_missing_settings(scored):
    _, result = scored
    pier, south = spot_result(result, "new-brighton-pier"), spot_result(result, "southshore")
    assert south["windows"]
    mean = lambda spot: sum(h["score"] for h in spot["hourly"] if not h["vetoed"]) / sum(1 for h in spot["hourly"] if not h["vetoed"])
    assert abs(mean(south) - mean(pier)) < 15


# --- item 6: safety vetoes ---------------------------------------------------

@pytest.mark.parametrize("changes, text", [
    ({"wind_gust_kmh": 46.0}, "gusts 46 km/h exceed this spot's limit of 45 km/h"),
    ({"wave_height_m": 2.1}, "waves 2.1 m exceed this spot's limit of 2.0 m"),
    ({"is_daylight": False}, "not fished after dark"),
])
def test_a_veto_zeroes_the_hour_and_says_why(config, changes, text):
    scoring, _ = config
    rules, vetoes = engine.load_rules()
    hour = make_hour(**changes)
    result = engine.score_hour(hour, PIER, make_ctx(hour, scoring["rules"]), rules, vetoes, scoring["weights"])
    assert result["score"] == 0.0 and result["vetoed"] is True
    assert result["score_before_veto"] > 0
    assert any(text in message for message in result["safety"])


def test_an_hour_without_forecast_is_scored_on_the_rules_that_still_have_data(config):
    """Liang's decision of 2026-10-10: missing wind or wave data is not a veto; those rules are simply skipped."""
    scoring, _ = config
    rules, vetoes = engine.load_rules()
    hour = make_hour(wind_speed_kmh=None, wind_gust_kmh=None, wind_relative=None, wave_height_m=None, precip_prob_pct=None)
    result = engine.score_hour(hour, PIER, make_ctx(hour, scoring["rules"]), rules, vetoes, scoring["weights"])
    assert result["vetoed"] is False and result["score"] > 0
    assert [p["rule"] for p in result["parts"] if p["score"] is None] == ["rain", "wave", "wind"]


def test_at_the_limit_is_still_allowed_and_night_spots_are_not_vetoed(config):
    scoring, _ = config
    rules, vetoes = engine.load_rules()
    hour = make_hour(wind_gust_kmh=45.0, wave_height_m=2.0)
    assert engine.score_hour(hour, PIER, make_ctx(hour, scoring["rules"]), rules, vetoes, scoring["weights"])["vetoed"] is False
    night_ok = Spot("n", "N", {**PIER.settings, "allow_night": True})
    hour = make_hour(is_daylight=False)
    assert engine.score_hour(hour, night_ok, make_ctx(hour, scoring["rules"]), rules, vetoes, scoring["weights"])["vetoed"] is False


def test_vetoed_hours_never_appear_in_a_window(scored):
    _, result = scored
    for spot in result["spots"]:
        vetoed = {h["time_utc"] for h in spot["hourly"] if h["vetoed"]}
        assert vetoed and all(h["score"] == 0 for h in spot["hourly"] if h["vetoed"])
        for window in spot["windows"]:
            t = parse_utc(window["start_utc"])
            while t < parse_utc(window["end_utc"]):
                assert t.strftime("%Y-%m-%dT%H:%M:%SZ") not in vetoed
                t += timedelta(hours=1)


def test_the_hour_around_dawn_and_dusk_is_not_treated_as_night(scored):
    """Night veto follows is_daylight, which already includes the hour before sunrise and after sunset."""
    out, result = scored
    conditions = json.loads((out / "conditions" / "new-brighton-pier.json").read_text())
    scores = {h["time_utc"]: h for h in spot_result(result, "new-brighton-pier")["hourly"]}
    edge = [h for h in conditions["hourly"] if h["is_daylight"] and any(
        abs(parse_utc(h["time_utc"]) - parse_utc(d[k])) <= timedelta(minutes=60)
        for d in conditions["days"] for k in ("sunrise_utc", "sunset_utc"))]
    assert len(edge) >= 14
    other_veto = {h["time_utc"] for h in conditions["hourly"]
                  if (h["wind_gust_kmh"] or 0) > 45 or (h["wave_height_m"] or 0) > 2}
    checked = [h for h in edge if h["time_utc"] not in other_veto]
    assert len(checked) >= 8 and all(not scores[h["time_utc"]]["vetoed"] for h in checked)


# --- item 7: confidence -------------------------------------------------------

def test_confidence_is_high_within_72_hours_and_low_after(scored):
    _, result = scored
    limit = SAMPLE_NOW.replace(microsecond=0) + timedelta(hours=72)
    seen = set()
    for spot in result["spots"]:
        for window in spot["windows"]:
            expected = "high" if parse_utc(window["start_utc"]) <= limit else "low"
            assert window["confidence"] == expected
            seen.add(expected)
    assert seen == {"high", "low"}


# --- item 8: same input, same output ------------------------------------------

def test_same_input_gives_byte_identical_output(collected, config):
    out, _ = collected
    scoring, spots = config
    first = json.dumps(engine.score_all(out, scoring, spots), sort_keys=True)
    assert first == json.dumps(engine.score_all(out, scoring, spots), sort_keys=True)


# --- item 9: a rule change needs a new version --------------------------------

@pytest.fixture
def project_copy(tmp_path):
    for folder in ("config", "scorer"):
        shutil.copytree(ROOT / folder, tmp_path / folder, ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def bump(root: Path):
    path = root / "config" / "scoring.yaml"
    text = path.read_text(encoding="utf-8")
    current = yaml.safe_load(text)["ruleset_version"]
    path.write_text(text.replace(f"ruleset_version: {current}", f"ruleset_version: {current + 1}"), encoding="utf-8")


def test_the_repo_itself_is_consistent():
    assert version.check() is None


def test_editing_a_rule_without_a_new_version_is_an_error(project_copy):
    assert version.check(project_copy) is None
    rule_file = project_copy / "scorer" / "rules" / "rain.py"
    rule_file.write_text(rule_file.read_text(encoding="utf-8").replace("/ 100,", "/ 90,"), encoding="utf-8")
    problem = version.check(project_copy)
    assert problem and f"ruleset_version is still {CURRENT_VERSION}" in problem
    with pytest.raises(SystemExit):
        version.update(project_copy)                      # cannot be waved through without a new number
    bump(project_copy)
    assert "lock file is not updated" in version.check(project_copy)
    version.update(project_copy)
    assert version.check(project_copy) is None


@pytest.mark.parametrize("edit", [
    lambda root: (root / "config" / "scoring.yaml", "tide: 3", "tide: 4"),
    lambda root: (root / "config" / "scoring.yaml", "min_score: 60", "min_score: 55"),
    lambda root: (root / "config" / "spots.yaml", "max_gust_kmh: 45", "max_gust_kmh: 40"),
])
def test_changing_a_setting_without_a_new_version_is_an_error(project_copy, edit):
    path, old, new = edit(project_copy)
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    assert f"ruleset_version is still {CURRENT_VERSION}" in version.check(project_copy)


def test_notes_and_comments_in_config_do_not_need_a_new_version(project_copy):
    path = project_copy / "config" / "spots.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace('notes: ""', 'notes: "Good on a making tide."', 1)
                    + "\n# a comment\n", encoding="utf-8")
    assert version.check(project_copy) is None


# --- publish carries the scores into the history table ------------------------

def test_scores_reach_the_history_rows(scored):
    out, result = scored
    full_rows, _ = publish.history_rows(out, SAMPLE_NOW)
    by_key = {(r["spot_id"], r["time_utc"]): r for r in full_rows}
    for spot in result["spots"]:
        for hour in spot["hourly"][:5] + spot["hourly"][-5:]:
            row = by_key[(spot["spot_id"], hour["time_utc"])]
            assert row["score"] == hour["score"] and row["ruleset_version"] == CURRENT_VERSION
    assert len({frozenset(r) for r in full_rows}) == 1          # every row has the same columns


def test_a_bad_recommendations_file_blocks_the_upload(scored):
    out, result = scored
    result["spots"][0]["windows"][0]["confidence"] = "medium"
    (out / "recommendations.json").write_text(json.dumps(result), encoding="utf-8")
    problems = publish.validate(out)
    assert problems and problems[0].startswith("recommendations.json: spots/0/windows/0/confidence")
