"""Reference data: docs snapshot (2026-10), attribution patterns and scaffold templates.

Pure data plus one predicate, no engine imports. Sets are extended in place by
`load_policy` / `load_catalog`, so every module shares the same objects."""

from __future__ import annotations

import re

# Date the sets below were last checked against the official Claude Code pages (settings, hooks,
# sub-agents, skills). Change it only together with a read of those pages.
DOCS_SNAPSHOT = "2026-10"

# Settings keys the docs list as removed: still accepted by the parser, but they do nothing.
REMOVED_SETTINGS_KEYS = {"teammateDefaultModel": "removed in Claude Code v2.1.234"}

KNOWN_SETTINGS_KEYS = {
    "$schema",
    "additionalDirectories",
    "agent",
    "allowManagedHooksOnly",
    "allowManagedPermissionRulesOnly",
    "allowedHttpHookUrls",
    "alwaysThinkingEnabled",
    "apiKeyHelper",
    "askUserQuestionTimeout",
    "attribution",
    "autoMemoryDirectory",
    "autoMemoryEnabled",
    "autoMode",
    "autoUpdates",
    "autoUpdatesChannel",
    "availableModels",
    "awsAuthRefresh",
    "awsCredentialExport",
    "bashOutputMaxChars",
    "claudeMd",
    "claudeMdExcludes",
    "cleanupPeriodDays",
    "companyAnnouncements",
    "crossSessionInbound",
    "defaultShell",
    "deniedMcpServers",
    "allowedMcpServers",
    "dialogExpiry",
    "disableAllHooks",
    "disableArtifact",
    "disableBundledSkills",
    "disableClaudeAiConnectors",
    "disableCommandPluginSources",
    "disableSkillShellExecution",
    "disabledMcpjsonServers",
    "effortLevel",
    "enableAllProjectMcpServers",
    "enableArtifact",
    "enabledMcpjsonServers",
    "enabledPlugins",
    "env",
    "extraKnownMarketplaces",
    "fallbackModel",
    "feedbackDrafts",
    "fileSuggestion",
    "forceLoginMethod",
    "forceLoginOrgUUID",
    "hooks",
    "httpHookAllowedEnvVars",
    "includeCoAuthoredBy",
    "includeGitInstructions",
    "isolatePeerMachines",
    "language",
    "maxEffortLevel",
    "model",
    "modelOverrides",
    "modelPicker",
    "modelSettings",
    "otelHeadersHelper",
    "outputStyle",
    "permissions",
    "pluginConfigs",
    "processWrapper",
    "remoteControlAtStartup",
    "requiredMinimumVersion",
    "respectGitignore",
    "sandbox",
    "skillListingBudgetFraction",
    "skillListingMaxDescChars",
    "skillOverrides",
    "spinnerTipsEnabled",
    "statusLine",
    "strictPluginOnlyCustomization",
    "subagentStatusLine",
    "syncClaudeAiPlugins",
    "syncClaudeAiSkills",
    "theme",
    "useAutoModeDuringPlan",
    "autoContinueAtUsageLimit",
    "agentPushNotifEnabled",
    "inputNeededNotifEnabled",
    "tui",
    "skipWorkflowUsageWarning",
    "workflowSizeGuideline",
    "modelPricing",
    "disableBypassPermissionsMode",
    "disableWorkflows",
    "ultracode",
    "subagentPromptCacheTtl",
    "strictKnownMarketplaces",
    "blockedMarketplaces",
    "advisorModel",
    "allowAllClaudeAiMcps",
    "allowClaudeInChromeWithManagedMcp",
    "allowManagedDomainsOnly",
    "allowManagedMcpServersOnly",
    "allowManagedReadPathsOnly",
    "allowedChannelPlugins",
    "allowedProviders",
    "appendPlugins",
    "autoCompactEnabled",
    "autoCompactWindow",
    "availableModelsMatch",
    "browserExternalPageTools",
    "channelsEnabled",
    "classifyAllShell",
    "copyOnSelect",
    "deniedModels",
    "diffTool",
    "disableAgentView",
    "disableAutoMode",
    "disableBrowserExternalNavigation",
    "disableDeepLinkRegistration",
    "disableDesktopLocalSessions",
    "disableRemoteControl",
    "disableSideloadFlags",
    "editorMode",
    "enforceAvailableModels",
    "fastMode",
    "fastModePerSessionOptIn",
    "fileCheckpointingEnabled",
    "forceLoginGatewayUrl",
    "forceRemoteSettingsRefresh",
    "gatewayInternalNetworks",
    "managedMcpServers",
    "managedSourcesBehavior",
    "minimumVersion",
    "parentSettingsBehavior",
    "plansDirectory",
    "pluginSuggestionMarketplaces",
    "pluginTrustMessage",
    "policyHelper",
    "prStatusFooterEnabled",
    "prUrlTemplate",
    "prependPlugins",
    "promptCacheTtl",
    "requiredMaximumVersion",
    "showThinkingSummaries",
    "skipAutoPermissionPrompt",
    "skipDangerousModePermissionPrompt",
    "skipWebFetchPreflight",
    "spellcheck",
    "spinnerTipsOverride",
    "spinnerVerbs",
    "sshConfigs",
    "sshHostAllowlist",
    "switchModelsOnFlag",
    "teammateDefaultModel",
    "teammateMode",
    "timeFormat",
    "timeZone",
    "verbose",
    "viewMode",
    "voice",
    "voiceEnabled",
    "worktree",
}
# Keys a repository file cannot set (dead config in .claude/settings*.json).
PROJECT_DEAD_KEYS = {
    "autoMode": "not read from shared project settings",
    "modelPicker": "ignored in project and local settings",
    "claudeMd": "honored only in managed settings",
    "allowManagedPermissionRulesOnly": "managed settings only",
    "allowManagedHooksOnly": "managed settings only",
    "forceLoginMethod": "managed settings only",
    "forceLoginOrgUUID": "managed settings only",
}
KNOWN_TOOLS = {
    "Agent",
    "Artifact",
    "AskUserQuestion",
    "Bash",
    "CronCreate",
    "CronDelete",
    "CronList",
    "Edit",
    "EndConversation",
    "EnterPlanMode",
    "EnterWorktree",
    "ExitPlanMode",
    "ExitWorktree",
    "Glob",
    "Grep",
    "ListAgents",
    "ListMcpResourcesTool",
    "LSP",
    "Monitor",
    "NotebookEdit",
    "PowerShell",
    "PushNotification",
    "Read",
    "ReadMcpResourceTool",
    "RemoteTrigger",
    "ReportFindings",
    "ScheduleWakeup",
    "SendFeedback",
    "SendMessage",
    "SendUserFile",
    "ShareOnboardingGuide",
    "Skill",
    "SubagentHandback",
    "TaskCreate",
    "TaskGet",
    "TaskList",
    "TaskOutput",
    "TaskStop",
    "TaskUpdate",
    "TodoWrite",
    "ToolSearch",
    "WaitForMcpServers",
    "WebFetch",
    "WebSearch",
    "Workflow",
    "Write",
}
RULE_ONLY_TOOLS = {"Cd"}
LEGACY_TOOLS = {
    "Task": "Agent",
    "MultiEdit": "Edit",
    "KillShell": "TaskStop",
    "BashOutput": "TaskOutput",
    "NotebookRead": "Read",
    "LS": "Read",
}
SPECIFIER_TOOLS = {
    "Bash",
    "Monitor",
    "PowerShell",
    "Read",
    "Grep",
    "Glob",
    "LSP",
    "Edit",
    "Write",
    "NotebookEdit",
    "Skill",
    "Agent",
    "WebFetch",
    "Cd",
}
# Path rules are only consulted for Read and Edit (docs: permissions#read-and-edit).
PATH_TOOL_REMAP = {
    "Write": "Edit",
    "NotebookEdit": "Edit",
    "MultiEdit": "Edit",
    "Glob": "Read",
    "Grep": "Read",
    "LSP": "Read",
}
PRIMARY_PARAMS = {"command", "file_path", "path", "notebook_path", "url"}
READONLY_BUILTINS = {
    "ls",
    "cat",
    "echo",
    "pwd",
    "head",
    "tail",
    "grep",
    "find",
    "wc",
    "which",
    "diff",
    "stat",
    "du",
    "cd",
}
ABS_ROOTS = {
    "home",
    "Users",
    "etc",
    "tmp",
    "var",
    "opt",
    "mnt",
    "srv",
    "root",
    "usr",
    "private",
    "Volumes",
    "media",
    "run",
    "data",
}

