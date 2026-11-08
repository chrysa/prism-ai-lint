"""Decide which plugin directories a run may import code from (D-046)."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AskFn = Callable[[str], str]

TRUSTED = "trusted"
DEPRECATED = "deprecated"
ASK = "ask"
YES = ("y", "yes", "o", "oui")


@dataclass(frozen=True)
class PluginSource:
    path: Path
    kind: str


class PluginTrust:
    """Classify plugin directories and decide, per directory, whether its code may be imported.

    An explicit `--plugin-dir` and the prism-ai-lint user directory load. The old shared directory
    `<Claude config dir>/plugins` still loads, with a deprecation finding. Directories under the
    current working directory (`.prism-ai-lint/plugins`, `.ai-lint/plugins`) belong to whatever
    repository is being scanned: they load only after an interactive "yes" (default no), and never
    in CI, pre-commit, a non-text or a quiet run.
    """

    def __init__(self, config_dir: Path, cwd: Path, interactive: bool, ask_fn: AskFn | None = None) -> None:
        self._config_dir = config_dir
        self._cwd = cwd
        self.interactive = interactive
        self._ask_fn = ask_fn
        self.skipped: list[tuple[Path, str]] = []
        self.deprecated: list[Path] = []

    @staticmethod
    def user_dir() -> Path:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        return Path(base) / "prism-ai-lint" / "plugins"

    @staticmethod
    def is_interactive(fmt: str, quiet: bool, tty: bool | None = None) -> bool:
        if fmt != "text" or quiet or os.environ.get("CI") or os.environ.get("PRE_COMMIT"):
            return False
        return (sys.stdin.isatty() and sys.stderr.isatty()) if tty is None else tty

    @staticmethod
    def plugin_files(directory: Path) -> list[Path]:
        try:
            return sorted(p for p in directory.glob("*.py") if not p.name.startswith("_"))
        except OSError:
            return []

    def sources(self, extra: list[Path] | None = None) -> list[PluginSource]:
        """Existing plugin directories, explicit ones first so a duplicate keeps its explicit trust."""
        candidates = [PluginSource(Path(d), TRUSTED) for d in extra or []]
        candidates += [
            PluginSource(self.user_dir(), TRUSTED),
            PluginSource(self._config_dir / "plugins", DEPRECATED),
            PluginSource(self._cwd / ".prism-ai-lint" / "plugins", ASK),
            PluginSource(self._cwd / ".ai-lint" / "plugins", ASK),
        ]
        seen: set[Path] = set()
        out = []
        for source in candidates:
            key = source.path.resolve() if source.path.exists() else source.path
            if key in seen or not source.path.is_dir():
                continue
            seen.add(key)
            out.append(source)
        return out

    def allowed(self, source: PluginSource) -> bool:
        files = self.plugin_files(source.path)
        if source.kind == TRUSTED or not files:
            return True
        if source.kind == DEPRECATED:
            self.deprecated.append(source.path)
            return True
        if not self.interactive or self._ask_fn is None:
            self.skipped.append((source.path, "non-interactive run"))
            return False
        names = ", ".join(p.stem for p in files)
        prompt = (
            f"prism-ai-lint: {source.path} holds {len(files)} plugin(s) ({names}) from the scanned directory. "
            "They run as Python code. Load them? [y/N] "
        )
        if self._ask_fn(prompt).strip().lower() in YES:
            return True
        self.skipped.append((source.path, "declined"))
        return False

    def report(self, rep: Any) -> None:
        """Add one finding per skipped or deprecated directory, so the behaviour change is visible."""
        for path, reason in self.skipped:
            rep.add(
                "info",
                "PLUGIN_SKIPPED_UNTRUSTED",
                path,
                f"plugins not loaded ({reason}): code from the scanned directory runs only after consent",
            )
        for path in self.deprecated:
            rep.add(
                "warn",
                "PLUGIN_DIR_DEPRECATED",
                path,
                f"plugins loaded from the shared Claude Code directory; move them to {self.user_dir()}",
            )
