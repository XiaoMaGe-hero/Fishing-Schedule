"""Spot coordinates used by the smoke tests.

Approximate values copied from the product design (section 7);
they are still to be confirmed by Liang.
"""
SPOTS = [
    {"id": "new-brighton-pier", "lat": -43.507, "lon": 172.733},
    {"id": "southshore", "lat": -43.558, "lon": 172.752},
]

# Open-sea fallback points (about 4-5 km east, in Pegasus Bay), tried only if
# the marine API returns nothing for the spot's own coordinates.
OFFSHORE_FALLBACK = {
    "new-brighton-pier": {"lat": -43.507, "lon": 172.790},
    "southshore": {"lat": -43.558, "lon": 172.810},
}