KNOWN_HOOK_EVENTS = {
    "SessionStart",
    "Setup",
    "UserPromptSubmit",
    "UserPromptExpansion",
    "PreToolUse",
    "PermissionRequest",
    "PermissionDenied",
    "PostToolUse",
    "PostToolUseFailure",
    "PostToolBatch",
    "Notification",
    "MessageDisplay",
    "SubagentStart",
    "SubagentStop",
    "TaskCreated",
    "TaskCompleted",
    "Stop",
    "StopFailure",
    "TeammateIdle",
    "InstructionsLoaded",
    "ConfigChange",
    "CwdChanged",
    "DirectoryAdded",
    "FileChanged",
    "WorktreeCreate",
    "WorktreeRemove",
    "PreCompact",
    "PostCompact",
    "PreModelSwitch",
    "PostModelSwitch",
    "Elicitation",
    "ElicitationResult",
    "SessionEnd",
}
TOOL_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionDenied",
}
NO_MATCHER_EVENTS = {
    "UserPromptSubmit",
    "PostToolBatch",
    "Stop",
    "TeammateIdle",
    "TaskCreated",
    "TaskCompleted",
    "WorktreeCreate",
    "WorktreeRemove",
    "MessageDisplay",
    "CwdChanged",
}
HOOK_TYPES = {
    "command": ("command",),
    "http": ("url",),
    "mcp_tool": ("server", "tool"),
    "prompt": ("prompt",),
    "agent": ("prompt",),
}
# Optional handler fields (hooks docs, 2026-10): name -> accepted type or values.
HOOK_FIELD_TYPES = {
    "onFailure": ("block",),
    "asyncRewake": bool,
    "continueOnBlock": bool,
    "statusMessage": str,
}
SHELL_META = re.compile(r"[|&;<>`()]|\$\((?!\s)|\s&&\s|\|\|")

