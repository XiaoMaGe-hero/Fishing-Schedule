"""What a rule file needs: the @rule and @veto decorators and the data types.

Writing a new rule: create a file in scorer/rules/, for example

    from scorer.api import RuleResult, rule

    @rule(name="my_rule", weight_key="my_rule")
    def my_rule(hour, spot, ctx):
        if hour.sea_temp_c is None:
            return None                      # nothing to judge: the rule is skipped for this hour
        return RuleResult(score=0.8, reason="sea is warm enough")

then add a weight for "my_rule" under `weights:` in config/scoring.yaml and
raise `ruleset_version`. The engine finds the file by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def parse_utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


@dataclass(frozen=True)
class HourConditions:
    """One hour at one spot. Field names and units are those of conditions/{spot_id}.json."""
    time_utc: str
    tide_height_m: float | None
    tide_phase: str | None
    air_temp_c: float | None
    precip_prob_pct: float | None
    weather_code: int | None
    wind_speed_kmh: float | None
    wind_gust_kmh: float | None
    wind_dir_deg: float | None
    wind_relative: str | None
    wave_height_m: float | None
    swell_height_m: float | None
    sea_temp_c: float | None
    is_daylight: bool

    @property
    def time(self) -> datetime:
        return parse_utc(self.time_utc)


@dataclass(frozen=True)
class Spot:
    """One spot from config/spots.yaml. `settings` holds every key of its block."""
    id: str
    name: str
    settings: dict

    def get(self, key: str, default=None):
        value = self.settings.get(key)
        return default if value is None else value


@dataclass(frozen=True)
class RuleResult:
    score: float    # 0 (bad) .. 1 (ideal)
    reason: str     # one short English sentence shown on the site


@dataclass(frozen=True)
class Context:
    """Everything else a rule may look at for the same spot."""
    index: int                      # position of the current hour in `hours`
    hours: list                     # every HourConditions of the week, in time order
    tide_events: list               # [{"time_utc", "type", "height_m"}]
    days: list                      # [{"date_local", "sunrise_utc", "sunset_utc", "moon_phase"}]
    river_flow: list                # [{"time_utc", "flow_m3s"}], measured, last 7 days
    params: dict = field(default_factory=dict)   # the `rules:` block of config/scoring.yaml

    def around(self, before: int, after: int) -> list:
        """The hours from `before` hours earlier to `after` hours later (current hour included)."""
        return self.hours[max(0, self.index - before): self.index + after + 1]

    def latest_river_flow(self) -> float | None:
        values = [p["flow_m3s"] for p in self.river_flow if p["flow_m3s"] is not None]
        return values[-1] if values else None

    def minutes_from_nearest(self, when: datetime, event_type: str) -> float | None:
        """Signed minutes from the nearest tide of that type ('high' or 'low'): negative = before it."""
        deltas = [(when - parse_utc(e["time_utc"])) / timedelta(minutes=1)
                  for e in self.tide_events if e["type"] == event_type]
        return min(deltas, key=abs) if deltas else None


def rule(name: str, weight_key: str | None = None):
    """Mark a function as a scoring rule. It returns a RuleResult, or None to be skipped."""
    def mark(fn):
        fn._rule_meta = {"name": name, "weight_key": weight_key or name}
        return fn
    return mark


def veto(name: str):
    """Mark a function as a veto rule. It returns a safety message to zero the hour, or None."""
    def mark(fn):
        fn._veto_meta = {"name": name}
        return fn
    return mark
