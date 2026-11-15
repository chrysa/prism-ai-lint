"""SETTINGS_MISNAMED_KEY: a name the settings reference does not list, reported with the key that was meant."""

from __future__ import annotations

import copy
import json

import pytest

from prism_ai_lint import _engine
from prism_ai_lint import _reference as ref
from prism_ai_lint.report import Report


def _check(tmp_path, data):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps(data), encoding="utf-8")
    rep = Report()
    _engine.check_settings(settings, tmp_path, "project", copy.deepcopy(_engine.DEFAULT_POLICY), rep)
    return settings, rep.findings


@pytest.mark.parametrize("key", sorted(ref.MISNAMED_SETTINGS_KEYS))
def test_misnamed_key_is_a_warning_with_its_hint(tmp_path, key):
    _, findings = _check(tmp_path, {key: True})
    hits = [f for f in findings if f.code == "SETTINGS_MISNAMED_KEY"]
    assert [f.level for f in hits] == ["warn"]
    assert ref.MISNAMED_SETTINGS_KEYS[key] in hits[0].message
    assert not any(f.code == "SETTINGS_UNKNOWN_KEY" for f in findings)


def test_auto_compact_points_at_the_real_key(tmp_path):
    _, findings = _check(tmp_path, {"autoCompact": True})
    assert "autoCompactEnabled" in next(f.message for f in findings if f.code == "SETTINGS_MISNAMED_KEY")


def test_misnamed_key_is_never_rewritten(tmp_path):
    settings, _ = _check(tmp_path, {"autoCompact": True, "autoCompactThreshold": 0.85})
    assert list(json.loads(settings.read_text(encoding="utf-8"))) == ["autoCompact", "autoCompactThreshold"]


def test_real_key_is_not_reported(tmp_path):
    _, findings = _check(tmp_path, {"autoCompactEnabled": True})
    assert not any(f.code in ("SETTINGS_MISNAMED_KEY", "SETTINGS_UNKNOWN_KEY") for f in findings)


def test_misnamed_names_are_not_known_keys():
    assert not set(ref.MISNAMED_SETTINGS_KEYS) & ref.KNOWN_SETTINGS_KEYS