SKILL_FIELDS = {
    "name",
    "description",
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
    "metadata",
    "license",
    "compatibility",
}
SKILL_SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
SKILL_TYPOS = {
    "allowed_tools": "allowed-tools",
    "allowedTools": "allowed-tools",
    "disallowed_tools": "disallowed-tools",
    "disallowedTools": "disallowed-tools",
    "disable_model_invocation": "disable-model-invocation",
    "disableModelInvocation": "disable-model-invocation",
    "user_invocable": "user-invocable",
    "userInvocable": "user-invocable",
    "when-to-use": "when_to_use",
    "whenToUse": "when_to_use",
    "argument_hint": "argument-hint",
    "argumentHint": "argument-hint",
}
AGENT_FIELDS = {
    "name",
    "description",
    "tools",
    "disallowedTools",
    "model",
    "permissionMode",
    "maxTurns",
    "skills",
    "mcpServers",
    "hooks",
    "memory",
    "background",
    "effort",
    "isolation",
    "color",
    "initialPrompt",
}
AGENT_TYPOS = {
    "allowed-tools": "tools",
    "allowed_tools": "tools",
    "allowedTools": "tools",
    "disallowed-tools": "disallowedTools",
    "disallowed_tools": "disallowedTools",
    "permission-mode": "permissionMode",
    "permission_mode": "permissionMode",
    "max-turns": "maxTurns",
    "max_turns": "maxTurns",
}
RULE_TYPOS = {
    "globs": "paths",
    "glob": "paths",
    "applyTo": "paths",
    "files": "paths",
    "include": "paths",
    "path": "paths",
}

ATTRIBUTION_PATTERNS = [  # written so this source file never matches itself
    re.compile(r"Co-Authored-By:\s*Claude", re.I),
    re.compile(r"Generated with \[?Claude Code", re.I),
    re.compile(r"noreply@anthropic\.com", re.I),
    # Session-link trailer: a link back to the assistant session that wrote the commit.
    re.compile(r"^Claude-Session:\s*https?://", re.I | re.M),
]
# A line that forbids attribution ("NEVER add Co-Authored-By...", "strip the
# Generated-with line") is documentation, not a trace: don't flag it.
ATTR_NEGATION = re.compile(
    r"\b(never|do ?n['o]t|no|without|strip|remove|forbid|avoid|jamais|sans|ne "
    r"pas|retire|supprime|interdit)\b",
    re.I,
)


