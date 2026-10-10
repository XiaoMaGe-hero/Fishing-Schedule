"""Rain: the lower the chance of rain the better."""
from scorer.api import RuleResult, rule


@rule(name="rain", weight_key="rain")
def rain_rule(hour, spot, ctx):
    if hour.precip_prob_pct is None:
        return None
    return RuleResult(1 - hour.precip_prob_pct / 100, f"{hour.precip_prob_pct:.0f}% chance of rain")
