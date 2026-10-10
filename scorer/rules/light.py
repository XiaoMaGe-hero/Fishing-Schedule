"""Light: the hour either side of sunrise and of sunset scores best."""
from datetime import timedelta

from scorer.api import RuleResult, parse_utc, rule


@rule(name="light", weight_key="light")
def light_rule(hour, spot, ctx):
    p = ctx.params["light"]
    margin = timedelta(minutes=p["window_min"])
    for day in ctx.days:
        for key, label in (("sunrise_utc", "sunrise"), ("sunset_utc", "sunset")):
            if abs(hour.time - parse_utc(day[key])) <= margin:
                return RuleResult(1.0, f"within {p['window_min']} min of {label}")
    if hour.is_daylight:
        return RuleResult(p["day_score"], "daytime")
    return RuleResult(p["night_score"], "night")
