"""Hook fields from the docs are validated; a gating hook without onFailure is reported; SessionStart context is generated."""

from __future__ import annotations

import json
import subprocess


def _check(m, tmp_path, handler, script_body=None):
    claude = tmp_path / ".claude"
    (claude / "hooks").mkdir(parents=True)
    if script_body is not None:
        s = claude / "hooks" / "gate.sh"
        s.write_text(script_body)
        s.chmod(0o755)
    path = claude / "settings.json"
    path.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [handler]}]}}))
    rep = m.Report()
    m.check_settings(path, tmp_path, "project", m.load_policy(None, [tmp_path]), rep)
    return {f.code for f in rep.findings}


GATE = {"type": "command", "command": "bash", "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/gate.sh"], "timeout": 10}


def test_gating_hook_without_on_failure_is_reported(linter_module, tmp_path):
    assert "HOOK_FAIL_OPEN" in _check(linter_module, tmp_path, dict(GATE), "#!/bin/sh\nexit 2\n")


def test_on_failure_block_silences_it(linter_module, tmp_path):
    codes = _check(linter_module, tmp_path, {**GATE, "onFailure": "block"}, "#!/bin/sh\nexit 2\n")
    assert "HOOK_FAIL_OPEN" not in codes


def test_non_gating_hook_is_not_reported(linter_module, tmp_path):
    assert "HOOK_FAIL_OPEN" not in _check(linter_module, tmp_path, dict(GATE), "#!/bin/sh\nexit 0\n")


def test_bad_field_values_are_warned(linter_module, tmp_path):
    for i, bad in enumerate(({"onFailure": "allow"}, {"asyncRewake": "yes"}, {"statusMessage": 3})):
        assert "HOOK_FIELD_VALUE" in _check(linter_module, tmp_path / str(i), {**GATE, **bad}, "#!/bin/sh\n")


def test_good_field_values_are_not_warned(linter_module, tmp_path):
    good = {"onFailure": "block", "asyncRewake": True, "continueOnBlock": False, "statusMessage": "checking"}
    assert "HOOK_FIELD_VALUE" not in _check(linter_module, tmp_path, {**GATE, **good}, "#!/bin/sh\n")


def test_installed_guard_hook_fails_closed(linter_module, tmp_path):
    m = linter_module
    handler = m.session_settings(m.load_policy(None, [tmp_path]))["hooks"]["PreToolUse"][0]["hooks"][0]
    assert handler["onFailure"] == "block"


def test_session_context_hook_generated_in_git_repo(linter_module, tmp_path):
    m = linter_module
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    rep = m.Report()
    m.generate_project(tmp_path, m.load_policy(None, [tmp_path]), rep)
    settings = json.loads(rep.new_files[tmp_path / ".claude" / "settings.json"][0])
    assert "SessionStart" in settings["hooks"]
    script = rep.new_files[tmp_path / ".claude" / "hooks" / "session-context.sh"][0]
    assert script.startswith("#!/usr/bin/env bash") and "exit 0" in script
