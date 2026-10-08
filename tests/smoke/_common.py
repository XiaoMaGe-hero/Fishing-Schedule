"""Shared helpers for the M0 data-source smoke tests.

Standard library only, so the scripts run with a plain `python3` (3.9+)
and need no `pip install`.
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "LiangsFishingSchedule/0.1 (personal non-commercial fishing site; M0 smoke test)"
SMOKE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = SMOKE_DIR / "samples"
TIMEOUT_S = 30


def http_get(url: str, accept: str | None = None) -> tuple[int, dict, bytes]:
    """Make ONE real GET request.

    Returns (status, headers, body). HTTP errors return their status code;
    network-level failures return status 0 with the error text as the body.
    """
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    print(f"GET {url}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            status, hdrs, body = resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as exc:
        status, hdrs, body = exc.code, dict(exc.headers.items()), exc.read()
    except Exception as exc:  # DNS failure, timeout, TLS error, connection reset...
        print(f"  -> NETWORK ERROR: {type(exc).__name__}: {exc}")
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            print("  -> Hint: this Python has no CA certificates. On macOS with python.org "
                  "Python, run 'Install Certificates.command' in the Python folder.")
        return 0, {}, str(exc).encode()
    print(f"  -> HTTP {status}, {len(body)} bytes, Content-Type: {hdrs.get('Content-Type')}")
    return status, hdrs, body


def save_sample(name: str, body: bytes) -> Path:
    """Save a raw response under tests/smoke/samples/ (reused by M1 unit tests)."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    path = SAMPLES_DIR / name
    path.write_bytes(body)
    print(f"  saved raw response -> {path.relative_to(SMOKE_DIR.parent.parent)}")
    return path


def finish(ok: bool, message: str) -> None:
    """Print the one-line verdict run_all.py looks for, and exit."""
    print()
    print(f"RESULT: {'PASS' if ok else 'FAIL'} - {message}")
    sys.exit(0 if ok else 1)
