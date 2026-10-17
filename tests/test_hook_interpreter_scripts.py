"""Hooks run through an interpreter (node x.cjs, command bash + args) are checked for a missing script."""

from __future__ import annotations

from prism_ai_lint.hook_checker import HookChecker
from prism_ai_lint.report import Report


def _check(tmp_path, handler, scope="project"):
    rep = Report()
    hooks = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "timeout": 5, **handler}]}]}
    fixed = HookChecker(check_env_secrets=lambda m, p, r, c: m).check_hooks(
        hooks, tmp_path, tmp_path / "settings.json", rep, scope
    )
    return rep, fixed


def _codes(rep):
    return {(f.level, f.code) for f in rep.findings}


def test_node_hook_with_missing_script_is_an_error(tmp_path):
    rep, _ = _check(tmp_path, {"command": "node .claude/hooks/secret-scanner.cjs"})
    assert ("error", "HOOK_MISSING_SCRIPT") in _codes(rep)


def test_node_hook_with_existing_script_is_clean_and_needs_no_exec_bit(tmp_path):
    script = tmp_path / ".claude" / "hooks" / "scan.cjs"
    script.parent.mkdir(parents=True)
    script.write_text("process.exit(0)\n")
    script.chmod(0o644)
    rep, _ = _check(tmp_path, {"command": "node .claude/hooks/scan.cjs"})
    assert ("error", "HOOK_MISSING_SCRIPT") not in _codes(rep)
    assert ("warn", "HOOK_NOT_EXECUTABLE") not in _codes(rep)


def test_relative_node_script_is_anchored_in_exec_form(tmp_path):
    script = tmp_path / ".claude" / "hooks" / "scan.cjs"
    script.parent.mkdir(parents=True)
    script.write_text("process.exit(0)\n")
    rep, fixed = _check(tmp_path, {"command": "node .claude/hooks/scan.cjs"})
    handler = fixed["PreToolUse"][0]["hooks"][0]
    assert handler["command"] == "node"
    assert handler["args"] == ["${CLAUDE_PROJECT_DIR}/.claude/hooks/scan.cjs"]
    assert ("warn", "HOOK_RELATIVE_PATH") in _codes(rep)


def test_exec_form_bash_with_missing_script_in_args(tmp_path):
    rep, _ = _check(tmp_path, {"command": "bash", "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/gone.sh"]})
    assert ("error", "HOOK_MISSING_SCRIPT") in _codes(rep)


def test_inline_code_has_no_script_to_check(tmp_path):
    rep, _ = _check(tmp_path, {"command": "node", "args": ["-e", "process.exit(0)"]})
    assert ("error", "HOOK_MISSING_SCRIPT") not in _codes(rep)
