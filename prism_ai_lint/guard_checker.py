"""PreToolUse checks that block configuration loosening and unvalidated critical edits."""

from __future__ import annotations

import json
import os
import re
import signal
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from prism_ai_lint._reference import CODEX_PERMISSION_PROFILES, CODEX_SANDBOX_MODES
from prism_ai_lint.codex_layer import CodexLayer
from prism_ai_lint.codex_patch import CodexPatch
from prism_ai_lint.codex_rules import CodexRules
from prism_ai_lint.content_validation import CriticalContentValidator
from prism_ai_lint.patch_error import PatchError
from prism_ai_lint.patch_op import PatchOp
from prism_ai_lint.rules_parse_error import RulesParseError

GUARD_MARKER = "--guard"
MAX_GUARDED_BYTES = 1_000_000  # larger (or non-regular) targets are not read: guarded ones are blocked
_UNKNOWN = object()  # a file whose text after a patch section cannot be rebuilt
GUARD_DEADLINE = 20  # seconds; below the 30 s hook timeout, after which Codex and Claude Code let the call through
PATCH_PROGRAM = re.compile(r"\b(apply_?patch|apply-patch|codex-run-as-apply-patch)\b", re.I)
SHELL_PATCH = re.compile(r"\s*apply_?patch\s+<<-?\s*(['\"]?)(\w+)\1[ \t]*\n(?P<body>.*)\n\2\s*", re.S)
MCP_CLI = re.compile(r"\b(codex|claude)\s+mcp\s+(add|add-json|add-from-claude-desktop|remove|rm)\b")
CONFIG_HINT = re.compile(
    r"(settings(\.local)?\.json|\.mcp\.json|\.claude\.json|/\.claude/|\.claude/|"
    r"\.agent-lint\.toml|\.claude-lint\.toml|\.git/hooks|ai-lint|ai_lint[/\\]|\.ai-lint\b|"
    r"SKILL\.md|CLAUDE(\.local)?\.md|AGENTS(\.override)?\.md|\.codex(/|\b)|\.agents/skills)",
    re.I,
)
# Codex config keys the guard lets an agent change freely: model choice, cost, display, and the
# persona fields of a custom agent. Keys it judges value by value are in CODEX_JUDGED_KEYS; a change
# to any other key (profiles, providers, notify, apps, plugins, memories, keys newer than the
# snapshot...) is left to the human, so an unknown key can never loosen the config (fail closed).
CODEX_SAFE_KEYS = frozenset(
    {
        "model",
        "model_reasoning_effort",
        "model_reasoning_summary",
        "model_verbosity",
        "model_context_window",
        "model_auto_compact_token_limit",
        "model_auto_compact_token_limit_scope",
        "model_post_turn_compact_threshold_percent",
        "plan_mode_reasoning_effort",
        "review_model",
        "service_tier",
        "personality",
        "tui",
        "file_opener",
        "hide_agent_reasoning",
        "show_raw_agent_reasoning",
        "notice",
        "check_for_update_on_startup",
        "suppress_unstable_features_warning",
        "disable_paste_burst",
        "project_doc_max_bytes",
        "project_doc_fallback_filenames",
        "tool_output_token_limit",
        "compact_prompt",
        "history",
        "name",
        "description",
        "nickname_candidates",
        "developer_instructions",
    }
)
CODEX_JUDGED_KEYS = frozenset(
    {
        "sandbox_mode",
        "default_permissions",
        "approval_policy",
        "approvals_reviewer",
        "web_search",
        "sandbox_workspace_write",
        "permissions",
        "mcp_servers",
        "hooks",
        "features",
        "projects",
        "skills",
    }
)
# MCP server fields whose change cannot widen what the server can do (timeouts, readiness, naming).
CODEX_MCP_SAFE_FIELDS = frozenset(
    {
        "startup_timeout_sec",
        "startup_timeout_ms",
        "tool_timeout_sec",
        "startup_readiness",
        "supports_parallel_tool_calls",
        "required",
        "name",
        "tool_input_schema_max_bytes",
    }
)
WEB_SEARCH_RANK = ("disabled", "cached", "indexed", "live")
BASH_WRITE_HINT = re.compile(
    r"(>|\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\bmv\b|\bcp\b|\brm\b|\bln\b|\bchmod\b|"
    r"\btruncate\b|\bdd\b|\binstall\b|\bpython3?\b|\bnode\b|\bruby\b|\bjq\b.*>|\bgit\s+(checkout|restore|apply|stash)|"
    r"\bapply_?patch\b|\bpatch\b)"
)


