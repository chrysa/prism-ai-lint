# External references reviewed

Public projects reviewed for ideas (2026-10). Nothing is vendored; ideas are re-written in our own words.

| Project | What it is | Licence | Verdict |
| --- | --- | --- | --- |
| multica-ai/andrej-karpathy-skills | Four working-style principles as CLAUDE.md, one on-demand skill, a Cursor rule | none at repo root; MIT in the skill/plugin metadata | Adopted in spirit (see below) |
| Infisical/agent-vault | Credential-broker proxy (`HTTPS_PROXY`): the agent holds dummy values | MIT (premium `ee/`) | Report hint only, no dependency |
| jeremylongshore/tons-of-skills-marketplace | 400+ plugins, mirrored upstream plugins with pinned sources | MIT scaffolding, per-plugin licences | Pattern: pinned sources |
| smtg-ai/claude-squad | Several agents in git worktrees and tmux | AGPL-3.0 | Not adopted; do not copy |
| voltagent/voltagent | TypeScript framework to build agents | not reviewed | Out of scope (not agent configuration) |

## Adopted

- **Working-style section.** A scaffolded `AGENTS.md` carries four short lines (state assumptions,
  smallest change, touch only what is needed, define a check first). Policy `[instructions]
  baseline_guidelines`. Existing instruction files are never edited.

## Why not in every CLAUDE.md

The upstream file is about 600 tokens, loaded in every session of every project. As an on-demand
skill it costs only its description (about 60 tokens). Projects that already have rules keep them;
a long always-loaded file is reported by `TOKEN_BUDGET` and moved to a skill by the restructure step.

## Backlog (not implemented)

1. **Unpinned plugin sources.** Report a marketplace or plugin whose source has no commit or tag pin
   (supply-chain risk). Report only; choosing a commit is the human's call.
2. **Secrets hint.** When `API_KEY_LEAK` or a literal value in `env` is reported, suggest a credential
   broker or `${VAR}` references.
3. **Worktrees and auto-accept.** Report a worktree directory that git does not ignore, and an
   auto-accept permission mode set in committed settings.
4. **Licence field.** The upstream skill declares `license` in its frontmatter; check the key is accepted
   by the reference snapshot before reporting it as unknown.
