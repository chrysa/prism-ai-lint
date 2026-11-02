"""Codex configuration checks: config.toml, hooks, rules, custom agents, skills, AGENTS.md."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _w(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def lint(linter_module, tmp_path):
    """Run the Codex project checks on a fresh repo; returns (repo, run) where run() gives findings."""
    m = linter_module
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    def run(user: bool = False):
        policy = m.load_policy(None, [repo])
        rep = m.Report()
        if user:
            m._CODEX.check_user(policy, rep)
        else:
            m._CODEX.check_repo(repo, policy, rep)
        return rep.findings

    return repo, run


def codes(findings) -> set[str]:
    return {f.code for f in findings}


def test_full_access_without_approval_is_an_error(lint):
    repo, run = lint
    _w(repo / ".codex/config.toml", 'sandbox_mode = "danger-full-access"\napproval_policy = "never"\n')
    found = run()
    assert "CODEX_NO_GUARDRAILS" in codes(found)
    assert next(f for f in found if f.code == "CODEX_NO_GUARDRAILS").level == "error"


def test_full_access_alone_warns(lint):
    repo, run = lint
    _w(repo / ".codex/config.toml", 'sandbox_mode = "danger-full-access"\n')
    assert codes(run()) >= {"CODEX_SANDBOX_FULL_ACCESS"}


def test_safe_config_has_no_findings(lint):
    repo, run = lint
    _w(
        repo / ".codex/config.toml",
        'sandbox_mode = "workspace-write"\napproval_policy = "on-request"\nmodel_reasoning_effort = "medium"\n',
    )
    assert not run()


def test_keys_unknown_deprecated_and_project_ignored(lint):
    repo, run = lint
    _w(
        repo / ".codex/config.toml",
        'sandbox_mod = "read-only"\nexperimental_instructions_file = "x"\nnotify = ["say"]\n'
        "[features]\ncodex_hooks = true\n",
    )
    found = run()
    assert codes(found) >= {"CODEX_UNKNOWN_KEY", "CODEX_DEPRECATED_KEY", "CODEX_PROJECT_IGNORED"}
    unknown = next(f for f in found if f.code == "CODEX_UNKNOWN_KEY")
    assert "sandbox_mode" in unknown.message  # suggestion
    assert any("features.codex_hooks" in f.message for f in found)


def test_extra_keys_policy_silences_unknown_key(linter_module, lint):
    repo, _ = lint
    _w(repo / ".codex/config.toml", "brand_new_key = 1\n")
    _w(repo / ".prism-ai-lint.toml", '[codex]\nextra_keys = ["brand_new_key"]\n')
    policy = linter_module.load_policy(None, [repo])
    rep = linter_module.Report()
    linter_module._CODEX.check_repo(repo, policy, rep)
    assert "CODEX_UNKNOWN_KEY" not in codes(rep.findings)


@pytest.mark.parametrize(
    ("line", "code"),
    [
        ('approval_policy = "on-failure"', "CODEX_APPROVAL_DEPRECATED"),
        ('approval_policy = "untrusted"', "CODEX_APPROVAL_INVALID"),
        ("approval_policy = { other = 1 }", "CODEX_APPROVAL_INVALID"),
        ('sandbox_mode = "yolo"', "CODEX_SANDBOX_INVALID"),
        ('default_permissions = ":workspace"\nsandbox_mode = "read-only"', "CODEX_PERMISSIONS_CONFLICT"),
        ("[sandbox_workspace_write]\nnetwork_access = true", "CODEX_NETWORK_OPEN"),
        ('[permissions.p]\nextends = ":danger-full-access"', "CODEX_PERMISSION_INVALID"),
        ('[permissions.p]\nextends = ":nope"', "CODEX_PERMISSION_INVALID"),
        ("[permissions.p.network]\ndangerously_allow_all_unix_sockets = true", "CODEX_PERMISSION_DANGEROUS"),
        ('[projects."/x"]\ntrust_level = "maybe"', "CODEX_TRUST_INVALID"),
        ('[shell_environment_policy]\nfilters = [{ include = "X" }]\nexclude = ["Y"]', "CODEX_SHELL_ENV_MIXED"),
        ('model_reasoning_effort = "xhigh"', "CODEX_EFFORT_HIGH"),
        ('[agents]\ndefault_subagent_reasoning_effort = "max"', "CODEX_EFFORT_HIGH"),
        ("[features]\nhooks = false", "CODEX_HOOKS_DISABLED"),
        ("sandbox_mode = [", "CODEX_TOML_INVALID"),
    ],
)
def test_config_value_checks(lint, line, code):
    repo, run = lint
    _w(repo / ".codex/config.toml", line + "\n")
    assert code in codes(run())


def test_mcp_servers(lint):
    repo, run = lint
    _w(
        repo / ".codex/config.toml",
        "[mcp_servers.empty]\nenabled = true\n"
        '[mcp_servers.typo]\nurl = "https://example.invalid/mcp"\nbearer_token = "x"\n'
        '[mcp_servers.gone]\ncommand = "definitely-not-a-real-binary-xyz"\n',
    )
    found = codes(run())
    assert {"CODEX_MCP_SHAPE", "CODEX_MCP_UNKNOWN_FIELD", "CODEX_MCP_BROKEN"} <= found


def test_mcp_literal_secret_reported_not_rewritten(lint):
    repo, run = lint
    token = "ghp_" + "Zx9" * 12
    cfg = _w(repo / ".codex/config.toml", f'[mcp_servers.gh]\ncommand = "true"\nenv = {{ GITHUB_TOKEN = "{token}" }}\n')
    before = cfg.read_text()
    assert "SECRET_INLINE" in codes(run())
    assert cfg.read_text() == before  # report only: TOML is never rewritten


def test_mcp_many(lint):
    repo, run = lint
    servers = "".join(f'[mcp_servers.s{i}]\nurl = "https://example.invalid/{i}"\n' for i in range(8))
    _w(repo / ".codex/config.toml", servers + '[mcp_servers.off]\nurl = "https://x.invalid"\nenabled = false\n')
    assert "CODEX_MCP_MANY" in codes(run())


def test_hooks_json_checks(lint):
    repo, run = lint
    _w(
        repo / ".codex/hooks.json",
        json.dumps(
            {
                "hooks": {
                    "Notification": [{"hooks": [{"type": "command", "command": "x"}]}],
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "prompt"}]},
                        {"hooks": [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/h.sh'}]},
                        {"hooks": [{"type": "command", "command": "python3 .codex/hooks/x.py"}]},
                        {"hooks": [{"type": "http", "url": "https://x.invalid"}]},
                        {"hooks": "nope"},
                    ],
                    "SessionEnd": [{"hooks": [{"type": "command", "command": "true", "timeout": 10}]}],
                }
            }
        ),
    )
    found = codes(run())
    assert {
        "CODEX_HOOK_EVENT",
        "CODEX_HOOK_SKIPPED",
        "CODEX_HOOK_CLAUDE_VAR",
        "CODEX_HOOK_RELATIVE",
        "CODEX_HOOK_TYPE",
        "CODEX_HOOK_SHAPE",
        "CODEX_HOOK_TIMEOUT",
    } <= found


def test_hooks_in_both_forms_warn(lint):
    repo, run = lint
    _w(repo / ".codex/hooks.json", json.dumps({"hooks": {}}))
    _w(
        repo / ".codex/config.toml",
        '[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ntype = "command"\ncommand = "true"\n',
    )
    assert "CODEX_HOOKS_DUAL" in codes(run())


def test_invalid_hooks_json(lint):
    repo, run = lint
    _w(repo / ".codex/hooks.json", "{nope")
    assert "CODEX_HOOK_SHAPE" in codes(run())


def test_rules_checks(lint):
    repo, run = lint
    _w(
        repo / ".codex/rules/default.rules",
        'prefix_rule(pattern = ["git", "push"])\n'
        'prefix_rule(pattern = ["bash"], decision = "allow")\n'
        'prefix_rule(pattern = ["npx"], decision = "allow")\n'
        'prefix_rule(pattern = ["git", "status"], decision = "allow")\n'
        'prefix_rule(pattern = ["rm", "-rf"], decision = "forbidden")\n',
    )
    found = run()
    assert [f.code for f in found].count("CODEX_RULE_BROAD_ALLOW") == 2
    ext = [f for f in found if f.code == "CODEX_RULE_EXTERNAL_ALLOW"]
    assert len(ext) == 1 and "git push" in ext[0].message


def test_unreadable_rules(lint):
    repo, run = lint
    _w(repo / ".codex/rules/x.rules", "prefix_rule(pattern = computed())\n")
    assert "CODEX_RULES_INVALID" in codes(run())


def test_custom_agent_fields_and_sandbox(lint):
    repo, run = lint
    _w(repo / ".codex/agents/reviewer.toml", 'name = "reviewer"\nsandbox_mode = "danger-full-access"\n')
    _w(
        repo / ".codex/agents/ok.toml",
        'name = "ok"\ndescription = "d"\ndeveloper_instructions = "do it"\nnickname_candidates = ["o"]\n',
    )
    found = run()
    field = [f for f in found if f.code == "CODEX_AGENT_FIELD"]
    assert len(field) == 1 and "description" in field[0].message and "developer_instructions" in field[0].message
    assert "CODEX_SANDBOX_FULL_ACCESS" in codes(found)
    assert "CODEX_UNKNOWN_KEY" not in codes(found)  # agent fields are not config keys


def test_agents_skill_fields(lint):
    repo, run = lint
    _w(repo / ".agents/skills/bad/SKILL.md", "---\nname: bad\n---\nbody\n")
    _w(repo / ".agents/skills/good/SKILL.md", "---\nname: good\ndescription: does good\n---\nbody\n")
    found = [f for f in run() if f.code == "CODEX_SKILL_FIELD"]
    assert len(found) == 1 and "bad" in found[0].path


def test_override_shadows_agents_md(lint):
    repo, run = lint
    _w(repo / "AGENTS.md", "- shared\n")
    _w(repo / "AGENTS.override.md", "- override\n")
    assert "CODEX_OVERRIDE_SHADOW" in codes(run())


def test_doc_size_uses_project_doc_max_bytes(lint):
    repo, run = lint
    _w(repo / ".codex/config.toml", "project_doc_max_bytes = 100\n")
    _w(repo / "AGENTS.md", "- rule\n" * 40)
    assert "CODEX_DOC_TRUNCATED" in codes(run())


def test_doc_size_default_limit_not_hit(lint):
    repo, run = lint
    (repo / ".codex").mkdir()
    _w(repo / "AGENTS.md", "- rule\n" * 40)
    assert "CODEX_DOC_TRUNCATED" not in codes(run())


def test_plain_repo_without_codex_has_no_codex_findings(lint):
    repo, run = lint
    _w(repo / "AGENTS.md", "- rule\n" * 10000)  # large, but nothing says Codex is used here
    assert not run()


def test_user_scope_reads_codex_home(lint, monkeypatch, tmp_path):
    _, run = lint
    home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(home))
    _w(home / "config.toml", 'approval_policy = "never"\nsandbox_mode = "danger-full-access"\nnotify = ["x"]\n')
    _w(home / "AGENTS.md", "x" * 40000)
    found = codes(run(user=True))
    assert {"CODEX_NO_GUARDRAILS", "CODEX_DOC_TRUNCATED"} <= found
    assert "CODEX_PROJECT_IGNORED" not in found  # notify is valid at user scope


def test_codex_disabled_by_policy(linter_module, tmp_path):
    m = linter_module
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _w(repo / ".codex/config.toml", 'sandbox_mode = "danger-full-access"\napproval_policy = "never"\n')
    _w(repo / ".prism-ai-lint.toml", "[codex]\nenabled = false\n")
    policy = m.load_policy(None, [repo])
    rep = m.Report()
    m.lint_repo(repo, policy, rep, history=False, user_text=None)
    assert not any(f.code.startswith("CODEX_") for f in rep.findings)


def test_lint_repo_runs_codex_checks(linter_module, tmp_path):
    m = linter_module
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    _w(repo / ".codex/config.toml", 'sandbox_mode = "danger-full-access"\napproval_policy = "never"\n')
    policy = m.load_policy(None, [repo])
    rep = m.Report()
    m.lint_repo(repo, policy, rep, history=False, user_text=None)
    assert "CODEX_NO_GUARDRAILS" in codes(rep.findings)
    assert m.category("CODEX_NO_GUARDRAILS") == "codex"


def test_every_codex_and_align_code_has_a_hint(linter_module):
    import re

    m = linter_module
    root = Path(m.__file__).parent
    emitted = set()
    for name in ("codex_checker.py", "agent_aligner.py"):
        emitted |= set(re.findall(r'"((?:CODEX|ALIGN)_[A-Z_]+)"', (root / name).read_text()))
    emitted.discard("CODEX_HOME")  # the environment variable, not a finding code
    assert emitted, "no codes found"
    assert not emitted - set(m.HINTS)
    assert not {c for c in emitted if c.startswith("ALIGN_")} - set(m.BRIEF_EN) - set(m.BRIEF_FR)
    assert set(m.BRIEF_EN) & emitted == set(m.BRIEF_FR) & emitted


@pytest.mark.parametrize(
    "text",
    [
        'prefix_rule(pattern = ["rm"], decision = [])\n',
        "prefix_rule(pattern = " + "1+" * 3000 + "1)\n",
        'def _keep():\n    prefix_rule(pattern = ["rm"], decision = "forbidden")\n',
    ],
)
def test_crafted_rules_are_reported_not_crashing(lint, text):
    repo, run = lint
    _w(repo / ".codex/rules/x.rules", text)
    assert "CODEX_RULES_INVALID" in codes(run())
