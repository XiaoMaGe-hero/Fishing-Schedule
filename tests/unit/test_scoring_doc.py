"""docs/scoring-logic.md must describe the scoring that the code actually does.

Liang reads and edits that document to steer the scoring, so it is checked
against the code: same settings, same rules, same vetoes, same version.
"""
from __future__ import annotations

import re

import yaml

from scorer import engine

from conftest import ROOT

DOC = (ROOT / "docs" / "scoring-logic.md").read_text(encoding="utf-8")
SCORING = yaml.safe_load((ROOT / "config" / "scoring.yaml").read_text(encoding="utf-8"))


def test_settings_in_the_document_equal_scoring_yaml():
    block = re.search(r"<!-- scoring.yaml:start -->\s*```yaml\n(.*?)```\s*<!-- scoring.yaml:end -->", DOC, re.S)
    assert block, "the 'current settings' block is missing from docs/scoring-logic.md"
    assert yaml.safe_load(block.group(1)) == SCORING, \
        "docs/scoring-logic.md and config/scoring.yaml disagree - update whichever is behind"


def test_every_rule_and_veto_in_the_code_is_described_and_nothing_else():
    rules, vetoes = engine.load_rules()
    assert sorted(re.findall(r"^### 规则 `(\w+)`", DOC, re.M)) == sorted(r._rule_meta["name"] for r in rules)
    assert sorted(re.findall(r"^### 否决 `(\w+)`", DOC, re.M)) == sorted(v._veto_meta["name"] for v in vetoes)


def test_every_setting_name_is_mentioned_in_the_rule_descriptions():
    described = DOC.split("## 规则", 1)[1]
    for rule_name, settings in SCORING["rules"].items():
        for key in settings:
            assert f"`{key}`" in described, f"setting '{key}' of rule '{rule_name}' is not explained in the document"
    intro = DOC.split("## 当前参数", 1)[0]
    for key in SCORING["window"]:
        assert f"`{key}`" in intro, f"window setting '{key}' is not explained in the document"


def test_change_log_ends_at_the_current_version():
    log = DOC.split("## 修改记录", 1)[1]
    versions = [int(v) for v in re.findall(r"^\| (\d+) \|", log, re.M)]
    assert versions == sorted(versions) and versions[-1] == SCORING["ruleset_version"], \
        "add a line for the current ruleset_version to the change log in docs/scoring-logic.md"
