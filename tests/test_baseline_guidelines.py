"""A scaffolded AGENTS.md carries a short working-style section; existing instruction files are never touched."""

from __future__ import annotations

import subprocess


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _scaffold(m, repo, **instructions):
    pol = m.load_policy(None, [repo])
    pol["instructions"].update(instructions)
    rep = m.Report()
    m.scaffold_project(repo, pol, rep)
    return rep


def test_new_agents_md_has_working_style(linter_module, tmp_path):
    rep = _scaffold(linter_module, _repo(tmp_path))
    text = rep.new_files[tmp_path / "AGENTS.md"][0]
    assert "## Working style" in text
    assert len(text.splitlines()) < 60


def test_switch_off(linter_module, tmp_path):
    rep = _scaffold(linter_module, _repo(tmp_path), baseline_guidelines=False)
    assert "Working style" not in rep.new_files[tmp_path / "AGENTS.md"][0]


def test_existing_instructions_are_left_alone(linter_module, tmp_path):
    repo = _repo(tmp_path)
    (repo / "CLAUDE.md").write_text("# mine\n")
    rep = _scaffold(linter_module, repo)
    assert repo / "AGENTS.md" not in rep.new_files
