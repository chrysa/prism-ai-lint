"""Codex, Gemini CLI, Cursor and headless CI checks: reports only, nothing is edited."""

from __future__ import annotations

import json
from pathlib import Path

from prism_ai_lint.other_tools_checker import OtherToolsChecker
from prism_ai_lint.report import Report


def _run(repo: Path):
    rep = Report()
    OtherToolsChecker().check_repo(repo, rep)
    return sorted((f.level, f.code) for f in rep.findings)


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_empty_repo_reports_nothing(tmp_path):
    assert _run(tmp_path) == []


def test_codex_open_sandbox_and_never_approval(tmp_path):
    _write(tmp_path, ".codex/config.toml", 'sandbox_mode = "danger-full-access"\napproval_policy = "never"\n')
    assert _run(tmp_path) == [("info", "CODEX_APPROVAL_NEVER"), ("warn", "CODEX_SANDBOX_OPEN")]


def test_codex_safe_config_and_broken_toml_are_quiet(tmp_path):
    _write(tmp_path, ".codex/config.toml", 'sandbox_mode = "workspace-write"\napproval_policy = "on-request"\n')
    assert _run(tmp_path) == []
    _write(tmp_path, ".codex/config.toml", "sandbox_mode = ")
    assert _run(tmp_path) == []


def test_gemini_auto_approve_trust_off_and_hooks(tmp_path):
    cfg = {"tools": {"autoAccept": True, "enableHooks": True}, "security": {"folderTrust": {"enabled": False}}}
    _write(tmp_path, ".gemini/settings.json", json.dumps(cfg))
    assert _run(tmp_path) == [
        ("info", "GEMINI_HOOKS_ON"),
        ("warn", "GEMINI_AUTO_APPROVE"),
        ("warn", "GEMINI_TRUST_OFF"),
    ]


def test_gemini_yolo_mode_is_auto_approve(tmp_path):
    _write(tmp_path, ".gemini/settings.json", json.dumps({"approvalMode": "yolo"}))
    assert _run(tmp_path) == [("warn", "GEMINI_AUTO_APPROVE")]


def test_gemini_default_trust_and_bad_json_are_quiet(tmp_path):
    _write(tmp_path, ".gemini/settings.json", json.dumps({"security": {"folderTrust": {"enabled": True}}}))
    assert _run(tmp_path) == []
    _write(tmp_path, ".gemini/settings.json", "{not json")
    assert _run(tmp_path) == []


def test_cursor_rule_without_frontmatter(tmp_path):
    _write(tmp_path, ".cursor/rules/a.mdc", "Just text, no frontmatter.\n")
    assert _run(tmp_path) == [("info", "CURSOR_RULE_NO_FRONTMATTER")]


def test_cursor_always_apply_large_rule(tmp_path):
    _write(tmp_path, ".cursor/rules/big.mdc", "---\nalwaysApply: true\n---\n" + "word " * 2500)
    assert _run(tmp_path) == [("info", "CURSOR_RULE_ALWAYS_LARGE")]


def test_cursor_small_or_scoped_rules_are_fine(tmp_path):
    _write(tmp_path, ".cursor/rules/small.mdc", "---\nalwaysApply: true\n---\nshort\n")
    _write(tmp_path, ".cursor/rules/scoped.mdc", "---\nalwaysApply: false\nglobs: src/**\n---\n" + "word " * 2500)
    assert _run(tmp_path) == []


def test_headless_skip_permissions_is_a_warning(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", "steps:\n  - run: claude -p 'fix' --dangerously-skip-permissions\n")
    assert _run(tmp_path) == [("warn", "HEADLESS_SKIP_PERMISSIONS")]


def test_headless_without_mode_is_a_hint(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", "steps:\n  - run: claude --print 'fix'\n")
    assert _run(tmp_path) == [("info", "HEADLESS_NO_PERMISSION_MODE")]


def test_headless_with_mode_or_allowed_tools_is_fine(tmp_path):
    _write(tmp_path, ".github/workflows/a.yml", "steps:\n  - run: claude -p 'x' --permission-mode acceptEdits\n")
    _write(tmp_path, ".github/workflows/b.yaml", "steps:\n  - run: claude -p 'x' --allowedTools 'Read'\n")
    assert _run(tmp_path) == []


def test_workflow_without_headless_claude_is_ignored(tmp_path):
    _write(tmp_path, ".github/workflows/ci.yml", "steps:\n  - run: pytest\n  - run: echo claude is nice\n")
    assert _run(tmp_path) == []
