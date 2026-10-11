"""procedure-to-skill never moves a managed block, another document's H1, or content git would ignore."""

from __future__ import annotations

import subprocess

STEPS = "\n".join(f"{i}. step number {i} of the procedure" for i in range(1, 20))


def _proposals(m, repo):
    pol = m.DEFAULT_POLICY
    return [p for p in m.compute_proposals([], [repo], pol) if p["kind"] == "procedure-to-skill"]


def _repo(tmp_path, claude):
    (tmp_path / "CLAUDE.md").write_text(claude, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_plain_procedure_is_proposed(linter_module, tmp_path):
    repo = _repo(tmp_path, f"# Project\n\n## Release\n\n{STEPS}\n")
    assert [p["section"] for p in _proposals(linter_module, repo)] == ["Release"]


def test_managed_block_section_is_never_moved(linter_module, tmp_path):
    body = (
        f"## Release\n\n{STEPS}\n\n<!-- team:standards:start · managed by sync.sh · DO NOT EDIT -->\n# Standards\n- a\n"
    )
    repo = _repo(tmp_path, "# Project\n\n" + body)
    assert _proposals(linter_module, repo) == []


def test_section_containing_another_h1_is_not_moved(linter_module, tmp_path):
    repo = _repo(tmp_path, f"# Project\n\n## Release\n\n{STEPS}\n\n# Another document\n")
    assert _proposals(linter_module, repo) == []


def test_ignored_skill_target_is_not_proposed(linter_module, tmp_path):
    repo = _repo(tmp_path, f"# Project\n\n## Release\n\n{STEPS}\n")
    (repo / ".gitignore").write_text("release\n", encoding="utf-8")
    assert _proposals(linter_module, repo) == []


def test_rules_sections_stay_in_the_instruction_file(linter_module, tmp_path):
    for title in ("Non-negotiable conventions", "Security rules", "Never do this"):
        repo = tmp_path / title.split()[0]
        repo.mkdir()
        _repo(repo, f"# Project\n\n## {title}\n\n{STEPS}\n")
        assert _proposals(linter_module, repo) == [], title


def test_a_procedure_title_is_still_proposed(linter_module, tmp_path):
    repo = _repo(tmp_path, f"# Project\n\n## Deploy to staging\n\n{STEPS}\n")
    assert [p["section"] for p in _proposals(linter_module, repo)] == ["Deploy to staging"]


def test_hostile_keep_list_falls_back_to_the_built_in_words(linter_module):
    for bad in (None, 5, True, "x", [], [""], [None, 3]):
        assert linter_module._is_rule_title("Security rules", bad) is True, bad
        assert linter_module._is_rule_title("Deploy to staging", bad) is False, bad
