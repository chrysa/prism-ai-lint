"""HOOK_CONTEXT_REPEATED / HOOK_DUPLICATE_SCOPE (D-049): context injected on every call, hooks running twice."""

from __future__ import annotations

import json

HINT = "graphify: knowledge graph at graphify-out/. Run graphify query before grepping raw files, it is cheaper."
INJECT = 'echo \'{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"' + HINT + "\"}}'"


def _settings(path, hooks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": hooks}))
    return path


def _group(event, command, matcher="Bash"):
    group = {"hooks": [{"type": "command", "command": command}]}
    if matcher is not None:
        group["matcher"] = matcher
    return {event: [group]}


def _run(m, repo, user):
    rep = m.Report()
    m.HookContextChecker().check_repo(repo, user, rep)
    return rep.findings


def test_inline_context_on_every_tool_call_is_reported_with_tokens(linter_module, tmp_path):
    _settings(tmp_path / ".claude" / "settings.json", _group("PreToolUse", INJECT))
    found = _run(linter_module, tmp_path, tmp_path / "user.json")
    assert [f.code for f in found] == ["HOOK_CONTEXT_REPEATED"]
    assert "PreToolUse" in found[0].message and "tokens" in found[0].message


def test_session_start_injection_is_fine(linter_module, tmp_path):
    _settings(tmp_path / ".claude" / "settings.json", _group("SessionStart", INJECT, matcher=None))
    assert _run(linter_module, tmp_path, tmp_path / "user.json") == []


def test_user_prompt_submit_stdout_is_context(linter_module, tmp_path):
    _settings(tmp_path / ".claude" / "settings.json", _group("UserPromptSubmit", "echo 'Reply terse.'", matcher=None))
    found = _run(linter_module, tmp_path, tmp_path / "user.json")
    assert [f.code for f in found] == ["HOOK_CONTEXT_REPEATED"]


def test_script_that_emits_additional_context_is_reported(linter_module, tmp_path):
    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "hint.js").write_text(
        "process.stdout.write(JSON.stringify({hookSpecificOutput:{additionalContext:'x'}}))\n"
    )
    _settings(
        tmp_path / ".claude" / "settings.json", _group("PostToolUse", "node .claude/hooks/hint.js", matcher="Edit")
    )
    found = _run(linter_module, tmp_path, tmp_path / "user.json")
    assert [f.code for f in found] == ["HOOK_CONTEXT_REPEATED"]


def test_blocking_hook_without_context_is_clean(linter_module, tmp_path):
    _settings(tmp_path / ".claude" / "settings.json", _group("PreToolUse", "python3 .claude/hooks/guard.py"))
    assert _run(linter_module, tmp_path, tmp_path / "user.json") == []


def test_same_hook_in_user_and_project_scope_runs_twice(linter_module, tmp_path):
    user = _settings(tmp_path / "home" / "settings.json", _group("PreToolUse", "rtk hook claude"))
    _settings(tmp_path / ".claude" / "settings.json", _group("PreToolUse", "rtk hook claude"))
    found = _run(linter_module, tmp_path, user)
    assert [f.code for f in found] == ["HOOK_DUPLICATE_SCOPE"]
    assert found[0].path.endswith(".claude/settings.json")


def test_duplicate_injecting_hook_reports_both_once(linter_module, tmp_path):
    user = _settings(tmp_path / "home" / "settings.json", _group("PreToolUse", INJECT))
    _settings(tmp_path / ".claude" / "settings.json", _group("PreToolUse", INJECT))
    codes = sorted(f.code for f in _run(linter_module, tmp_path, user))
    assert codes == ["HOOK_CONTEXT_REPEATED", "HOOK_DUPLICATE_SCOPE"]


def test_user_scope_injection_is_reported_by_check_user(linter_module, tmp_path):
    user = _settings(tmp_path / "home" / "settings.json", _group("UserPromptSubmit", INJECT, matcher=None))
    rep = linter_module.Report()
    linter_module.HookContextChecker().check_user(user, rep)
    assert [f.code for f in rep.findings] == ["HOOK_CONTEXT_REPEATED"]


def test_codes_have_an_action(linter_module, monkeypatch):
    monkeypatch.setattr(linter_module.state, "lang", "en")
    assert linter_module._action_for("HOOK_CONTEXT_REPEATED")
    assert linter_module._action_for("HOOK_DUPLICATE_SCOPE")
