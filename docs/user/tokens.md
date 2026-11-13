# Token savings

Every report ends with a **TOKENS** block: an estimate (bytes / 4) of what is re-sent with every
request, split into instruction files and their imports, unscoped rules, the skill and subagent
listing, the auto-memory index and MCP servers, with the biggest contributors. Above
`tokens.max_always_loaded` (10,000 by default) it becomes a warning. In `--details`, each
finding that weighs on context shows its `~N tokens/session`, and the block ends with the
potential savings of acting on them.

## Levers

| Lever | How prism-ai-lint applies it |
|---|---|
| Instruction files under 200 lines; HTML comments for maintainer notes (not loaded) | lint (`INSTR_*`, `TOKEN_IMPORTS`) |
| Bullet points instead of prose, no filler or hedging wording | lint (`INSTR_PROSE`, `INSTR_FILLER`, `INSTR_VAGUE`) |
| Rules scoped with `paths:` so they load only for matching files | lint (`RULE_UNSCOPED`), `-i` adds the glob |
| Short skill descriptions (listed every turn); side-effect skills get `disable-model-invocation` | lint, `--fix`, `-i` shortens |
| Subagent packs and skill families moved into on-demand plugins | `-i` restructuring |
| Long skills split into `SKILL.md` + `references/`; long `CLAUDE.md` procedures moved into skills | `-i` restructuring |
| No MCP server when the CLI is installed (`gh`, `aws`...); server count capped | lint (`MCP_PREFER_CLI`) |
| Generated and vendored directories denied to `Read` (`node_modules`, `.venv`, `dist`...) | `--generate` |
| Mechanical subagents on a light model; heavy model not the session default | lint (`TOKEN_MODEL`, `TOKEN_SUBAGENT_MODEL`) |
| Security and review subagents never on Haiku (pinned or inherited); no legacy model id in agents or skills | lint (`SUBAGENT_MODEL_UNDERSIZED`, `MODEL_LEGACY`); `--generate` pins `model: sonnet` on code-reviewer, security-auditor, infra-reviewer |
| Instructions duplicated between user and project scope | lint (`INSTR_DUPLICATED`) |
| An always-loaded file repeating lines of a file it `@imports` (e.g. a standards block in both `CLAUDE.md` and the imported `AGENTS.md`) | lint (`INSTR_IMPORT_OVERLAP`, with the tokens paid twice) |
| Hooks that add text on every tool call or prompt (re-read every later turn); the same hook in user and project scope (runs twice) | lint (`HOOK_CONTEXT_REPEATED`, `HOOK_DUPLICATE_SCOPE`) |
| Output compression with rtk (Bash) and llmtrim when the context is heavy | lint (`LLMTRIM_SUGGESTED`), rtk routing |

## Measured use (`--usage`)

`prism-ai-lint [PATH] --usage` reads the project's recent Claude Code session transcripts
(`<config dir>/projects/<project>/*.jsonl`, newest `--usage-sessions N`, default 10) and adds up what was really
sent: model calls, input, cache read, cache write and output tokens, compactions, the hook-injected texts that cost
the most (count × size), tool output by tool, files read more than once, and MCP servers that failed to connect.
Read only and offline; nothing is sent. Only counts, sizes, tool names, read paths, hook names and the first 60
characters of hook-injected text are shown; prompts, tool output and model output never are. `--format json`
prints the same data (`usage_schema_version: 1`). The transcript format is internal to Claude Code: unknown records
are skipped.

## Interactive restructuring (`-i`)

Every run ends with a **RESTRUCTURE** plan ranked by the tokens each change removes from every
session. With `-i`, each proposal is offered in turn and applied only if you accept:

| Proposal | What `-i` does |
|---|---|
| Subagent pack (3+ agents) → on-demand plugin | moves the agents into a local marketplace plugin; nothing loads until installed where needed |
| Skill family (3+ skills sharing a prefix) → plugin | same, under `plugins/<prefix>-skills/` |
| Skill over 500 lines → `SKILL.md` + `references/` | keeps the first sections, moves the rest into linked references |
| Command → skill | moves `commands/x.md` to `skills/x/SKILL.md` |
| Unscoped rule about one language → `paths:` | adds the matching glob |
| Procedure section in `CLAUDE.md` → skill | moves it into a skill, leaves a one-line pointer |

Every move is reversible (`restore.sh` in the trash folder, backups for edits).

## Habits the tool cannot enforce

`/clear` between tasks, `/context` and `/usage` to check, a lighter model by default and a
heavier one only when needed.
