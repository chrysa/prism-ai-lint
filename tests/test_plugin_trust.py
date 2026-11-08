"""Plugin trust (D-046): a scan imports plugin code only from trusted locations.

`--plugin-dir` and the prism-ai-lint user directory load; the old Claude Code config directory loads
with a deprecation finding; plugins under the current directory load only after an interactive "yes",
never in CI, pre-commit or a non-text run. The guard never imports any plugin.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = (
    "import pathlib\n"
    "pathlib.Path(__file__).with_name('RAN.marker').write_text('imported')\n"
    "def register(api):\n"
    "    pass\n"
)


def _probe(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "probe.py").write_text(PROBE)
    return directory / "RAN.marker"


def _cli(
    cwd: Path, home: Path, *args: str, env_extra: dict | None = None, stdin: str = ""
) -> subprocess.CompletedProcess:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        **(env_extra or {}),
    }
    cmd = [sys.executable, str(ROOT / "prism-ai-lint.py"), *args, "--no-update-check", "--no-history", "--no-cli"]
    return subprocess.run(cmd, cwd=cwd, env=env, input=stdin, capture_output=True, text=True, timeout=300)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def test_cwd_plugin_is_not_imported_by_a_non_interactive_scan(tmp_path):
    repo = _repo(tmp_path)
    marker = _probe(repo / ".prism-ai-lint" / "plugins")
    res = _cli(repo, tmp_path / "home", ".", "--format", "json")
    assert not marker.exists(), "a repo-local plugin ran without consent"
    assert "PLUGIN_SKIPPED_UNTRUSTED" in res.stdout


def test_legacy_cwd_plugin_dir_is_not_imported_either(tmp_path):
    repo = _repo(tmp_path)
    marker = _probe(repo / ".ai-lint" / "plugins")
    _cli(repo, tmp_path / "home", ".", "-q")
    assert not marker.exists()


def test_pre_commit_and_ci_never_load_even_when_interactive(linter_module, tmp_path, monkeypatch):
    m = linter_module
    for var in ("PRE_COMMIT", "CI"):
        monkeypatch.setenv(var, "1")
        assert not m.PluginTrust.is_interactive("text", quiet=False, tty=True)
        monkeypatch.delenv(var)
    assert m.PluginTrust.is_interactive("text", quiet=False, tty=True)
    assert not m.PluginTrust.is_interactive("json", quiet=False, tty=True)
    assert not m.PluginTrust.is_interactive("text", quiet=True, tty=True)
    assert not m.PluginTrust.is_interactive("text", quiet=False, tty=False)


def _trust(m, tmp_path, interactive, answer=""):
    asked: list[str] = []

    def ask(prompt: str) -> str:
        asked.append(prompt)
        return answer

    trust = m.PluginTrust(tmp_path / "claude", tmp_path / "cwd", interactive, ask)
    return trust, asked


def _reset(m):
    m._PLUGIN_CHECKS.clear()
    m._PLUGINS_LOADED.clear()


def test_interactive_yes_loads_and_default_no_skips(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    marker = _probe(tmp_path / "cwd" / ".prism-ai-lint" / "plugins")
    _reset(m)
    trust, asked = _trust(m, tmp_path, interactive=True, answer="")
    m._PLUGIN_REGISTRY.load(None, trust)
    assert asked and "probe" in asked[0] and not marker.exists()
    assert trust.skipped and trust.skipped[0][1] == "declined"
    _reset(m)
    trust, _ = _trust(m, tmp_path, interactive=True, answer="y")
    m._PLUGIN_REGISTRY.load(None, trust)
    assert marker.exists() and "probe" in m._PLUGINS_LOADED


def test_non_interactive_never_asks(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    marker = _probe(tmp_path / "cwd" / ".prism-ai-lint" / "plugins")
    _reset(m)
    trust, asked = _trust(m, tmp_path, interactive=False, answer="y")
    m._PLUGIN_REGISTRY.load(None, trust)
    assert not asked and not marker.exists()
    assert trust.skipped[0][1] == "non-interactive run"


def test_plugin_dir_flag_is_an_explicit_opt_in(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    plugins = tmp_path / "cwd" / ".prism-ai-lint" / "plugins"
    marker = _probe(plugins)
    _reset(m)
    trust, asked = _trust(m, tmp_path, interactive=False)
    m._PLUGIN_REGISTRY.load([plugins], trust)
    assert marker.exists() and not asked and not trust.skipped


def test_user_dir_loads_and_old_dir_loads_with_deprecation(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    new_marker = _probe(tmp_path / "xdg" / "prism-ai-lint" / "plugins")
    old_marker = _probe(tmp_path / "claude" / "plugins")
    _reset(m)
    trust, _ = _trust(m, tmp_path, interactive=False)
    m._PLUGIN_REGISTRY.load(None, trust)
    assert new_marker.exists() and old_marker.exists()
    rep = m.Report()
    trust.report(rep)
    assert [f.code for f in rep.findings] == ["PLUGIN_DIR_DEPRECATED"]


def test_guard_never_imports_plugins(tmp_path):
    repo = _repo(tmp_path)
    marker = _probe(repo / ".prism-ai-lint" / "plugins")
    payload = '{"tool_name": "Read", "tool_input": {"file_path": "README.md"}}'
    _cli(repo, tmp_path / "home", "--guard", stdin=payload)
    assert not marker.exists()


def test_list_plugins_shows_the_skip_reason(tmp_path):
    repo = _repo(tmp_path)
    _probe(repo / ".prism-ai-lint" / "plugins")
    res = _cli(repo, tmp_path / "home", "--list-plugins")
    assert "skipped" in res.stdout and "non-interactive run" in res.stdout


def test_control_characters_in_plugin_names_are_refused_without_asking(linter_module, tmp_path, monkeypatch):
    """A file name with terminal escapes could rewrite the consent prompt (security review of #126)."""
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    plugins = tmp_path / "cwd" / ".prism-ai-lint" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "\x1b[1A\x1b[2K\rok.py").write_text(PROBE)
    _reset(m)
    trust, asked = _trust(m, tmp_path, interactive=True, answer="y")
    m._PLUGIN_REGISTRY.load(None, trust)
    assert not asked and not (plugins / "RAN.marker").exists()
    assert trust.skipped[0][1] == "unsafe file names"


