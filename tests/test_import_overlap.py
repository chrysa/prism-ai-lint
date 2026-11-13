"""INSTR_IMPORT_OVERLAP: an always-loaded file that imports another one and repeats its lines pays them twice."""

from __future__ import annotations

BLOCK = "\n".join(f"- Rule number {i}: keep the configuration tight and documented" for i in range(12)) + "\n"


def _findings(m, repo):
    pol = m.load_policy(None, [repo])
    rep = m.Report()
    m.ImportOverlapChecker().check_repo(repo, pol, rep)
    return [f for f in rep.findings if f.code == "INSTR_IMPORT_OVERLAP"]


def test_claude_md_repeating_the_imported_agents_md_is_reported(linter_module, tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Project\n\n" + BLOCK)
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\n## Notes\n\n" + BLOCK)
    found = _findings(linter_module, tmp_path)
    assert len(found) == 1
    assert found[0].path.endswith("CLAUDE.md")
    assert "12 lines" in found[0].message and "AGENTS.md" in found[0].message
    assert "tokens" in found[0].message


def test_import_without_repeated_content_is_clean(linter_module, tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Project\n\n" + BLOCK)
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\n## Claude only\n\n- Use the plan mode for risky edits.\n")
    assert _findings(linter_module, tmp_path) == []


def test_a_few_shared_lines_are_tolerated(linter_module, tmp_path):
    (tmp_path / "AGENTS.md").write_text("# Project\n\n" + BLOCK)
    two = "".join(BLOCK.splitlines(keepends=True)[:2])
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\n" + two)
    assert _findings(linter_module, tmp_path) == []


def test_repeated_content_without_import_is_not_this_finding(linter_module, tmp_path):
    (tmp_path / "AGENTS.md").write_text(BLOCK)
    (tmp_path / "CLAUDE.md").write_text(BLOCK)
    assert _findings(linter_module, tmp_path) == []


def test_code_blocks_and_comments_do_not_count(linter_module, tmp_path):
    fenced = "```\n" + BLOCK + "```\n"
    (tmp_path / "AGENTS.md").write_text(fenced)
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\n<!--\n" + BLOCK + "-->\n" + fenced)
    assert _findings(linter_module, tmp_path) == []


def test_nested_import_overlap_is_found(linter_module, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "standards.md").write_text(BLOCK)
    (tmp_path / "AGENTS.md").write_text("@docs/standards.md\n")
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n\n" + BLOCK)
    found = _findings(linter_module, tmp_path)
    assert len(found) == 1 and "docs/standards.md" in found[0].message


def test_import_outside_the_repo_is_ignored(linter_module, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text(BLOCK)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text(f"@{outside}\n\n" + BLOCK)
    assert _findings(linter_module, repo) == []


def test_code_has_an_action(linter_module, monkeypatch):
    monkeypatch.setattr(linter_module.state, "lang", "en")
    assert linter_module._action_for("INSTR_IMPORT_OVERLAP")
