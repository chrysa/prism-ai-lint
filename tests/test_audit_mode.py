"""--audit: strictly read-only, lists what --fix --generate would change, exits 1 when anything is pending."""

from __future__ import annotations

import json
import subprocess


def _repo(tmp_path):
    repo = tmp_path / "svc"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='svc'\n")
    (repo / "app.py").write_text("print('hi')\n")
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "i"], check=True, capture_output=True)
    return repo


def _listing(repo):
    return sorted(str(p.relative_to(repo)) for p in repo.rglob("*") if ".git" not in p.relative_to(repo).parts)


def test_audit_writes_nothing_and_reports_pending(env, tmp_path):
    repo = _repo(tmp_path)
    before = _listing(repo)
    proc = env.run(str(repo), "--audit", "--lang", "en", "--no-cli", "--no-history")
    assert _listing(repo) == before
    assert proc.returncode == 1
    assert "would change with --fix --generate" in proc.stdout


def test_audit_json_lists_pending_changes(env, tmp_path):
    repo = _repo(tmp_path)
    proc = env.run(str(repo), "--audit", "--format", "json", "--no-cli", "--no-history")
    assert json.loads(proc.stdout)["pending_changes"]


def test_audit_refuses_writing_modes(env, tmp_path):
    repo = _repo(tmp_path)
    for flag in ("--fix", "--full-yes", "-i", "--graphify"):
        proc = env.run(str(repo), "--audit", flag, "--no-cli")
        assert proc.returncode == 2


def test_report_writes_markdown_outside_repo(env, tmp_path):
    repo = _repo(tmp_path)
    out = tmp_path / "out" / "report.md"
    before = _listing(repo)
    env.run(str(repo), "--audit", "--report", str(out), "--no-cli", "--no-history")
    text = out.read_text()
    assert "# prism-ai-lint report" in text and "## Needs a human decision" in text
    assert "would change with --fix --generate" in text
    assert _listing(repo) == before


def test_report_refuses_path_inside_repo(env, tmp_path):
    repo = _repo(tmp_path)
    proc = env.run(str(repo), "--report", str(repo / "report.md"), "--no-cli", "--no-history")
    assert proc.returncode == 2
    assert not (repo / "report.md").exists()


def test_force_requires_text_format(env, tmp_path):
    proc = env.run("--force", "--format", "json", "--no-cli")
    assert proc.returncode == 2  # --force needs text output like --full-yes


def test_force_regenerates_generated_files_but_keeps_deny(env, tmp_path):
    repo = _repo(tmp_path)
    claude = repo / ".claude"
    (claude / "hooks").mkdir(parents=True)
    (claude / "hooks" / "read_guard.py").write_text("# stale hand edit\n")
    (claude / "settings.json").write_text(
        json.dumps({"model": "opus", "permissions": {"deny": ["Read(./secrets/**)"], "allow": ["Bash(ls)"]}})
    )
    (repo / "CLAUDE.md").write_text("# mine\n")
    proc = env.run(str(repo), "--force", "--no-cli", "--no-history")
    assert proc.returncode in (0, 1)
    assert "stale hand edit" not in (claude / "hooks" / "read_guard.py").read_text()
    settings = json.loads((claude / "settings.json").read_text())
    assert "Read(./secrets/**)" in settings["permissions"]["deny"]
    assert {"Bash(ls)", "Bash(rtk ls)"} & set(settings["permissions"]["allow"])  # --fix may rtk-wrap it, never drop it
    assert settings["model"] != "opus"
    assert (repo / "CLAUDE.md").read_text() == "# mine\n"


def test_audit_refuses_force(env, tmp_path):
    repo = _repo(tmp_path)
    assert env.run(str(repo), "--audit", "--force", "--no-cli").returncode == 2


def test_report_has_a_per_repository_table_for_several_repos(env, tmp_path):
    a, b = _repo(tmp_path), _repo(tmp_path / "other" if (tmp_path / "other").mkdir() is None else tmp_path)
    out = tmp_path / "r" / "report.md"
    env.run(str(a), str(b), "--audit", "--report", str(out), "--no-cli", "--no-history")
    text = out.read_text()
    assert "## Per repository" in text and "| Repository |" in text
