"""Plugin loading and execution registry."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from prism_ai_lint.plugin_trust import PluginTrust
from prism_ai_lint.report import Report

ReadTextFn = Callable[[Path], str | None]
ConfigDirFn = Callable[[], Path]
LogFn = Callable[[int, str], None]


class PluginRegistry:
    def __init__(
        self,
        config_dir_fn: ConfigDirFn,
        read_text_fn: ReadTextFn,
        log_fn: LogFn,
        brief_fr: dict,
        brief_en: dict,
    ) -> None:
        self._config_dir_fn = config_dir_fn
        self._read_text_fn = read_text_fn
        self._log_fn = log_fn
        self._brief_fr = brief_fr
        self._brief_en = brief_en
        self.checks: list = []
        self.loaded: list = []
        self.trust: PluginTrust | None = None

    def default_trust(self) -> PluginTrust:
        """Non-interactive trust: what a run without a prompt function may load."""
        return PluginTrust(self._config_dir_fn(), Path.cwd(), interactive=False)

    def plugin_dirs(self, extra: list[Path] | None = None, trust: PluginTrust | None = None) -> list[Path]:
        return [source.path for source in (trust or self.default_trust()).sources(extra)]

    def load(self, extra: list[Path] | None = None, trust: PluginTrust | None = None) -> None:
        """Import the plugins of every trusted directory and call register(api). Broken plugins are skipped.

        `extra` directories are an explicit opt-in. Other directories go through `trust` (D-046).
        """
        trust = trust or self.default_trust()
        self.trust = trust
        for source in trust.sources(extra):
            for file in trust.approve(source):  # exactly the approved files, never a second glob
                try:
                    spec = importlib.util.spec_from_file_location(f"ai_lint_plugin_{file.stem}", file)
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    register = getattr(module, "register", None)
                    if callable(register):
                        register(self._api(file.stem))
                        self.loaded.append(file.stem)
                    else:
                        self._log_fn(1, f"plugin {file.name}: no register(api), skipped")
                except Exception as error:  # noqa: BLE001
                    self._log_fn(
                        1,
                        f"plugin {file.name}: failed to load ({error.__class__.__name__}: {error})",
                    )

    def report_trust(self, report: Report) -> None:
        """Add the findings of the last load's trust decisions (skipped or deprecated directories)."""
        if self.trust is not None:
            self.trust.report(report)

    def run_checks(self, scope: str, root: Path, policy: dict, report: Report) -> None:
        for code, check_scope, check_fn in self.checks:
            if check_scope != scope:
                continue
            try:
                check_fn(self._context(scope, root, policy, report))
            except Exception as error:  # noqa: BLE001
                self._log_fn(1, f"plugin check {code}: error ({error.__class__.__name__}: {error})")

    def _api(self, name: str) -> SimpleNamespace:
        def check(code: str, scope: str = "project"):
            if scope not in ("project", "user"):
                raise ValueError("scope must be 'project' or 'user'")

            def deco(fn):
                self.checks.append((code, scope, fn))
                return fn

            return deco

        return SimpleNamespace(name=name, check=check)

    def _context(self, scope: str, root: Path, policy: dict, report: Report) -> SimpleNamespace:
        context = SimpleNamespace(scope=scope, root=Path(root), policy=policy)

        def path(*parts: str) -> Path:
            return context.root.joinpath(*parts)

        def glob(pattern: str) -> list[Path]:
            try:
                return sorted(context.root.glob(pattern))
            except OSError:
                return []

        def add(
            level: str,
            code: str,
            target_path: Any,
            message: str,
            action_fr: str = "",
            action_en: str = "",
            fixable: bool = False,
        ) -> None:
            if action_fr or action_en:
                self._brief_fr.setdefault(code, ("other", "", action_fr or action_en))
                self._brief_en.setdefault(code, ("other", "", action_en or action_fr))
            report.add(level, code, target_path, message, fixable)

        context.path = path
        context.read = self._read_text_fn
        context.glob = glob
        context.add = add
        return context
