"""Instruction files naming things that do not exist, and the skill/subagent listing budget."""

from __future__ import annotations

from prism_ai_lint.claude_files_checker import ClaudeFilesChecker
from prism_ai_lint.report import Report


def _run(repo):
    rep = Report()
    ClaudeFilesChecker().check_repo(repo, rep)
    return [(f.level, f.code, f.message) for f in rep.findings]


def _codes(repo):
    return {c for _, c, _ in _run(repo)}


def test_existing_targets_and_files_are_quiet(tmp_path):
    (tmp_path / "Makefile").write_text(".PHONY: test\ntest:\n\techo ok\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "GUIDE.md").write_text("x")
    (tmp_path / "CLAUDE.md").write_text("Run `make test`. See `docs/GUIDE.md`.\n")
    assert _run(tmp_path) == []


def test_missing_make_target_and_file(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\techo ok\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "AGENTS.md").write_text("```\nmake lint\n```\nSee `docs/GONE.md`.\n")
    out = _run(tmp_path)
    assert [c for _, c, _ in out] == ["INSTR_DEAD_REF"]
    assert "make lint" in out[0][2] and "docs/GONE.md" in out[0][2]


def test_missing_npm_script(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"build": "x"}}')
    (tmp_path / "CLAUDE.md").write_text("`npm run build` then `npm run deploy`\n")
    out = _run(tmp_path)
    assert "npm run deploy" in out[0][2] and "npm run build" not in out[0][2]


def test_prose_and_placeholders_and_generated_dirs_are_ignored(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\techo ok\n")
    (tmp_path / "CLAUDE.md").write_text(
        "Please make sure it works. Use `path/to/file.py`, `dist/app.js`, `https://x.io/a/b.md`, `src/*.py`.\n"
    )
    assert _run(tmp_path) == []


def test_makefile_with_include_is_not_judged(tmp_path):
    (tmp_path / "Makefile").write_text("include other.mk\ntest:\n\techo ok\n")
    (tmp_path / "CLAUDE.md").write_text("`make lint`\n")
    assert _run(tmp_path) == []


def test_rules_are_scanned(tmp_path):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / ".claude" / "rules" / "a.md").write_text("See `docs/NOPE.md`.\n")
    assert _codes(tmp_path) == {"INSTR_DEAD_REF"}


def _skill(repo, name, desc, extra=""):
    d = repo / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n{extra}---\nbody\n")


def test_skill_listing_over_budget_names_biggest(tmp_path):
    for i in range(6):
        _skill(tmp_path, f"s{i}", "x" * 1500)
    out = _run(tmp_path)
    assert [c for _, c, _ in out] == ["TOKEN_LISTING_BUDGET"]
    assert "disable-model-invocation" in out[0][2]


def test_manual_skills_do_not_count(tmp_path):
    for i in range(6):
        _skill(tmp_path, f"s{i}", "x" * 1500, "disable-model-invocation: true\n")
    assert _run(tmp_path) == []


def test_small_skill_listing_is_quiet(tmp_path):
    _skill(tmp_path, "a", "does a thing")
    assert _run(tmp_path) == []


def test_subagent_listing_over_budget_warns(tmp_path):
    d = tmp_path / ".claude" / "agents"
    d.mkdir(parents=True)
    for i in range(20):
        (d / f"a{i}.md").write_text(f"---\nname: a{i}\ndescription: {'y' * 3500}\n---\nbody\n")
    assert _run(tmp_path)[0][:2] == ("warn", "TOKEN_LISTING_BUDGET")


def test_path_into_an_unknown_directory_is_not_judged(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("See `standards/STANDARDS.md` and `ui-ux/SKILL.md`.\n")
    assert _run(tmp_path) == []


def test_package_without_scripts_is_not_judged(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "x"}')
    (tmp_path / "CLAUDE.md").write_text("`npm run dev`\n")
    assert _run(tmp_path) == []
