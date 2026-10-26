"""A session-link trailer (a link back to the assistant session that wrote the
commit) is assistant attribution: detected in history, stripped by the generated
commit-msg hook, and a hook that strips it counts as the guard."""

from __future__ import annotations

import subprocess

# Built from parts so this source file never itself carries the trailer it tests for.
KEY = "Cl" + "aude-Session:"
TRAILER = KEY + " https://" + "claude.ai/code/session_0123456789abcdef"


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


def _repo(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


def test_session_trailer_matches_attribution_patterns(linter_module):
    m = linter_module
    msg = f"feat: thing\n\nbody line\n\n{TRAILER}\n"
    assert any(p.search(msg) for p in m.ATTRIBUTION_PATTERNS)
    assert m._is_attribution(TRAILER)
    # Mentioned mid-sentence, not as a trailer line: not a trace.
    assert not any(p.search(f"see the {KEY} https://x docs") for p in m.ATTRIBUTION_PATTERNS)


def test_session_trailer_in_history_is_reported(linter_module, tmp_path):
    m = linter_module
    repo = _repo(tmp_path)
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "--no-verify", "-m", f"feat: thing\n\n{TRAILER}")
    rep = m.Report()
    m.check_attribution(repo, m.load_policy(None, [tmp_path]), rep, history=True)
    assert any(f.code == "ATTR_HISTORY" for f in rep.findings)


def test_generated_hook_strips_session_trailer(linter_module):
    m = linter_module
    assert "-e '/^" + KEY + "/Id' \\" in m.COMMIT_MSG_HOOK


def test_hook_stripping_only_session_trailer_is_the_guard(linter_module, tmp_path):
    m = linter_module
    repo = _repo(tmp_path)
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\nsed -i '/^" + KEY + '/d\' "$1"\n')
    rep = m.Report()
    m.check_attribution(repo, m.load_policy(None, [tmp_path]), rep, history=False)
    codes = {f.code for f in rep.findings}
    assert "ATTR_HOOK_CONFLICT" not in codes
    assert "ATTR_HOOK_MISSING" not in codes
