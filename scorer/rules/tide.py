"""Tide: best inside the spot's window around high tide."""
from scorer.api import RuleResult, rule


@rule(name="tide", weight_key="tide")
def tide_rule(hour, spot, ctx):
    window = spot.get("best_tide_window_min")
    minutes = ctx.minutes_from_nearest(hour.time, "high")
    if window is None or minutes is None:
        return None
    start, end = window
    falloff = ctx.params["tide"]["falloff_min"]
    outside = max(start - minutes, minutes - end, 0)
    score = max(0.0, 1 - outside / falloff)
    side = "before" if minutes < 0 else "after"
    where = "inside" if outside == 0 else "outside"
    hours, mins = divmod(round(abs(minutes)), 60)
    return RuleResult(score, f"{hours} h {mins:02d} min {side} high tide, {where} the best window")
