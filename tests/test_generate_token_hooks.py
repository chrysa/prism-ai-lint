"""--generate adds a Read size guard (PreToolUse) and a PreCompact snapshot hook; both fail open."""

from __future__ import annotations

import json
import subprocess
import sys


def _gen(m, repo, **gen):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    pol = m.load_policy(None, [repo])
    pol["generate"].update(gen)
    rep = m.Report()
    m.generate_project(repo, pol, rep)
    return rep


def _settings(rep, repo):
    return json.loads(rep.new_files[repo / ".claude" / "settings.json"][0])


def test_hooks_generated_by_default(linter_module, tmp_path):
    rep = _gen(linter_module, tmp_path)
    hooks = _settings(rep, tmp_path)["hooks"]
    assert hooks["PreToolUse"][0]["matcher"] == "Read"
    assert "PreCompact" in hooks
    assert tmp_path / ".claude" / "hooks" / "read_guard.py" in rep.new_files
    assert tmp_path / ".claude" / "hooks" / "pre-compact.sh" in rep.new_files


def test_hooks_can_be_disabled(linter_module, tmp_path):
    rep = _gen(linter_module, tmp_path, read_guard_hook=False, compact_hook=False)
    hooks = _settings(rep, tmp_path).get("hooks", {})
    assert "PreToolUse" not in hooks and "PreCompact" not in hooks


def test_bad_limit_falls_back(linter_module, tmp_path):
    rep = _gen(linter_module, tmp_path, read_guard_kb="9; rm -rf /")
    script = rep.new_files[tmp_path / ".claude" / "hooks" / "read_guard.py"][0]
    assert "LIMIT_KB = 256" in script


def _run(script, payload):
    return subprocess.run(
        [sys.executable, "-I", str(script)], input=json.dumps(payload), text=True, capture_output=True
    )


def test_guard_blocks_big_whole_read_only(linter_module, tmp_path):
    script = tmp_path / "g.py"
    script.write_text(linter_module.READ_GUARD_HOOK.replace("__LIMIT_KB__", "16"))
    big = tmp_path / "big.txt"
    big.write_text("x" * 40_000)
    assert _run(script, {"tool_input": {"file_path": str(big)}}).returncode == 2
    assert _run(script, {"tool_input": {"file_path": str(big), "limit": 50}}).returncode == 0
    assert _run(script, {"tool_input": {"file_path": str(tmp_path / "missing")}}).returncode == 0
    assert subprocess.run([sys.executable, "-I", str(script)], input="not json", text=True).returncode == 0
