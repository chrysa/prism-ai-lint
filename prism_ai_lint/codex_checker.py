"""Codex (OpenAI) configuration checks: config.toml, hooks, rules, custom agents, skills and AGENTS.md.

Reports only. TOML has no writer in the standard library, so nothing here edits a Codex file:
every finding names the line to change and leaves the change to the human."""

from __future__ import annotations

import difflib
import re
import shlex
from pathlib import Path
from typing import Any

from prism_ai_lint._markup import split_frontmatter
from prism_ai_lint._reference import (
    CODEX_AGENT_REQUIRED,
    CODEX_APPROVAL_DEPRECATED,
    CODEX_APPROVAL_POLICIES,
    CODEX_APPROVAL_UNSUPPORTED,
    CODEX_DEPRECATED_FEATURES,
    CODEX_DEPRECATED_KEYS,
    CODEX_EFFORTS,
    CODEX_HOOK_EVENTS,
    CODEX_HOOK_HANDLER_TYPES,
    CODEX_HOOK_SKIPPED_TYPES,
    CODEX_KNOWN_KEYS,
    CODEX_MCP_FIELDS,
    CODEX_PERMISSION_PROFILES,
    CODEX_PROJECT_DOC_MAX_BYTES,
    CODEX_PROJECT_IGNORED_KEYS,
    CODEX_SANDBOX_MODES,
    CODEX_TRUST_LEVELS,
)
from prism_ai_lint._runtime import log, read_text
from prism_ai_lint.codex_layer import CodexLayer
from prism_ai_lint.codex_rules import CodexRules
from prism_ai_lint.mcp_checker import McpChecker
from prism_ai_lint.report import Report
from prism_ai_lint.rules_parse_error import RulesParseError
from prism_ai_lint.secret_scan import InlineSecretScanner

AGENT_FIELDS = frozenset({"name", "description", "developer_instructions", "nickname_candidates"})
SHORT_HOOK_EVENTS = frozenset({"SessionEnd", "Interrupt"})  # 1 s default, 3 s at most
INTERPRETERS = frozenset({"bash", "sh", "zsh", "fish", "python", "python3", "node", "ruby", "perl", "sudo"})


