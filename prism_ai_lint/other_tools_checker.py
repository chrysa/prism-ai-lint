"""Checks on the config of other agent tools (Codex, Gemini CLI, Cursor) and on headless CI runs.

Everything here is a report: a switch the user set on purpose is never edited, only named, so a
repair can not loosen anything. Key names follow each tool's public documentation; an unknown key
is ignored, never guessed.

- CODEX_SANDBOX_OPEN / CODEX_APPROVAL_NEVER: `.codex/config.toml` removes the sandbox or the prompts.
- GEMINI_AUTO_APPROVE / GEMINI_TRUST_OFF / GEMINI_HOOKS_ON: `.gemini/settings.json` removes a
  confirmation, the folder trust check, or turns on experimental hooks that run commands.
- CURSOR_RULE_NO_FRONTMATTER / CURSOR_RULE_ALWAYS_LARGE: a `.cursor/rules/*.mdc` rule that never
  applies as intended, or a large rule that is loaded in every request.
- HEADLESS_SKIP_PERMISSIONS / HEADLESS_NO_PERMISSION_MODE: a CI step runs `claude -p` with every
  check off, or with no permission mode or allow rule, so a run with nobody to answer stalls."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from prism_ai_lint._runtime import read_text
from prism_ai_lint.report import Report

ALWAYS_LARGE_CHARS = 8000  # about 2000 tokens loaded in every request
HEADLESS_RE = re.compile(r"\bclaude\b[^\n|;&]*?\s(?:-p|--print)\b")
PERMISSION_FLAGS = (
    "--permission-mode",
    "--allowedtools",
    "--allowed-tools",
    "--settings",
    "--dangerously-skip-permissions",
)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in ("true", "1", "yes", "on")


def _nested(data: Any, *keys: str) -> Any:
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data


class OtherToolsChecker:
    """Reports only: nothing here edits a config file or a workflow."""

    def check_repo(self, repo: Path, rep: Report) -> None:
        self._codex(repo / ".codex" / "config.toml", rep)
        self._gemini(repo / ".gemini" / "settings.json", rep)
        self._cursor(repo / ".cursor" / "rules", rep)
        self._headless(repo / ".github" / "workflows", rep)

    def _codex(self, path: Path, rep: Report) -> None:
        text = read_text(path) if path.is_file() else None
        if text is None:
            return
        try:
            cfg = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return
        if cfg.get("sandbox_mode") == "danger-full-access":
            rep.add(
                "warn",
                "CODEX_SANDBOX_OPEN",
                path,
                "sandbox_mode = danger-full-access: Codex runs commands with no sandbox in this project",
            )
        if cfg.get("approval_policy") == "never":
            rep.add(
                "info",
                "CODEX_APPROVAL_NEVER",
                path,
                "approval_policy = never: Codex runs every command without asking",
            )

    def _gemini(self, path: Path, rep: Report) -> None:
        text = read_text(path) if path.is_file() else None
        if text is None:
            return
        try:
            cfg = json.loads(text)
        except ValueError:
            return
        if not isinstance(cfg, dict):
            return
        auto = cfg.get("autoAccept") or _nested(cfg, "tools", "autoAccept")
        if (
            _truthy(auto)
            or str(cfg.get("approvalMode") or _nested(cfg, "general", "defaultApprovalMode")).lower() == "yolo"
        ):
            rep.add(
                "warn",
                "GEMINI_AUTO_APPROVE",
                path,
                "Gemini CLI approves tool calls without asking (autoAccept or yolo)",
            )
        trust = _nested(cfg, "security", "folderTrust", "enabled")
        if trust is not None and not _truthy(trust):
            rep.add(
                "warn",
                "GEMINI_TRUST_OFF",
                path,
                "security.folderTrust.enabled is off: untrusted folders load their config",
            )
        if _truthy(_nested(cfg, "hooks", "enabled")) or _truthy(_nested(cfg, "tools", "enableHooks")):
            rep.add(
                "info",
                "GEMINI_HOOKS_ON",
                path,
                "Gemini CLI hooks are on (experimental): a hook runs commands on events",
            )

    def _cursor(self, rules_dir: Path, rep: Report) -> None:
        for rule in sorted(rules_dir.glob("**/*.mdc")) if rules_dir.is_dir() else ():
            text = read_text(rule)
            if text is None:
                continue
            m = FRONTMATTER_RE.match(text)
            if not m:
                rep.add(
                    "info",
                    "CURSOR_RULE_NO_FRONTMATTER",
                    rule,
                    "no frontmatter: the rule has no description, globs or alwaysApply",
                )
                continue
            always = re.search(r"^alwaysApply:\s*(\S+)", m.group(1), re.M)
            if always and _truthy(always.group(1)) and len(text) > ALWAYS_LARGE_CHARS:
                rep.add(
                    "info",
                    "CURSOR_RULE_ALWAYS_LARGE",
                    rule,
                    f"alwaysApply with ~{len(text) // 4} tokens: loaded in every request; scope it with globs or a description",
                )

    def _headless(self, workflows: Path, rep: Report) -> None:
        files = [p for p in sorted(workflows.glob("*")) if p.suffix in (".yml", ".yaml")] if workflows.is_dir() else []
        for wf in files:
            text = read_text(wf)
            if not text or not HEADLESS_RE.search(text):
                continue
            lowered = text.lower()
            if "--dangerously-skip-permissions" in lowered:
                rep.add(
                    "warn",
                    "HEADLESS_SKIP_PERMISSIONS",
                    wf,
                    "claude -p runs with --dangerously-skip-permissions: every permission check is off in CI",
                )
            elif not any(flag in lowered for flag in PERMISSION_FLAGS):
                rep.add(
                    "info",
                    "HEADLESS_NO_PERMISSION_MODE",
                    wf,
                    "claude -p without --permission-mode or --allowedTools: recent versions start in manual mode, "
                    "so the run can stall waiting for an answer",
                )
