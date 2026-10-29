"""`Task(...)` permission rules and plugin marketplace pins: reports only, nothing is edited."""

from __future__ import annotations

from pathlib import Path

from prism_ai_lint.permission_rules_checker import PermissionRulesChecker
from prism_ai_lint.report import Report

P = Path("settings.json")


def _run(settings, base: Path):
    rep = Report()
    PermissionRulesChecker().check(settings, P, rep, base)
    return [(f.level, f.code) for f in rep.findings]


def _agent(base: Path, filename: str, name: str | None = None) -> None:
    folder = base / ".claude" / "agents"
    folder.mkdir(parents=True, exist_ok=True)
    body = f"---\nname: {name}\n---\nbody\n" if name else "body\n"
    (folder / filename).write_text(body, encoding="utf-8")


def test_known_agent_by_file_name_is_fine(tmp_path):
    _agent(tmp_path, "reviewer.md")
    assert _run({"permissions": {"deny": ["Task(reviewer)"]}}, tmp_path) == []


def test_known_agent_by_frontmatter_name_is_fine(tmp_path):
    _agent(tmp_path, "file.md", "Senior-Reviewer")
    assert _run({"permissions": {"deny": ["Task(senior-reviewer)"]}}, tmp_path) == []


def test_builtin_agent_is_fine(tmp_path):
    assert _run({"permissions": {"deny": ["Task(Explore)"]}}, tmp_path) == []


def test_agent_alias_rule_is_read_like_task(tmp_path):
    assert _run({"permissions": {"deny": ["Agent(ghost)"]}}, tmp_path) == [("info", "TASK_RULE_UNKNOWN_AGENT")]


def test_unknown_agent_is_reported_in_each_list(tmp_path):
    settings = {"permissions": {"allow": ["Task(ghost)"], "deny": ["Task(phantom)"]}}
    assert _run(settings, tmp_path) == [("info", "TASK_RULE_UNKNOWN_AGENT")] * 2


def test_bare_and_wildcard_task_rules_are_ignored(tmp_path):
    assert _run({"permissions": {"allow": ["Task", "Task(*)", "Bash(ls)"]}}, tmp_path) == []


def test_plugin_doubt_is_named_in_the_message(tmp_path):
    rep = Report()
    settings = {"permissions": {"deny": ["Task(ghost)"]}, "enabledPlugins": {"x@y": True}}
    PermissionRulesChecker().check(settings, P, rep, tmp_path)
    assert "plugin may provide" in rep.findings[0].message


def test_malformed_permissions_do_not_crash(tmp_path):
    assert _run({"permissions": {"deny": "Task(ghost)", "allow": [1, None]}}, tmp_path) == []
    assert _run(["not", "a", "dict"], tmp_path) == []


def test_unpinned_marketplace_is_reported(tmp_path):
    cfg = {"extraKnownMarketplaces": {"m": {"source": {"source": "github", "repo": "o/r"}}}}
    assert _run(cfg, tmp_path) == [("info", "PLUGIN_SOURCE_UNPINNED")]


def test_moving_branch_counts_as_unpinned(tmp_path):
    cfg = {"extraKnownMarketplaces": {"m": {"source": {"source": "git", "url": "https://h/r.git", "ref": "main"}}}}
    assert _run(cfg, tmp_path) == [("info", "PLUGIN_SOURCE_UNPINNED")]


def test_pinned_marketplace_and_local_directory_are_fine(tmp_path):
    cfg = {
        "extraKnownMarketplaces": {
            "pinned": {"source": {"source": "github", "repo": "o/r", "ref": "v1.2.3"}},
            "sha": {"source": {"source": "git", "url": "https://h/r.git", "sha": "a" * 40}},
            "local": {"source": {"source": "directory", "path": "./plugins"}},
        }
    }
    assert _run(cfg, tmp_path) == []
