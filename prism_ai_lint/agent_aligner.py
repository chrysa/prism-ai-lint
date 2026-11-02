"""Claude Code <-> Codex parity (--align): what one tool enforces or loads that the other does not.

The only changes it registers tighten: deny/ask rules mirrored into the tool that lacks them, a
deny on the Codex credentials file, and the prism-ai-lint guard hook copied to the tool that lacks
it. Everything that would add a capability (MCP servers, skills, subagents) or rewrite critical
content (instruction files) is reported with the next step and left to the human."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from prism_ai_lint._markup import import_targets, split_frontmatter
from prism_ai_lint._reference import SECRET_VALUE_PATTERNS
from prism_ai_lint._runtime import lenient_json, read_text
from prism_ai_lint.codex_layer import CodexLayer
from prism_ai_lint.codex_rules import CodexRules
from prism_ai_lint.guard_command import GuardCommand
from prism_ai_lint.prefix_rule import PrefixRule
from prism_ai_lint.report import Report
from prism_ai_lint.rules_parse_error import RulesParseError

MANAGED_RULES = "prism-ai-lint.rules"
RULES_MARKER = "# Managed by prism-ai-lint --align"
RULES_HEADER = (
    f"{RULES_MARKER}: Claude Code deny/ask rules mirrored for Codex.\n"
    "# Codex applies the most restrictive matching rule; this file only adds prompt/forbidden rules.\n"
)
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")


class AgentAligner:
    def __init__(
        self,
        *,
        split_rule: Callable[[str], tuple[str, str | None] | None],
        trailing_wildcard: Callable[[str], tuple[str, str | None]],
        write_json_merged: Callable[[Path, dict, Report, str], None],
        gen_new_file: Callable[..., None],
        config_dir: Callable[[], Path],
    ) -> None:
        self.split_rule = split_rule
        self.trailing_wildcard = trailing_wildcard
        self.write_json_merged = write_json_merged
        self.gen_new_file = gen_new_file
        self.config_dir = config_dir
        self._base: Path | None = None  # repository root while checking a project, for short paths
        self._guard_cmd = GuardCommand()

    # ---- small helpers -----------------------------------------------------------------------

    @staticmethod
    def _names(items: list[str], limit: int = 3) -> str:
        shown = ", ".join(items[:limit])
        return shown + (f" (+{len(items) - limit})" if len(items) > limit else "")

    @staticmethod
    def _home_rel(path: Path) -> str:
        """`path` written with ~ when it is under the home directory (Claude Code expands ~ in rules)."""
        try:
            return "~/" + path.resolve().relative_to(Path.home().resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    @classmethod
    def _rule_path(cls, path: Path) -> str:
        """`path` as a Claude Code permission path: ~/... under home, //abs otherwise (a single / is
        relative to the settings file)."""
        shown = cls._home_rel(path)
        return shown if shown.startswith("~/") else "/" + path.resolve().as_posix()

    @staticmethod
    def _body_lines(text: str) -> list[str]:
        """Lines that carry instructions: not blank, not an @import line, not an HTML comment."""
        out = []
        for line in re.sub(r"<!--.*?-->", "", text, flags=re.S).splitlines():
            stripped = line.strip()
            if stripped and not re.fullmatch(r"@\S+", stripped):
                out.append(stripped)
        return out

    def _show(self, path: Path) -> str:
        """`path` relative to the repository being checked, else written with ~."""
        if self._base is not None:
            try:
                return path.relative_to(self._base).as_posix()
            except ValueError:
                pass
        return self._home_rel(path)

    # ---- entry points --------------------------------------------------------------------------

    def check_repo(self, repo: Path, rep: Report) -> None:
        self._base = repo
        claude_files = [repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"]
        layer = repo / ".codex"
        self._project_instructions(repo, rep)
        self._permissions(claude_files, claude_files[:1], repo / ".claude" / "settings.json", layer, rep)
        self._read_denies(claude_files, layer, rep)
        self._guard(claude_files, repo / ".claude" / "settings.json", layer, rep, "project")
        self._mcp(self._json(repo / ".mcp.json").get("mcpServers"), repo / ".mcp.json", layer, rep)
        self._skills(repo / ".claude" / "skills", repo / ".agents" / "skills", rep)
        self._agents(repo / ".claude" / "agents", layer / "agents", rep)
        self._effort(claude_files, layer, rep)

    def check_user(self, rep: Report) -> None:
        self._base = None
        home, cfg = CodexLayer.home(), self.config_dir()
        claude_files = [cfg / "settings.json", cfg / "settings.local.json"]
        self._user_instructions(cfg, home, rep)
        self._permissions(claude_files, claude_files, cfg / "settings.json", home, rep)
        self._auth_file(claude_files, cfg / "settings.json", home, rep)
        self._guard(claude_files, cfg / "settings.json", home, rep, "user")
        claude_json = Path(os.path.expanduser("~/.claude.json"))
        self._mcp(self._json(claude_json).get("mcpServers"), claude_json, home, rep)
        self._skills(cfg / "skills", Path.home() / ".agents" / "skills", rep)
        self._agents(cfg / "agents", home / "agents", rep)
        self._effort(claude_files, home, rep)

    # ---- helpers -----------------------------------------------------------------------------

    @staticmethod
    def _json(path: Path) -> dict:
        raw = read_text(path)
        if not raw:
            return {}
        try:
            data = lenient_json(raw)[0]
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _claude_rules(self, files: list[Path]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {"allow": [], "ask": [], "deny": []}
        for f in files:
            perms = self._json(f).get("permissions")
            if isinstance(perms, dict):
                for key in out:
                    out[key] += [r for r in perms.get(key) or [] if isinstance(r, str)]
        return out

    def _shell_prefix(self, rule: str) -> tuple[tuple[str, ...], bool] | None:
        """(command tokens, has trailing wildcard) of a literal Bash/PowerShell rule, else None."""
        parsed = self.split_rule(rule)
        if not parsed or parsed[0] not in ("Bash", "PowerShell") or not parsed[1]:
            return None
        cmd, kind = self.trailing_wildcard(parsed[1])
        cmd = cmd[4:] if cmd.startswith("rtk ") else cmd
        if not cmd or re.search(r"[*?\[\]{}$`|&;<>]", cmd):
            return None
        return tuple(cmd.split()), kind is not None

    def _claude_decision(self, rules: dict[str, list[str]], tokens: tuple[str, ...]) -> str | None:
        """The Claude Code decision for a command starting with `tokens` (deny > ask > allow)."""
        for key in ("deny", "ask", "allow"):
            for r in rules[key]:
                parsed = self.split_rule(r)
                if parsed and parsed[0] == "Bash" and (parsed[1] is None or parsed[1].strip() in ("*", ":*")):
                    return key
                pre = self._shell_prefix(r)
                if pre and tokens[: len(pre[0])] == pre[0] and (pre[1] or pre[0] == tokens):
                    return key
        return None

    @staticmethod
    def _codex_rules(layer: Path) -> tuple[list[PrefixRule], bool]:
        """Rules of a layer and whether every rules file could be read."""
        rules: list[PrefixRule] = []
        readable = True
        rules_dir = layer / "rules"
        for f in sorted(rules_dir.glob("*.rules")) if rules_dir.is_dir() else []:
            try:
                rules += CodexRules.parse(read_text(f) or "")
            except RulesParseError:
                readable = False
        return rules, readable

    @staticmethod
    def _codex_decision(rules: list[PrefixRule], tokens: tuple[str, ...]) -> str | None:
        found = [r.decision for r in rules if r.matches(tokens)]
        return max(found, key=CodexRules.STRICTNESS.__getitem__) if found else None

    # ---- instructions ------------------------------------------------------------------------

    def _project_instructions(self, repo: Path, rep: Report) -> None:
        claude = next((p for p in (repo / "CLAUDE.md", repo / ".claude" / "CLAUDE.md") if p.is_file()), None)
        agents = repo / "AGENTS.md"
        ctext = read_text(claude) if claude else None
        atext = read_text(agents)
        body = self._body_lines(ctext or "")
        if ctext is not None and atext is None and body:
            rep.add(
                "warn",
                "ALIGN_INSTR_CODEX_BLIND",
                claude,
                f"Codex reads AGENTS.md, not CLAUDE.md: it sees none of these {len(body)} line(s). Move them with "
                "--convert-from claude --convert-to codex --apply-conversion --approve-conversion, then reduce "
                "CLAUDE.md to '@AGENTS.md'",
            )
        elif ctext is not None and atext is not None and len(body) >= 3:
            imports = {ref for ref, _ in import_targets(claude, ctext)} if claude else set()
            if any(ref.endswith("AGENTS.md") for ref in imports):
                rep.add(
                    "info",
                    "ALIGN_INSTR_CLAUDE_ONLY",
                    claude,
                    f"{len(body)} line(s) of CLAUDE.md besides the AGENTS.md import are read by Claude Code only; "
                    "move the rules both tools need into AGENTS.md",
                )
        if atext:
            refs = [ref for ref, _ in import_targets(agents, atext)]
            if refs:
                rep.add(
                    "warn",
                    "ALIGN_IMPORT_CODEX",
                    agents,
                    f"Codex does not expand @imports: {self._names(refs)} reach Claude Code only; inline what Codex needs",
                )
        rules_dir = repo / ".claude" / "rules"
        rule_files = sorted(rules_dir.rglob("*.md")) if rules_dir.is_dir() else []
        if rule_files:
            rep.add(
                "info",
                "ALIGN_RULES_CLAUDE_ONLY",
                rules_dir,
                f"{len(rule_files)} rule file(s) under .claude/rules load in Claude Code only; for Codex, put "
                "folder-specific rules in a nested AGENTS.md in that folder",
            )

    def _user_instructions(self, cfg: Path, home: Path, rep: Report) -> None:
        claude = cfg / "CLAUDE.md"
        codex = next(
            (p for p in (home / "AGENTS.override.md", home / "AGENTS.md") if (read_text(p) or "").strip()), None
        )
        ctext = read_text(claude)
        body = self._body_lines(ctext or "")
        if not body:
            return
        if codex is None:
            rep.add(
                "warn",
                "ALIGN_INSTR_CODEX_BLIND",
                claude,
                f"Codex reads {self._home_rel(home / 'AGENTS.md')}, which is missing: it sees none of these {len(body)} "
                f"line(s). Keep one source: move them to {self._home_rel(home / 'AGENTS.md')} and make CLAUDE.md "
                f"'@{self._home_rel(home / 'AGENTS.md')}'",
            )
            return
        imports = {ref for ref, _ in import_targets(claude, ctext or "")}
        if any(ref.endswith(codex.name) for ref in imports):
            return
        if self._body_lines(read_text(codex) or "") != body:
            rep.add(
                "warn",
                "ALIGN_INSTR_DIVERGED",
                claude,
                f"{self._home_rel(claude)} and {self._home_rel(codex)} differ: the two tools follow different user rules; "
                f"keep one source and make CLAUDE.md '@{self._home_rel(codex)}'",
            )

    # ---- permissions -------------------------------------------------------------------------

    def _permissions(
        self, claude_files: list[Path], mirror_files: list[Path], claude_target: Path, layer: Path, rep: Report
    ) -> None:
        """Mirror deny/ask both ways. Only `mirror_files` feed the Codex side: a project's personal
        settings.local.json must not end up in a committed rules file."""
        claude = self._claude_rules(claude_files)
        source = self._claude_rules(mirror_files)
        codex, readable = self._codex_rules(layer)
        to_codex: dict[str, list[tuple[str, ...]]] = {"forbidden": [], "prompt": []}
        for key, decision in (("deny", "forbidden"), ("ask", "prompt")):
            for r in source[key]:
                pre = self._shell_prefix(r)
                if not pre or any(p.search(t) for t in pre[0] for p in SECRET_VALUE_PATTERNS):
                    continue
                have = self._codex_decision(codex, pre[0])
                if (have is None or CodexRules.STRICTNESS[have] < CodexRules.STRICTNESS[decision]) and pre[
                    0
                ] not in to_codex[decision]:
                    to_codex[decision].append(pre[0])
        to_claude: dict[str, list[tuple[str, ...]]] = {"deny": [], "ask": []}
        for r in codex:
            want = {"forbidden": "deny", "prompt": "ask"}.get(r.decision)
            if not want:
                continue
            have = self._claude_decision(claude, r.prefix)
            if have != "deny" and not (want == "ask" and have == "ask") and r.prefix not in to_claude[want]:
                to_claude[want].append(r.prefix)
        self._write_codex_rules(layer, to_codex, readable, rep)
        self._write_claude_rules(claude_target, to_claude, rep)

    def _unsafe_target(self, target: Path) -> str | None:
        """Why `target` must not be written: a symlink between the scanned root and the file (the
        write would land outside it), or a resolved path outside that root."""
        root = self._base if self._base is not None else self._user_root(target)
        if root is None:
            return "outside the scanned folders"
        try:
            rel = target.relative_to(root)
        except ValueError:
            return "outside the scanned folders"
        probe = root
        for part in rel.parts:
            probe = probe / part
            if probe.is_symlink():
                return f"{probe} is a symlink"
        try:
            target.resolve().relative_to(root.resolve())
        except (ValueError, OSError, RuntimeError):
            return "resolves outside the scanned folders"
        return None

    def _user_root(self, target: Path) -> Path | None:
        for root in (self.config_dir(), CodexLayer.home()):
            try:
                target.relative_to(root)
                return root
            except ValueError:
                continue
        return None

    def _write_codex_rules(
        self, layer: Path, missing: dict[str, list[tuple[str, ...]]], readable: bool, rep: Report
    ) -> None:
        total = missing["forbidden"] + missing["prompt"]
        if not total:
            return
        target = layer / "rules" / MANAGED_RULES
        unsafe = self._unsafe_target(target)
        existing = read_text(target) if unsafe is None else None
        managed = existing is None or existing.startswith(RULES_MARKER)
        fixable = readable and managed and unsafe is None
        blocks = "".join(
            CodexRules.render(p, d, f"Mirrors a Claude Code {'deny' if d == 'forbidden' else 'ask'} rule")
            for d in ("forbidden", "prompt")
            for p in missing[d]
        )
        cmds = [" ".join(p) for p in total]
        why = (
            ""
            if fixable
            else f" (not fixed: {unsafe})"
            if unsafe
            else " (not fixed: a rules file cannot be read)"
            if not readable
            else f" (not fixed: {MANAGED_RULES} exists and is not managed by prism-ai-lint)"
        )
        rep.add(
            "warn" if missing["forbidden"] else "info",
            "ALIGN_DENY_CODEX_MISSING" if missing["forbidden"] else "ALIGN_ASK_CODEX_MISSING",
            target,
            f"{len(cmds)} Claude Code deny/ask rule(s) have no Codex equivalent: {self._names(cmds)}; Codex runs them "
            f"without the check Claude Code applies{why}",
            fixable,
        )
        if not fixable:
            return
        if existing is None:
            self.gen_new_file(target, RULES_HEADER + "\n" + blocks, rep, "Codex rules mirrored from Claude Code")
        else:
            current = rep.current(target) or existing
            rep.edit(target, existing, current.rstrip("\n") + "\n\n" + blocks)

    def _write_claude_rules(self, target: Path, missing: dict[str, list[tuple[str, ...]]], rep: Report) -> None:
        wanted = {
            key: [r for p in prefixes for r in (f"Bash({' '.join(p)})", f"Bash({' '.join(p)} *)")]
            for key, prefixes in missing.items()
        }
        cmds = [" ".join(p) for p in missing["deny"] + missing["ask"]]
        if not cmds:
            return
        unsafe = self._unsafe_target(target)
        rep.add(
            "warn" if missing["deny"] else "info",
            "ALIGN_DENY_CLAUDE_MISSING" if missing["deny"] else "ALIGN_ASK_CLAUDE_MISSING",
            target,
            f"{len(cmds)} Codex forbidden/prompt rule(s) have no Claude Code equivalent: {self._names(cmds)}"
            + (f" (not fixed: {unsafe})" if unsafe else ""),
            unsafe is None,
        )
        if unsafe:
            return
        self.write_json_merged(
            target, {"permissions": {k: v for k, v in wanted.items() if v}}, rep, "rules mirrored from Codex"
        )

    def _read_denies(self, claude_files: list[Path], layer: Path, rep: Report) -> None:
        if not layer.is_dir():
            return
        reads = [r for r in self._claude_rules(claude_files)["deny"] if r.startswith("Read(")]
        if reads:
            rep.add(
                "info",
                "ALIGN_READ_DENY_UNMAPPED",
                layer,
                f"{len(reads)} Claude Code Read() deny rule(s) (e.g. {reads[0]}) do not apply to Codex: its sandbox "
                "reads those paths; deny them in a [permissions.<name>] filesystem profile",
            )

    def _auth_file(self, claude_files: list[Path], target: Path, home: Path, rep: Report) -> None:
        auth = home / "auth.json"
        if not auth.is_file():
            return
        rel = self._rule_path(auth)
        parent = rel.rsplit("/", 1)[0]
        denied = self._claude_rules(claude_files)["deny"]
        if any(r in (f"Read({rel})", f"Read({parent}/**)", f"Read({parent}/*)") for r in denied):
            return
        unsafe = self._unsafe_target(target)
        rep.add(
            "warn",
            "ALIGN_CODEX_AUTH_READABLE",
            target,
            f"Claude Code can read the Codex credentials ({rel}): deny Read({rel})"
            + (f" (not fixed: {unsafe})" if unsafe else ""),
            unsafe is None,
        )
        if unsafe:
            return
        self.write_json_merged(target, {"permissions": {"deny": [f"Read({rel})"]}}, rep, "Codex credentials denied")

    # ---- guard -------------------------------------------------------------------------------

    def _guard_handlers(self, groups_by_event: Any) -> list[dict]:
        out = []
        groups = groups_by_event.get("PreToolUse") if isinstance(groups_by_event, dict) else None
        for group in groups if isinstance(groups, list) else []:
            for h in (group.get("hooks") or []) if isinstance(group, dict) else []:
                if isinstance(h, dict) and self._guard_cmd.mentions_guard(h):
                    out.append(h)
        return out

    def _codex_guard(self, layer: Path) -> list[dict]:
        found = self._guard_handlers((self._json(layer / "hooks.json") or {}).get("hooks"))
        found += self._guard_handlers((CodexLayer.load_toml(layer / "config.toml", Report()) or {}).get("hooks"))
        return found

    def _guard(self, claude_files: list[Path], claude_target: Path, layer: Path, rep: Report, scope: str) -> None:
        """Copy the guard to the tool that lacks it. Never copies a command: when the existing hook is
        a plain `prism-ai-lint --guard` call, the canonical call of this installation is written."""
        claude = [h for f in claude_files for h in self._guard_handlers(self._json(f).get("hooks"))]
        codex = self._codex_guard(layer)
        if claude and not codex:
            plain = any(self._guard_cmd.is_plain(h) for h in claude)
            target = layer / "hooks.json"
            inline = isinstance((CodexLayer.load_toml(layer / "config.toml", Report()) or {}).get("hooks"), dict)
            unsafe = self._unsafe_target(target)
            why = (
                f" (not fixed: {unsafe})"
                if unsafe
                else " (not fixed: the existing guard is not a plain prism-ai-lint --guard call)"
                if not plain
                else " (not fixed: this layer already has hooks; add it by hand)"
                if target.exists() or inline
                else ""
            )
            rep.add(
                "warn",
                "ALIGN_GUARD_CODEX_MISSING",
                target,
                "the prism-ai-lint guard runs before Claude Code tool calls but not before Codex ones: add a "
                f"PreToolUse hook (matcher {GuardCommand.CODEX_MATCHER!r}); Codex asks to trust it in /hooks"
                + (" and loads project hooks only in a trusted project" if scope == "project" else "")
                + why,
                not why,
            )
            if not why:
                handler = self._guard_cmd.codex_handler()
                doc = {
                    "description": "prism-ai-lint guard: blocks edits that loosen agent configuration.",
                    "hooks": {"PreToolUse": [{"matcher": GuardCommand.CODEX_MATCHER, "hooks": [handler]}]},
                }
                self.gen_new_file(target, json.dumps(doc, indent=2) + "\n", rep, "Codex guard hook")
        elif codex and not claude:
            plain = any(self._guard_cmd.is_plain(h) for h in codex)
            unsafe = self._unsafe_target(claude_target)
            why = (
                f" (not fixed: {unsafe})"
                if unsafe
                else ""
                if plain
                else " (not fixed: the existing guard is not a plain prism-ai-lint --guard call)"
            )
            rep.add(
                "warn",
                "ALIGN_GUARD_CLAUDE_MISSING",
                claude_target,
                "the prism-ai-lint guard runs before Codex tool calls but not before Claude Code ones: add a "
                f"PreToolUse hook (matcher {GuardCommand.CLAUDE_MATCHER!r})" + why,
                not why,
            )
            if not why:
                handler = self._guard_cmd.claude_handler()
                group = {"matcher": GuardCommand.CLAUDE_MATCHER, "hooks": [handler]}
                self.write_json_merged(claude_target, {"hooks": {"PreToolUse": [group]}}, rep, "guard hook from Codex")

    # ---- MCP, skills, agents, effort -------------------------------------------------------

    def _mcp(self, claude: Any, claude_path: Path, layer: Path, rep: Report) -> None:
        claude = claude if isinstance(claude, dict) else {}
        codex = (CodexLayer.load_toml(layer / "config.toml", Report()) or {}).get("mcp_servers")
        codex = codex if isinstance(codex, dict) else {}
        only_claude = sorted(set(claude) - set(codex))
        only_codex = sorted(set(codex) - set(claude))
        if only_claude:
            rep.add(
                "info",
                "ALIGN_MCP_CODEX_MISSING",
                layer / "config.toml",
                f"{len(only_claude)} MCP server(s) only in {claude_path.name}: {self._names(only_claude)}; add them under "
                "[mcp_servers.<name>] (command/args/url carry over; pass env values with env_vars, never literals)",
            )
        if only_codex:
            rep.add(
                "info",
                "ALIGN_MCP_CLAUDE_MISSING",
                claude_path,
                f"{len(only_codex)} MCP server(s) only in Codex: {self._names(only_codex)}; add them to {claude_path.name} "
                "if Claude Code needs them",
            )
        for name in sorted(set(claude) & set(codex)):
            a, b = claude[name], codex[name]
            if not (isinstance(a, dict) and isinstance(b, dict)):
                continue
            if (a.get("command"), a.get("url")) != (b.get("command"), b.get("url")):
                rep.add(
                    "info",
                    "ALIGN_MCP_DIFFERENT",
                    layer / "config.toml",
                    f"MCP server {name!r} points to a different command or URL in each tool",
                )

    @staticmethod
    def _skill_names(root: Path) -> set[str]:
        return {p.parent.name for p in root.glob("*/SKILL.md")} if root.is_dir() else set()

    def _skills(self, claude_dir: Path, codex_dir: Path, rep: Report) -> None:
        try:
            if claude_dir.resolve() == codex_dir.resolve():
                return  # one directory reached through a symlink
        except OSError:
            return
        claude, codex = self._skill_names(claude_dir), self._skill_names(codex_dir)
        if claude - codex:
            rep.add(
                "info",
                "ALIGN_SKILLS_CODEX_MISSING",
                claude_dir,
                f"{len(claude - codex)} skill(s) only in {self._show(claude_dir)}: {self._names(sorted(claude - codex))}; "
                f"Codex reads {self._show(codex_dir)}: keep one folder and symlink the other to it",
            )
        if codex - claude:
            rep.add(
                "info",
                "ALIGN_SKILLS_CLAUDE_MISSING",
                codex_dir,
                f"{len(codex - claude)} skill(s) only in {self._show(codex_dir)}: {self._names(sorted(codex - claude))}; "
                f"Claude Code reads {self._show(claude_dir)}",
            )

    def _agents(self, claude_dir: Path, codex_dir: Path, rep: Report) -> None:
        claude = set()
        for f in claude_dir.rglob("*.md") if claude_dir.is_dir() else []:
            meta, _ = split_frontmatter(read_text(f) or "")
            claude.add(((meta or {}).get("name") or f.stem).strip())
        codex = set()
        for f in codex_dir.glob("*.toml") if codex_dir.is_dir() else []:
            name = (CodexLayer.load_toml(f, Report()) or {}).get("name")
            codex.add(str(name).strip() if name else f.stem)
        if claude and claude - codex:
            rep.add(
                "info",
                "ALIGN_AGENTS_CODEX_MISSING",
                claude_dir,
                f"{len(claude - codex)} subagent(s) have no Codex custom agent: {self._names(sorted(claude - codex))}; "
                f"Codex reads {self._show(codex_dir)}/<name>.toml (name, description, developer_instructions)",
            )
        if codex and codex - claude:
            rep.add(
                "info",
                "ALIGN_AGENTS_CLAUDE_MISSING",
                codex_dir,
                f"{len(codex - claude)} Codex custom agent(s) have no Claude Code subagent: {self._names(sorted(codex - claude))}",
            )

    def _effort(self, claude_files: list[Path], layer: Path, rep: Report) -> None:
        claude = next(
            (self._json(f).get("effortLevel") for f in claude_files if self._json(f).get("effortLevel")), None
        )
        codex = (CodexLayer.load_toml(layer / "config.toml", Report()) or {}).get("model_reasoning_effort")
        if claude in EFFORTS and codex in EFFORTS and claude != codex:
            low = min(claude, codex, key=EFFORTS.index)
            rep.add(
                "info",
                "ALIGN_EFFORT_DIVERGED",
                layer / "config.toml",
                f"Claude Code effortLevel = {claude!r}, Codex model_reasoning_effort = {codex!r}: the same work costs "
                f"differently in each tool; {low!r} is the cheaper common default",
            )
