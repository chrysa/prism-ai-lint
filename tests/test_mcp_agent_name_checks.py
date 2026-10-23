"""MCP reserved names and hidden whitespace; subagent names that are skipped at load. Reports only."""

from __future__ import annotations

from pathlib import Path

from prism_ai_lint.mcp_checker import McpChecker, hidden_whitespace
from prism_ai_lint.report import Report
from prism_ai_lint.secret_scan import InlineSecretScanner
from prism_ai_lint.skill_agent_checker import AGENT_NAME_MAX, SkillAgentChecker


def _mcp(servers):
    rep = Report()
    McpChecker(InlineSecretScanner()).check_servers(servers, Path(".mcp.json"), rep, "mcpServers", False)
    return {f.code for f in rep.findings}


def test_clean_server_has_neither_finding():
    codes = _mcp({"files": {"command": "echo", "args": ["a"]}})
    assert not codes & {"MCP_RESERVED_NAME", "MCP_WHITESPACE"}


def test_reserved_name_is_reported():
    assert "MCP_RESERVED_NAME" in _mcp({"claude-in-chrome": {"command": "echo"}})
    assert "MCP_RESERVED_NAME" in _mcp({"Workspace": {"command": "echo"}})


def test_hidden_whitespace_in_each_field():
    assert hidden_whitespace({"command": " echo"}) == ["command"]
    assert hidden_whitespace({"url": "https://x.io​"}) == ["url"]
    assert hidden_whitespace({"args": ["ok", "a "]}) == ["args[1]"]
    assert hidden_whitespace({"env": {"K": "v "}, "headers": {"A": "\tb"}}) == ["env.K", "headers.A"]
    assert hidden_whitespace({"command": "echo", "args": ["a b"], "env": {"K": "v"}}) == []
    assert "MCP_WHITESPACE" in _mcp({"s": {"command": "echo ", "args": ["x"]}})


def _agent(tmp_path, name):
    f = tmp_path / "a.md"
    f.write_text(f"---\nname: {name}\ndescription: does a thing\n---\nbody\n")
    rep = Report()
    checker = object.__new__(SkillAgentChecker)  # the constructor needs the instruction checker; this method does not
    checker.check_subagent(f, rep)
    return {f.code for f in rep.findings}


def test_agent_names_skipped_at_load(tmp_path):
    assert "AGENT_NAME_SKIPPED" in _agent(tmp_path, "-lead")
    assert "AGENT_NAME_SKIPPED" in _agent(tmp_path, "team:lead")
    assert "AGENT_NAME_SKIPPED" in _agent(tmp_path, "x" * (AGENT_NAME_MAX + 1))
    assert "AGENT_NAME_SKIPPED" not in _agent(tmp_path, "reviewer")