def _is_attribution(line: str) -> bool:
    for p in ATTRIBUTION_PATTERNS:
        m = p.search(line)
        if not m:
            continue
        if ATTR_NEGATION.search(line):
            return False
        # A match inside an inline-code span (`...Co-Authored-By...`) is quoting the
        # trailer as an example in prose/plans, not committing it. A real trailer
        # sits on its own line, unquoted.
        before, after = line[: m.start()], line[m.end() :]
        if before.count("`") % 2 == 1 and "`" in after:
            return False
        return True
    return False


SECRET_VALUE_PATTERNS = [
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{20,}$"),
    re.compile(r"^github_pat_[A-Za-z0-9_]{20,}$"),
    re.compile(r"^sk-[A-Za-z0-9_-]{20,}$"),
    re.compile(r"^xox[abpr]-[A-Za-z0-9-]{10,}$"),
    re.compile(r"^AKIA[0-9A-Z]{16}$"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"^(ntn|secret|hvs|s)\.?_?[A-Za-z0-9]{20,}$"),
    re.compile(r"^glpat-[\w-]{20,}$"),
]
SECRET_REDACT_RE = re.compile(
    r"(gh[pousr]_|github_pat_|sk-|xox[abpr]-|AKIA|ntn_|secret_|hvs\.|glpat-)[A-Za-z0-9_-]{8,}"
)
SECRET_KEY_RE = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_KEY|AUTHORIZATION)", re.I)

COMMIT_MSG_HOOK = """#!/usr/bin/env sh
# Strip AI-assistant attribution trailers from commit messages.
# Installed by prism-ai-lint. Deterministic and agent-agnostic.
sed -i -E \\
  -e '/^Co-Authored-By:.*(claude|anthropic)/Id' \\
  -e '/Generated with \\[?Claude Code/Id' \\
  -e '/^Claude-Session:/Id' \\
  "$1"
sed -i -e :a -e '/^\\n*$/{$d;N;ba' -e '}' "$1"
"""
HOOK_SIGNATURE = "prism-ai-lint"

# Portable, tool-agnostic PreCompact hook. No project-specific coupling: it writes
# a small session snapshot (git state + working dir) so context survives a compact.
# Referenced by settings that declare a PreCompact hook but ship no script.
PRE_COMPACT_HOOK = """#!/usr/bin/env bash
# PreCompact hook — snapshot session state before context compaction.
# Portable scaffold written by prism-ai-lint. Safe to edit or extend.
set -uo pipefail
SNAP_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/pre-compact-snapshots"
mkdir -p "$SNAP_DIR"
SNAP="$SNAP_DIR/snapshot-$(date +%Y%m%d-%H%M%S).md"
{
  echo "# Pre-compact snapshot · $(date -Iseconds)"
  echo "working_dir: $(pwd)"
  if git rev-parse --git-dir >/dev/null 2>&1; then
    echo "branch: $(git branch --show-current 2>/dev/null || echo DETACHED)"
    echo "## Uncommitted changes (preserve)"
    git status --porcelain 2>/dev/null | head -50
    echo "## Recent commits"
    git log --oneline -5 2>/dev/null
  fi
} > "$SNAP" 2>/dev/null || true
exit 0
"""

SESSION_CONTEXT_HOOK = """#!/usr/bin/env bash
# SessionStart hook: print the git state once so the agent need not spend tool calls on it.
# Written by prism-ai-lint. Output stays under ~25 lines. Never fails the session.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
echo "branch: $(git branch --show-current 2>/dev/null || echo DETACHED)"
git status --porcelain 2>/dev/null | head -15
git log --oneline -3 2>/dev/null
exit 0
"""

# Lines a repo should git-ignore so secrets never get committed. Appended (never
# overwritten) to .gitignore under a labelled block when any are missing.
SECRETS_GITIGNORE = [
    ".env",
    ".env.*",
    "!.env.example",
    "*.pem",
    "*.key",
    "secrets/",
    ".claude/settings.local.json",
]
SECRETS_GITIGNORE_HEADER = "# prism-ai-lint: keep secrets and local config out of git"

AGENTS_SKELETON = """# {name}

<!-- Neutral agent instructions. Tool-specific files (e.g. CLAUDE.md) only import this one.
     HTML comments are stripped before loading: they cost no context. -->

## Overview

<!-- One paragraph: what this project is, who uses it, current maturity. -->

## Commands

{commands}

## Conventions

- Everything written to disk is in English (identifiers, commits, docs).
- Configuration comes from environment variables; no committed secrets.
<!-- Only what differs from tool defaults; skip what the code already shows. -->

## Boundaries

- Ask before any action with external effects (push, release, deploy, DNS, secrets, messages).
- Never add assistant attribution to commits, PRs, files or docs.
"""


