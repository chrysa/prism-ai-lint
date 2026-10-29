"""The docs snapshot: its date, the removed-key table and the settings keys added since the last check."""

from __future__ import annotations

import copy

from prism_ai_lint import _reference as ref
from prism_ai_lint.report import Report


def test_snapshot_date_is_a_single_constant():
    assert ref.DOCS_SNAPSHOT == "2026-10"


def test_dialog_expiry_is_a_known_key():
    assert "dialogExpiry" in ref.KNOWN_SETTINGS_KEYS


def test_removed_key_is_reported_by_a_settings_check(tmp_path):
    from prism_ai_lint import _engine

    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"teammateDefaultModel": "haiku"}\n', encoding="utf-8")
    rep = Report()
    _engine.check_settings(settings, tmp_path, "project", copy.deepcopy(_engine.DEFAULT_POLICY), rep)
    codes = {(f.level, f.code) for f in rep.findings}
    assert ("info", "SETTINGS_REMOVED_KEY") in codes
    assert not any(c == "SETTINGS_UNKNOWN_KEY" for _, c in codes)


def test_current_key_is_not_reported_as_removed(tmp_path):
    from prism_ai_lint import _engine

    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"dialogExpiry": 30}\n', encoding="utf-8")
    rep = Report()
    _engine.check_settings(settings, tmp_path, "project", copy.deepcopy(_engine.DEFAULT_POLICY), rep)
    assert not any(f.code in ("SETTINGS_REMOVED_KEY", "SETTINGS_UNKNOWN_KEY") for f in rep.findings)
