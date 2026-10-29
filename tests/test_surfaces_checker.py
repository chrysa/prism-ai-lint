"""Per-surface checks (Claude Code extension and action, agent CLIs, Codex config): reports only."""

from __future__ import annotations

import json
from pathlib import Path

from prism_ai_lint.report import Report
from prism_ai_lint.surfaces_checker import SurfacesChecker

SHA = "a" * 40


def _run(repo: Path):
    rep = Report()
    SurfacesChecker().check_repo(repo, rep)
    return sorted((f.level, f.code) for f in rep.findings), rep


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_empty_repo_reports_nothing(tmp_path):
    assert _run(tmp_path)[0] == []


def test_vscode_bypass_setting_is_a_warning(tmp_path):
    _write(tmp_path, ".vscode/settings.json", '// c\n{"claudeCode.initialPermissionMode": "bypassPermissions"}')
    assert _run(tmp_path)[0] == [("warn", "VSCODE_CLAUDE_BYPASS")]
    _write(tmp_path, ".vscode/settings.json", json.dumps({"claudeCode.allowDangerouslySkipPermissions": True}))
    assert _run(tmp_path)[0] == [("warn", "VSCODE_CLAUDE_BYPASS")]


def test_vscode_default_and_broken_json_are_quiet(tmp_path):
    _write(tmp_path, ".vscode/settings.json", json.dumps({"claudeCode.initialPermissionMode": "default"}))
    assert _run(tmp_path)[0] == []
    _write(tmp_path, ".vscode/settings.json", "{oops")
    assert _run(tmp_path)[0] == []


def test_action_unpinned_open_users_and_skip(tmp_path):
    wf = (
        "steps:\n  - uses: anthropics/claude-code-action@v1\n    with:\n"
        "      allowed_non_write_users: '*'\n      claude_args: --dangerously-skip-permissions\n"
    )
    _write(tmp_path, ".github/workflows/c.yml", wf)
    assert _run(tmp_path)[0] == [
        ("info", "CLAUDE_ACTION_UNPINNED"),
        ("warn", "CLAUDE_ACTION_OPEN_USERS"),
        ("warn", "HEADLESS_SKIP_PERMISSIONS"),
    ]


def test_action_pinned_to_a_commit_is_fine(tmp_path):
    _write(tmp_path, ".github/workflows/c.yml", f"steps:\n  - uses: anthropics/claude-code-action@{SHA} # v1\n")
    assert _run(tmp_path)[0] == []


def test_codex_action_is_read_like_the_claude_one(tmp_path):
    _write(tmp_path, ".github/workflows/c.yml", "steps:\n  - uses: openai/codex-action@main\n")
    assert _run(tmp_path)[0] == [("info", "CLAUDE_ACTION_UNPINNED")]


def test_package_json_moving_cli_version(tmp_path):
    pkg = {"devDependencies": {"@anthropic-ai/claude-code": "latest", "@openai/codex": "0.5.0"}}
    _write(tmp_path, "package.json", json.dumps(pkg))
    assert _run(tmp_path)[0] == [("info", "AGENT_CLI_UNPINNED")]


def test_install_script_without_a_pinned_version(tmp_path):
    _write(tmp_path, "Dockerfile", "RUN npm install -g @anthropic-ai/claude-code\n")
    assert _run(tmp_path)[0] == [("info", "AGENT_CLI_UNPINNED")]
    _write(tmp_path, "Dockerfile", "RUN npm install -g @anthropic-ai/claude-code@2.1.300 @openai/codex@0.5.0\n")
    assert _run(tmp_path)[0] == []


def test_install_script_with_latest_tag_is_unpinned(tmp_path):
    _write(tmp_path, "Makefile", "setup:\n\tnpm i -g @openai/codex@latest\n")
    assert _run(tmp_path)[0] == [("info", "AGENT_CLI_UNPINNED")]


def test_codex_trust_on_a_broad_directory(tmp_path):
    _write(
        tmp_path,
        ".codex/config.toml",
        '[projects."/"]\ntrust_level = "trusted"\n[projects."/work/app"]\ntrust_level = "trusted"\n',
    )
    assert _run(tmp_path)[0] == [("warn", "CODEX_TRUST_BROAD")]


def test_codex_literal_mcp_secret_is_reported_without_its_value(tmp_path):
    cfg = '[mcp_servers.x]\ncommand = "x"\n[mcp_servers.x.env]\nAPI_TOKEN = "literal-credential-1234"\nMODE = "fast"\n'
    _write(tmp_path, ".codex/config.toml", cfg)
    found, rep = _run(tmp_path)
    assert found == [("warn", "CODEX_MCP_LITERAL_SECRET")]
    assert "literal-credential" not in rep.findings[0].message


def test_codex_mcp_secret_read_from_the_environment_is_fine(tmp_path):
    cfg = '[mcp_servers.x.env]\nAPI_TOKEN = "$API_TOKEN"\n[mcp_servers.x]\nbearer_token_env_var = "X_TOKEN"\n'
    _write(tmp_path, ".codex/config.toml", cfg)
    assert _run(tmp_path)[0] == []