class GuardChecker:
    """Evaluate edits with shared parsing and permission helpers supplied by the caller."""

    def __init__(
        self,
        *,
        covers: Callable[[str, str], bool],
        split_rule: Callable[[str], tuple[str, str | None] | None],
        split_frontmatter: Callable[[str], tuple[dict[str, str] | None, int]],
        frontmatter_block: Callable[[str], str],
        read_text: Callable[[Path], str | None],
        config_dir: Callable[[], Path],
        lenient_json: Callable[[str], tuple[Any, bool]],
        attribution_patterns: list[re.Pattern[str]],
        toml_parser: Any,
        engine_path: Path,
    ) -> None:
        self.covers = covers
        self.split_rule = split_rule
        self.split_frontmatter = split_frontmatter
        self.frontmatter_block = frontmatter_block
        self.read_text = read_text
        self.config_dir = config_dir
        self.lenient_json = lenient_json
        self._attribution_patterns = attribution_patterns
        self.tomllib = toml_parser
        self.engine_path = engine_path.resolve()

    def _norm_handlers(self, hooks: Any) -> set[str]:
        if not isinstance(hooks, dict):
            return set()
        return {
            f"{event}:{self._handler_target(handler)}"
            for event, groups in hooks.items()
            for handler in self._handlers(groups)
        }

    def _handlers(self, groups: Any):
        if not isinstance(groups, list):
            return
        for group in groups:
            if not isinstance(group, dict):
                continue
            for handler in group.get("hooks", []):
                if isinstance(handler, dict):
                    yield handler

    def _handler_target(self, handler: dict) -> str:
        target = handler.get("command") or handler.get("url") or f"{handler.get('server')}:{handler.get('tool')}"
        target = " ".join([str(target), *map(str, handler.get("args") or [])])
        return re.sub(r"[\"']?\$\{?CLAUDE_PROJECT_DIR\}?[\"']?/|^\./", "", target.strip())

    def settings_violations(self, old: dict, new: dict) -> list[str]:
        po, pn = old.get("permissions") or {}, new.get("permissions") or {}
        return (
            self._allow_violations(po, pn)
            + self._restriction_violations(po, pn)
            + self._permission_mode_violations(po, pn)
            + self._hook_violations(old, new)
            + self._environment_violations(old, new)
            + self._executable_violations(old, new)
        )

    def _allow_violations(self, po: dict, pn: dict) -> list[str]:
        v: list[str] = []
        ao, an = list(po.get("allow") or []), list(pn.get("allow") or [])
        for r in an:
            if r in ao or any(self.covers(o, r) for o in ao):
                continue
            parsed = self.split_rule(r)
            if parsed and parsed[0] == "Bash" and (parsed[1] or "").startswith("rtk "):
                plain = f"Bash({parsed[1][4:]})"
                if plain in ao or any(self.covers(o, plain) for o in ao):
                    continue  # rtk routing of an existing rule: same scope
            v.append(f"new allow rule {r!r}")
        return v

    def _restriction_violations(self, po: dict, pn: dict) -> list[str]:
        v: list[str] = []
        for key, stricter in (("deny", ()), ("ask", ("deny",))):
            for r in po.get(key) or []:
                pools = [pn.get(key) or []] + [pn.get(k) or [] for k in stricter]
                if not any(r in pool or any(self.covers(n, r) for n in pool) for pool in pools):
                    v.append(f"{key} rule removed {r!r}")
        return v

    def _permission_mode_violations(self, po: dict, pn: dict) -> list[str]:
        v: list[str] = []
        if pn.get("defaultMode") in ("bypassPermissions", "auto", "acceptEdits") and pn.get("defaultMode") != po.get(
            "defaultMode"
        ):
            v.append(f"defaultMode set to {pn.get('defaultMode')!r}")
        for k in ("disableBypassPermissionsMode", "disableAutoMode"):
            if po.get(k) and pn.get(k) != po.get(k):
                v.append(f"{k} relaxed")
        if set(pn.get("additionalDirectories") or []) - set(po.get("additionalDirectories") or []):
            v.append("additionalDirectories extended")
        return v

    def _guard_handlers(self, hooks: Any) -> set[str]:
        """Each handler that runs a --guard, with its event and matcher, as a comparable string."""
        out: set[str] = set()
        if not isinstance(hooks, dict):
            return out
        for event, groups in hooks.items():
            for group in groups if isinstance(groups, list) else []:
                if not isinstance(group, dict):
                    continue
                for h in group.get("hooks") or []:
                    if isinstance(h, dict) and GUARD_MARKER in json.dumps(h):
                        out.add(json.dumps([event, group.get("matcher"), h], sort_keys=True))
        return out

    def _hook_violations(self, old: dict, new: dict) -> list[str]:
        v: list[str] = []
        if self._guard_handlers(old.get("hooks")) - self._guard_handlers(new.get("hooks")):
            v.append("guard hook changed or removed (matcher, command, timeout or failure mode)")
        if self._table(old.get("hooks")).get("state") != self._table(new.get("hooks")).get("state"):
            v.append("hooks.state changed (it can turn hooks off)")
        removed = self._norm_handlers(old.get("hooks")) - self._norm_handlers(new.get("hooks"))
        if removed:
            v.append("hook(s) removed: " + ", ".join(sorted(removed)[:3]))
        if new.get("disableAllHooks") and not old.get("disableAllHooks"):
            v.append("disableAllHooks enabled")
        if new.get("enableAllProjectMcpServers") and not old.get("enableAllProjectMcpServers"):
            v.append("enableAllProjectMcpServers enabled")
        if set(new.get("enabledMcpjsonServers") or []) - set(old.get("enabledMcpjsonServers") or []):
            v.append("enabledMcpjsonServers extended")
        return v

    def _environment_violations(self, old: dict, new: dict) -> list[str]:
        v: list[str] = []
        so, sn = old.get("sandbox") or {}, new.get("sandbox") or {}
        if so.get("enabled") and not sn.get("enabled"):
            v.append("sandbox disabled")
        if sn.get("allowUnsandboxedCommands") and not so.get("allowUnsandboxedCommands"):
            v.append("allowUnsandboxedCommands enabled")
        if set((new.get("env") or {})) - set((old.get("env") or {})):
            v.append("env variable(s) added")
        return v

    def _executable_violations(self, old: dict, new: dict) -> list[str]:
        v: list[str] = []
        for k in (
            "apiKeyHelper",
            "awsAuthRefresh",
            "awsCredentialExport",
            "otelHeadersHelper",
            "statusLine",
            "fileSuggestion",
            "processWrapper",
            "extraKnownMarketplaces",
            "enabledPlugins",
        ):
            if new.get(k) not in (None, old.get(k)):
                v.append(f"{k} added or changed (executes code)")
        attr = new.get("attribution")
        if isinstance(attr, dict) and any(attr.get(k) for k in ("commit", "pr")):
            v.append("attribution re-enabled")
        return v

    def mcp_violations(self, old: dict, new: dict) -> list[str]:
        so = old.get("mcpServers", old) if isinstance(old, dict) else {}
        sn = new.get("mcpServers", new) if isinstance(new, dict) else {}
        v = [f"new MCP server {n!r}" for n in set(sn) - set(so)]
        for n in set(sn) & set(so):
            v.extend(self._mcp_server_violations(n, so[n], sn[n]))
        return v

    def _mcp_server_violations(self, n: str, old: Any, new: Any) -> list[str]:
        v: list[str] = []
        a, b = old if isinstance(old, dict) else {}, new if isinstance(new, dict) else {}
        old_cmd = " ".join([str(a.get("command") or a.get("url") or ""), *map(str, a.get("args") or [])]).split()
        new_cmd = " ".join([str(b.get("command") or b.get("url") or ""), *map(str, b.get("args") or [])]).split()
        if old_cmd != new_cmd:
            v.append(f"MCP server {n!r} command/url changed")
        if set(b.get("env") or {}) - set(a.get("env") or {}):
            v.append(f"MCP server {n!r} env extended")
        return v

    def frontmatter_violations(self, old: str, new: str) -> list[str]:
        mo, _ = self.split_frontmatter(old)
        mn, _ = self.split_frontmatter(new)
        mo, mn = mo or {}, mn or {}
        v = []
        tok = lambda s: {t for t in re.split(r"[\s,\[\]]+", s or "") if t}
        for key in ("allowed-tools", "tools", "allowed_tools", "allowedTools"):
            if tok(mn.get(key)) - tok(mo.get(key)):
                v.append(f"{key} extended")
        if mo.get("disable-model-invocation", "").lower() in ("true", "yes", "on", "1") and mn.get(
            "disable-model-invocation", ""
        ).lower() not in ("true", "yes", "on", "1"):
            v.append("disable-model-invocation removed")
        if set(tok(mo.get("disallowed-tools"))) - tok(mn.get("disallowed-tools")) or set(
            tok(mo.get("disallowedTools"))
        ) - tok(mn.get("disallowedTools")):
            v.append("disallowed tools reduced")
        v.extend(self._frontmatter_execution_violations(mo, mn, old, new))
        return v

    def _frontmatter_execution_violations(self, mo: dict, mn: dict, old: str, new: str) -> list[str]:
        v: list[str] = []
        if ("hooks" in self.frontmatter_block(new)) and "hooks" not in self.frontmatter_block(old):
            v.append("frontmatter hooks added")
        if mn.get("permissionMode") in ("bypassPermissions", "auto", "acceptEdits") and mn.get(
            "permissionMode"
        ) != mo.get("permissionMode"):
            v.append("permissionMode loosened")
        if (
            mn.get("mcpServers") or "mcpServers" in self.frontmatter_block(new)
        ) and "mcpServers" not in self.frontmatter_block(old):
            v.append("inline mcpServers added")
        if re.search(r"(?m)^\s*!`|^```!", new) and not re.search(r"(?m)^\s*!`|^```!", old):
            v.append("shell injection (!`cmd`) added")
        return v

    def lint_toml_violations(self, old: str, new: str) -> list[str]:
        if self.tomllib is None:
            return ["cannot verify .prism-ai-lint.toml: no TOML parser available"]
        try:
            o = self.tomllib.loads(old) if old.strip() else {}
            n = self.tomllib.loads(new)
        except Exception as e:  # noqa: BLE001
            return [f"invalid TOML: {e}"]
        o.pop("reference", None)
        n.pop("reference", None)
        return [] if o == n else ["only the [reference] table may change"]

    def protected_path(self, p: Path) -> str | None:
        rp = p.resolve()
        # Compared case-insensitively: on macOS and WSL /mnt/c, .GIT/HOOKS reaches .git/hooks.
        s, name = str(rp).casefold(), rp.name.casefold()
        package = str(self.engine_path.parent).casefold()
        own = {
            str(x).casefold()
            for x in (self.engine_path, Path(__file__).resolve(), self.engine_path.parent.parent / "prism-ai-lint.py")
        }
        if s in own or s == package or s.startswith(package + os.sep):
            return "the linter itself"
        if name == ".claude.json":
            return "~/.claude.json is written by Claude Code"
        if s.startswith(
            (
                "/etc/claude-code",
                "/library/application support/claudecode",
                "c:\\program files\\claudecode",
            )
        ):
            return "managed settings"
        if "/skills/synced/" in s:
            return "skills synced from claude.ai"
        if "/.claude/plugins/" in s and str(self.config_dir()).casefold() in s:
            return "installed plugins (managed by the CLI)"
        if "/.git/hooks/" in s or s.endswith("/.git/hooks"):
            return "git hooks (installed by the linter only)"
        if s.startswith("/etc/codex/") or (name == "requirements.toml" and self._is_codex_layer(rp.parent)):
            return "managed Codex requirements"
        if name == "auth.json" and self._is_codex_layer(rp.parent):
            return "Codex credentials"
        try:
            if rp.is_file() and rp.stat().st_nlink > 1:
                return "a file with several hard links (another name may be a guarded file)"
        except OSError:
            pass
        existing, _ = self._read_bounded(rp)
        if f'"{GUARD_MARKER}"' in existing:
            return "the guarded session settings"
        return None

    def _guard_json(self, old: str, new: str, label: str) -> tuple[dict, dict] | str:
        """Parse the pre/post contents of a guarded JSON file. The old text is
        read leniently (a malformed file on disk must not block a repair); the new
        text must be strict JSON, else a guard block reason is returned. Non-object
        JSON is normalised to an empty dict so callers can treat both as mappings."""
        try:
            o = self.lenient_json(old)[0] if old.strip() else {}
        except json.JSONDecodeError:
            o = {}
        try:
            n = json.loads(new)
        except json.JSONDecodeError as e:
            return f"guard: {label} must stay strict JSON ({e})"
        return (o if isinstance(o, dict) else {}), (n if isinstance(n, dict) else {})

    def guard_check(self, data: dict) -> str | None:
        """Return a block reason, or None to let the normal permission flow decide."""
        tool = data.get("tool_name", "")
        ti = data.get("tool_input") or {}
        cwd = Path(data.get("cwd") or os.getcwd())
        if tool in ("Bash", "PowerShell", "Monitor"):
            return self._command_reason(str(ti.get("command", "")), cwd)
        if tool == "apply_patch":  # Codex file edits (also matched as Edit/Write by Codex hooks)
            return self._patch_reason(ti, cwd)
        if tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            return None
        raw = ti.get("file_path") or ti.get("notebook_path")
        if not raw:
            return None
        path = self._resolve(str(raw), cwd)
        why = self.protected_path(path)
        if why:
            return f"guard: {path} is protected ({why})"
        old, readable = self._read_bounded(path)
        if not readable:
            if self._guarded(path, cwd):
                return f"guard: cannot verify {path} (not a regular file, or above {MAX_GUARDED_BYTES} bytes)"
            inserted = "\n".join(
                str(x)
                for x in [
                    ti.get("content"),
                    ti.get("new_string"),
                    *[e.get("new_string") for e in ti.get("edits") or []],
                ]
                if x
            )
            return self._attribution_reason("", inserted)
        if tool == "NotebookEdit":
            return None
        new = self._edited_content(tool, ti, old)
        return self._content_reason(path, cwd, old, new)

    @staticmethod
    def _resolve(raw: str, cwd: Path) -> Path:
        path = Path(os.path.expanduser(raw))
        return path if path.is_absolute() else cwd / path

    @staticmethod
    def _candidates(path: Path) -> list[Path]:
        """The path as written (with '..' folded) and the real file it reaches through symlinks."""
        out = [Path(os.path.normpath(path))]
        try:
            real = path.resolve()
        except (OSError, RuntimeError):
            return out
        return out if real == out[0] else [*out, real]

    def _read_bounded(self, path: Path) -> tuple[str, bool]:
        """(text, readable). An absent file reads as "", readable; a non-regular or oversized file
        is not read at all, so a FIFO or a huge file cannot push the guard past the hook timeout."""
        try:
            st = path.stat()
        except FileNotFoundError:
            return "", True
        except OSError:
            return "", False
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_GUARDED_BYTES:
            return "", False
        try:
            return path.read_bytes().decode("utf-8"), True
        except (OSError, UnicodeDecodeError):
            return "", False  # a file the guard cannot decode is not judged as empty

    def _guarded(self, path: Path, cwd: Path) -> bool:
        """Files whose new text must be known exactly before the change is judged."""
        validator = CriticalContentValidator([cwd])
        return any(
            CONFIG_HINT.search(str(c)) or self._validator_for(c) is not None or validator.is_critical(c)
            for c in self._candidates(path)
        )

    def _attribution_reason(self, old: str, new: str) -> str | None:
        for pat in self._attribution_patterns:
            if pat.search(new) and not pat.search(old):
                return "guard: assistant attribution is forbidden"
        return None

    def _patch_reason(self, ti: dict, cwd: Path) -> str | None:
        """Judge a Codex apply_patch call as the Writes it amounts to.

        Codex applies the file sections one after another, so each section starts from the text the
        previous ones left (a virtual state keyed by real path); each change is judged, and so is
        the final text of every touched file against the disk. On a guarded file the rebuilt text
        must be certain (strict match), else the call is blocked."""
        patcher = CodexPatch()
        try:
            patcher.check_wrapper(ti.get("command"))
            ops = patcher.parse(ti.get("command"))
        except PatchError as e:
            return f"guard: cannot read the apply_patch input, blocking by default ({e})"
        workdir = ti.get("workdir")
        if workdir and self._key(self._resolve(str(workdir), cwd)) != self._key(cwd):
            return "guard: a patch applied from another folder cannot be verified; blocking"
        virtual: dict[Path, str | None | object] = {}
        shown: dict[Path, Path] = {}
        for op in ops:
            reason = self._patch_op_reason(op, cwd, virtual, shown)
            if reason:
                return reason
        for real, final in virtual.items():
            if final is _UNKNOWN:
                continue
            disk, readable = self._read_bounded(real)
            text = final if isinstance(final, str) else ""
            if not readable:
                if self._guarded(shown[real], cwd):
                    return f"guard: cannot verify {shown[real]} (not a regular file, or too large)"
                reason = self._attribution_reason("", text)
                if reason:
                    return reason
                continue
            if text != disk:
                reason = self._content_reason(shown[real], cwd, disk, text)
                if reason:
                    return reason
        return None

    def _patch_op_reason(
        self, op: PatchOp, cwd: Path, virtual: dict[Path, str | None | object], shown: dict[Path, Path]
    ) -> str | None:
        src = self._resolve(op.path, cwd)
        dst = self._resolve(op.move_to, cwd) if op.move_to else None
        targets = [t for t in (src, dst) if t is not None]
        for target in targets:
            why = self.protected_path(target)
            if why:
                return f"guard: {target} is protected ({why})"
        for target in targets:
            shown.setdefault(self._key(target), target)
        guarded = any(self._guarded(t, cwd) for t in targets)

        def current(path: Path) -> tuple[str | object, bool]:
            key = self._key(path)
            if key in virtual:
                value = virtual[key]
                return ("" if value is None else value), True
            return self._read_bounded(path)

        old, readable = current(src)
        if old is _UNKNOWN or not readable:
            if guarded:
                return f"guard: cannot verify the patch to {src} (unknown or unreadable current text); blocking"
            if op.kind != "add":
                for t in targets:
                    virtual[self._key(t)] = _UNKNOWN
                return self._attribution_reason("", op.added_text())
            old = ""
        assert isinstance(old, str)
        new: str | None
        if op.kind == "add":
            new = "\n".join(op.lines) + "\n" if op.lines else ""
        elif op.kind == "delete":
            new = None
        else:
            try:
                # Strict on every file: a looser rebuild is not trusted, even if a later section moves the
                # file to a guarded path. An unguarded file that only rebuilds loosely becomes unknown.
                new = CodexPatch().apply_update(old, op.chunks, strict=True)
            except PatchError as e:
                if guarded:
                    return f"guard: cannot verify the patch to {src} ({e}); blocking by default"
                for t in targets:
                    virtual[self._key(t)] = _UNKNOWN
                return self._attribution_reason(old, op.added_text())
        if dst is None:
            virtual[self._key(src)] = new
            return self._content_reason(src, cwd, old, new or "")
        dst_old, dst_readable = current(dst)
        if dst_old is _UNKNOWN or not dst_readable:
            return f"guard: cannot verify the move to {dst}; blocking"
        assert isinstance(dst_old, str)
        virtual[self._key(src)] = None
        virtual[self._key(dst)] = new
        return self._content_reason(src, cwd, old, "") or self._content_reason(dst, cwd, dst_old, new or "")

    @staticmethod
    def _key(path: Path) -> Path:
        try:
            return path.resolve()
        except (OSError, RuntimeError):
            return Path(os.path.normpath(path))

    def _content_reason(self, path: Path, cwd: Path, old: str, new: str) -> str | None:
        reason = self._attribution_reason(old, new)
        if reason:
            return reason
        violations = self._file_violations(path, old, new)
        if isinstance(violations, str):
            return violations
        if violations:
            return (
                "guard: this change would loosen the configuration: "
                + "; ".join(violations)
                + ". Leave it for the human and list it under 'not fixed'."
            )
        content_reason = CriticalContentValidator([cwd]).validation_reason(path, old, new)
        if content_reason:
            return f"guard: {path} needs validation ({content_reason})"
        return None

    def _command_reason(self, cmd: str, cwd: Path | None = None) -> str | None:
        linter = r"\S*(prism-ai-lint\.py|prism_ai_lint[/\\]_engine\.py)"
        if re.fullmatch(rf"\s*(rtk\s+)?(\S*python[\d.]*\s+)?{linter}(\s+[\w\-./=~:]+)*\s*", cmd):
            human_only = r"--session-settings\b|--policy\b|\s-i\b|--interactive\b|--full-yes\b|--plugin-dir\b"
            if re.search(human_only, cmd) or (re.search(r"--generate\b", cmd) and re.search(r"--fix\b", cmd)):
                return (
                    "guard: --generate --fix, --session-settings, --policy, -i/--full-yes and --plugin-dir "
                    "add permissions or run code: the human runs them (a --generate preview is allowed)"
                )
            return None  # the linter only tightens
        if CodexPatch.BEGIN in cmd or PATCH_PROGRAM.search(cmd):
            # Only `apply_patch <<'EOF' ... EOF` with nothing around it is read: then the patch is the
            # whole command. Any other shape could run more, or apply the patch from another folder.
            m = SHELL_PATCH.fullmatch(cmd)
            if m is None or CodexPatch.BEGIN not in m.group("body"):
                return "guard: run patches as `apply_patch <<'EOF' ... EOF` alone, so they can be verified"
            return self._patch_reason({"command": m.group("body")}, cwd or Path(os.getcwd()))
        if MCP_CLI.search(cmd):
            return "guard: adding or removing MCP servers is left to the human (codex mcp / claude mcp)"
        if CONFIG_HINT.search(cmd) and BASH_WRITE_HINT.search(cmd):
            return (
                "guard: agent configuration files may only be changed with Edit/Write "
                "(so the change can be inspected), or by running prism-ai-lint.py"
            )
        return self._attribution_reason("", cmd)

    def _edited_content(self, tool: str, ti: dict, old: str) -> str:
        if tool == "Write":
            new = str(ti.get("content", ""))
        elif tool == "Edit":
            a, b = str(ti.get("old_string", "")), str(ti.get("new_string", ""))
            new = old.replace(a, b) if ti.get("replace_all") else old.replace(a, b, 1)
        elif tool == "MultiEdit":
            new = old
            for e in ti.get("edits") or []:
                a, b = str(e.get("old_string", "")), str(e.get("new_string", ""))
                new = new.replace(a, b) if e.get("replace_all") else new.replace(a, b, 1)
        return new

    @staticmethod
    def _is_codex_layer(folder: Path) -> bool:
        """A Codex config layer: a project .codex/ folder or the Codex home ($CODEX_HOME, ~/.codex)."""
        if folder.name.casefold() == ".codex":
            return True
        try:
            return str(folder.resolve()).casefold() == str(CodexLayer.home().resolve()).casefold()
        except (OSError, RuntimeError):
            return False

    def _validator_for(self, path: Path) -> tuple[str, str, Callable[..., list[str] | str]] | None:
        """(format, label, validator) for a structured config file the guard judges, else None."""
        name, parent = path.name.casefold(), path.parent
        pname = parent.name.casefold()
        if name in ("settings.json", "settings.local.json") or re.search(r"settings.*\.json$", name):
            return "json", "settings", self.settings_violations
        if name in (".mcp.json", "claude_desktop_config.json"):
            return "json", ("Desktop config" if name == "claude_desktop_config.json" else name), self.mcp_violations
        if pname == ".claude-plugin":
            plugin = {"plugin.json": self._plugin_violations, "marketplace.json": self._marketplace_violations}
            return ("json", name, plugin[name]) if name in plugin else None
        if name == "hooks.json" and (pname == "hooks" or self._is_codex_layer(parent)):
            return "json", name, self._hooks_file_violations
        if name.endswith("config.toml") and self._is_codex_layer(parent):  # config.toml and <profile>.config.toml
            return "toml", f"Codex {name}", self.codex_config_violations
        if name.endswith(".toml") and pname == "agents" and self._is_codex_layer(parent.parent):
            return "toml", "Codex agent file", self.codex_config_violations
        if name.endswith(".rules") and pname == "rules" and self._is_codex_layer(parent.parent):
            return "rules", "Codex rules", self.codex_rules_violations
        return None

    def _file_violations(self, path: Path, old: str, new: str) -> list[str] | str:
        """Judge the change with every validator that applies to the path as written or as resolved."""
        candidates = self._candidates(path)
        found = {}
        for c in candidates:
            v = self._validator_for(c)
            if v is not None:
                found[v[2]] = v
        if not found:
            out: list[str] = []
            for c in candidates:
                out += [x for x in self._text_file_violations(c, old, new) if x not in out]
            return out
        violations: list[str] = []
        for fmt, label, validator in found.values():
            if fmt == "rules":
                result = validator(old, new)
            else:
                parsed = self._guard_toml(old, new, label) if fmt == "toml" else self._guard_json(old, new, label)
                result = parsed if isinstance(parsed, str) else validator(*parsed)
            if isinstance(result, str):
                return result
            violations += result
        return violations

    def _guard_toml(self, old: str, new: str, label: str) -> tuple[dict, dict] | str:
        """Pre/post tables of a guarded TOML file; the new text must parse (Codex refuses invalid TOML)."""
        if self.tomllib is None:
            return f"guard: cannot verify {label}: no TOML parser available"
        try:
            o = self.tomllib.loads(old) if old.strip() else {}
        except Exception:  # noqa: BLE001 - a broken file on disk must not block its repair
            o = {}
        try:
            n = self.tomllib.loads(new)
        except Exception as e:  # noqa: BLE001
            return f"guard: {label} must stay valid TOML ({e})"
        return o, n

    # ---- Codex ---------------------------------------------------------------------------------

    @staticmethod
    def _rank(order: tuple[str, ...], value: Any, default: int) -> int | None:
        """Position of `value` in `order` (None for an unknown value); an absent value is `default`."""
        if value is None:
            return default
        return order.index(value) if value in order else None

    def _widened(self, what: str, order: tuple[str, ...], old: Any, new: Any, default: int) -> list[str]:
        if old == new:
            return []
        ro, rn = self._rank(order, old, default), self._rank(order, new, default)
        if rn is None or ro is None or rn > ro:
            return [f"{what} {old!r} -> {new!r}"]
        return []

    def codex_config_violations(self, old: dict, new: dict) -> list[str]:
        """Loosening between two Codex config tables (config.toml or a custom agent file)."""
        v = self._widened("sandbox_mode", CODEX_SANDBOX_MODES, old.get("sandbox_mode"), new.get("sandbox_mode"), 1)
        v += self._widened(
            "default_permissions",
            CODEX_PERMISSION_PROFILES,
            old.get("default_permissions"),
            new.get("default_permissions"),
            1,
        )
        full = (
            new.get("sandbox_mode") == "danger-full-access" or new.get("default_permissions") == ":danger-full-access"
        )
        if new.get("approval_policy") == "never" and old.get("approval_policy") != "never" and full:
            v.append("approval_policy set to 'never' with full access")
        if new.get("approvals_reviewer") not in (None, "user", old.get("approvals_reviewer")):
            v.append(f"approvals_reviewer set to {new.get('approvals_reviewer')!r}")
        v += self._widened("web_search", WEB_SEARCH_RANK, old.get("web_search"), new.get("web_search"), 1)
        v += self._codex_sandbox_write_violations(
            old.get("sandbox_workspace_write"), new.get("sandbox_workspace_write")
        )
        v += self._codex_table_changes(old, new)
        v += self._codex_mcp_violations(old.get("mcp_servers"), new.get("mcp_servers"))
        v += self.settings_violations({"hooks": old.get("hooks")}, {"hooks": new.get("hooks")})
        v += self._codex_feature_violations(old.get("features"), new.get("features"))
        v += self._codex_trust_violations(old.get("projects"), new.get("projects"))
        v += self._codex_skill_violations(old.get("skills"), new.get("skills"))
        return v

    @staticmethod
    def _table(value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    def _codex_sandbox_write_violations(self, old: Any, new: Any) -> list[str]:
        o, n = self._table(old), self._table(new)
        v = []
        if n.get("network_access") is True and o.get("network_access") is not True:
            v.append("sandbox_workspace_write.network_access enabled")
        for key in ("exclude_slash_tmp", "exclude_tmpdir_env_var"):
            if o.get(key) is True and n.get(key) is not True:
                v.append(f"sandbox_workspace_write.{key} turned off")
        if set(map(str, n.get("writable_roots") or [])) - set(map(str, o.get("writable_roots") or [])):
            v.append("sandbox_workspace_write.writable_roots extended")
        return v

    def _codex_table_changes(self, old: dict, new: dict) -> list[str]:
        """Any change to a key that is neither known safe nor judged below is left to the human."""
        v = [
            f"{key} added, changed or removed (not a key the guard can judge)"
            for key in sorted(set(old) | set(new), key=str)
            if key not in CODEX_SAFE_KEYS and key not in CODEX_JUDGED_KEYS and old.get(key) != new.get(key)
        ]
        po, pn = self._table(old.get("permissions")), self._table(new.get("permissions"))
        v += [
            f"permissions profile {name!r} added, changed or removed"
            for name in sorted(set(po) | set(pn), key=str)
            if po.get(name) != pn.get(name)
        ]
        return v

    def _codex_mcp_violations(self, old: Any, new: Any) -> list[str]:
        o, n = self._table(old), self._table(new)
        v = self.mcp_violations({"mcpServers": o}, {"mcpServers": n})
        for name in sorted(set(o) & set(n), key=str):
            a, b = self._table(o[name]), self._table(n[name])
            if a.get("enabled") is False and b.get("enabled") is not False:
                v.append(f"MCP server {name!r} enabled")
            if set(map(str, b.get("enabled_tools") or [])) - set(map(str, a.get("enabled_tools") or [])) or (
                "enabled_tools" in a and "enabled_tools" not in b
            ):
                v.append(f"MCP server {name!r} enabled_tools extended")
            if set(map(str, a.get("disabled_tools") or [])) - set(map(str, b.get("disabled_tools") or [])):
                v.append(f"MCP server {name!r} disabled_tools reduced")
            judged = {"enabled", "enabled_tools", "disabled_tools", "command", "url", "args", "env"}
            v += [
                f"MCP server {name!r} {key} added, changed or removed"
                for key in sorted(set(a) | set(b), key=str)
                if key not in CODEX_MCP_SAFE_FIELDS and key not in judged and a.get(key) != b.get(key)
            ]
            if set(b.get("env") or {}) == set(a.get("env") or {}) and (a.get("env") or {}) != (b.get("env") or {}):
                v.append(f"MCP server {name!r} env changed")
        return v

    def _codex_feature_violations(self, old: Any, new: Any) -> list[str]:
        """Feature flags grant or remove capabilities (and protections): any change is left to the human."""
        o, n = self._table(old), self._table(new)
        v = []
        for key in sorted(set(o) | set(n), key=str):
            if o.get(key) == n.get(key):
                continue
            if key in ("hooks", "codex_hooks") and n.get(key) is False:
                v.append(f"features.{key} disabled (hooks, including the guard, stop running)")
            else:
                v.append(f"features.{key} changed")
        return v

    def _codex_trust_violations(self, old: Any, new: Any) -> list[str]:
        o, n = self._table(old), self._table(new)
        return [
            f"project {where!r} trusted"
            for where, entry in n.items()
            if self._table(entry).get("trust_level") == "trusted"
            and self._table(o.get(where)).get("trust_level") != "trusted"
        ]

    def _codex_skill_violations(self, old: Any, new: Any) -> list[str]:
        def disabled(table: Any) -> set[str]:
            entries = self._table(table).get("config") or []
            return {
                str(e.get("name") or e.get("path"))
                for e in entries
                if isinstance(e, dict) and e.get("enabled") is False
            }

        v = [f"skill {name!r} re-enabled" for name in sorted(disabled(old) - disabled(new))]
        o, n = self._table(old), self._table(new)
        v += [
            f"skills.{key} changed"
            for key in sorted(set(o) | set(n), key=str)
            if key not in ("config", "max_context_tokens") and o.get(key) != n.get(key)
        ]
        return v

    def codex_rules_violations(self, old: str, new: str) -> list[str] | str:
        """New allow rules, or prompt/forbidden rules removed or weakened, in a Codex .rules file."""
        try:
            rn = CodexRules.parse(new)
        except RulesParseError as e:
            return f"guard: Codex rules must stay readable without running them ({e})"
        try:
            ro = CodexRules.parse(old) if old.strip() else []
        except RulesParseError as e:
            return f"guard: the current Codex rules cannot be read statically ({e}); leave this change to the human"
        v = [
            f"new allow rule {r.command!r}"
            for r in rn
            if r.decision == "allow" and not any(o.decision == "allow" and o.matches(r.prefix) for o in ro)
        ]
        for o in ro:
            if o.decision == "allow":
                continue
            now = CodexRules.decision_for(rn, o.prefix)
            if now is None or CodexRules.STRICTNESS[now] < CodexRules.STRICTNESS[o.decision]:
                v.append(f"{o.decision} rule removed or weakened {o.command!r}")
        return v

    def _plugin_violations(self, old: dict, new: dict) -> list[str]:
        return [
            f"plugin {key} added or changed (executes code)"
            for key in ("hooks", "mcpServers", "lspServers", "monitors", "channels", "userConfig")
            if new.get(key) not in (None, old.get(key))
        ]

    def _marketplace_violations(self, old: dict, new: dict) -> list[str]:
        on = {p.get("name") for p in old.get("plugins") or [] if isinstance(p, dict)}
        nn = {p.get("name") for p in new.get("plugins") or [] if isinstance(p, dict)}
        return [f"new marketplace plugin {x!r}" for x in sorted(nn - on)]

    def _hooks_file_violations(self, old: dict, new: dict) -> list[str]:
        return self.settings_violations({"hooks": old.get("hooks")}, {"hooks": new.get("hooks")})

    def _text_file_violations(self, path: Path, old: str, new: str) -> list[str]:
        name, where = path.name.casefold(), str(path).casefold()
        violations: list[str] = []
        if name.endswith((".yml", ".yaml")) and "/.github/workflows/" in where and "claude-code" in new:
            violations = self._workflow_violations(old, new)
        elif name in (".prism-ai-lint.toml", ".ai-lint.toml", ".claude-lint.toml", ".agent-lint.toml"):
            violations = self.lint_toml_violations(old, new)
        elif name.endswith(".md") and any(
            part in where for part in ("/.claude/skills/", "/.claude/agents/", "/.claude/commands/", "/.agents/skills/")
        ):
            violations = self.frontmatter_violations(old, new)
        return violations

    def _workflow_violations(self, old: str, new: str) -> list[str]:
        risky = [
            (
                r"dangerously-skip-permissions|permission-mode\W+bypassPermissions",
                "permissions bypass added",
            ),
            (r"(?m)^\s*pull_request_target\s*:", "pull_request_target trigger added"),
            (
                r"(allowed_tools|allowedTools)\W[^\n]*?\bBash(\(\*\))?(?=[\s,\"']|$)",
                "unrestricted Bash added",
            ),
        ]
        violations = [msg for pat, msg in risky if re.search(pat, new) and not re.search(pat, old)]
        if re.search(r"(?m)^\s*permissions\s*:", old) and not re.search(r"(?m)^\s*permissions\s*:", new):
            violations.append("workflow permissions block removed")
        return violations

    @staticmethod
    def _deadline(signum: int, frame: Any) -> None:
        raise TimeoutError(f"no decision within {GUARD_DEADLINE} s")

    def run_guard(
        self,
        stdin: TextIO | None = None,
        stderr: TextIO | None = None,
        check: Callable[[dict], str | None] | None = None,
    ) -> int:
        armed = hasattr(signal, "SIGALRM")
        if armed:
            previous = signal.signal(signal.SIGALRM, self._deadline)
            signal.alarm(GUARD_DEADLINE)
        try:
            data = json.load(sys.stdin if stdin is None else stdin)
            reason = (self.guard_check if check is None else check)(data if isinstance(data, dict) else {})
        except Exception as e:  # noqa: BLE001 - fail closed: any internal error blocks
            reason = f"guard: internal error, blocking by default ({e.__class__.__name__}: {e})"
        finally:
            if armed:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous)
        if reason:
            print(reason, file=sys.stderr if stderr is None else stderr)
            return 2
        return 0
