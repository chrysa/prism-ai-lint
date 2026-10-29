"""Checks on `Task(...)` permission rules and plugin marketplace sources of a settings file.

Everything here is a report: a rule or a source the user wrote is never edited, only named, so a
repair can not loosen anything.

- TASK_RULE_UNKNOWN_AGENT: a `Task(Name)` rule targets a subagent that is not defined here, so the
  rule does nothing (a deny that guards nothing is worse than none: it reads as a protection).
- PLUGIN_SOURCE_UNPINNED: a marketplace is fetched from a moving branch, so what runs in the
  session can change without a review."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from prism_ai_lint._runtime import read_text
from prism_ai_lint.report import Report

TASK_RULE_RE = re.compile(r"^(?:Task|Agent)\((?P<name>[^)]*)\)$")
BUILTIN_AGENTS = {"explore", "plan", "general-purpose", "statusline-setup", "claude-code-guide"}
PERMISSION_LISTS = ("allow", "ask", "deny")
MOVING_REFS = {"", "main", "master", "head", "develop", "latest"}
PINNABLE_SOURCES = {"github", "git", "url"}
NAME_RE = re.compile(r"^name:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.M)


def _defined_agents(base: Path) -> set[str]:
    """Names of the subagents defined under the settings file's project or config directory."""
    names: set[str] = set()
    for root in (base / ".claude" / "agents", base / "agents"):
        for md in root.glob("**/*.md") if root.is_dir() else ():
            names.add(md.stem.lower())
            m = NAME_RE.search((read_text(md) or "")[:2000])
            if m:
                names.add(m.group(1).strip().lower())
    return names


class PermissionRulesChecker:
    """Report `Task(...)` rules aimed at nothing and marketplaces that are not pinned. Never edits."""

    def check(self, settings: Any, path: Path, rep: Report, base: Path) -> None:
        if not isinstance(settings, dict):
            return
        self._task_rules(settings, path, rep, base)
        self._marketplaces(settings, path, rep)

    def _task_rules(self, settings: dict, path: Path, rep: Report, base: Path) -> None:
        perms = settings.get("permissions")
        if not isinstance(perms, dict):
            return
        targets: list[tuple[str, str]] = []
        for key in PERMISSION_LISTS:
            rules = perms.get(key)
            for rule in rules if isinstance(rules, list) else ():
                m = TASK_RULE_RE.match(rule.strip()) if isinstance(rule, str) else None
                if m and m.group("name").strip() not in ("", "*"):
                    targets.append((key, m.group("name").strip()))
        if not targets:
            return
        known = _defined_agents(base) | BUILTIN_AGENTS
        # A plugin may ship the agent, which this file can not show: name the doubt in the message.
        plugins = bool(settings.get("enabledPlugins"))
        for key, name in targets:
            if name.lower() in known:
                continue
            tail = " (an enabled plugin may provide it)" if plugins else ""
            rep.add(
                "info",
                "TASK_RULE_UNKNOWN_AGENT",
                path,
                f"permissions.{key}: Task({name}) targets a subagent not defined here, so the rule does nothing{tail}",
            )

    def _marketplaces(self, settings: dict, path: Path, rep: Report) -> None:
        markets = settings.get("extraKnownMarketplaces")
        if not isinstance(markets, dict):
            return
        for name, cfg in markets.items():
            source = cfg.get("source") if isinstance(cfg, dict) else None
            if not isinstance(source, dict) or source.get("source") not in PINNABLE_SOURCES:
                continue
            ref = str(source.get("ref") or source.get("sha") or source.get("commit") or "").strip().lower()
            if ref in MOVING_REFS:
                rep.add(
                    "info",
                    "PLUGIN_SOURCE_UNPINNED",
                    path,
                    f"extraKnownMarketplaces.{name}: no tag or commit pinned, so the plugins can change without a review",
                )
