"""Wind: the lighter the better; offshore wind adds a little, onshore wind takes a little away."""
from scorer.api import RuleResult, rule


@rule(name="wind", weight_key="wind")
def wind_rule(hour, spot, ctx):
    if hour.wind_speed_kmh is None:
        return None
    p = ctx.params["wind"]
    calm, strong = p["calm_kmh"], p["strong_kmh"]
    score = 1 - (hour.wind_speed_kmh - calm) / (strong - calm)
    score = min(1.0, max(0.0, score))
    if hour.wind_relative == "offshore":
        score, direction = score + p["offshore_bonus"], "offshore wind"
    elif hour.wind_relative == "onshore":
        score, direction = score - p["onshore_penalty"], "onshore wind"
    elif hour.wind_relative == "cross":
        direction = "cross-shore wind"
    else:
        return RuleResult(min(1.0, max(0.0, score)),
                          f"wind {hour.wind_speed_kmh:.0f} km/h (direction not scored: this spot's shore direction is not set)")
    return RuleResult(min(1.0, max(0.0, score)), f"{direction} {hour.wind_speed_kmh:.0f} km/h")
