"""The AGENTS.md import goes after a leading level-1 title, so the first line stays a heading (markdownlint MD041)."""

from __future__ import annotations

from prism_ai_lint.instruction_checker import InstructionChecker

ADD = InstructionChecker.with_import


def test_no_title_puts_the_import_at_the_top():
    assert ADD("Some notes.\n", "AGENTS.md") == "@AGENTS.md\n\nSome notes.\n"


def test_a_leading_title_stays_the_first_line():
    assert ADD("# Project\n\nRules here.\n", "AGENTS.md") == "# Project\n\n@AGENTS.md\n\nRules here.\n"


def test_title_without_blank_line_or_trailing_newline():
    assert ADD("# Project\nRules here.\n", "AGENTS.md") == "# Project\n\n@AGENTS.md\n\nRules here.\n"
    assert ADD("# Project", "AGENTS.md") == "# Project\n\n@AGENTS.md\n"


def test_leading_blank_lines_are_kept_before_the_title():
    assert ADD("\n# Project\n\nx\n", "AGENTS.md") == "\n# Project\n\n@AGENTS.md\n\nx\n"


def test_only_a_level_one_title_counts():
    assert ADD("## Section\n\nx\n", "AGENTS.md").startswith("@AGENTS.md\n\n## Section")
    assert ADD("#hashtag\n", "AGENTS.md").startswith("@AGENTS.md\n\n#hashtag")
    assert ADD("", "AGENTS.md") == "@AGENTS.md\n\n"


def test_fix_imports_after_the_title_and_converges(linter_module, tmp_path):
    m = linter_module
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "AGENTS.md").write_text("# Shared\n\n- rule\n")
    claude = repo / "CLAUDE.md"
    claude.write_text("# Project\n\nClaude-only notes.\n")
    rep = m.Report()
    policy = m.load_policy(None, [repo])
    m._INSTRUCTIONS.check_agents_md(repo, policy, rep)
    assert rep.edits[claude][1] == "# Project\n\n@AGENTS.md\n\nClaude-only notes.\n"
    assert any(f.code == "AGENTS_IGNORED" and "after the title" in f.message for f in rep.findings)
    claude.write_text(rep.edits[claude][1])
    again = m.Report()
    m._INSTRUCTIONS.check_agents_md(repo, policy, again)
    assert claude not in again.edits
