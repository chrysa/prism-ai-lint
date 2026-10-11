"""Settings keys, permission modes and effort scale follow the Claude Code docs."""

from prism_ai_lint._engine import _effort_rank
from prism_ai_lint._reference import KNOWN_SETTINGS_KEYS, PERMISSION_MODES


def test_documented_keys_are_known():
    for key in ("deniedModels", "disableAutoMode", "classifyAllShell", "promptCacheTtl", "plansDirectory"):
        assert key in KNOWN_SETTINGS_KEYS


def test_permission_modes_complete():
    assert {"auto", "dontAsk", "plan", "acceptEdits", "default", "bypassPermissions"} == PERMISSION_MODES


def test_effort_scale_includes_xhigh_and_max():
    order = ["low", "medium", "high", "xhigh", "max"]
    assert _effort_rank("xhigh", order) > _effort_rank("high", order)
    assert _effort_rank("max", order) > _effort_rank("xhigh", order)


def _modes(m, tmp_path, mode):
    rep = m.Report()
    out = m.optimize_permissions(
        {"defaultMode": mode}, m.load_policy(None, [tmp_path]), tmp_path / "s.json", rep, "user", False
    )
    return rep, out


def test_unknown_mode_is_flagged_not_rewritten(linter_module, tmp_path):
    rep, out = _modes(linter_module, tmp_path, "yolo")
    assert any(f.code == "PERM_MODE_UNKNOWN" for f in rep.findings)
    assert out["defaultMode"] == "yolo"


def test_documented_modes_are_not_flagged(linter_module, tmp_path):
    for mode in ("default", "acceptEdits", "auto", "plan", "dontAsk"):
        rep, _ = _modes(linter_module, tmp_path, mode)
        assert not any(f.code == "PERM_MODE_UNKNOWN" for f in rep.findings)


def test_prompt_skipping_keys_are_reported_not_removed(linter_module, tmp_path):
    m = linter_module
    path = tmp_path / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text('{"skipAutoPermissionPrompt": true}')
    rep = m.Report()
    out = m.check_settings(path, tmp_path, "user", m.load_policy(None, [tmp_path]), rep)
    assert any(f.code == "SETTINGS_SKIPS_PROMPT" for f in rep.findings)
    assert out["skipAutoPermissionPrompt"] is True
