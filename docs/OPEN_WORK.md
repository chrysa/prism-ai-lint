# Open work

State at 2026-10-27. Released: v1.21.0 (APE hook, MCP and subagent checkers). Items are split by who has to act.
No secret value appears here; credentials are referred to by name only.

## Waiting on a human decision or action

| Item | Why it is blocked | Next step once unblocked |
| --- | --- | --- |
| GuardRails "1 new security issue" on the APE hook PRs | The finding is only readable in the GuardRails dashboard (login). The check summary is empty. The hook file is byte-identical on `chrysa/dotfiles` (passes) and `chrysa/D-D` (fails), so it looks like a baseline difference, not a code difference. | Read the finding, then fix the hook once in `claude-config` and re-run `bin/ape_update.sh`, or accept it with a traced decision. |
| `chrysa/project-init` #268 | Install of the private `chrysa-quality-gate` now works (read-only deploy key, `RUN --mount=type=ssh`). Docker tests still fail: coverage 24% for a floor of 80%. `scripts/gen_context_files.py` has no test; `scripts/quality_gate.py` is a stale vendored copy that tests no longer import. | Choose: delete the vendored copy and repoint `makefiles/quality-gate.Makefile` to the package commands, then add tests for `gen_context_files.py` or exclude it explicitly. The 80% floor is not lowered. |
| Home Assistant token | The old token was removed from `~/.claude-perso/.claude.json` (now `Bearer ${HOME_ASSISTANT_TOKEN}`). A new token has to be generated in Home Assistant. | Set `HOME_ASSISTANT_TOKEN` in the Claude Code environment. |
| Anthropic API key in `dev-nexus/backend/.env` | Key must be revoked and recreated in the console. | Replace the value in the file with an environment reference. |
| Read-only `--plan` mode | Idea only: group proposed fixes by severity without writing. Per-project overrides in `.prism-ai-lint.toml` also considered. Nothing implemented. | Decide whether to study it. Must stay stdlib-only and never loosen. |
| Linter batch with v1.21.0 | Not relaunched on the allowed repos. | Decide who runs it (one PR per repo). |

## Follow-ups that depend on the items above

- `chrysa/github-actions`: second PR so the reusable "Quality Gates" job gets the same `CHRYSA_LIB_DEPLOY_KEY` (after #268 is green).
- 55 APE hook PRs (`fix/ape-hook-json-stdin`, hardened hook pushed 2026-10-25): 14 still waiting on Bandit/Trivy, 37 blocked by the GuardRails finding, 1 mergeable (`dotfiles` #54, held on purpose). `chrysa/server` and 3 other repos have no PR. Re-run `python3 ~/.cache/prism-batch/bin/ape_classify.py` after the cause is known; merge only where `guardrails/scan` passes and the remaining failures are billing or metadata (labels, size-label, shortcut-link, branch-policy), with a manual secret grep of the diff when Gitleaks could not run.
- Older red PRs to rebase on the fixed `develop`: `epub-sorter` #211/#216, `django-query-optimizer` #234/#235/#240, `usefull-containers` #242/#245, `github-actions` #320/#321/#324, `shared-standards` #598/#601.
- Real failures unrelated to APE, to triage per repo: `server` #402 (Gitleaks), `lifeos` #282, `django-traceid` #194, `gestureOS` #159, `django-app-forge` #197, `floating-agent` #277, `guideline-checker` #471, `pre-commit-tools` #459, `plateform_socle` #396 (Gitleaks, do not force).

## Housekeeping

- Local `ruff` reports 2 `BLE001` in the tracked `.claude/hooks/format.py`. Not in CI, untouched.
- `.claude/skills/check/SKILL.md` shows as deleted in the working tree; that deletion predates this work and must not be committed.
- Clone failures to retry: `av-devtool`, `django-app-forge`, `42_save`, `django-pytest`.
- 5 files still carry an attribution trace (`ATTR_TRACE`) to clean.
- Notion: duplicate empty row "prism-ai-lint — Archive du journal" (ID fiche 549) can be removed.

## Done this cycle

- v1.21.0 released with the APE hook, MCP reserved-name and subagent-name checkers.
- APE hook hardened (sha256, private per-user marker directory, symlink-safe) and merged in `claude-config` #226.
- Lint fix PRs merged: `epub-sorter` #217, `github-actions` #325, `usefull-containers` #246, `shared-standards` #606, `django-query-optimizer` #242 (Sonar gate and Docker tests green).
- Deploy key and repo secret created for `project-init`; private key shredded locally.
