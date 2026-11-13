"""--usage (D-050): measured token use from local Claude Code transcripts; offline, counts only."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HINT = "graphify: knowledge graph at graphify-out/. Prefer graphify query over grep."


def _usage(i, o, cr, cw):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}


def _assistant(mid, blocks, usage):
    return {"type": "assistant", "message": {"id": mid, "role": "assistant", "content": blocks, "usage": usage}}


def _tool_use(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def _result(tid, content):
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": content}]},
    }


def _hook(event, name, text):
    return {
        "type": "attachment",
        "attachment": {"type": "hook_additional_context", "hookEvent": event, "hookName": name, "content": [text]},
    }


def _session(path: Path) -> Path:
    u1 = _usage(10, 5, 100, 50)
    records = [
        # one API response written as two records (two content blocks): usage must count once
        _assistant("m1", [_tool_use("t1", "Read", file_path="/repo/a.py")], u1),
        _assistant("m1", [_tool_use("t2", "Bash", command="ls")], u1),
        _result("t1", "x" * 400),
        _result("t2", [{"type": "text", "text": "y" * 1000}]),
        _hook("PreToolUse", "PreToolUse:Bash", HINT),
        _hook("PreToolUse", "PreToolUse:Bash", HINT),
        _hook("PreToolUse", "PreToolUse:Bash", HINT),
        _assistant("m2", [_tool_use("t3", "Read", file_path="/repo/a.py")], _usage(1, 7, 300, 0)),
        _result("t3", "z" * 200),
        {
            "type": "attachment",
            "attachment": {
                "type": "deferred_tools_delta",
                "failedMcpServers": [{"name": "home-assistant", "errorCode": "AUTH"}],
            },
        },
        {"type": "system", "subtype": "compact_boundary"},
    ]
    lines = [json.dumps(r) for r in records] + ["{not json"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def test_totals_count_each_api_response_once(linter_module, tmp_path):
    data = linter_module.UsageAnalyzer().analyze([_session(tmp_path / "s.jsonl")])
    t = data["totals"]
    assert data["sessions"] == 1 and t["calls"] == 2
    assert (t["input"], t["output"], t["cache_read"], t["cache_write"]) == (11, 12, 400, 50)
    assert data["compactions"] == 1


def test_injected_context_is_ranked_by_total_size(linter_module, tmp_path):
    data = linter_module.UsageAnalyzer().analyze([_session(tmp_path / "s.jsonl")])
    top = data["injections"][0]
    assert top["hook"] == "PreToolUse:Bash" and top["count"] == 3
    assert top["tokens"] == 3 * (len(HINT) // 4)
    assert top["preview"].startswith("graphify")


def test_tool_outputs_repeated_reads_and_mcp_failures(linter_module, tmp_path):
    data = linter_module.UsageAnalyzer().analyze([_session(tmp_path / "s.jsonl")])
    tools = {t["tool"]: t for t in data["tools"]}
    assert tools["Bash"]["chars"] == 1000 and tools["Read"]["calls"] == 2
    assert data["repeated_reads"] == [{"path": "/repo/a.py", "count": 2}]
    assert data["mcp_failures"] == [{"server": "home-assistant", "sessions": 1}]


def test_sessions_are_found_by_project_slug_newest_first(linter_module, tmp_path):
    repo = tmp_path / "my.repo"
    repo.mkdir()
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    old = _session(tmp_path / "cfg" / "projects" / slug / "old.jsonl")
    new = _session(tmp_path / "cfg" / "projects" / slug / "new.jsonl")
    import os

    os.utime(old, (1, 1))
    found = linter_module.UsageAnalyzer.sessions_for(repo, tmp_path / "cfg", limit=1)
    assert found == [new]


def test_cli_usage_json_prints_counts_not_content(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))
    _session(tmp_path / "cfg" / "projects" / slug / "s.jsonl")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg")}
    cmd = [
        sys.executable,
        str(ROOT / "prism-ai-lint.py"),
        str(repo),
        "--usage",
        "--format",
        "json",
        "--no-update-check",
    ]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    data = json.loads(res.stdout)
    assert data["usage_schema_version"] == 1 and data["totals"]["calls"] == 2
    assert "yyyy" not in res.stdout and "zzzz" not in res.stdout  # tool output content never printed


def test_cli_usage_text_without_sessions_says_so(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_CONFIG_DIR": str(tmp_path / "cfg"), "NO_COLOR": "1"}
    cmd = [sys.executable, str(ROOT / "prism-ai-lint.py"), str(repo), "--usage", "--lang", "en", "--no-update-check"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0 and "no Claude Code session" in res.stdout
