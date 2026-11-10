"""Model per task (D-047): judgment subagents off Haiku, mechanical ones on it, no legacy model ids."""

from __future__ import annotations

import json
import subprocess


def _agent(d, name, description, model=None, tools="Read, Grep, Glob"):
    d.mkdir(parents=True, exist_ok=True)
    line = f"model: {model}\n" if model else ""
    (d / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {description}\ntools: {tools}\n{line}---\n\nBody.\n"
    )


def _settings(claude, model):
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "settings.json").write_text(json.dumps({"model": model}))


def test_legacy_ids_are_detected_by_generation(linter_module):
    status = linter_module.model_status
    assert status("claude-sonnet-4-5") == "legacy"
    assert status("claude-3-5-sonnet-20241022") == "legacy"
    assert status("claude-opus-4-1") == "legacy"
    assert status("claude-sonnet-5-5") == "current"
    assert status("claude-sonnet-6") == ""  # newer than the snapshot: not judged
    assert status("sonnet") == ""


def test_judgment_agents_are_not_called_mechanical(linter_module):
    c = linter_module.SubagentModelChecker
    assert c.is_mechanical("test-runner", "Runs the project's test and lint commands and summarizes failures")
    assert not c.is_mechanical("general-code-quality-debugger", "systematic code review, debugging, root cause, logs")
    assert not c.is_mechanical("general-qa", "quality assurance: test planning, edge cases, regression testing")
    assert not c.is_mechanical("security-auditor", "Audits code for secrets and injection; triage of findings")


def test_security_agent_inheriting_a_haiku_session_is_undersized(linter_module, tmp_path):
    m = linter_module
    claude = tmp_path / ".claude"
    _settings(claude, "haiku")
    _agent(claude / "agents", "security-auditor", "Audits code and configuration for secrets")
    _agent(claude / "agents", "code-reviewer", "Reviews code changes", model="sonnet")
    _agent(claude / "agents", "test-runner", "Runs tests and summarizes failures", model="haiku")
    rep = m.Report()
    m.SubagentModelChecker().check_dir(claude, m.SubagentModelChecker.session_model([claude / "settings.json"]), rep)
    hits = [(f.code, f.path.rsplit("/", 1)[-1]) for f in rep.findings]
    assert hits == [("SUBAGENT_MODEL_UNDERSIZED", "security-auditor.md")]


def test_pinned_haiku_reviewer_is_undersized(linter_module, tmp_path):
    m = linter_module
    claude = tmp_path / ".claude"
    _agent(claude / "agents", "code-reviewer", "Reviews code changes for correctness", model="haiku")
    rep = m.Report()
    m.SubagentModelChecker().check_dir(claude, "", rep)
    assert [f.code for f in rep.findings] == ["SUBAGENT_MODEL_UNDERSIZED"]


def test_legacy_model_pinned_in_a_skill_or_agent_is_reported(linter_module, tmp_path):
    m = linter_module
    claude = tmp_path / ".claude"
    skill = claude / "skills" / "idea-validation"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: idea-validation\ndescription: x\nmodel: claude-sonnet-4-5\n---\n\nBody.\n"
    )
    _agent(claude / "agents", "writer", "Writes docs", model="claude-opus-4-5")
    rep = m.Report()
    m.SubagentModelChecker().check_dir(claude, "", rep)
    assert sorted(f.code for f in rep.findings) == ["MODEL_LEGACY", "MODEL_LEGACY"]


def test_generated_review_agents_pin_sonnet(linter_module, tmp_path):
    m = linter_module
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')
    (tmp_path / "Makefile").write_text("test:\n\t@true\n")
    pol = m.load_policy(None, [tmp_path])
    rep = m.Report()
    m.generate_project(tmp_path, pol, rep)
    agents = {p.stem: rep.new_files[p][0] for p in rep.new_files if p.parent.name == "agents"}
    for name in ("code-reviewer", "security-auditor", "infra-reviewer"):
        assert "\nmodel: sonnet\n" in agents[name], name
    assert "\nmodel: haiku\n" in agents["test-runner"]


def test_new_code_has_an_action(linter_module, monkeypatch):
    monkeypatch.setattr(linter_module.state, "lang", "en")
    assert linter_module._action_for("SUBAGENT_MODEL_UNDERSIZED")
