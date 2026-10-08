"""M0 smoke test: Environment Canterbury river flow, site 66401.

Answers unknowns 4, 5 and 6 of M0:
  4. Is the flow data in the page HTML, or served by a backing endpoint?
  5. Does ECan answer requests from this machine / from GitHub Actions?
  6. Which gauge is 66401, and does its reading look tidal?

Makes two requests: the public page, then ECan's data catalogue endpoint.
Run it both on your own computer and on GitHub Actions.

Result of the first real run (2026-10-08, local machine):
  - the public page answers scripts with a bot challenge (Incapsula), not the
    real page, so scraping its HTML is not possible;
  - the data catalogue endpoint returns the 7-day series as CSV
    (site_no, DateTime, Value), one reading every 5 minutes.
The verdict therefore depends on the data endpoint; the page is reported only.
"""
from __future__ import annotations

import csv
import io
import os
import re
from datetime import datetime
from statistics import mean, median, pstdev

from _common import finish, http_get, save_sample

SITE = "66401"
PAGE_URL = f"https://www.ecan.govt.nz/data/riverflow/sitedetails/{SITE}"
# ECan's open data catalogue, method 79 ("River stage flow data for individual
# site"). Confirmed working on 2026-10-08. Catalogue page:
# https://data.ecan.govt.nz/Catalogue/Method?MethodId=79&SiteNo=66401
DATA_URL = ("https://data.ecan.govt.nz/data/79/Water/"
            "River%20stage%20flow%20data%20for%20individual%20site/CSV"
            f"?SiteNo={SITE}&Period=1_Week&StageFlow=River%20Flow")
