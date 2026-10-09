"""Environment Canterbury river flow, site 66401 (Waimakariri River at Old Highway Bridge).

Facts confirmed in M0 (docs/m0-report.md 2.4):
  * ECan's data catalogue (method 79) returns the last week as CSV:
    site_no, DateTime, Value - one reading every 5 minutes, flow in m3/s;
  * DateTime looks like '8/10/2026 10:00:00 PM' (day/month/year, 12-hour clock);
  * the times are NZ Standard Time (UTC+12) all year - inferred, not documented;
  * the public web page blocks scripts, so it is not used.

Public entry point: fetch(). It returns times in UTC.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from collector.http import http_get
from collector.timeutil import NZST, iso

SITE_ID = "66401"
SITE_NAME = "Waimakariri River at Old Highway Bridge"
URL = ("https://data.ecan.govt.nz/data/79/Water/"
       "River%20stage%20flow%20data%20for%20individual%20site/CSV"
       f"?SiteNo={SITE_ID}&Period=1_Week&StageFlow=River%20Flow")
TIME_FORMAT = "%d/%m/%Y %I:%M:%S %p"


def parse(text: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or not {"DateTime", "Value"} <= set(rows[0]):
        raise ValueError("unexpected ECan CSV layout")
    series = []
    for row in rows:
        when = datetime.strptime(row["DateTime"].strip(), TIME_FORMAT).replace(tzinfo=NZST)
        series.append({"time_utc": iso(when), "flow_m3s": float(row["Value"])})
    series.sort(key=lambda p: p["time_utc"])
    return {"site_id": SITE_ID, "site_name": SITE_NAME, "series": series}


def fetch(get=http_get) -> dict:
    """One request. Returns {"site_id", "site_name", "series": [{"time_utc", "flow_m3s"}]}."""
    return parse(get(URL).decode("utf-8-sig"))
