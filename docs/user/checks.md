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

A `DESIGN.md` is optional. When one exists — at the root or next to a frontend (`web/DESIGN.md`,
`frontend/DESIGN.md`) — Prism reports four separate facts about it:

| Fact | What Prism checks | Finding when it fails |
| ---- | ----------------- | --------------------- |
| **Present** | Deterministic discovery: hidden, dependency, build, cache and git-ignored trees are skipped; linked directories are not followed; a symlinked `DESIGN.md` is read only when it resolves inside the project. | `DESIGN_EXTERNAL` for a symlink out of the project |
| **Analysed** | `@` imports, local Markdown links (resolved from the contract's folder), `make` / `npm run` commands against the nearest `Makefile` / `package.json`, size against an on-demand budget (`design_warn_lines`, `design_warn_tokens`). | `IMPORT_MISSING`, `DESIGN_DEAD_LINK`, `INSTR_DEAD_REF`, `DESIGN_LONG` |
| **Referenced** | An instruction file (`CLAUDE.md`, `AGENTS.md`, `.claude/rules/`, Copilot/Gemini renders, a nested `CLAUDE.md`/`AGENTS.md`) or a referenced contract names it. | `DESIGN_UNREFERENCED` |
| **Loaded at launch** | An always-loaded instruction file `@`-imports it. | `DESIGN_ALWAYS_LOADED` (info: prefer an on-demand reference) |

No agent loads a file because it is named `DESIGN.md`: reference it from your instructions for UI
work. Prism can only see that reference statically; whether an agent actually read the contract in a
session is not something a linter can know.

The contract is never edited and never style-linted: design rationale is content, not filler. To
have the guard ask for human validation before an agent changes it, list it under `[critical]
extra_files`. Prism imposes no section schema, brand or organisation policy, and static checks do not
certify visual quality, usability or accessibility.
