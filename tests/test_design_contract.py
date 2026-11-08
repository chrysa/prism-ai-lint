"""Optional DESIGN.md contracts: discovery, budget, imports, links, wiring; never required, never edited."""

from __future__ import annotations

import json
import os
import subprocess

import pytest

DESIGN_CODES = {"DESIGN_LONG", "DESIGN_UNREFERENCED", "DESIGN_ALWAYS_LOADED", "DESIGN_EXTERNAL", "DESIGN_DEAD_LINK"}


def _lint(m, repo, monkeypatch, scaffold=False):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(repo.parent / "user-config"))
    monkeypatch.setattr(m.state, "scaffold", scaffold)
    rep = m.Report()
    m.lint_repo(repo, m.load_policy(None, [repo]), rep, False, None)
    return rep


def _codes_for(rep, path):
    return {f.code for f in rep.findings if f.path == str(path)}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    return root


def test_absent_contract_is_not_a_finding(linter_module, repo, monkeypatch):
    _write(repo / "CLAUDE.md", "# Project\n")
    rep = _lint(linter_module, repo, monkeypatch)
    assert not DESIGN_CODES & {f.code for f in rep.findings}
    assert "design contracts" not in rep.stats


def test_imports_resolve_from_the_contract(linter_module, repo, monkeypatch):
    design = _write(repo / "DESIGN.md", "# Design\n@missing-tokens.md\n")
    _write(repo / "CLAUDE.md", "Before UI work read `DESIGN.md`.\n")
    rep = _lint(linter_module, repo, monkeypatch)
    assert "IMPORT_MISSING" in _codes_for(rep, design)


def test_on_demand_budget_replaces_the_always_loaded_one(linter_module, repo, monkeypatch):
    design = _write(repo / "DESIGN.md", "Long design rationale written as prose sentences here.\n" * 300)
    _write(repo / "AGENTS.md", "Read DESIGN.md before UI work.\n")
    codes = _codes_for(_lint(linter_module, repo, monkeypatch), design)
    # 300 lines is past the 200-line target of an always-loaded file, but within the contract budget,
    # and prose rationale is content: no style suggestion pushes it towards compression.
    assert not codes & {"INSTR_LONG", "DESIGN_LONG", "INSTR_PROSE", "INSTR_FILLER"}
    design.write_text("- Use semantic tokens.\n" * 500, encoding="utf-8")
    assert "DESIGN_LONG" in _codes_for(_lint(linter_module, repo, monkeypatch), design)


def test_nested_discovery_skips_dependency_build_and_hidden_trees(linter_module, repo, monkeypatch):
    for folder in ("frontend", "node_modules/dep", "dist", ".git/x", ".cache", "vendor/lib"):
        _write(repo / folder / "DESIGN.md", "@missing.md\n")
    found = linter_module.DESIGN_CONTRACTS.discover(repo)
    assert found == [repo / "frontend" / "DESIGN.md"]
    rep = _lint(linter_module, repo, monkeypatch)
    assert [f.path for f in rep.findings if f.code == "IMPORT_MISSING"] == [str(repo / "frontend/DESIGN.md")]


def test_git_ignored_contract_is_skipped(linter_module, repo):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _write(repo / ".gitignore", "generated/\n")
    _write(repo / "generated" / "DESIGN.md", "# copied output\n")
    kept = _write(repo / "web" / "DESIGN.md", "# real\n")
    assert linter_module.DESIGN_CONTRACTS.discover(repo) == [kept]


def test_symlinks_inside_are_read_once_and_outside_are_not_read(linter_module, repo, tmp_path, monkeypatch):
    real = _write(repo / "docs" / "design" / "DESIGN.md", "# Design\n")
    (repo / "DESIGN.md").symlink_to(os.path.relpath(real, repo))
    outside = _write(tmp_path / "elsewhere" / "DESIGN.md", "@secret-notes.md\n")
    (repo / "app").mkdir()
    (repo / "app" / "DESIGN.md").symlink_to(outside)
    (repo / "linked-dir").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    found = linter_module.DESIGN_CONTRACTS.discover(repo)
    assert len(found) == 1 and found[0].resolve() == real.resolve()
    rep = _lint(linter_module, repo, monkeypatch)
    assert "DESIGN_EXTERNAL" in _codes_for(rep, repo / "app" / "DESIGN.md")
    assert not any(f.code == "IMPORT_MISSING" for f in rep.findings)  # the outside file was never parsed


