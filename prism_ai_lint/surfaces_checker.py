"""Checks per product surface: Claude Code (CLI, IDE extension, GitHub action) and Codex (CLI, IDE, cloud, ChatGPT).

Everything here is a report: a switch the user set on purpose is never edited, only named, so a
repair can not loosen anything. A literal secret is never echoed, only its location.

- VSCODE_CLAUDE_BYPASS: the Claude Code extension starts with permission checks off.
- CLAUDE_ACTION_UNPINNED / CLAUDE_ACTION_OPEN_USERS / HEADLESS_SKIP_PERMISSIONS: the GitHub action
  runs from a moving tag, accepts any commenter, or has every check off.
- AGENT_CLI_UNPINNED: the Claude Code or Codex CLI is installed from a moving version.
- CODEX_TRUST_BROAD / CODEX_MCP_LITERAL_SECRET: `.codex/config.toml` trusts a whole home or root
  directory, or holds a literal credential for an MCP server."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from prism_ai_lint._runtime import read_text
from prism_ai_lint.report import Report

CLI_PACKAGES = ("@anthropic-ai/claude-code", "@openai/codex")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ACTION_RE = re.compile(r"uses:\s*['\"]?((?:anthropics/claude-code-action|openai/codex-action)[\w./-]*)@([^\s'\"#]+)")
INSTALL_RE = re.compile(
    r"(?:npm|pnpm|yarn|bun)\s+(?:i|install|add)\b[^\n]*?(@anthropic-ai/claude-code|@openai/codex)(?![\w/-])(@\S+)?"
)
MOVING_VERSIONS = {"latest", "next", "*", ""}
SECRET_KEY_RE = re.compile(r"(?:key|token|secret|password|credential)", re.I)
BROAD_TRUST = {"/", "~", "$home", "/home", "/users", "c:\\", "c:/"}
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in ("true", "1", "yes", "on")


class SurfacesChecker:
    """Reports only: nothing here edits a config file, a workflow or an install script."""

    def check_repo(self, repo: Path, rep: Report) -> None:
        self._vscode(repo / ".vscode" / "settings.json", rep)
        self._codex(repo / ".codex" / "config.toml", rep)
        self._package_json(repo / "package.json", rep)
        for path in self._install_files(repo):
            self._install_script(path, rep)
        for path in self._workflows(repo):
            self._action(path, rep)

    @staticmethod
    def _workflows(repo: Path) -> list[Path]:
        folder = repo / ".github" / "workflows"
        return [p for p in sorted(folder.glob("*")) if p.suffix in (".yml", ".yaml")] if folder.is_dir() else []

    @classmethod
    def _install_files(cls, repo: Path) -> list[Path]:
        found = [p for p in sorted(repo.glob("Dockerfile*")) if p.is_file()]
        found += [p for p in sorted(repo.glob(".devcontainer/*")) if p.is_file() and p.suffix in ("", ".json", ".sh")]
        found += [p for p in (repo / "Makefile",) if p.is_file()]
        return found + cls._workflows(repo)

    def _vscode(self, path: Path, rep: Report) -> None:
        text = read_text(path) if path.is_file() else None
        if text is None:
            return
        try:
            cfg = json.loads(LINE_COMMENT_RE.sub("", text))
        except ValueError:
            return
        if not isinstance(cfg, dict):
            return
        if _truthy(cfg.get("claudeCode.allowDangerouslySkipPermissions")) or (
            str(cfg.get("claudeCode.initialPermissionMode", "")) == "bypassPermissions"
        ):
            rep.add(
                "warn",
                "VSCODE_CLAUDE_BYPASS",
                path,
                "the Claude Code extension starts with permission checks off for everyone who opens this folder",
            )

    def _codex(self, path: Path, rep: Report) -> None:
        text = read_text(path) if path.is_file() else None
        if text is None:
            return
        try:
            cfg = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return
        projects = cfg.get("projects")
        for key, value in projects.items() if isinstance(projects, dict) else ():
            trusted = isinstance(value, dict) and value.get("trust_level") == "trusted"
            if trusted and str(key).strip().rstrip("/\\").lower() in {b.rstrip("/\\") for b in BROAD_TRUST} | {""}:
                rep.add(
                    "warn",
                    "CODEX_TRUST_BROAD",
                    path,
                    f"projects.{key}: trust_level = trusted on a home or root directory trusts every project below it",
                )
        servers = cfg.get("mcp_servers")
        for name, server in servers.items() if isinstance(servers, dict) else ():
            if not isinstance(server, dict):
                continue
            values: dict[str, Any] = {"bearer_token": server.get("bearer_token")}
            for table in ("env", "http_headers"):
                if isinstance(server.get(table), dict):
                    values.update({f"{table}.{k}": v for k, v in server[table].items()})
            for label, value in values.items():
                is_secret_name = SECRET_KEY_RE.search(label) or label.endswith("Authorization")
                if (
                    is_secret_name
                    and isinstance(value, str)
                    and len(value) >= 8
                    and not value.startswith(("$", "env:"))
                ):
                    rep.add(
                        "warn",
                        "CODEX_MCP_LITERAL_SECRET",
                        path,
                        f"mcp_servers.{name}.{label} holds a literal credential; read it from an environment variable",
                    )

    def _package_json(self, path: Path, rep: Report) -> None:
        text = read_text(path) if path.is_file() else None
        if text is None:
            return
        try:
            pkg = json.loads(text)
        except ValueError:
            return
        for section in ("dependencies", "devDependencies", "optionalDependencies"):
            deps = pkg.get(section) if isinstance(pkg, dict) else None
            for name in CLI_PACKAGES:
                if isinstance(deps, dict) and name in deps and str(deps[name]).strip().lower() in MOVING_VERSIONS:
                    rep.add(
                        "info",
                        "AGENT_CLI_UNPINNED",
                        path,
                        f"{section}.{name} follows a moving version ({deps[name]!r}); pin a release",
                    )

    def _install_script(self, path: Path, rep: Report) -> None:
        text = read_text(path)
        if not text:
            return
        for m in INSTALL_RE.finditer(text):
            version = (m.group(2) or "")[1:].strip().lower()
            if version in MOVING_VERSIONS:
                rep.add(
                    "info",
                    "AGENT_CLI_UNPINNED",
                    path,
                    f"{m.group(1)} is installed without a pinned version; every build can get a different CLI",
                )
                return

    def _action(self, path: Path, rep: Report) -> None:
        text = read_text(path)
        if not text:
            return
        actions = ACTION_RE.findall(text)
        if not actions:
            return
        for name, ref in actions:
            if not SHA_RE.match(ref):
                rep.add(
                    "info",
                    "CLAUDE_ACTION_UNPINNED",
                    path,
                    f"{name}@{ref}: a tag can move; pin the action to a commit",
                )
        if re.search(r"allowed_non_write_users:\s*['\"]?\*", text):
            rep.add(
                "warn",
                "CLAUDE_ACTION_OPEN_USERS",
                path,
                "allowed_non_write_users = *: any commenter without write access can trigger the agent",
            )
        if "--dangerously-skip-permissions" in text.lower():
            rep.add(
                "warn",
                "HEADLESS_SKIP_PERMISSIONS",
                path,
                "the action runs with --dangerously-skip-permissions: every permission check is off in CI",
            )
