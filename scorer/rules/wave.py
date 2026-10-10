"""Waves: the lower the better, measured against the spot's limit."""
from scorer.api import RuleResult, rule


@rule(name="wave", weight_key="wave")
def wave_rule(hour, spot, ctx):
    limit = spot.get("max_wave_m")
    if hour.wave_height_m is None or limit is None:
        return None
    score = min(1.0, max(0.0, 1 - hour.wave_height_m / limit))
    return RuleResult(score, f"waves {hour.wave_height_m:.1f} m (limit {limit:.1f} m)")
