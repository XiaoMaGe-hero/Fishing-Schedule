"""Guard for ruleset_version.

Scores only mean something next to the rules that produced them, so every
change to the rules or their settings must come with a new ruleset_version.
This module keeps a fingerprint of the scoring inputs in scorer/ruleset.lock:

    python3 -m scorer.version            # check; error if something changed without a new version
    python3 -m scorer.version --update   # after raising ruleset_version: record the new fingerprint

The fingerprint covers every file in scorer/rules/, config/scoring.yaml
(except the version number itself) and the scoring settings of each spot.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOCK = Path(__file__).resolve().parent / "ruleset.lock"
# spot settings the rules read; names, notes and coordinates do not change scores by themselves
SPOT_SCORING_KEYS = ["id", "allow_night", "best_tide_window_min", "max_gust_kmh", "max_wave_m"]


def fingerprint(root: Path = ROOT) -> tuple[int, str]:
    """(ruleset_version from scoring.yaml, hash of everything that shapes a score)."""
    scoring = yaml.safe_load((root / "config" / "scoring.yaml").read_text(encoding="utf-8"))
    version = scoring.pop("ruleset_version")
    spots = yaml.safe_load((root / "config" / "spots.yaml").read_text(encoding="utf-8"))
    digest = hashlib.sha256()
    digest.update(json.dumps(scoring, sort_keys=True).encode())
    digest.update(json.dumps([{k: s.get(k) for k in SPOT_SCORING_KEYS} for s in spots], sort_keys=True).encode())
    for path in sorted((root / "scorer" / "rules").glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return version, digest.hexdigest()


def check(root: Path = ROOT, lock: Path | None = None) -> str | None:
    """None when everything is in order, otherwise the problem as a sentence."""
    lock = lock or root / "scorer" / "ruleset.lock"
    version, digest = fingerprint(root)
    if not lock.exists():
        return "scorer/ruleset.lock is missing. Run: python3 -m scorer.version --update"
    recorded = json.loads(lock.read_text(encoding="utf-8"))
    if digest == recorded["fingerprint"] and version == recorded["ruleset_version"]:
        return None
    if digest != recorded["fingerprint"] and version == recorded["ruleset_version"]:
        return (f"A rule file or a scoring setting changed, but ruleset_version is still {version}. "
                "Raise ruleset_version in config/scoring.yaml, then run: python3 -m scorer.version --update")
    if version < recorded["ruleset_version"]:
        return f"ruleset_version went down from {recorded['ruleset_version']} to {version}; it must only go up."
    return (f"ruleset_version is now {version} (was {recorded['ruleset_version']}) but the lock file is not updated. "
            "Run: python3 -m scorer.version --update")


def update(root: Path = ROOT, lock: Path | None = None) -> str:
    lock = lock or root / "scorer" / "ruleset.lock"
    version, digest = fingerprint(root)
    if lock.exists():
        recorded = json.loads(lock.read_text(encoding="utf-8"))
        if digest != recorded["fingerprint"] and version <= recorded["ruleset_version"]:
            raise SystemExit(f"Something changed since version {recorded['ruleset_version']}: "
                             "raise ruleset_version in config/scoring.yaml first.")
    lock.write_text(json.dumps({"ruleset_version": version, "fingerprint": digest}, indent=2) + "\n", encoding="utf-8")
    return f"recorded ruleset_version {version}"


def main() -> int:
    if "--update" in sys.argv[1:]:
        print(update())
        return 0
    problem = check()
    print(problem or f"ruleset_version {fingerprint()[0]} matches the rules and settings")
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
