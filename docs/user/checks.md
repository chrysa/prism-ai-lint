# What it checks

**Settings** (`.claude/settings*.json`, user settings): strict JSON (comments, trailing commas
and BOM repaired), `$schema`, deprecated keys migrated, attribution disabled, keys a repository
cannot set, inline secrets removed, `settings.local.json` git-ignored.

**Permissions**: rule syntax and tool-name case, legacy tools, path rules on tools that never
consult them, unanchored or unrestricted allow rules, environment runners (`npx *`,
`uv run *`), external actions moved from `allow` to `ask`, allow rules dead under a deny,
shadowed and duplicate rules, required deny rules for secrets, rtk routing.

**Hooks**: event names, legacy formats, handler types and required fields, matchers that match
nothing, missing or non-executable scripts, gating scripts that exit 1 instead of 2, async
gating hooks, HTTP header variables missing from `allowedEnvVars`.

**MCP** (`.mcp.json`, read-only `~/.claude.json`): shape, `type` for URL servers, command/args
split, deprecated SSE, inline secrets replaced by `${VAR}`, server count.

**Instructions**: size (200-line target), `@imports` (missing, too deep, external), `AGENTS.md`
loading rules, lines duplicated from user scope, auto-memory `MEMORY.md` size, wording (prose,
filler, vague instructions). Other tools' instruction files are checked the same way.

**Rules** (`.claude/rules`): `paths` only, invalid patterns, frontmatter position.

**Skills, subagents, commands**: frontmatter position and typos, custom fields moved under
`metadata:`, triggers copied into `when_to_use`, description length, 500-line body,
`disable-model-invocation` on side-effect skills, broad `allowed-tools`, duplicates and
families.

**Plugins and marketplaces**: manifest, component paths, `enabledPlugins` and
`extraKnownMarketplaces`.

**Other**: misplaced or misnamed files (`claude.md`, `mcp.json`, flat skills), GitHub Actions
running the Claude action (moving refs, literal credentials, permission bypass), Anthropic API
keys in any file, assistant attribution in files and commits.

**Codex** (`~/.codex` or `$CODEX_HOME`, project `.codex/`; report only): `config.toml` keys
(unknown, deprecated, ignored at project scope), sandbox and approvals (`danger-full-access`, full
access with `approval_policy = "never"`), permission profiles, MCP servers (shape, fields, missing
command, literal secrets, count), hooks (`hooks.json` and `[hooks]`: events, handler types,
Claude Code variables, timeouts), `.rules` files (`allow` on external actions, shells or runners),
custom agents, `.agents/skills`, `AGENTS.override.md` and the 32 KiB `project_doc_max_bytes` limit.

**Claude Code ↔ Codex** (`--align`): instructions one tool never reads, deny/ask rules missing on
one side, Codex credentials readable by Claude Code, the guard on one side only, and MCP servers,
skills, subagents or effort that differ. `--align --fix` only adds deny/ask mirrors, a credentials
deny and the guard hook; it never copies MCP servers, skills, subagents or instructions.

**rtk and llmtrim** (when present): installation, hook, permission routing, dead route agents.

Run `prism-ai-lint --dump-reference` to see the documentation snapshot the checks compare against.
Unknown keys are reported as info, never as errors.

## Design contracts

Existing `DESIGN.md` files at the root or in nested UI directories are checked for instruction size, import resolution and dead
local file/command references, like other project instructions. Their presence does not mean
Claude loads it automatically; reference it explicitly from your agent instructions for UI
work. It is optional: Prism does not create a design contract or impose a brand, section
schema or organisation-specific UI policy. Static checks do not certify visual quality,
usability or accessibility compliance.

Discovery excludes hidden and generated/dependency directories and does not follow symlinks.