WHERE = "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local machine"
DATE_FORMATS = ["%d/%m/%Y %I:%M:%S %p",  # what the endpoint actually returns: 8/10/2026 10:00:00 PM
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M"]


def strip_tags(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def inspect_page(html: str) -> None:
    title = re.search(r"(?is)<title>(.*?)</title>", html)
    print(f"page <title>: {title.group(1).strip() if title else None}")
    text = strip_tags(html)

    print("\n--- Visible text around 'm3/s' (is the latest value in the HTML?) ---")
    for m in list(re.finditer(r"m3/s|m³/s|cumecs", text))[:5]:
        print("  ..." + text[max(0, m.start() - 160):m.end() + 60] + "...")

    print("\n--- Visible text mentioning 'tid' (tide / tidal) ---")
    hits = list(re.finditer(r"(?i)\btid(e|al)", text))
    for m in hits[:5]:
        print("  ..." + text[max(0, m.start() - 120):m.end() + 120] + "...")
    if not hits:
        print("  (none)")

    print("\n--- <script src> files ---")
    for src in re.findall(r'(?i)<script[^>]+src=["\']([^"\']+)', html)[:40]:
        print("  " + src)

    print("\n--- URLs and paths in the HTML that look like data endpoints ---")
    candidates = set(re.findall(r'https?://[^\s"\'<>\\)]+', html))
    candidates |= set(re.findall(r'["\'](/[^"\'\s<>]*(?:api|riverflow|data)[^"\'\s<>]*)["\']', html, re.I))
    for url in sorted(c for c in candidates if re.search(r"(?i)data\.ecan|api|riverflow|json|csv|SiteNo", c))[:60]:
        print("  " + url)

    print("\n--- Inline script lines that fetch data ---")
    shown = 0
    for m in re.finditer(r"(?i)(\$\.getJSON|\$\.ajax|fetch\(|XMLHttpRequest|SiteNo|chartData|series\s*:)", html):
        print("  ..." + re.sub(r"\s+", " ", html[max(0, m.start() - 100):m.end() + 200]) + "...")
        shown += 1
        if shown >= 12:
            break
    if not shown:
        print("  (none found)")


def parse_series(text: str) -> list[tuple[datetime, float]]:
    """Best-effort parse of a CSV with one datetime column and one flow column."""
    rows = list(csv.reader(io.StringIO(text)))
    series = []
    for row in rows:
        when = value = None
        for cell in (c.strip() for c in row):
            if when is None:
                for fmt in DATE_FORMATS:
                    try:
                        when = datetime.strptime(cell, fmt)
                        break
                    except ValueError:
                        pass
                if when is not None:
                    continue
            try:
                value = float(cell)  # the last numeric cell in the row wins
            except ValueError:
                pass
        if when is not None and value is not None:
            series.append((when, value))
    return sorted(series)


def tidal_check(series: list[tuple[datetime, float]]) -> None:
    """Indicative only: look for a ~12.4 h rhythm in the flow record."""
    print("\n--- Tidal influence check (indicative only) ---")
    if len(series) < 200:
        print(f"  only {len(series)} points; not enough to judge")
        return
    step_h = median((series[i + 1][0] - series[i][0]).total_seconds() for i in range(len(series) - 1)) / 3600
    values = [v for _, v in series]
    half = max(1, round(12.42 / step_h))  # moving-average half-window, about 24.8 h in total
    lag = max(1, round(12.42 / step_h))
    detrended = []
    for i in range(half, len(values) - half):
        detrended.append(values[i] - mean(values[i - half:i + half + 1]))
    if len(detrended) <= lag + 10 or pstdev(detrended) == 0:
        print("  record too short or perfectly flat after detrending; cannot judge")
        return
    a, b = detrended[:-lag], detrended[lag:]
    ma, mb = mean(a), mean(b)
    cov = mean((x - ma) * (y - mb) for x, y in zip(a, b))
    corr = cov / (pstdev(a) * pstdev(b)) if pstdev(a) and pstdev(b) else 0.0
    ripple = pstdev(detrended) / mean(values) * 100
    print(f"  sampling step: {step_h * 60:.0f} min; points: {len(series)}")
    print(f"  correlation of the detrended flow with itself 12.4 h later: {corr:+.2f}")
    print(f"  short-term ripple: {ripple:.2f} % of mean flow")
    if corr > 0.5 and ripple > 1.0:
        print("  -> a repeating ~12.4 h pattern is present: readings MAY be tidally influenced")
    else:
        print("  -> no clear ~12.4 h pattern in this week of data")


def main() -> None:
    print(f"Running from: {WHERE}")
    status, _, body = http_get(PAGE_URL)
    html = body.decode("utf-8", "replace") if status == 200 else ""
    if status != 200:
        page_state = f"HTTP {status}"
    elif "_Incapsula_Resource" in html and len(html) < 2000:
        page_state = "BLOCKED by bot challenge (Incapsula)"
    else:
        page_state = "readable"
    print(f"public page: {page_state}")
    if status == 200:
        save_sample(f"ecan_page_{SITE}.html", body)
        inspect_page(html)
    else:
        print(body[:300].decode("utf-8", "replace"))

    print("\n=== Data endpoint (ECan data catalogue, method 79) ===")
    status2, hdrs2, body2 = http_get(DATA_URL)
    series: list[tuple[datetime, float]] = []
    if status2 == 200:
        save_sample(f"ecan_flow_{SITE}_1week.csv", body2)
        text = body2.decode("utf-8-sig", "replace")
        lines = text.splitlines()
        print(f"lines: {len(lines)}")
        for ln in lines[:6]:
            print("  " + repr(ln))
        if len(lines) > 8:
            print("  ...")
            for ln in lines[-2:]:
                print("  " + repr(ln))
        series = parse_series(text)
        if series:
            print(f"parsed {len(series)} (time, flow) points: {series[0][0]} .. {series[-1][0]}; "
                  f"flow min {min(v for _, v in series)}, max {max(v for _, v in series)}")
            print("  (timestamps are printed exactly as given; time zone to be confirmed in the M0 report)")
            tidal_check(series)
        else:
            print("could not parse a (time, flow) series from this response")
    else:
        print(body2[:300].decode("utf-8", "replace"))

    span_days = (series[-1][0] - series[0][0]).total_seconds() / 86400 if series else 0
    summary = (f"from {WHERE}: public page {page_state}; data endpoint HTTP {status2}, "
               f"{len(series)} flow points over {span_days:.1f} days")
    finish(span_days >= 6.5, summary)


if __name__ == "__main__":
    main()
