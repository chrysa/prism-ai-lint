"""Hooks that add context on every tool call or prompt, and hooks declared in two scopes (D-049)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

FREQUENT = ("PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit")
SCRIPT_EXT = (".js", ".cjs", ".mjs", ".ts", ".py", ".sh", ".bash")
CONTEXT_RE = re.compile(r'"?additionalContext"?\s*:\s*"((?:[^"\\]|\\.)*)"')
ECHO_RE = re.compile(r"^\s*(?:echo|printf)\s+(?:-[a-z]+\s+)?(['\"])(.+?)\1", re.S)
MAX_SCRIPT_BYTES = 512 * 1024


class HookContextChecker:
    """Report hooks that inject text into the context on high-frequency events, and duplicated hooks.

    `HOOK_CONTEXT_REPEATED` (info): a hook on PreToolUse, PostToolUse(Failure) or UserPromptSubmit that emits
    `additionalContext` (or, on UserPromptSubmit, prints text: stdout becomes context). The text is added on every
    matching call and stays in the conversation, so it is re-read on every later turn. `HOOK_DUPLICATE_SCOPE` (warn):
    the same handler in user and project settings runs twice, injecting or blocking twice. Read only.
    """

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        hooks = data.get("hooks") if isinstance(data, dict) else None
        return hooks if isinstance(hooks, dict) else {}

    @classmethod
    def _handlers(cls, path: Path) -> list[tuple[str, str, str]]:
        """(event, matcher, command) of every command handler in a settings file."""
        out = []
        for event, groups in cls._load(path).items():
            for group in groups if isinstance(groups, list) else []:
                if not isinstance(group, dict):
                    continue
                matcher = str(group.get("matcher", "") or "")
                out.extend(
                    (str(event), matcher, str(h["command"]).strip())
                    for h in group.get("hooks") or []
                    if isinstance(h, dict) and h.get("type", "command") == "command" and h.get("command")
                )
        return out

    @staticmethod
    def _script(command: str, base: Path) -> Path | None:
        for word in command.replace(";", " ").split():
            word = word.strip("'\"")
            word = re.sub(r"\$\{?CLAUDE_PROJECT_DIR\}?", str(base), word)
            word = os.path.expandvars(os.path.expanduser(word))
            if word.endswith(SCRIPT_EXT):
                p = Path(word) if Path(word).is_absolute() else base / word
                try:
                    if p.is_file() and p.stat().st_size <= MAX_SCRIPT_BYTES:
                        return p
                except OSError:
                    return None
        return None

    def _injection(self, event: str, command: str, base: Path) -> str | None:
        """Describe what the handler injects, or None when it injects nothing visible statically."""
        m = CONTEXT_RE.search(command)
        if m:
            return f"~{max(1, len(m.group(1)) // 4)} tokens"
        if event == "UserPromptSubmit":
            e = ECHO_RE.match(command)
            if e:
                return f"~{max(1, len(e.group(2)) // 4)} tokens"
        script = self._script(command, base)
        if script is not None:
            try:
                text = script.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                return None
            if "additionalContext" in text:
                return "context (size set at run time)"
        return None

    def _report_injections(self, path: Path, base: Path, rep: Any) -> None:
        for event, matcher, command in self._handlers(path):
            if event not in FREQUENT:
                continue
            what = self._injection(event, command, base)
            if what:
                where = f"{event} {matcher}".strip()
                rep.add(
                    "info",
                    "HOOK_CONTEXT_REPEATED",
                    path,
                    f"{where}: injects {what} on every matching call; it stays in context and is re-read every turn",
                )

    def check_repo(self, repo: Path, user_settings: Path, rep: Any) -> None:
        user = {(e, m, c) for e, m, c in self._handlers(user_settings)}
        for name in ("settings.json", "settings.local.json"):
            path = repo / ".claude" / name
            if not path.is_file():
                continue
            self._report_injections(path, repo, rep)
            for event, matcher, command in sorted(set(self._handlers(path)) & user):
                rep.add(
                    "warn",
                    "HOOK_DUPLICATE_SCOPE",
                    path,
                    f"{event} {matcher}".strip() + f": same hook also in user settings, runs twice ({command[:50]})",
                )

    def check_user(self, user_settings: Path, rep: Any) -> None:
        if user_settings.is_file():
            self._report_injections(user_settings, user_settings.parent, rep)
