# Fixer & security policy

The contract every repair, generation and guard decision must honour. This is the
project's core invariant; treat it as binding, not aspirational. Architecture context:
[../ARCHITECTURE.md](../ARCHITECTURE.md).

## The invariant: only ever tighten

An automatic action may **tighten, repair, or stay neutral**. It may **never loosen**.
Concretely, no code path (`--fix`, `--generate`, `-i`, scaffolding) may:

- add or widen an `allow` permission rule, or broaden a matcher;
- remove or weaken a `deny` / `ask` rule;
- enable a control that was disabled (hooks, bypass-permissions, project MCP servers…);
- add assistant/AI attribution;
- write a secret anywhere.

If a change *could* loosen, it is **reported as a finding and left for the human** under
"not fixed" — never applied.

## What `--fix` is allowed to do

- Repair syntax: JSON comments / trailing commas / BOM, strict-JSON re-emit, `$schema`.
- Migrate deprecated keys to their current form (e.g. `includeCoAuthoredBy` → attribution off).
- Rename legacy tool names to canonical ones (`Task` → `Agent`).
- Rewrite path rules attached to tools that never consult them onto the right tool.
- Add **deny** entries required by policy (`required_deny`), and rtk twin **deny** rules.
- Convert hooks to exec form / anchor relative paths, add `type: command`.
- Add attribution-off, disable-bypass and other **tightening** defaults on scaffold.
- `--align --fix` (Claude Code ↔ Codex; never through a symlink or outside the scanned folders): add Codex `forbidden`/`prompt` rules mirroring Claude Code `deny`/`ask` (in
  `.codex/rules/prism-ai-lint.rules`, created or extended only when it carries the prism-ai-lint marker), add Claude
  Code `deny`/`ask` rules mirroring Codex `forbidden`/`prompt`, deny `Read(~/.codex/auth.json)`, and copy the guard
  hook to the tool that lacks it (Codex: a new `.codex/hooks.json` only). The guard command itself is never
  copied: only when the existing hook is a plain `[python] <this prism-ai-lint> --guard` call is the canonical call
  of this installation written. A project's `settings.local.json` is not mirrored into the shared rules file.
  Codex `allow` rules, MCP servers, skills, subagents and instruction files are never copied.
- Codex TOML (`config.toml`, custom agents) is never edited: findings are report-only.

## What `--generate` / scaffolding may create

- Baseline `settings.json` with attribution off, secrets denied, external actions on `ask`.
- Format hook, `check` / `review-changes` skills, read-only reviewer subagents.
- `.mcp.json` for detected services (never with an inline secret — env refs only).
- Security files ([../README.md](../README.md) → Generation): a portable `PreCompact`
  hook when settings reference a missing one, and a secrets `.gitignore` block. Writes are
  confined to the scanned repo or the user config dir — never an arbitrary absolute path.

Generation is proposal-only until `--fix` / `-i` applies it; existing files are never
overwritten (`gen_new_file` skips if the target exists).

## The guard (`--guard`)

A PreToolUse hook that **blocks** (exit 2 + reason) any Edit/Write/Bash that would:

- loosen settings / `.mcp.json` / plugin / marketplace / hooks / workflow files
  (`settings_violations`, `mcp_violations`, workflow risk patterns);
- add attribution;
- edit a protected path;
- turn valid strict-JSON config into something looser or invalid.
- loosen Codex config: `sandbox_mode` / `default_permissions` widened or removed, full access with
  `approval_policy = "never"`, `approvals_reviewer` off `user`, network or writable roots widened, a new or re-enabled
  MCP server or tool, hooks removed or disabled (`[features]`, `hooks.state`), a project trusted, any `[features]`
  flag or permission profile changed. Codex keys work on an allowlist: outside the safe keys (model, effort, display,
  custom-agent name and description; instruction content such as `developer_instructions` or `project_doc_*` is
  left to the human) and the keys judged value by value, **any** change (`profile`/`[profiles]`, providers, base
  URLs, `notify`, `apps`, `plugins`, `shell_environment_policy`, keys newer than the snapshot) is blocked. The same
  applies to `<profile>.config.toml` files in the Codex home;
- add a Codex `allow` rule (the default decision) or remove/weaken a `forbidden`/`prompt` rule;
- write a Codex `apply_patch` it cannot read, or whose result on a guarded file is not certain: sections
  are replayed in order on a virtual copy (as Codex applies them), a chunk on a guarded file must match exactly and
  its text must occur once in the file, and each change plus each file's final text is judged; paths are judged as
  written (`..` folded) and as resolved (symlinks), case-insensitively; a guarded target that is not a regular file
  or is above 1 MB is not read and the call is blocked (so the guard cannot be pushed past the hook timeout);
- run a patch through the shell in any form other than `apply_patch <<'EOF' ... EOF` alone, with a quoted delimiter (no `cd`, no other
  program, no patch read from a file), apply a patch from another `workdir`, or run `codex mcp` / `claude mcp`
  add/remove;
- write a file with several hard links, or a guarded file that is not valid UTF-8;
- change a guard hook entry (matcher, command, timeout, failure mode) or `hooks.state`;
- change a Codex `.rules` file whose current text cannot be read statically. Only top-level `prefix_rule()`
  calls with literal, Starlark-compatible arguments and consistent `match` / `not_match` examples are read;
- touch Codex credentials (`auth.json`) or managed requirements (`requirements.toml`, `/etc/codex/`).

It **fails closed**: any internal error blocks by default. It also blocks when it has not decided within 20 s (a `BaseException`, so no `except` on the way can swallow it) (below the 30 s hook
timeout, after which Claude Code and Codex would let the call through). It recognises prism-ai-lint's own
edits by *behaviour*, not filename, so renaming the tool cannot bypass it. Running the
linter itself is allowed (it only tightens); running it with permission-adding flags
(`--session-settings`, `--policy`, `-i`, `--generate --fix`) is left to the human.

## Secret handling

`API_KEY_LEAK` reports an Anthropic key only when it looks random. It ignores obvious
placeholders (`XXXX`, sequential `ABCDEFGHIJ`/`1234567890`, `example`/`fake`/`test-key`/
`your-key`) and any line carrying a `claude-secret-ok` allow marker. A real committed key
is never auto-removed — it is reported so the human rotates it.

## Severity model

- `error` — broken or insecure config that will not work as intended.
- `warn` — works, but risky or wasteful.
- `info` — advisory (token levers, style, habits). Info is not meant to reach zero.

Severity is re-rankable per code via the catalogue, and codes can be disabled, but that
never changes the tighten-only invariant — only what is surfaced.

## When adding a fixer

1. Prove it can only tighten/repair/neutral. If not, make it report-only.
2. Confine any file write to the scanned repo or user config dir.
3. Add a test that fails if the fixer loosens or writes outside scope.
