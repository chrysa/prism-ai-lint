# Open work

State at 2026-10-28. Linter on `main`: v1.22.0. Items are split by who has to act.
No secret value appears here; credentials are referred to by name only.

## Waiting on a human decision or action

| Item | Why it is blocked | Next step once unblocked |
| --- | --- | --- |
| GuardRails "1 new security issue" on the APE hook PRs | The finding is only readable in the GuardRails dashboard (login). The check summary is empty. The hook file is byte-identical on `chrysa/dotfiles` (passes) and `chrysa/D-D` (fails), so it looks like a baseline difference, not a code difference. | Read the finding, then fix the hook once in `claude-config` and re-run `bin/ape_update.sh`, or accept it with a traced decision. |
| `chrysa/project-init` #268 | Install of the private `chrysa-quality-gate` now works (read-only deploy key, `RUN --mount=type=ssh`). Docker tests still fail: coverage 24% for a floor of 80%. `scripts/gen_context_files.py` has no test; `scripts/quality_gate.py` is a stale vendored copy that tests no longer import. | Choose: delete the vendored copy and repoint `makefiles/quality-gate.Makefile` to the package commands, then add tests for `gen_context_files.py` or exclude it explicitly. The 80% floor is not lowered. |
| Merge of the 4 clean linter PRs | `skunk-simulator` #73, `django-query-optimizer-vscode` #226, `guideline-checker` #476, `linkendin-resume` #504 have no real failing check (only billing and metadata). Not merged: waiting for a go. | Squash-merge with `--admin` after a manual secret grep of each diff. |
| `chrysa/pre-commit-hooks-changelog` #257 | Every test job fails (Python 3.9 to 3.14), plus Pre-commit, Docker tests and Sonar. Not compared with the base branch yet. | Compare with `develop`; fix or drop the PR. |
| Organisation `heya` | Third-party org (20 JavaScript repos, last push 2020). Neither `chrysa` nor `anthony-greau` can push, and neither has a commit there, so the scope rule "only repos where the user committed" matches none. Nothing was done. | Only on an explicit go that waives the commit rule; it would mean fork-based PRs to strangers. |
| Merge of docs PR #92 | A push to `main` cuts a release. | Decide whether this docs-only change justifies one. |
| Home Assistant token | The old token was removed from `~/.claude-perso/.claude.json` (now `Bearer ${HOME_ASSISTANT_TOKEN}`). A new token has to be generated in Home Assistant. | Set `HOME_ASSISTANT_TOKEN` in the Claude Code environment. |
| Anthropic API key in `dev-nexus/backend/.env` | Key must be revoked and recreated in the console. | Replace the value in the file with an environment reference. |
| Read-only `--plan` mode | Idea only: group proposed fixes by severity without writing. Per-project overrides in `.prism-ai-lint.toml` also considered. Nothing implemented. | Decide whether to study it. Must stay stdlib-only and never loosen. |

## Follow-ups that depend on the items above

- `chrysa/github-actions`: second PR so the reusable "Quality Gates" job gets the same `CHRYSA_LIB_DEPLOY_KEY` (after #268 is green).
- 55 APE hook PRs (`fix/ape-hook-json-stdin`, hardened hook pushed 2026-10-25): 14 still waiting on Bandit/Trivy, 37 blocked by the GuardRails finding, 1 mergeable (`dotfiles` #54, held on purpose). `chrysa/server` and 3 other repos have no PR. Re-run `python3 ~/.cache/prism-batch/bin/ape_classify.py` after the cause is known; merge only where `guardrails/scan` passes and the remaining failures are billing or metadata (labels, size-label, shortcut-link, branch-policy), with a manual secret grep of the diff when Gitleaks could not run.
- Linter batch of 2026-10-28 (v1.22.0, 88 `chrysa` repos): 73 had no change, 3 commits were stacked on open PRs (`arena-techno`, `github-actions`, `usefull-containers`, CI not checked), 12 new PRs. Real CI failures on the new ones: `personal-cfo` #4 (Sonar), `diy-stream-deck` #247 (PR dependencies, Sonar), `django-app-forge` #198 (Docker tests, Sonar, quality gates), `floating-agent` #278 and `project-init` #269 (Docker tests, quality gates; both were red before), `pre-commit-tools` #461 (pre-commit hooks, quality gates), `shared-standards` #613 (pre-commit checks), `pre-commit-hooks-changelog` #257 (see above). Ten of them use the branch `chore/prism-ai-lint-v1-22` because `chore/prism-ai-lint-full` already existed on the remote with no open PR and a push there was not forced.
- Older red PRs to rebase on the fixed `develop`: `epub-sorter` #211/#216, `django-query-optimizer` #234/#235/#240, `usefull-containers` #242/#245, `github-actions` #320/#321/#324, `shared-standards` #598/#601.
- Real failures unrelated to APE, to triage per repo: `server` #402 (Gitleaks), `lifeos` #282, `django-traceid` #194, `gestureOS` #159, `django-app-forge` #197, `floating-agent` #277, `guideline-checker` #471, `pre-commit-tools` #459, `plateform_socle` #396 (Gitleaks, do not force).

## Housekeeping

- Local `ruff` reports 2 `BLE001` in the tracked `.claude/hooks/format.py`. Not in CI, untouched.
- `.claude/skills/check/SKILL.md` shows as deleted in the working tree; that deletion predates this work and must not be committed.
- Clone failures to retry: `av-devtool`, `django-app-forge`, `42_save`, `django-pytest`.
- 5 files still carry an attribution trace (`ATTR_TRACE`) to clean.
- Notion: duplicate empty row "prism-ai-lint — Archive du journal" (ID fiche 549) can be removed.
- Batch tooling: a `grep` run through RTK can print instead of redirect; build repo lists with Python. The batch scripts refuse to run when the linter checkout lacks `origin/main`.

## Done

- v1.21.0 released with the APE hook, MCP reserved-name and subagent-name checkers; `main` is now v1.22.0.
- APE hook hardened (sha256, private per-user marker directory, symlink-safe) and merged in `claude-config` #226.
- Lint fix PRs merged: `epub-sorter` #217, `github-actions` #325, `usefull-containers` #246, `shared-standards` #606, `django-query-optimizer` #242 (Sonar gate and Docker tests green).
- Deploy key and repo secret created for `project-init`; private key shredded locally; PR #268 open.
- Linter v1.22.0 applied to all 88 allowed `chrysa` repos (no merge). The APE hook needs nothing more: the other 33 repos have no APE hook (32) or are up to date (1).
