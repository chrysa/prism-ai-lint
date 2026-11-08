"""A Codex configuration layer: the Codex home ($CODEX_HOME, ~/.codex) or a project .codex/ folder."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

from prism_ai_lint._runtime import read_text
from prism_ai_lint.report import Report


class CodexLayer:
    """Locate and read Codex layers; read-only, parse errors are reported on the given Report."""

    @staticmethod
    def home() -> Path:
        """The Codex home directory: $CODEX_HOME, else ~/.codex."""
        return Path(os.path.expanduser(os.environ.get("CODEX_HOME") or "~/.codex"))

    @staticmethod
    def in_use(repo: Path) -> bool:
        """True when the repository carries Codex-specific configuration."""
        return (
            (repo / ".codex").is_dir()
            or (repo / ".agents" / "skills").is_dir()
            or (repo / "AGENTS.override.md").exists()
        )

    @staticmethod
    def load_toml(path: Path, rep: Report) -> dict | None:
        """Parsed TOML table, None when absent; a parse error is reported (Codex refuses the file)."""
        raw = read_text(path)
        if raw is None:
            return None
        try:
            return tomllib.loads(raw)
        except tomllib.TOMLDecodeError as e:
            rep.add("error", "CODEX_TOML_INVALID", path, f"invalid TOML, Codex cannot load this file: {e}")
            return None

    @staticmethod
    def load_hooks_json(path: Path, rep: Report) -> dict | None:
        raw = read_text(path)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            rep.add("error", "CODEX_HOOK_SHAPE", path, f"invalid JSON, no hook in this file runs: {e}")
            return None
        if not isinstance(data, dict):
            rep.add("error", "CODEX_HOOK_SHAPE", path, "hooks.json must be a JSON object")
            return None
        return data

    @staticmethod
    def hook_commands(hooks: Any) -> list[tuple[str, str]]:
        """(event, command) for each command handler of a hooks table."""
        out: list[tuple[str, str]] = []
        if not isinstance(hooks, dict):
            return out
        for event, groups in hooks.items():
            for group in groups if isinstance(groups, list) else []:
                for handler in (group.get("hooks") or []) if isinstance(group, dict) else []:
                    if isinstance(handler, dict) and isinstance(handler.get("command"), str):
                        out.append((event, handler["command"]))  # noqa: PERF401
        return out
