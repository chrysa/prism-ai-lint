"""Decide which plugin files a run may import code from (D-046)."""

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
PROMPT_NAMES = 10


@dataclass(frozen=True)
class PluginSource:
    path: Path
    kind: str


class PluginTrust:
    """Classify plugin directories and approve, per directory, the exact files whose code may be imported.

    An explicit `--plugin-dir` and the prism-ai-lint user directory load. The old shared directory
    `<Claude config dir>/plugins` still loads, with a deprecation finding, except in CI or pre-commit.
    Directories under the current working directory (`.prism-ai-lint/plugins`, `.ai-lint/plugins`, and
    any non-explicit directory that resolves inside it) belong to whatever checkout the run starts in:
    they load only after an interactive "yes" (default no), never in CI, pre-commit, a non-text or a
    quiet run. File names with control characters are refused without asking (they could rewrite the
    prompt), symlinked files there are ignored, and only the files listed in the prompt are imported.
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
        base = os.environ.get("XDG_CONFIG_HOME", "")
        root = Path(base) if base and Path(base).is_absolute() else Path.home() / ".config"  # XDG: ignore relative
        return root / "prism-ai-lint" / "plugins"

    @staticmethod
    def automated() -> bool:
        return bool(os.environ.get("CI") or os.environ.get("PRE_COMMIT"))

    @classmethod
    def is_interactive(cls, fmt: str, quiet: bool, tty: bool | None = None) -> bool:
        if fmt != "text" or quiet or cls.automated():
            return False
        return (sys.stdin.isatty() and sys.stderr.isatty()) if tty is None else tty

    @staticmethod
    def plugin_files(directory: Path, follow_links: bool = True) -> list[Path]:
        try:
            files = sorted(p for p in directory.glob("*.py") if not p.name.startswith("_"))
        except OSError:
            return []
        return files if follow_links else [p for p in files if not p.is_symlink()]

    def _inside_cwd(self, path: Path) -> bool:
        try:
            return path.resolve().is_relative_to(self._cwd.resolve())
        except (OSError, ValueError):
            return True  # cannot tell: treat as untrusted

    def sources(self, extra: list[Path] | None = None) -> list[PluginSource]:
        """Existing plugin directories, explicit ones first so a duplicate keeps its explicit trust."""
        candidates = [PluginSource(Path(d), TRUSTED) for d in extra or []]
        for path, kind in (
            (self.user_dir(), TRUSTED),
            (self._config_dir / "plugins", DEPRECATED),
            (self._cwd / ".prism-ai-lint" / "plugins", ASK),
            (self._cwd / ".ai-lint" / "plugins", ASK),
        ):
            candidates.append(PluginSource(path, ASK if self._inside_cwd(path) else kind))
        seen: set[Path] = set()
        out = []
        for source in candidates:
            key = source.path.resolve() if source.path.exists() else source.path
            if key in seen or not source.path.is_dir():
                continue
            seen.add(key)
            out.append(source)
        return out

    def approve(self, source: PluginSource) -> list[Path]:
        """The plugin files of `source` that may be imported: all, none, or exactly those shown in the prompt."""
        if source.kind == TRUSTED:
            return self.plugin_files(source.path)
        if source.kind == DEPRECATED:
            return self._approve_deprecated(source.path)
        return self._approve_local(source.path)

    def _approve_local(self, path: Path) -> list[Path]:
        files = self.plugin_files(path, follow_links=False)
        reason = ""
        if not files:
            return []
        if any(not (p.name.isprintable() and str(path).isprintable()) for p in files):
            reason = "unsafe file names"
        elif not self.interactive or self._ask_fn is None:
            reason = "non-interactive run"
        elif self._ask_fn(self._prompt(path, files)).strip().lower() not in YES:
            reason = "declined"
        if reason:
            self.skipped.append((path, reason))
            return []
        return files

    def _approve_deprecated(self, path: Path) -> list[Path]:
        files = self.plugin_files(path)
        if files and self.automated():
            self.skipped.append((path, "deprecated location, not loaded in CI or pre-commit"))
            return []
        if files:
            self.deprecated.append(path)
        return files

    @staticmethod
    def _prompt(path: Path, files: list[Path]) -> str:
        names = ", ".join(p.stem for p in files[:PROMPT_NAMES]) + (", ..." if len(files) > PROMPT_NAMES else "")
        return (
            f"prism-ai-lint: {path} holds {len(files)} plugin(s) ({names}) from the current directory. "
            "They run as Python code. Load them? [y/N] "
        )

    def report(self, rep: Any) -> None:
        """Add one finding per skipped or deprecated directory, so the behaviour change is visible."""
        for path, reason in self.skipped:
            rep.add(
                "info",
                "PLUGIN_SKIPPED_UNTRUSTED",
                path,
                f"plugins not loaded ({reason}): code from the current directory runs only after consent",
            )
        for path in self.deprecated:
            rep.add(
                "warn",
                "PLUGIN_DIR_DEPRECATED",
                path,
                f"plugins loaded from the shared Claude Code directory; move them to {self.user_dir()}",
            )
