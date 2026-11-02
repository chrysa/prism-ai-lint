"""The prism-ai-lint guard as a hook command: recognise a plain call and build the canonical one."""

from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path


class GuardCommand:
    """A guard hook is copied between tools only as the canonical call of this installation, and only
    when the existing hook is a plain call of it: a command string is never copied verbatim."""

    PATTERN = re.compile(r"(prism-ai-lint\.py|prism_ai_lint[/\\]_engine\.py|\bprism-ai-lint)\b.*--guard\b")
    SHELL_META = re.compile(r"[;&|`$<>(){}\n\\*?!]")
    CODEX_MATCHER = "Bash|apply_patch"
    CLAUDE_MATCHER = "Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell|Monitor"  # as session_settings

    def __init__(self) -> None:
        self.engine = Path(__file__).resolve().parent / "_engine.py"
        self.wrapper = self.engine.parent.parent / "prism-ai-lint.py"

    def mentions_guard(self, handler: dict) -> bool:
        return bool(self.PATTERN.search(str(handler)))

    @staticmethod
    def tokens(handler: dict) -> list[str] | None:
        """The argv a command hook handler runs (command + args), or None when it cannot be split."""
        cmd = handler.get("command")
        if not isinstance(cmd, str):
            return None
        args = handler.get("args")
        if isinstance(args, list):
            return [cmd, *map(str, args)]
        try:
            return shlex.split(cmd)
        except ValueError:
            return None

    def is_plain(self, handler: dict) -> bool:
        """True for a bare `[python] <prism-ai-lint entry point> --guard` call of this installation."""
        tokens = self.tokens(handler) or []
        if not tokens or tokens[-1] != "--guard" or any(self.SHELL_META.search(t) for t in tokens):
            return False
        body = tokens[:-1]
        if len(body) == 2 and re.fullmatch(r"(\S*/)?python[\d.]*", body[0]):
            body = body[1:]
        if len(body) != 1:
            return False
        try:
            target = Path(os.path.expanduser(body[0])).resolve()
        except (OSError, RuntimeError):
            return False
        return target in (self.engine, self.wrapper)

    def codex_handler(self) -> dict:
        return {
            "type": "command",
            "command": f"{shlex.quote(sys.executable)} {shlex.quote(str(self.engine))} --guard",
            "timeout": 30,
            "statusMessage": "prism-ai-lint guard",
        }

    def claude_handler(self) -> dict:
        return {
            "type": "command",
            "command": sys.executable,
            "args": [str(self.engine), "--guard"],
            "timeout": 30,
            "onFailure": "block",
        }
