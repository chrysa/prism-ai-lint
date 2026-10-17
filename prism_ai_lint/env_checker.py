"""Checks for the `env` block and sandbox keys of a settings file.

Everything here is a report: an environment variable or a sandbox switch the user set on purpose
is never edited, only named, so a repair can not loosen anything."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prism_ai_lint.report import Report

# Switches that remove a safety prompt or a protection when they are on.
WEAKENING_VARS = (
    "CLAUDE_CODE_DISABLE_DANGEROUS_RM_TIMEOUT",
    "CLAUDE_CODE_DISABLE_INLINE_SHELL_RM_PROMPT",
    "CLAUDE_CODE_DISABLE_SUBSTITUTION_RM_PROMPT",
    "CLAUDE_CODE_DISABLE_POWERSHELL_CMD_RM_DENY",
    "CLAUDE_CODE_DISABLE_ADMIN_ENV_UNION",
)
OFF_VALUES = {"", "0", "false", "no", "off"}

# Variable -> why it no longer does anything useful.
DEPRECATED_VARS = {
    "ANTHROPIC_SMALL_FAST_MODEL": "deprecated, use ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION": "removed, now a no-op",
    "CLAUDE_CODE_CONNECT_TIMEOUT_MS": "removed, now a no-op",
    "CLAUDE_CODE_AUTO_BACKGROUND_WORKER_CHECKIN_SECONDS": "removed, now a no-op",
    "CLAUDE_CODE_ENABLE_OPUS_4_7_FAST_MODE": "removed, now a no-op",
    "CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE": "removed, now a no-op",
    "CLAUDE_CODE_ENABLE_AUTO_MODE": "has no effect",
}

# Variable -> documented default. A value above it pays tokens on every large output.
RAISED_CAPS = {
    "MAX_MCP_OUTPUT_TOKENS": 25000,
    "BASH_MAX_OUTPUT_LENGTH": 30000,
    "CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS": 25000,
}


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() not in OFF_VALUES


def _number(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except ValueError:
        return None


class EnvChecker:
    """Report risky or wasteful `env` entries and a weakened sandbox. Never edits."""

    def check(self, settings: Any, path: Path, rep: Report) -> None:
        if not isinstance(settings, dict):
            return
        env = settings.get("env")
        if isinstance(env, dict):
            self._check_env(env, path, rep)
        sandbox = settings.get("sandbox")
        if isinstance(sandbox, dict) and _truthy(sandbox.get("enableWeakerNestedSandbox", False)):
            rep.add(
                "warn",
                "ENV_SANDBOX_WEAK",
                path,
                "sandbox.enableWeakerNestedSandbox is on: the sandbox runs with weaker isolation",
            )

    def _check_env(self, env: dict, path: Path, rep: Report) -> None:
        for name in WEAKENING_VARS:
            if name in env and _truthy(env[name]):
                rep.add(
                    "warn",
                    "ENV_WEAKENS_SECURITY",
                    path,
                    f"env.{name} turns off a safety prompt or protection; remove it unless it is deliberate",
                )
        for name, why in DEPRECATED_VARS.items():
            if name in env:
                rep.add("info", "ENV_DEPRECATED", path, f"env.{name}: {why}")
        for name, default in RAISED_CAPS.items():
            value = _number(env.get(name)) if name in env else None
            if value is not None and value > default:
                rep.add(
                    "info",
                    "ENV_TOKEN_CAP",
                    path,
                    f"env.{name}={value} is above the default {default}: one large output costs more tokens",
                )
        if str(env.get("CLAUDE_CODE_PROMPT_CACHE_TTL", "")).strip().lower() == "1h":
            rep.add(
                "info",
                "ENV_TOKEN_CAP",
                path,
                "env.CLAUDE_CODE_PROMPT_CACHE_TTL=1h bills cache writes at a higher rate",
            )
