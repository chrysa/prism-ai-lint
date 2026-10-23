"""Checks on a repo's prompt-engineering hook (`.claude/ape/ape_hook.py`) and on UserPromptSubmit hooks that
match too broadly. Reports only: nothing here edits a hook.

- APE_UNWIRED: the hook script is in the repo but no UserPromptSubmit hook runs it.
- APE_DEAD_WIRING: a UserPromptSubmit hook runs it but the script is not there (a guarded command then
  skips it silently).
- APE_STDIN_RAW: the script reads stdin as text. Claude Code sends JSON, so a triage on the text never
  matches and the full spec is injected on every prompt, where it stays in the context.
- HOOK_BROAD_MATCH: a UserPromptSubmit shell hook tests the whole JSON input for a `/word` substring, so any
  prompt that merely mentions a path like `.claude/ape/` triggers it."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from prism_ai_lint._runtime import lenient_json, read_text
from prism_ai_lint.report import Report

HOOK_REL = Path(".claude") / "ape" / "ape_hook.py"
SETTINGS = ("settings.json", "settings.local.json")
# case "$in" in *"/ape"* ... : a substring test on the whole hook input.
BROAD_CASE = re.compile(r"""case\s+["']?\$\{?\w+\}?["']?\s+in\s+\*\\?["']?/[\w.-]+\\?["']?\*""")


def _prompt_commands(settings: Any) -> list[str]:
    """Commands of the UserPromptSubmit hooks of a settings object."""
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    blocks = hooks.get("UserPromptSubmit") if isinstance(hooks, dict) else None
    out: list[str] = []
    for block in blocks if isinstance(blocks, list) else []:
        for handler in block.get("hooks", []) if isinstance(block, dict) else []:
            if isinstance(handler, dict) and isinstance(handler.get("command"), str):
                out.append(handler["command"])
    return out


class ApeHookChecker:
    """Reports only."""

    def check_repo(self, repo: Path, rep: Report) -> None:
        commands: list[tuple[Path, str]] = []
        for name in SETTINGS:
            path = repo / ".claude" / name
            if path.is_file():
                commands += [(path, c) for c in _prompt_commands(lenient_json(read_text(path) or "{}")[0])]
        script = repo / HOOK_REL
        wired = [(p, c) for p, c in commands if "ape_hook" in c]
        if script.is_file():
            if not wired:
                rep.add(
                    "info",
                    "APE_UNWIRED",
                    script,
                    "ape_hook.py is present but no UserPromptSubmit hook runs it, so it does nothing",
                )
            self._check_script(script, rep)
        elif wired:
            rep.add(
                "info",
                "APE_DEAD_WIRING",
                wired[0][0],
                "a UserPromptSubmit hook runs .claude/ape/ape_hook.py, which is not in the repo",
            )
        self._broad(commands, rep)

    def check_user(self, config_dir: Path, rep: Report) -> None:
        """The user-level settings file: only the over-broad match applies there."""
        for name in SETTINGS:
            path = config_dir / name
            if path.is_file():
                commands = [(path, c) for c in _prompt_commands(lenient_json(read_text(path) or "{}")[0])]
                self._broad(commands, rep)

    @staticmethod
    def _broad(commands: list[tuple[Path, str]], rep: Report) -> None:
        for path, command in commands:
            if BROAD_CASE.search(command):
                rep.add(
                    "info",
                    "HOOK_BROAD_MATCH",
                    path,
                    "a UserPromptSubmit hook tests the whole input for a '/word' substring: any prompt that "
                    "mentions such a path triggers it; match the start of the prompt instead",
                )

    @staticmethod
    def _check_script(script: Path, rep: Report) -> None:
        text = read_text(script) or ""
        if "stdin" in text and "json" not in text.lower():
            rep.add(
                "warn",
                "APE_STDIN_RAW",
                script,
                "the hook reads stdin as plain text but Claude Code sends JSON: its triage never matches and "
                "the full spec is injected on every prompt (read the `prompt` field)",
            )