def test_prompt_lists_only_printable_names_and_is_capped(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    plugins = tmp_path / "cwd" / ".prism-ai-lint" / "plugins"
    plugins.mkdir(parents=True)
    for i in range(15):
        (plugins / f"p{i:02}.py").write_text("def register(api):\n    pass\n")
    _reset(m)
    trust, asked = _trust(m, tmp_path, interactive=True, answer="")
    m._PLUGIN_REGISTRY.load(None, trust)
    assert "15 plugin(s)" in asked[0] and "p14" not in asked[0] and "current directory" in asked[0]


def test_file_added_after_the_prompt_is_not_imported(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    plugins = tmp_path / "cwd" / ".prism-ai-lint" / "plugins"
    _probe(plugins)
    late = plugins / "late.py"
    late_marker = tmp_path / "late.marker"

    def ask(prompt: str) -> str:
        late.write_text(f"import pathlib\npathlib.Path({str(late_marker)!r}).write_text('x')\n")
        return "y"

    _reset(m)
    trust = m.PluginTrust(tmp_path / "claude", tmp_path / "cwd", True, ask)
    m._PLUGIN_REGISTRY.load(None, trust)
    assert (plugins / "RAN.marker").exists() and not late_marker.exists()


def test_symlinked_plugin_file_in_current_directory_is_not_imported(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    outside = tmp_path / "outside"
    marker = _probe(outside)
    plugins = tmp_path / "cwd" / ".prism-ai-lint" / "plugins"
    plugins.mkdir(parents=True)
    (plugins / "linked.py").symlink_to(outside / "probe.py")
    _reset(m)
    trust, _ = _trust(m, tmp_path, interactive=True, answer="y")
    m._PLUGIN_REGISTRY.load(None, trust)
    assert not marker.exists() and "linked" not in m._PLUGINS_LOADED


def test_config_dir_inside_the_current_directory_is_not_trusted(linter_module, tmp_path, monkeypatch):
    """CI pointing CLAUDE_CONFIG_DIR / XDG_CONFIG_HOME into the checkout must not trust the checkout's plugins."""
    m = linter_module
    cwd = tmp_path / "cwd"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(cwd / "xdg"))
    xdg_marker = _probe(cwd / "xdg" / "prism-ai-lint" / "plugins")
    claude_marker = _probe(cwd / ".claude" / "plugins")
    _reset(m)
    trust = m.PluginTrust(cwd / ".claude", cwd, False, None)
    m._PLUGIN_REGISTRY.load(None, trust)
    assert not xdg_marker.exists() and not claude_marker.exists()
    assert {reason for _, reason in trust.skipped} == {"non-interactive run"}


def test_relative_xdg_config_home_is_ignored(linter_module, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "rel/xdg")
    assert linter_module.PluginTrust.user_dir().is_absolute()


def test_deprecated_dir_is_not_loaded_in_ci_or_pre_commit(linter_module, tmp_path, monkeypatch):
    m = linter_module
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    marker = _probe(tmp_path / "claude" / "plugins")
    for var in ("CI", "PRE_COMMIT"):
        monkeypatch.setenv(var, "1")
        _reset(m)
        trust, _ = _trust(m, tmp_path, interactive=False)
        m._PLUGIN_REGISTRY.load(None, trust)
        assert not marker.exists(), var
        monkeypatch.delenv(var)


def test_new_codes_have_an_action(linter_module, monkeypatch):
    monkeypatch.setattr(linter_module.state, "lang", "en")
    assert linter_module._action_for("PLUGIN_SKIPPED_UNTRUSTED")
    assert linter_module._action_for("PLUGIN_DIR_DEPRECATED")
