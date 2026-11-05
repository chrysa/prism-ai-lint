# Claude Code and Codex

prism-ai-lint reads Codex configuration natively, next to Claude Code's:

| Layer | Where |
|---|---|
| User | `$CODEX_HOME`, or `~/.codex` when it is not set |
| Project | `.codex/` at the repository root |
| Instructions | `AGENTS.md`, `AGENTS.override.md` |
| Skills | `.agents/skills/` |

Codex findings are **report-only**: the standard library reads TOML but cannot write it, and
rewriting `config.toml` by hand would risk corrupting it. See [What it checks](checks.md) for the
full list.

## Make both tools enforce the same rules

```sh
prism-ai-lint . --align          # report what Claude Code and Codex do not share
prism-ai-lint . --align --fix    # write the tightening mirrors
```

`--align` adds the parity checks (`ALIGN_*` findings) to the normal report. With `--fix`, it
writes only changes that tighten:

| Gap | What `--fix` writes |
|---|---|
| A Claude Code `deny` / `ask` rule has no Codex rule | A `forbidden` / `prompt` rule in `.codex/rules/prism-ai-lint.rules` |
| A Codex `forbidden` / `prompt` rule has no Claude Code rule | A `Bash()` `deny` / `ask` rule in `.claude/settings.json` |
| Claude Code can read the Codex credentials | A `Read(~/.codex/auth.json)` deny |
| The guard runs before one tool's calls only | The guard hook on the other side: a new `.codex/hooks.json`, or a `PreToolUse` hook in `.claude/settings.json` |

`.codex/rules/prism-ai-lint.rules` is created, or extended only when it carries the prism-ai-lint
marker. A rules file you wrote by hand is never edited.

These gaps are reported with the next step, never fixed, because copying them would add a
capability or rewrite critical content:

- instructions Codex never reads: `CLAUDE.md` without `AGENTS.md`, lines outside the
  `@AGENTS.md` import, `@imports` inside `AGENTS.md`, `.claude/rules`;
- MCP servers, skills and subagents present on one side only;
- a different reasoning effort.

`--align --fix` never adds an `allow` rule, never removes a `deny`, never copies a hook command
from the repository, and never writes through a symlink or outside the scanned folders. The
rationale is decision D-040 in `DECISIONS.md`.

## After an alignment change

1. **Trust the project once in Codex.** Codex loads a project's `.codex/` (rules, hooks,
   config) only when the project is trusted, so the mirrored rules apply from then on.
2. **Trust the hook** in Codex `/hooks` if `.codex/hooks.json` was created.
3. **Run `prism-ai-lint . --align` again.** What remains is report-only: decide each item by hand.

## Review an alignment change

| File | Expected change |
|---|---|
| `.codex/rules/prism-ai-lint.rules` | One rule per Claude Code `deny` (`forbidden`) or `ask` (`prompt`) |
| `.claude/settings.json` | `deny` / `ask` entries and tightening repairs only, never an `allow` |
| `CLAUDE.md` | One `@AGENTS.md` line at the top, so Claude Code loads the instructions Codex reads |
| `.claude/skills/*/SKILL.md` | Frontmatter repairs: missing `name` / `description`, unknown keys moved under `metadata` |

The `CLAUDE.md` and `SKILL.md` changes come from the standard `--fix` repairs (`AGENTS_IGNORED`,
`AGENTS_MENTION`, skill frontmatter checks), not from `--align`. When `CLAUDE.md` gains the
import, check that `AGENTS.md` holds the rules both tools must follow.

## Roll out on many repositories

Run one repository at a time, with one pull request each:

1. **Select the repositories.** Keep the ones you maintain and commit to. Skip archived ones.
2. **Clone the default branch fresh** into a scratch folder. Create a dedicated branch, for
   example `chore/prism-ai-lint-align`.
3. **Run isolated from your own configuration**:

   ```sh
   mkdir -p "$SCRATCH/emptyhome/codex"
   CLAUDE_CONFIG_DIR="$SCRATCH/emptyhome" CODEX_HOME="$SCRATCH/emptyhome/codex" \
     prism-ai-lint "$CLONE" --align --fix --no-scaffold --strict \
       --no-update-check --no-history --no-cli
   ```

   | Option | Why |
   |---|---|
   | Empty `CLAUDE_CONFIG_DIR` / `CODEX_HOME` | Your user-level rules and hooks stay out of the repository |
   | `--no-scaffold` | No new instruction or guard skeleton files |
   | `--no-cli` | Does not call the `claude` or `codex` CLIs |
   | `--no-history`, `--no-update-check` | No transcript scan, no network check |
   | `--strict` | Exits `1` while report-only findings remain: expected, not a failure |

4. **Check the diff before committing.** Stop if `CLAUDE.md` or `AGENTS.md` loses lines: the
   repairs only add lines there.
5. **Commit and open the pull request.** Use a Conventional Commit such as
   `chore: align Claude Code and Codex rules with prism-ai-lint --align`. In the description,
   list each changed file, the safety guarantees, and the trust step above.
6. **Never merge automatically.** Each pull request waits for a human review.

Update the linter between repositories if a release lands during the rollout, so every
repository is judged by the same version.

## Configuration

```toml
[codex]
enabled = true        # lint Codex config.toml, hooks, rules, custom agents and skills when present
max_effort = "high"   # model_reasoning_effort above this is reported (CODEX_EFFORT_HIGH)
extra_keys = []       # config.toml keys newer than the built-in snapshot
```

Set `enabled = false` to skip Codex. Leave out `--align` to keep the two tools independent.
