"""Prompt-engineering hook: wiring, JSON stdin, and over-broad UserPromptSubmit matches. Reports only."""

from __future__ import annotations

import json

from prism_ai_lint.ape_hook_checker import ApeHookChecker
from prism_ai_lint.report import Report

JSON_HOOK = "import json, sys\nprompt = json.loads(sys.stdin.read()).get('prompt', '')\n"
RAW_HOOK = "import sys\nprompt = sys.stdin.read()\n"
WIRED = 'sh -c \'f="$CLAUDE_PROJECT_DIR/.claude/ape/ape_hook.py"; [ ! -f "$f" ] || python3 "$f"\''


def _repo(tmp_path, script=None, command=None):
    claude = tmp_path / ".claude"
    claude.mkdir()
    if script is not None:
        (claude / "ape").mkdir()
        (claude / "ape" / "ape_hook.py").write_text(script)
    if command is not None:
        settings = {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": command}]}]}}
        (claude / "settings.json").write_text(json.dumps(settings))
    return tmp_path


def _codes(repo):
    rep = Report()
    ApeHookChecker().check_repo(repo, rep)
    return {(f.level, f.code) for f in rep.findings}


def test_wired_json_hook_is_clean(tmp_path):
    assert _codes(_repo(tmp_path, JSON_HOOK, WIRED)) == set()


def test_script_without_wiring(tmp_path):
    assert _codes(_repo(tmp_path, JSON_HOOK)) == {("info", "APE_UNWIRED")}


def test_wiring_without_script(tmp_path):
    assert _codes(_repo(tmp_path, None, WIRED)) == {("info", "APE_DEAD_WIRING")}


def test_raw_stdin_hook_warns(tmp_path):
    assert _codes(_repo(tmp_path, RAW_HOOK, WIRED)) == {("warn", "APE_STDIN_RAW")}


def test_broad_substring_match(tmp_path):
    command = 'sh -c \'in=$(cat); case "$in" in *"/ape"*) cat spec.md;; esac\''
    assert _codes(_repo(tmp_path, None, command)) == {("info", "HOOK_BROAD_MATCH")}


def test_hook_that_anchors_on_the_prompt_is_not_broad(tmp_path):
    assert _codes(_repo(tmp_path, None, "sh ~/hooks/ape-opt-in.sh")) == set()


def test_repo_without_claude_dir_is_quiet(tmp_path):
    assert _codes(tmp_path) == set()
