"""Design contracts participate in project instruction checks without being required."""

from __future__ import annotations


def test_design_contract_imports_checked_by_project_lint(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "user-config"))
    monkeypatch.setattr(m.state, "scaffold", False)
    (tmp_path / "DESIGN.md").write_text("# Design\n@missing-tokens.md\n")
    rep = m.Report()
    m.lint_repo(tmp_path, m.load_policy(None, [tmp_path]), rep, False, None)
    assert any(f.code == "IMPORT_MISSING" and f.path == str(tmp_path / "DESIGN.md") for f in rep.findings)


def test_design_contract_length_checked(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "user-config"))
    monkeypatch.setattr(m.state, "scaffold", False)
    (tmp_path / "DESIGN.md").write_text("- Use semantic tokens.\n" * 500)
    rep = m.Report()
    m.lint_repo(tmp_path, m.load_policy(None, [tmp_path]), rep, False, None)
    assert any(f.code == "INSTR_LONG" and f.path == str(tmp_path / "DESIGN.md") for f in rep.findings)


def test_nested_design_and_generated_tree_exclusion(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "user-config"))
    monkeypatch.setattr(m.state, "scaffold", False)
    for folder in ("frontend", "node_modules/dependency", ".git"):
        directory = tmp_path / folder
        directory.mkdir(parents=True)
        (directory / "DESIGN.md").write_text("@missing.md\n")
    rep = m.Report()
    m.lint_repo(tmp_path, m.load_policy(None, [tmp_path]), rep, False, None)
    findings = [f for f in rep.findings if f.code == "IMPORT_MISSING"]
    assert [f.path for f in findings] == [str(tmp_path / "frontend/DESIGN.md")]