# Claude model lineup, docs snapshot 2026-10 (platform.claude.com models overview).
# Tier order is cost order, cheapest first. Anything pinned to an id outside CURRENT_MODELS
# is older: still available (LEGACY_MODELS) but not the recommended generation.
CURRENT_MODELS = {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"}
LEGACY_MODELS = {
    "claude-fable-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
}
MODEL_SNAPSHOT = "2026-10"


# claude-<family>-<major>[-<minor>] (current naming) and claude-<n>-... / claude-instant-... (pre-2025 naming).
_FAMILY_ID = re.compile(r"^claude-(haiku|sonnet|opus|fable)-(\d+)(?:-(\d+))?$")
_OLD_NAMING = re.compile(r"^claude-(?:instant-)?\d")


def _generation(base: str) -> tuple[str, tuple[int, int]] | None:
    m = _FAMILY_ID.match(base)
    return (m.group(1), (int(m.group(2)), int(m.group(3) or 0))) if m else None


def model_status(name: str) -> str:
    """'current', 'legacy' or '' (an alias such as 'sonnet', or an id newer than this snapshot).

    An id is legacy when the snapshot lists it, uses the pre-2025 naming, or is an older version of a family whose
    current id is known (claude-sonnet-4-5 < claude-sonnet-5-5). A newer version is not judged (D-047).
    """
    base = re.sub(r"(\[1m\])?$", "", name.strip().lower())
    base = re.sub(r"-\d{8}$", "", base)
    if base in CURRENT_MODELS:
        return "current"
    if base in LEGACY_MODELS or _OLD_NAMING.match(base):
        return "legacy"
    gen = _generation(base)
    current = {g[0]: g[1] for c in CURRENT_MODELS if (g := _generation(c))}
    return "legacy" if gen and gen[0] in current and gen[1] < current[gen[0]] else ""


# defaultMode values (permission-modes docs, 2026-10); anything else is a typo.
PERMISSION_MODES = {"default", "acceptEdits", "auto", "plan", "dontAsk", "bypassPermissions"}
MODEL_ALIASES = {"sonnet", "opus", "haiku", "fable"}


def safe_model(value: object, fallback: str) -> str:
    """A model name that is safe to write into settings or frontmatter: a known alias or a known id.

    Policy files come from the scanned project and are untrusted: anything else (a route name, a
    string with a newline, a path) is replaced by `fallback`, so a repository cannot choose what is
    written into the user's own configuration."""
    name = str(value).strip().lower()
    if name in MODEL_ALIASES or model_status(name):
        return name
    return fallback


# --------------------------------------------------------------------------- #
# Codex (OpenAI) snapshot: config.toml schema, hooks, rules, custom agents.
# Checked against learn.chatgpt.com/docs (config-reference, hooks, rules, subagents,
# agents-md, build-skills) and the published config-schema.json on 2026-11-02.
# Change it only together with a read of those pages.
# --------------------------------------------------------------------------- #

CODEX_DOCS_SNAPSHOT = "2026-11"
CODEX_DOCS = "https://learn.chatgpt.com/docs/"
CLAUDE_DOCS = "https://code.claude.com/docs/en/"

# Top-level keys of config.toml (config-schema.json `properties`).
CODEX_KNOWN_KEYS = frozenset(
    """
    agents allow_login_shell allow_symlinked_codex_home analytics approval_policy approvals_reviewer apps
    apps_mcp_product_sku audio auto_review background_terminal_max_timeout browser_use chatgpt_base_url
    check_for_update_on_startup cli_auth_credentials_store cloud compact_prompt computer_use daybreak
    default_permissions desktop developer_instructions disable_paste_burst experimental_compact_prompt_file
    experimental_realtime_start_instructions experimental_realtime_webrtc_call_base_url
    experimental_realtime_ws_backend_prompt experimental_realtime_ws_base_url experimental_realtime_ws_model
    experimental_realtime_ws_startup_context experimental_thread_store experimental_use_unified_exec_tool
    features feedback file_opener forced_chatgpt_workspace_id forced_login_method ghost_snapshot goals
    hide_agent_reasoning history hooks include_apps_instructions include_collaboration_mode_instructions
    include_environment_context include_environment_context_time include_permissions_instructions instructions
    log_dir marketplaces mcp_enterprise_managed_auth mcp_oauth_callback_port mcp_oauth_callback_url
    mcp_oauth_credentials_store mcp_optional_startup_grace_ms mcp_servers memories model
    model_auto_compact_token_limit model_auto_compact_token_limit_scope model_catalog_json model_context_window
    model_instructions_file model_post_turn_compact_threshold_percent model_provider model_providers
    model_reasoning_effort model_reasoning_summary model_verbosity notice notify openai_base_url orchestrator
    oss_provider otel permissions personality plan_mode_reasoning_effort plugins profile profiles
    project_doc_fallback_filenames project_doc_max_bytes project_root_markers projects realtime
    responses_api_metadata review_model sandbox_mode sandbox_workspace_write service_tier
    shell_environment_policy show_raw_agent_reasoning skills sqlite_home suppress_unstable_features_warning
    thread_unload_delay_secs tool_output_token_limit tool_suggest tools tui web_search windows
    """.split()
)
# Deprecated or legacy top-level keys -> what to use instead.
CODEX_DEPRECATED_KEYS = {
    "experimental_instructions_file": "model_instructions_file",
    "background_terminal_timeout": "background_terminal_max_timeout",
    "disable_paste_burst": "tui.disable_paste_burst",
    "experimental_use_unified_exec_tool": "features.unified_exec",
    "personality": "nothing: the key no longer selects a style",
}
# Deprecated [features] flags -> replacement.
CODEX_DEPRECATED_FEATURES = {
    "codex_hooks": "features.hooks",
    "web_search": 'top-level web_search = "cached"',
    "web_search_cached": 'top-level web_search = "cached"',
    "web_search_request": 'top-level web_search = "live"',
    "personality": "nothing: the flag is ignored",
}
# Keys Codex ignores in a project .codex/config.toml (user config only).
CODEX_PROJECT_IGNORED_KEYS = frozenset(
    {
        "openai_base_url",
        "chatgpt_base_url",
        "apps_mcp_product_sku",
        "model_provider",
        "model_providers",
        "notify",
        "profile",
        "profiles",
        "experimental_realtime_ws_base_url",
        "otel",
    }
)
CODEX_APPROVAL_POLICIES = frozenset({"on-request", "never"})  # or { granular = {...} }
CODEX_APPROVAL_DEPRECATED = {"on-failure": "on-request (interactive) or never (non-interactive)"}
CODEX_APPROVAL_UNSUPPORTED = frozenset({"untrusted"})
# Sandbox modes, least to most permissive.
CODEX_SANDBOX_MODES = ("read-only", "workspace-write", "danger-full-access")
# Built-in permission profiles, least to most permissive.
CODEX_PERMISSION_PROFILES = (":read-only", ":workspace", ":danger-full-access")
CODEX_TRUST_LEVELS = frozenset({"trusted", "untrusted"})
# MCP server fields (RawMcpServerConfig).
CODEX_MCP_FIELDS = frozenset(
    """
    args auth bearer_token_env_var command cwd default_tools_approval_mode disabled_tools enabled enabled_tools
    env env_http_headers env_vars environment_id http_headers http_headers_helper name oauth oauth_resource
    omit_tools_from required scopes startup_readiness startup_timeout_ms startup_timeout_sec
    supports_parallel_tool_calls tool_input_schema_max_bytes tool_timeout_sec tools url
    """.split()
)
CODEX_HOOK_EVENTS = frozenset(
    {
        "PreModelRequest",
        "PostModelRequest",
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "PreCompact",
        "PostCompact",
        "SessionStart",
        "SessionEnd",
        "SubagentStart",
        "SubagentStop",
        "UserPromptSubmit",
        "Stop",
        "Interrupt",
    }
)
CODEX_HOOK_HANDLER_TYPES = frozenset({"command", "mcp_tool"})
CODEX_HOOK_SKIPPED_TYPES = frozenset({"prompt", "agent"})  # parsed, then skipped
# Custom agent files (.codex/agents/*.toml): required fields.
CODEX_AGENT_REQUIRED = ("name", "description", "developer_instructions")
CODEX_PROJECT_DOC_MAX_BYTES = 32 * 1024  # project_doc_max_bytes default
# Reasoning efforts by cost, as listed in the docs; model-dependent, unknown values are not judged.
CODEX_EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
