"""Run the M0 smoke tests and keep their output as acceptance evidence.

    python3 tests/smoke/run_all.py            # all four data sources
    python3 tests/smoke/run_all.py ecan       # only the named ones

Output of each script is shown and saved to tests/smoke/output/.
Raw responses are saved to tests/smoke/samples/.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SMOKE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SMOKE_DIR / "output"
SCRIPTS = {
    "linz": "smoke_linz.py",
    "weather": "smoke_open_meteo_weather.py",
    "marine": "smoke_open_meteo_marine.py",
    "ecan": "smoke_ecan.py",
}
WHERE = "github" if os.environ.get("GITHUB_ACTIONS") else "local"


def main() -> int:
    names = sys.argv[1:] or list(SCRIPTS)
    unknown = [n for n in names if n not in SCRIPTS]
    if unknown:
        print(f"unknown source(s): {unknown}; choose from {list(SCRIPTS)}")
        return 2
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    preamble = (f"run started {started} | where: {WHERE} | python {platform.python_version()} "
                f"| {platform.system()} {platform.machine()}")
    results = []
    for name in names:
        print(f"\n{'=' * 70}\n{name}: {SCRIPTS[name]}\n{'=' * 70}")
        proc = subprocess.run([sys.executable, str(SMOKE_DIR / SCRIPTS[name])],
                              capture_output=True, text=True, cwd=SMOKE_DIR)
        out = proc.stdout + (("\n--- stderr ---\n" + proc.stderr) if proc.stderr.strip() else "")
        print(out)
        (OUTPUT_DIR / f"{name}-{WHERE}.txt").write_text(preamble + "\n\n" + out, encoding="utf-8")
        verdict = next((ln for ln in reversed(out.splitlines()) if ln.startswith("RESULT:")),
                       f"RESULT: FAIL - script crashed (exit code {proc.returncode})")
        results.append(f"{name:8} {verdict}")

    summary = preamble + "\n" + "\n".join(results) + "\n"
    (OUTPUT_DIR / f"summary-{WHERE}.txt").write_text(summary, encoding="utf-8")
    print(f"\n{'=' * 70}\nSUMMARY\n{'=' * 70}\n{summary}")
    print(f"Saved to {OUTPUT_DIR}")
    return 0 if all("RESULT: PASS" in r for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
