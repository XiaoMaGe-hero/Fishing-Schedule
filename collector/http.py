"""The one place collector talks to the network."""
from __future__ import annotations

import urllib.request

USER_AGENT = "LiangsFishingSchedule/1.0 (personal non-commercial fishing site)"
TIMEOUT_S = 30


def http_get(url: str) -> bytes:
    """GET a URL and return the body. Raises on any network or HTTP error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return resp.read()