class CodexChecker:
    """Validate a Codex home (~/.codex) and a project .codex/ layer; records findings, never writes."""

    def __init__(self, secrets: InlineSecretScanner) -> None:
        self._secrets = secrets

    @staticmethod
    def _table(value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    # ---- entry points --------------------------------------------------------------------------

    def check_user(self, policy: dict, rep: Report) -> None:
        home = CodexLayer.home()
        if not home.is_dir():
            log(1, f"Codex home absent: {home}")
            return
        log(1, f"Codex user scope: {home}")
        cfg = self._check_layer(home, "user", policy, rep)
        limit = self._doc_limit(cfg)
        doc = next((p for p in (home / "AGENTS.override.md", home / "AGENTS.md") if (read_text(p) or "").strip()), None)
        if doc is not None:
            self._check_doc_size(doc, limit, rep)
        self._check_skills(Path.home() / ".agents" / "skills", rep)

    def check_repo(self, repo: Path, policy: dict, rep: Report) -> None:
        layer = repo / ".codex"
        cfg = self._check_layer(layer, "project", policy, rep) if layer.is_dir() else None
        self._check_skills(repo / ".agents" / "skills", rep)
        if not (CodexLayer.in_use(repo) or CodexLayer.home().is_dir()):
            return
        override, base = repo / "AGENTS.override.md", repo / "AGENTS.md"
        if (read_text(override) or "").strip() and base.exists():
            rep.add(
                "warn",
                "CODEX_OVERRIDE_SHADOW",
                override,
                "Codex reads AGENTS.override.md and skips AGENTS.md in this folder, while Claude Code reads "
                "AGENTS.md: the two tools follow different instructions; merge the override into AGENTS.md",
            )
        doc = next((p for p in (override, base) if (read_text(p) or "").strip()), None)
        if doc is not None:
            user_cfg = CodexLayer.load_toml(CodexLayer.home() / "config.toml", Report()) if cfg is None else cfg
            self._check_doc_size(doc, self._doc_limit(user_cfg), rep)

    # ---- one config layer --------------------------------------------------------------------

    def _check_layer(self, layer: Path, scope: str, policy: dict, rep: Report) -> dict | None:
        cfg_path = layer / "config.toml"
        cfg = CodexLayer.load_toml(cfg_path, rep)
        if cfg is not None:
            rep.stats["Codex config files"] = rep.stats.get("Codex config files", 0) + 1
            self.check_config(cfg, cfg_path, scope, policy, rep)
        hooks_path = layer / "hooks.json"
        hooks_file = CodexLayer.load_hooks_json(hooks_path, rep)
        if hooks_file is not None:
            self.check_hooks(hooks_file.get("hooks"), hooks_path, rep)
            if cfg is not None and cfg.get("hooks"):
                rep.add(
                    "warn",
                    "CODEX_HOOKS_DUAL",
                    hooks_path,
                    "hooks.json and inline [hooks] in config.toml are both set in this layer: Codex merges them and "
                    "warns at startup; keep one representation",
                )
        rules_dir = layer / "rules"
        if rules_dir.is_dir():
            for f in sorted(rules_dir.glob("*.rules")):
                self.check_rules(f, policy, rep)
        agents_dir = layer / "agents"
        if agents_dir.is_dir():
            for f in sorted(agents_dir.glob("*.toml")):
                self.check_agent(f, policy, rep)
        return cfg

    def check_config(self, cfg: dict, path: Path, scope: str, policy: dict, rep: Report) -> None:
        self._check_keys(cfg, path, scope, policy, rep)
        self._check_sandbox(cfg, path, scope, rep)
        self._check_permissions(cfg, path, rep)
        self._check_projects(cfg, path, rep)
        self._check_mcp(cfg, path, policy, rep)
        self._check_shell_env(cfg, path, rep)
        self._check_effort(cfg, path, policy, rep)
        if isinstance(cfg.get("hooks"), dict):
            self.check_hooks(cfg["hooks"], path, rep)
        features = self._table(cfg.get("features"))
        if features.get("hooks") is False or (features.get("codex_hooks") is False and "hooks" not in features):
            rep.add(
                "warn",
                "CODEX_HOOKS_DISABLED",
                path,
                "[features] hooks = false: no lifecycle hook runs, including a prism-ai-lint guard",
            )

    def _check_keys(self, cfg: dict, path: Path, scope: str, policy: dict, rep: Report) -> None:
        extra = set(policy.get("codex", {}).get("extra_keys") or [])
        for key in cfg:
            if scope == "agent" and key in AGENT_FIELDS:
                continue
            if key in CODEX_DEPRECATED_KEYS:
                rep.add("warn", "CODEX_DEPRECATED_KEY", path, f"{key} is deprecated: use {CODEX_DEPRECATED_KEYS[key]}")
            elif key not in CODEX_KNOWN_KEYS and key not in extra:
                close = difflib.get_close_matches(key, CODEX_KNOWN_KEYS, n=1, cutoff=0.8)
                hint = f" (did you mean {close[0]!r}?)" if close else ""
                rep.add("warn", "CODEX_UNKNOWN_KEY", path, f"unknown key {key!r}{hint}")
            if scope == "project" and key in CODEX_PROJECT_IGNORED_KEYS:
                rep.add(
                    "warn",
                    "CODEX_PROJECT_IGNORED",
                    path,
                    f"{key} is ignored in a project .codex/config.toml: set it in ~/.codex/config.toml",
                )
        features = cfg.get("features")
        if isinstance(features, dict):
            for flag, instead in CODEX_DEPRECATED_FEATURES.items():
                if flag in features:
                    rep.add("warn", "CODEX_DEPRECATED_KEY", path, f"features.{flag} is deprecated: use {instead}")

    def _check_sandbox(self, cfg: dict, path: Path, scope: str, rep: Report) -> None:
        approval = cfg.get("approval_policy")
        if isinstance(approval, str):
            if approval in CODEX_APPROVAL_DEPRECATED:
                rep.add(
                    "warn",
                    "CODEX_APPROVAL_DEPRECATED",
                    path,
                    f"approval_policy = {approval!r} is deprecated: use {CODEX_APPROVAL_DEPRECATED[approval]}",
                )
            elif approval in CODEX_APPROVAL_UNSUPPORTED or approval not in CODEX_APPROVAL_POLICIES:
                rep.add(
                    "error",
                    "CODEX_APPROVAL_INVALID",
                    path,
                    f"approval_policy = {approval!r} is not supported (on-request, never, or {{ granular = ... }})",
                )
        elif approval is not None and not (isinstance(approval, dict) and isinstance(approval.get("granular"), dict)):
            rep.add("error", "CODEX_APPROVAL_INVALID", path, "approval_policy table needs a granular = { ... } entry")
        mode = cfg.get("sandbox_mode")
        if mode is not None and mode not in CODEX_SANDBOX_MODES:
            rep.add(
                "error", "CODEX_SANDBOX_INVALID", path, f"sandbox_mode = {mode!r} is not one of {CODEX_SANDBOX_MODES}"
            )
        full = mode == "danger-full-access" or cfg.get("default_permissions") == ":danger-full-access"
        if full and approval == "never":
            rep.add(
                "error",
                "CODEX_NO_GUARDRAILS",
                path,
                "full access without any approval: every command and edit runs unchecked; use "
                'sandbox_mode = "workspace-write" with approval_policy = "on-request"',
            )
        elif full:
            where = "committed for every teammate" if scope == "project" else "in every session"
            rep.add(
                "warn",
                "CODEX_SANDBOX_FULL_ACCESS",
                path,
                f"danger-full-access turns the sandbox off ({where}); prefer workspace-write",
            )
        if cfg.get("default_permissions") and ("sandbox_mode" in cfg or "sandbox_workspace_write" in cfg):
            rep.add(
                "warn",
                "CODEX_PERMISSIONS_CONFLICT",
                path,
                "default_permissions is combined with sandbox_mode or [sandbox_workspace_write]: the docs say not to "
                "combine them; keep one model",
            )
        sww = cfg.get("sandbox_workspace_write")
        if isinstance(sww, dict) and sww.get("network_access") is True:
            rep.add(
                "info",
                "CODEX_NETWORK_OPEN",
                path,
                "sandbox_workspace_write.network_access = true: sandboxed commands can reach the network",
            )

    def _check_permissions(self, cfg: dict, path: Path, rep: Report) -> None:
        perms = cfg.get("permissions")
        if not isinstance(perms, dict):
            return
        for name, prof in perms.items():
            if not isinstance(prof, dict):
                continue
            if prof.get("extends") == ":danger-full-access":
                rep.add(
                    "error",
                    "CODEX_PERMISSION_INVALID",
                    path,
                    f"permissions.{name}: extends = ':danger-full-access' is rejected by Codex",
                )
            elif isinstance(prof.get("extends"), str) and prof["extends"].startswith(":"):
                if prof["extends"] not in CODEX_PERMISSION_PROFILES:
                    rep.add(
                        "error",
                        "CODEX_PERMISSION_INVALID",
                        path,
                        f"permissions.{name}: unknown built-in profile {prof['extends']!r}",
                    )
            net = self._table(prof.get("network"))
            risky = sorted(k for k, v in net.items() if k.startswith("dangerously_") and v is True)
            if risky:
                rep.add(
                    "warn",
                    "CODEX_PERMISSION_DANGEROUS",
                    path,
                    f"permissions.{name}.network: {', '.join(risky)} enabled",
                )

    def _check_projects(self, cfg: dict, path: Path, rep: Report) -> None:
        projects = cfg.get("projects")
        if not isinstance(projects, dict):
            return
        for where, entry in projects.items():
            level = entry.get("trust_level") if isinstance(entry, dict) else None
            if level is not None and level not in CODEX_TRUST_LEVELS:
                rep.add("error", "CODEX_TRUST_INVALID", path, f"projects.{where!r}: trust_level {level!r} is unknown")

    def _check_mcp(self, cfg: dict, path: Path, policy: dict, rep: Report) -> None:
        servers = cfg.get("mcp_servers")
        if not isinstance(servers, dict):
            return
        enabled = 0
        for name, server in servers.items():
            rep.stats["Codex MCP servers"] = rep.stats.get("Codex MCP servers", 0) + 1
            if not isinstance(server, dict) or not (server.get("command") or server.get("url")):
                rep.add("error", "CODEX_MCP_SHAPE", path, f"mcp_servers.{name}: needs 'command' or 'url'")
                continue
            enabled += server.get("enabled", True) is not False
            unknown = sorted(set(server) - CODEX_MCP_FIELDS)
            if unknown:
                rep.add(
                    "warn",
                    "CODEX_MCP_UNKNOWN_FIELD",
                    path,
                    f"mcp_servers.{name}: unknown field(s) {', '.join(unknown[:4])}",
                )
            for sect in ("env", "http_headers"):
                if isinstance(server.get(sect), dict):
                    self._secrets.check_env_secrets(server[sect], path, rep, f"mcp_servers.{name}.{sect}", "report")
            literal = {k: server[k] for k in ("bearer_token", "experimental_bearer_token") if k in server}
            if literal:  # not Codex fields: a token written here is a committed secret, never read by Codex
                self._secrets.check_env_secrets(literal, path, rep, f"mcp_servers.{name}", "report")
            command = server.get("command")
            if isinstance(command, str) and not server.get("url") and not McpChecker._command_found(command, path):
                try:
                    first = shlex.split(command)[0]
                except (ValueError, IndexError):
                    first = command
                rep.add("info", "CODEX_MCP_BROKEN", path, f"mcp_servers.{name}: command {first!r} not found")
        cap = policy.get("mcp", {}).get("max_servers", 6)
        if enabled > cap:
            rep.add(
                "info",
                "CODEX_MCP_MANY",
                path,
                f"{enabled} enabled MCP servers (more than {cap}): each one's tool list costs tokens in every turn; "
                "disable the ones a project does not use (enabled = false)",
            )

    def _check_shell_env(self, cfg: dict, path: Path, rep: Report) -> None:
        sep = cfg.get("shell_environment_policy")
        if not isinstance(sep, dict):
            return
        if sep.get("filters") and ("exclude" in sep or "include_only" in sep):
            rep.add(
                "warn",
                "CODEX_SHELL_ENV_MIXED",
                path,
                "shell_environment_policy mixes filters with the legacy exclude/include_only arrays; use filters only",
            )
        if isinstance(sep.get("set"), dict):
            self._secrets.check_env_secrets(sep["set"], path, rep, "shell_environment_policy.set", "report")

    def _check_effort(self, cfg: dict, path: Path, policy: dict, rep: Report) -> None:
        ceiling = str(policy.get("codex", {}).get("max_effort", "high"))
        if ceiling not in CODEX_EFFORTS:
            return
        agents = self._table(cfg.get("agents"))
        for key, value in (
            ("model_reasoning_effort", cfg.get("model_reasoning_effort")),
            ("agents.default_subagent_reasoning_effort", agents.get("default_subagent_reasoning_effort")),
        ):
            if value in CODEX_EFFORTS and CODEX_EFFORTS.index(value) > CODEX_EFFORTS.index(ceiling):
                rep.add(
                    "info",
                    "CODEX_EFFORT_HIGH",
                    path,
                    f"{key} = {value!r} is above {ceiling!r}: more reasoning tokens on every turn; raise it per task",
                )

    # ---- hooks, rules, agents, skills --------------------------------------------------------

    def check_hooks(self, hooks: Any, path: Path, rep: Report) -> None:
        if hooks is None:
            return
        if not isinstance(hooks, dict):
            rep.add("error", "CODEX_HOOK_SHAPE", path, "hooks must be a table of events")
            return
        for event, groups in hooks.items():
            if event == "state":
                continue
            if event not in CODEX_HOOK_EVENTS:
                close = difflib.get_close_matches(event, CODEX_HOOK_EVENTS, n=1, cutoff=0.7)
                hint = f" (did you mean {close[0]!r}?)" if close else ""
                rep.add("error", "CODEX_HOOK_EVENT", path, f"unknown hook event {event!r}{hint}: it never fires")
                continue
            if not isinstance(groups, list):
                rep.add("error", "CODEX_HOOK_SHAPE", path, f"{event}: expected a list of matcher groups")
                continue
            for group in groups:
                handlers = group.get("hooks") if isinstance(group, dict) else None
                if not isinstance(handlers, list):
                    rep.add("error", "CODEX_HOOK_SHAPE", path, f"{event}: each matcher group needs a hooks list")
                    continue
                for h in handlers:
                    self._check_handler(event, h, path, rep)

    def _check_handler(self, event: str, h: Any, path: Path, rep: Report) -> None:
        if not isinstance(h, dict):
            rep.add("error", "CODEX_HOOK_SHAPE", path, f"{event}: a handler must be a table")
            return
        kind = h.get("type")
        if kind in CODEX_HOOK_SKIPPED_TYPES:
            rep.add("warn", "CODEX_HOOK_SKIPPED", path, f"{event}: type = {kind!r} handlers are parsed but never run")
            return
        if kind not in CODEX_HOOK_HANDLER_TYPES:
            rep.add("error", "CODEX_HOOK_TYPE", path, f"{event}: handler type {kind!r} is not command or mcp_tool")
            return
        if kind == "command" and not isinstance(h.get("command"), str):
            rep.add("error", "CODEX_HOOK_SHAPE", path, f"{event}: command handler without a command string")
            return
        if kind == "mcp_tool" and not (h.get("server") and h.get("tool")):
            rep.add("error", "CODEX_HOOK_SHAPE", path, f"{event}: mcp_tool handler needs server and tool")
            return
        command = str(h.get("command") or "")
        if "CLAUDE_PROJECT_DIR" in command or "CLAUDE_PLUGIN_ROOT" in command:
            rep.add(
                "warn",
                "CODEX_HOOK_CLAUDE_VAR",
                path,
                f"{event}: the command uses a Claude Code variable that Codex does not set; resolve the path from "
                '"$(git rev-parse --show-toplevel)" instead',
            )
        elif re.match(r"^\s*(\S*\s+)?\.?/?\.codex/", command):
            rep.add(
                "info",
                "CODEX_HOOK_RELATIVE",
                path,
                f"{event}: relative .codex/ path breaks when Codex starts in a subfolder; resolve it from the git root",
            )
        timeout = h.get("timeout")
        if event in SHORT_HOOK_EVENTS and isinstance(timeout, (int, float)) and timeout > 3:
            rep.add("warn", "CODEX_HOOK_TIMEOUT", path, f"{event}: timeout {timeout}s is above the 3 s maximum")

    def check_rules(self, path: Path, policy: dict, rep: Report) -> None:
        text = read_text(path)
        if text is None:
            return
        try:
            rules = CodexRules.parse(text)
        except RulesParseError as e:
            rep.add("error", "CODEX_RULES_INVALID", path, f"cannot read the rules statically: {e}")
            return
        rep.stats["Codex rules"] = rep.stats.get("Codex rules", 0) + len(rules)
        perms = policy.get("permissions", {})
        external = [p.split() for p in perms.get("external_action_prefixes", [])]
        runners = [r.split() for r in perms.get("exec_runners", [])]
        for r in rules:
            if r.decision != "allow":
                continue
            tokens = list(r.prefix)
            ext = next((" ".join(e) for e in external if tokens[: len(e)] == e or e[: len(tokens)] == tokens), None)
            if ext:
                rep.add(
                    "warn",
                    "CODEX_RULE_EXTERNAL_ALLOW",
                    path,
                    f"line {r.line}: {r.command!r} ({'' if ext == r.command else ext + ', '}an external action) runs "
                    'outside the sandbox without asking; use decision = "prompt"',
                )
            elif tokens in runners or (len(tokens) == 1 and tokens[0] in INTERPRETERS):
                rep.add(
                    "warn",
                    "CODEX_RULE_BROAD_ALLOW",
                    path,
                    f"line {r.line}: allowing {r.command!r} allows any command it runs; allow the exact commands instead",
                )

    def check_agent(self, path: Path, policy: dict, rep: Report) -> None:
        data = CodexLayer.load_toml(path, rep)
        if data is None:
            return
        rep.stats["Codex agents"] = rep.stats.get("Codex agents", 0) + 1
        missing = [k for k in CODEX_AGENT_REQUIRED if not str(data.get(k) or "").strip()]
        if missing:
            rep.add("error", "CODEX_AGENT_FIELD", path, f"missing required field(s): {', '.join(missing)}")
        self.check_config(data, path, "agent", policy, rep)

    def _check_skills(self, root: Path, rep: Report) -> None:
        if not root.is_dir():
            return
        for skill in sorted(root.glob("*/SKILL.md")):
            meta, _ = split_frontmatter(read_text(skill) or "")
            missing = [k for k in ("name", "description") if not (meta or {}).get(k, "").strip()]
            rep.stats["Codex skills"] = rep.stats.get("Codex skills", 0) + 1
            if missing:
                rep.add("error", "CODEX_SKILL_FIELD", skill, f"SKILL.md frontmatter lacks {', '.join(missing)}")

    # ---- AGENTS.md size ----------------------------------------------------------------------

    @staticmethod
    def _doc_limit(cfg: dict | None) -> int:
        value = (cfg or {}).get("project_doc_max_bytes")
        return value if isinstance(value, int) and value > 0 else CODEX_PROJECT_DOC_MAX_BYTES

    @staticmethod
    def _check_doc_size(doc: Path, limit: int, rep: Report) -> None:
        try:
            size = doc.stat().st_size
        except OSError:
            return
        if size > limit:
            rep.add(
                "warn",
                "CODEX_DOC_TRUNCATED",
                doc,
                f"{size} bytes, above project_doc_max_bytes ({limit}): Codex stops loading instructions at the "
                "limit, so the end of this file is never read; split it or move procedures into skills",
            )
