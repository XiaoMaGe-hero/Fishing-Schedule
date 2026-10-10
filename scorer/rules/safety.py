"""Veto rules: any of these sets the hour's score to 0, whatever the other rules say."""
from scorer.api import veto


@veto(name="gust")
def gust_veto(hour, spot, ctx):
    limit = spot.get("max_gust_kmh")
    if limit is not None and hour.wind_gust_kmh is not None and hour.wind_gust_kmh > limit:
        return f"Unsafe: gusts {hour.wind_gust_kmh:.0f} km/h exceed this spot's limit of {limit:.0f} km/h"
    return None


@veto(name="wave")
def wave_veto(hour, spot, ctx):
    limit = spot.get("max_wave_m")
    if limit is not None and hour.wave_height_m is not None and hour.wave_height_m > limit:
        return f"Unsafe: waves {hour.wave_height_m:.1f} m exceed this spot's limit of {limit:.1f} m"
    return None


@veto(name="night")
def night_veto(hour, spot, ctx):
    if not hour.is_daylight and not spot.get("allow_night", False):
        return "Night: this spot is not fished after dark"
    return None


@veto(name="no_forecast")
def no_forecast_veto(hour, spot, ctx):
    # Without gusts or waves the two safety limits above cannot be checked,
    # so the hour is not recommended rather than scored on tide and light alone.
    if hour.wind_gust_kmh is None or hour.wave_height_m is None:
        return "No wind or wave forecast for this hour, so it cannot be checked against the safety limits"
    return None
