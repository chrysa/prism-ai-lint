"""Codex and Claude Code <-> Codex (--align) finding texts: hints and brief-report rows.

Data only, merged into the engine tables (HINTS, BRIEF_FR, BRIEF_EN) so the engine stays small.
French appears only in the brief-report rows (user-facing strings)."""

from __future__ import annotations

from prism_ai_lint._reference import CLAUDE_DOCS as DOCS
from prism_ai_lint._reference import CODEX_DOCS

# code -> (why/how, reference)
CODEX_HINTS: dict[str, tuple[str, str]] = {
    "CODEX_TOML_INVALID": (
        "Codex refuses a config file that is not valid TOML: none of its settings apply.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_UNKNOWN_KEY": (
        "Typo, or a key newer than this snapshot: check the reference, or list it in [codex] extra_keys.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_DEPRECATED_KEY": (
        "The key or flag still parses but is deprecated; use its replacement.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_PROJECT_IGNORED": (
        "Provider, notification, profile and telemetry keys only work in ~/.codex/config.toml.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_APPROVAL_DEPRECATED": (
        "on-failure is deprecated: on-request for interactive runs, never otherwise.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_APPROVAL_INVALID": (
        "Only on-request, never or { granular = ... } are accepted.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_SANDBOX_INVALID": (
        "sandbox_mode takes read-only, workspace-write or danger-full-access.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_NO_GUARDRAILS": (
        "Full access with approval_policy = never runs every command and edit with no check at all.",
        CODEX_DOCS + "agent-approvals-security",
    ),
    "CODEX_SANDBOX_FULL_ACCESS": (
        "danger-full-access removes filesystem and network isolation; workspace-write keeps edits in the repo.",
        CODEX_DOCS + "agent-approvals-security",
    ),
    "CODEX_PERMISSIONS_CONFLICT": (
        "Permission profiles replace sandbox_mode; the docs say not to mix them.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_NETWORK_OPEN": (
        "Sandboxed commands can reach the network (exfiltration path).",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_PERMISSION_INVALID": (
        "A permission profile cannot extend :danger-full-access or an unknown profile.",
        CODEX_DOCS + "permissions",
    ),
    "CODEX_PERMISSION_DANGEROUS": (
        "dangerously_* network switches widen what sandboxed commands reach.",
        CODEX_DOCS + "permissions",
    ),
    "CODEX_TRUST_INVALID": ("trust_level takes trusted or untrusted.", CODEX_DOCS + "config-file/config-reference"),
    "CODEX_MCP_SHAPE": ("An MCP server needs a command (stdio) or a url (HTTP).", CODEX_DOCS + "extend/mcp"),
    "CODEX_MCP_UNKNOWN_FIELD": (
        "Unknown server fields are typos or newer than this snapshot.",
        CODEX_DOCS + "extend/mcp",
    ),
    "CODEX_MCP_BROKEN": ("The server command is not on PATH: the server cannot start.", CODEX_DOCS + "extend/mcp"),
    "CODEX_MCP_MANY": ("Every enabled server adds its tool list to the context.", CODEX_DOCS + "extend/mcp"),
    "CODEX_SHELL_ENV_MIXED": (
        "filters and the legacy exclude/include_only arrays must not share a layer.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_EFFORT_HIGH": (
        "A high default effort spends reasoning tokens on every turn, trivial ones included.",
        CODEX_DOCS + "config-file/config-reference",
    ),
    "CODEX_HOOK_SHAPE": (
        "Hooks are events -> matcher groups -> handlers; a malformed entry never runs.",
        CODEX_DOCS + "hooks",
    ),
    "CODEX_HOOK_EVENT": ("Codex has its own event list; an unknown event never fires.", CODEX_DOCS + "hooks"),
    "CODEX_HOOK_SKIPPED": (
        "prompt and agent handlers are parsed but skipped; use a command hook.",
        CODEX_DOCS + "hooks",
    ),
    "CODEX_HOOK_TYPE": ("Codex runs command and mcp_tool handlers only.", CODEX_DOCS + "hooks"),
    "CODEX_HOOK_CLAUDE_VAR": (
        "Codex does not set CLAUDE_PROJECT_DIR; resolve paths from the git root.",
        CODEX_DOCS + "hooks",
    ),
    "CODEX_HOOK_RELATIVE": (
        "Codex may start in a subfolder; a git-root-based path keeps the hook found.",
        CODEX_DOCS + "hooks",
    ),
    "CODEX_HOOK_TIMEOUT": ("SessionEnd and Interrupt hooks get 3 seconds at most.", CODEX_DOCS + "hooks"),
    "CODEX_HOOKS_DUAL": (
        "Codex merges hooks.json and inline [hooks] and warns; keep one per layer.",
        CODEX_DOCS + "hooks",
    ),
    "CODEX_HOOKS_DISABLED": ("With hooks off, no lifecycle hook runs, including a guard.", CODEX_DOCS + "hooks"),
    "CODEX_RULES_INVALID": (
        "The rules file could not be read without running it; Codex validates it at load.",
        CODEX_DOCS + "agent-configuration/rules",
    ),
    "CODEX_RULE_EXTERNAL_ALLOW": (
        "An allow rule runs the command outside the sandbox with no prompt; decision defaults to allow.",
        CODEX_DOCS + "agent-configuration/rules",
    ),
    "CODEX_RULE_BROAD_ALLOW": (
        "Allowing a shell, interpreter or runner allows every command it can start.",
        CODEX_DOCS + "agent-configuration/rules",
    ),
    "CODEX_AGENT_FIELD": (
        "A custom agent needs name, description and developer_instructions.",
        CODEX_DOCS + "agent-configuration/subagents",
    ),
    "CODEX_SKILL_FIELD": ("SKILL.md must declare name and description.", CODEX_DOCS + "build-skills"),
    "CODEX_OVERRIDE_SHADOW": (
        "Codex reads at most one file per folder and prefers AGENTS.override.md.",
        CODEX_DOCS + "agent-configuration/agents-md",
    ),
    "CODEX_DOC_TRUNCATED": (
        "Codex stops adding instruction files at project_doc_max_bytes (32 KiB by default).",
        CODEX_DOCS + "agent-configuration/agents-md",
    ),
    "ALIGN_INSTR_CODEX_BLIND": (
        "Codex reads AGENTS.md; keep the shared rules there and let CLAUDE.md import it.",
        CODEX_DOCS + "agent-configuration/agents-md",
    ),
    "ALIGN_INSTR_CLAUDE_ONLY": ("Lines outside the AGENTS.md import reach Claude Code only.", DOCS + "memory"),
    "ALIGN_INSTR_DIVERGED": (
        "Two user instruction files drift; one source imported by the other stays in sync.",
        DOCS + "memory",
    ),
    "ALIGN_IMPORT_CODEX": (
        "Codex concatenates AGENTS.md files as text; @imports are not followed.",
        CODEX_DOCS + "agent-configuration/agents-md",
    ),
    "ALIGN_RULES_CLAUDE_ONLY": (
        "Codex scopes rules by folder with nested AGENTS.md files.",
        CODEX_DOCS + "agent-configuration/agents-md",
    ),
    "ALIGN_DENY_CODEX_MISSING": (
        "A command Claude Code denies is not forbidden for Codex; --align --fix adds a forbidden prefix_rule.",
        CODEX_DOCS + "agent-configuration/rules",
    ),
    "ALIGN_ASK_CODEX_MISSING": (
        "--align --fix adds a prompt prefix_rule for each Claude Code ask rule.",
        CODEX_DOCS + "agent-configuration/rules",
    ),
    "ALIGN_DENY_CLAUDE_MISSING": (
        "--align --fix adds the matching Bash() deny rules to Claude Code.",
        DOCS + "permissions",
    ),
    "ALIGN_ASK_CLAUDE_MISSING": (
        "--align --fix adds the matching Bash() ask rules to Claude Code.",
        DOCS + "permissions",
    ),
    "ALIGN_READ_DENY_UNMAPPED": (
        "Read() rules are Claude Code only; Codex needs a filesystem permission profile.",
        CODEX_DOCS + "permissions",
    ),
    "ALIGN_CODEX_AUTH_READABLE": (
        "~/.codex/auth.json holds Codex credentials; --align --fix denies reading it.",
        DOCS + "permissions",
    ),
    "ALIGN_GUARD_CODEX_MISSING": (
        "The guard judges Codex Bash and apply_patch calls too; trust it in /hooks.",
        CODEX_DOCS + "hooks",
    ),
    "ALIGN_GUARD_CLAUDE_MISSING": (
        "--align --fix adds the same guard as a Claude Code PreToolUse hook.",
        DOCS + "hooks",
    ),
    "ALIGN_MCP_CODEX_MISSING": (
        "Adding an MCP server grants new tools, so it stays a human decision.",
        CODEX_DOCS + "extend/mcp",
    ),
    "ALIGN_MCP_CLAUDE_MISSING": (
        "Adding an MCP server grants new tools, so it stays a human decision.",
        DOCS + "mcp",
    ),
    "ALIGN_MCP_DIFFERENT": ("The same server name runs different code in each tool.", CODEX_DOCS + "extend/mcp"),
    "ALIGN_SKILLS_CODEX_MISSING": (
        "Codex reads .agents/skills; a symlink keeps one copy for both tools.",
        CODEX_DOCS + "build-skills",
    ),
    "ALIGN_SKILLS_CLAUDE_MISSING": (
        "Claude Code reads .claude/skills; a symlink keeps one copy for both tools.",
        DOCS + "skills",
    ),
    "ALIGN_AGENTS_CODEX_MISSING": (
        "Codex custom agents are TOML files in .codex/agents.",
        CODEX_DOCS + "agent-configuration/subagents",
    ),
    "ALIGN_AGENTS_CLAUDE_MISSING": (
        "Claude Code subagents are Markdown files in .claude/agents.",
        DOCS + "sub-agents",
    ),
    "ALIGN_EFFORT_DIVERGED": (
        "The same task costs differently when the default effort differs.",
        CODEX_DOCS + "config-file/config-reference",
    ),
}

# code -> (section, what it means, what to do)
CODEX_BRIEF_FR: dict[str, tuple[str, str, str]] = {
    "CODEX_NO_GUARDRAILS": (
        "security",
        "Codex en accès total sans approbation",
        "sandbox workspace-write + on-request",
    ),
    "CODEX_SANDBOX_FULL_ACCESS": (
        "security",
        "sandbox Codex désactivé (danger-full-access)",
        "passer en workspace-write",
    ),
    "CODEX_RULE_EXTERNAL_ALLOW": ("security", "règle Codex qui autorise une action externe", 'decision = "prompt"'),
    "CODEX_RULE_BROAD_ALLOW": (
        "security",
        "règle Codex qui autorise un shell ou un lanceur",
        "autoriser les commandes exactes",
    ),
    "CODEX_PERMISSION_DANGEROUS": (
        "security",
        "profil réseau Codex en mode dangerously_*",
        "désactiver ces options",
    ),
    "CODEX_HOOKS_DISABLED": (
        "security",
        "hooks Codex désactivés (guard inactif)",
        "retirer features.hooks = false",
    ),
    "CODEX_TOML_INVALID": ("broken", "config Codex TOML invalide", "corriger la syntaxe TOML"),
    "CODEX_APPROVAL_INVALID": ("broken", "approval_policy Codex invalide", "on-request ou never"),
    "CODEX_SANDBOX_INVALID": (
        "broken",
        "sandbox_mode Codex invalide",
        "read-only, workspace-write ou danger-full-access",
    ),
    "CODEX_HOOK_EVENT": ("broken", "hook Codex sur un événement inconnu", "utiliser un événement Codex"),
    "CODEX_HOOK_SHAPE": ("broken", "hook Codex mal formé", "événement -> matcher -> hooks[]"),
    "CODEX_HOOK_TYPE": ("broken", "type de hook Codex non exécuté", "type command ou mcp_tool"),
    "CODEX_HOOK_SKIPPED": ("broken", "hook Codex prompt/agent ignoré", "le réécrire en type command"),
    "CODEX_HOOK_CLAUDE_VAR": ("broken", "hook Codex avec une variable Claude Code", "partir de la racine git"),
    "CODEX_RULES_INVALID": ("broken", "fichier .rules Codex illisible", "corriger le prefix_rule()"),
    "CODEX_AGENT_FIELD": ("broken", "agent Codex sans champ requis", "name, description, developer_instructions"),
    "CODEX_SKILL_FIELD": ("broken", "skill .agents sans name/description", "compléter le frontmatter"),
    "CODEX_PROJECT_IGNORED": ("broken", "clé Codex ignorée dans le projet", "la mettre dans ~/.codex/config.toml"),
    "CODEX_MCP_SHAPE": ("broken", "serveur MCP Codex sans command ni url", "ajouter command ou url"),
    "CODEX_OVERRIDE_SHADOW": (
        "broken",
        "AGENTS.override.md masque AGENTS.md pour Codex",
        "fusionner dans AGENTS.md",
    ),
    "CODEX_DOC_TRUNCATED": ("broken", "AGENTS.md tronqué par Codex (> 32 Kio)", "découper ou passer en skills"),
    "CODEX_EFFORT_HIGH": (
        "tokens",
        "effort de raisonnement Codex élevé par défaut",
        "baisser model_reasoning_effort",
    ),
    "CODEX_MCP_MANY": ("tokens", "beaucoup de serveurs MCP Codex actifs", "enabled = false sur les inutiles"),
    "ALIGN_DENY_CODEX_MISSING": (
        "align",
        "deny Claude Code absents de Codex",
        "--align --fix ajoute des règles forbidden",
    ),
    "ALIGN_ASK_CODEX_MISSING": (
        "align",
        "ask Claude Code absents de Codex",
        "--align --fix ajoute des règles prompt",
    ),
    "ALIGN_DENY_CLAUDE_MISSING": (
        "align",
        "forbidden Codex absents de Claude Code",
        "--align --fix ajoute des deny",
    ),
    "ALIGN_ASK_CLAUDE_MISSING": ("align", "prompt Codex absents de Claude Code", "--align --fix ajoute des ask"),
    "ALIGN_CODEX_AUTH_READABLE": (
        "align",
        "identifiants Codex lisibles par Claude Code",
        "--align --fix ajoute un deny Read",
    ),
    "ALIGN_GUARD_CODEX_MISSING": (
        "align",
        "guard actif pour Claude Code, pas pour Codex",
        "--align --fix crée .codex/hooks.json",
    ),
    "ALIGN_GUARD_CLAUDE_MISSING": (
        "align",
        "guard actif pour Codex, pas pour Claude Code",
        "--align --fix ajoute le hook",
    ),
    "ALIGN_INSTR_CODEX_BLIND": (
        "align",
        "consignes que Codex ne lit pas",
        "les mettre dans AGENTS.md (--convert-to codex)",
    ),
    "ALIGN_INSTR_DIVERGED": (
        "align",
        "consignes utilisateur différentes entre les outils",
        "une source, importée par l'autre",
    ),
    "ALIGN_IMPORT_CODEX": ("align", "@imports dans AGENTS.md ignorés par Codex", "intégrer le contenu utile"),
    "ALIGN_INSTR_CLAUDE_ONLY": (
        "align",
        "consignes de CLAUDE.md lues par Claude Code seul",
        "déplacer le commun dans AGENTS.md",
    ),
    "ALIGN_RULES_CLAUDE_ONLY": ("align", ".claude/rules ignoré par Codex", "AGENTS.md imbriqués par dossier"),
    "ALIGN_READ_DENY_UNMAPPED": ("align", "deny Read() sans équivalent Codex", "profil [permissions] filesystem"),
    "ALIGN_MCP_CODEX_MISSING": ("align", "serveurs MCP absents de Codex", "les ajouter à la main si utiles"),
    "ALIGN_MCP_CLAUDE_MISSING": ("align", "serveurs MCP absents de Claude Code", "les ajouter à la main si utiles"),
    "ALIGN_MCP_DIFFERENT": ("align", "même serveur MCP, commandes différentes", "choisir une définition"),
    "ALIGN_SKILLS_CODEX_MISSING": ("align", "skills absentes de .agents/skills", "un dossier + un lien symbolique"),
    "ALIGN_SKILLS_CLAUDE_MISSING": (
        "align",
        "skills absentes de .claude/skills",
        "un dossier + un lien symbolique",
    ),
    "ALIGN_AGENTS_CODEX_MISSING": (
        "align",
        "subagents sans agent Codex",
        "créer .codex/agents/<nom>.toml si utile",
    ),
    "ALIGN_AGENTS_CLAUDE_MISSING": (
        "align",
        "agents Codex sans subagent Claude Code",
        "créer .claude/agents/<nom>.md si utile",
    ),
    "ALIGN_EFFORT_DIVERGED": ("align", "effort différent entre les outils", "choisir le niveau le moins cher"),
}

CODEX_BRIEF_EN: dict[str, tuple[str, str, str]] = {
    "CODEX_NO_GUARDRAILS": (
        "security",
        "Codex full access with no approval",
        "workspace-write sandbox + on-request",
    ),
    "CODEX_SANDBOX_FULL_ACCESS": (
        "security",
        "Codex sandbox off (danger-full-access)",
        "switch to workspace-write",
    ),
    "CODEX_RULE_EXTERNAL_ALLOW": ("security", "Codex rule allowing an external action", 'decision = "prompt"'),
    "CODEX_RULE_BROAD_ALLOW": ("security", "Codex rule allowing a shell or runner", "allow the exact commands"),
    "CODEX_PERMISSION_DANGEROUS": (
        "security",
        "Codex network profile with dangerously_* on",
        "turn those switches off",
    ),
    "CODEX_HOOKS_DISABLED": ("security", "Codex hooks disabled (no guard)", "remove features.hooks = false"),
    "CODEX_TOML_INVALID": ("broken", "invalid Codex TOML config", "fix the TOML syntax"),
    "CODEX_APPROVAL_INVALID": ("broken", "invalid Codex approval_policy", "on-request or never"),
    "CODEX_SANDBOX_INVALID": (
        "broken",
        "invalid Codex sandbox_mode",
        "read-only, workspace-write or danger-full-access",
    ),
    "CODEX_HOOK_EVENT": ("broken", "Codex hook on an unknown event", "use a Codex event name"),
    "CODEX_HOOK_SHAPE": ("broken", "malformed Codex hook", "event -> matcher -> hooks[]"),
    "CODEX_HOOK_TYPE": ("broken", "Codex hook type that never runs", "type command or mcp_tool"),
    "CODEX_HOOK_SKIPPED": ("broken", "skipped Codex prompt/agent hook", "rewrite it as a command hook"),
    "CODEX_HOOK_CLAUDE_VAR": ("broken", "Codex hook using a Claude Code variable", "resolve from the git root"),
    "CODEX_RULES_INVALID": ("broken", "unreadable Codex .rules file", "fix the prefix_rule()"),
    "CODEX_AGENT_FIELD": (
        "broken",
        "Codex agent missing a required field",
        "name, description, developer_instructions",
    ),
    "CODEX_SKILL_FIELD": ("broken", ".agents skill without name/description", "complete the frontmatter"),
    "CODEX_PROJECT_IGNORED": ("broken", "Codex key ignored at project scope", "move it to ~/.codex/config.toml"),
    "CODEX_MCP_SHAPE": ("broken", "Codex MCP server with no command or url", "add command or url"),
    "CODEX_OVERRIDE_SHADOW": ("broken", "AGENTS.override.md hides AGENTS.md from Codex", "merge it into AGENTS.md"),
    "CODEX_DOC_TRUNCATED": ("broken", "AGENTS.md cut by Codex (> 32 KiB)", "split it or move procedures to skills"),
    "CODEX_EFFORT_HIGH": ("tokens", "high default Codex reasoning effort", "lower model_reasoning_effort"),
    "CODEX_MCP_MANY": ("tokens", "many enabled Codex MCP servers", "enabled = false on unused ones"),
    "ALIGN_DENY_CODEX_MISSING": (
        "align",
        "Claude Code deny rules missing in Codex",
        "--align --fix adds forbidden rules",
    ),
    "ALIGN_ASK_CODEX_MISSING": (
        "align",
        "Claude Code ask rules missing in Codex",
        "--align --fix adds prompt rules",
    ),
    "ALIGN_DENY_CLAUDE_MISSING": (
        "align",
        "Codex forbidden rules missing in Claude Code",
        "--align --fix adds deny rules",
    ),
    "ALIGN_ASK_CLAUDE_MISSING": (
        "align",
        "Codex prompt rules missing in Claude Code",
        "--align --fix adds ask rules",
    ),
    "ALIGN_CODEX_AUTH_READABLE": (
        "align",
        "Codex credentials readable by Claude Code",
        "--align --fix adds a Read deny",
    ),
    "ALIGN_GUARD_CODEX_MISSING": (
        "align",
        "guard on for Claude Code, not for Codex",
        "--align --fix creates .codex/hooks.json",
    ),
    "ALIGN_GUARD_CLAUDE_MISSING": (
        "align",
        "guard on for Codex, not for Claude Code",
        "--align --fix adds the hook",
    ),
    "ALIGN_INSTR_CODEX_BLIND": (
        "align",
        "instructions Codex never reads",
        "move them to AGENTS.md (--convert-to codex)",
    ),
    "ALIGN_INSTR_DIVERGED": (
        "align",
        "user instructions differ between the tools",
        "one source, imported by the other",
    ),
    "ALIGN_IMPORT_CODEX": ("align", "@imports in AGENTS.md ignored by Codex", "inline what Codex needs"),
    "ALIGN_INSTR_CLAUDE_ONLY": (
        "align",
        "CLAUDE.md lines read by Claude Code only",
        "move shared rules to AGENTS.md",
    ),
    "ALIGN_RULES_CLAUDE_ONLY": ("align", ".claude/rules ignored by Codex", "nested AGENTS.md per folder"),
    "ALIGN_READ_DENY_UNMAPPED": (
        "align",
        "Read() deny rules with no Codex equivalent",
        "a [permissions] filesystem profile",
    ),
    "ALIGN_MCP_CODEX_MISSING": ("align", "MCP servers missing in Codex", "add them by hand if needed"),
    "ALIGN_MCP_CLAUDE_MISSING": ("align", "MCP servers missing in Claude Code", "add them by hand if needed"),
    "ALIGN_MCP_DIFFERENT": ("align", "same MCP server, different commands", "keep one definition"),
    "ALIGN_SKILLS_CODEX_MISSING": ("align", "skills missing from .agents/skills", "one folder plus a symlink"),
    "ALIGN_SKILLS_CLAUDE_MISSING": ("align", "skills missing from .claude/skills", "one folder plus a symlink"),
    "ALIGN_AGENTS_CODEX_MISSING": (
        "align",
        "subagents with no Codex agent",
        "add .codex/agents/<name>.toml if needed",
    ),
    "ALIGN_AGENTS_CLAUDE_MISSING": (
        "align",
        "Codex agents with no Claude Code subagent",
        "add .claude/agents/<name>.md if needed",
    ),
    "ALIGN_EFFORT_DIVERGED": ("align", "different effort in each tool", "pick the cheaper level"),
}