def test_links_resolve_from_the_nested_contract(linter_module, repo, monkeypatch):
    _write(repo / "frontend" / "src" / "theme.css", ":root {}\n")
    _write(repo / "docs" / "journeys.md", "# Journeys\n")
    design = _write(
        repo / "frontend" / "DESIGN.md",
        "Tokens: [theme](src/theme.css) · [journeys](../docs/journeys.md#j1) · [web](https://example.org)\n"
        "[anchor](#states) · [sibling repo](../../other-repo/DESIGN.md) · [gone](../docs/missing.md)\n"
        "[ref]: ./src/removed.css\n"
        "```md\n[in code](nowhere.md)\n```\n",
    )
    findings = [f for f in _lint(linter_module, repo, monkeypatch).findings if f.code == "DESIGN_DEAD_LINK"]
    assert len(findings) == 1 and findings[0].path == str(design)
    assert "../docs/missing.md" in findings[0].message and "./src/removed.css" in findings[0].message
    assert "nowhere.md" not in findings[0].message and "other-repo" not in findings[0].message


def test_nested_commands_resolve_against_their_own_package(linter_module, repo, monkeypatch):
    _write(repo / "package.json", json.dumps({"scripts": {"build": "x"}}))
    _write(repo / "frontend" / "package.json", json.dumps({"scripts": {"storybook": "x"}}))
    design = _write(repo / "frontend" / "DESIGN.md", "Run `npm run storybook`, then `npm run nope`.\n")
    rep = linter_module.Report()
    linter_module._CLAUDE_FILES.check_repo(repo, rep)  # the dead-reference pass runs once per repo
    msgs = [f.message for f in rep.findings if f.code == "INSTR_DEAD_REF" and f.path == str(design)]
    assert len(msgs) == 1 and "npm run nope" in msgs[0] and "storybook" not in msgs[0]


def test_unreferenced_contract_is_reported(linter_module, repo, monkeypatch):
    design = _write(repo / "DESIGN.md", "# Design\n")
    _write(repo / "CLAUDE.md", "# Project\nSee frontend/DESIGN.md for the web app.\n")
    assert "DESIGN_UNREFERENCED" in _codes_for(_lint(linter_module, repo, monkeypatch), design)


def test_reference_reaches_nested_contracts_through_the_root_one(linter_module, repo, monkeypatch):
    root = _write(repo / "DESIGN.md", "# Design\nWeb details: [web](web/DESIGN.md).\n")
    nested = _write(repo / "web" / "DESIGN.md", "# Web\n")
    orphan = _write(repo / "admin" / "DESIGN.md", "# Admin\n")
    _write(repo / "AGENTS.md", "Before UI work, read `DESIGN.md` and the specs it links.\n")
    rep = _lint(linter_module, repo, monkeypatch)
    assert "DESIGN_UNREFERENCED" not in _codes_for(rep, root) | _codes_for(rep, nested)
    assert "DESIGN_UNREFERENCED" in _codes_for(rep, orphan)


def test_nested_instruction_file_references_its_sibling(linter_module, repo, monkeypatch):
    nested = _write(repo / "app" / "DESIGN.md", "# App\n")
    _write(repo / "app" / "CLAUDE.md", "Read DESIGN.md before editing components.\n")
    assert "DESIGN_UNREFERENCED" not in _codes_for(_lint(linter_module, repo, monkeypatch), nested)


def test_always_loaded_import_is_distinguished_from_an_on_demand_rule(linter_module, repo, monkeypatch):
    design = _write(repo / "DESIGN.md", "# Design\n")
    _write(repo / "CLAUDE.md", "# Project\n@DESIGN.md\n")
    assert "DESIGN_ALWAYS_LOADED" in _codes_for(_lint(linter_module, repo, monkeypatch), design)
    _write(repo / "CLAUDE.md", "# Project\n")
    _write(repo / ".claude" / "rules" / "ui.md", '---\npaths:\n  - "src/**/*.tsx"\n---\n@../../DESIGN.md\n')
    codes = _codes_for(_lint(linter_module, repo, monkeypatch), design)
    assert "DESIGN_ALWAYS_LOADED" not in codes and "DESIGN_UNREFERENCED" not in codes


def test_contract_is_never_edited(linter_module, repo, monkeypatch):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    text = "# Design\n\nPlease note that we really want a calm, dense layout.\n@missing.md\n"
    design = _write(repo / "DESIGN.md", text)
    _write(repo / "AGENTS.md", "# Agents\n")
    _write(repo / "CLAUDE.md", "# Project\n")
    rep = _lint(linter_module, repo, monkeypatch, scaffold=True)
    assert design not in rep.edits and not any(p.name == "DESIGN.md" for p in rep.new_files)
    assert design.read_text(encoding="utf-8") == text
