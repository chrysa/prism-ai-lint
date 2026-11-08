---
name: roadmap-v1
status: draft
created: 2026-11-08
base: main @ c115378 (v2.7.1)
---

# Plan — prism-ai-lint roadmap V1

## Summary

This plan turns the "Audit technique et roadmap V1" (2026-11-08) into PR-sized steps, after checking
each proposal against the code on `main` so nothing already shipped is planned again. It also folds
in the open items from Notion, Drive, Shortcut and GitHub issues. Positioning is unchanged: an
independent, open-source engine that checks, secures and optimises AI coding-agent configuration,
generic at its core, never loosening. It is not an agent orchestrator, a task manager, an LLM host
or a Ruff/Sonar replacement. CHRYSA-specific rules move to external policy packs.

Each product step has a spec in `reports/specs/<slug>.md` (status `draft`). A spec is approved by
the owner, then gets its own `reports/plans/<slug>.md` (the `/plan` gate) before any code.

## Sources

- Audit V1: Drive `plop` doc 1dKOk4IuKbKkw51pWqhGtEPe-i8jc_5_5w4EVfITCp-s; Notion
  https://app.notion.com/p/41259293e35e813b9a38cd65f30d8eca
- Project page (owner to-do, CI notes): https://app.notion.com/p/3eb59293e35e81cb9913da270a4a41a6
- Ideas archive 2026-10-04/06 (not yet decided): https://app.notion.com/p/40459293e35e8187af66ed5bcd528ea5
- Drive `plop`: multi-LLM compatibility (1I_t6F_N6y_swsg6aIFkKqbSWYgJh7dp-S1tGfKpLIEE), "Règle IA ou
  script" (1f0dIvKbtppMDBjYZMGz119jzTNs9qNwb-ctwYeNn5qk), continuous-improvement watch
  (1z4qxbY_FytWDXVoYzH9xvHFfxzkHdT5GPTTmwk_odsg), client-server sync (1v6gIB7qbJ3kgrVQxWyLfK_kv4l8F7w1AX8nleM3e_W4)
- Shortcut: sc-5824 (Sonar key), sc-5282 (`DOCKERHUB_TOKEN`). No prism-ai-lint epic exists.
- GitHub issues open: #3, #7, #8, #15, #17, #18, #22, #25, #26, #108.

## What already exists (do not re-plan)

Checked on `main` @ c115378:

- `Finding(level, code, path, message, fixable)`: no rule id, severity scale, confidence, evidence
  or remediation fields.
- Feedback JSON has `feedback_schema_version: 1`; conversion JSON has `conversion_schema_version: 1`.
- No SARIF, no baseline/suppression file, no `FixPlan`, no policy packs.
- `DesignContractChecker` (#109): presence, nesting, size, always-loaded, dead links, external
  links and wiring (`DESIGN_*` codes). Contract sections, UI-profile gating and contradictions are
  not covered.
- `_reference.py`: one `DOCS_SNAPSHOT = "2026-10"` and `MODEL_SNAPSHOT = "2026-10"`; no per-reference
  observation date and no staleness signal.
- Guard returns before plugins load (guard does not depend on plugins).
- Scans import every top-level `*.py` from `$CLAUDE_CONFIG_DIR/plugins` (default `~/.claude/plugins`,
  which is also Claude Code's own plugin directory), `./.prism-ai-lint/plugins` and
  `./.ai-lint/plugins` (relative to the current directory, not the scanned repo), with no trust
  gate (`plugin_registry.py:35-66`). Found by reading the code; not reproduced yet.
- mypy disables 11 error codes; CI coverage floor is `--fail-under=60`; 125 `noqa` in the package.
- `_engine.py` is 7879 lines; 60 modules exist beside it.
- Self-update (`self_update.py`, `git pull --ff-only` after confirmation) and the feedback
  contract (`fix_mode`, `next_action`) exist; issues #18 and #17 look done and need a check.

## Tracks and steps

Branches start from `main` (the real integration branch). One step = one branch, one PR, squash
merge, no force push. Every PR: tests, docs in the same commit, `make check` and `make selfcheck`
(`traces in repo: 0`) green, and a compatibility and rollback note in the PR body.

### Track O — owner actions (no code)

| Step | Action | Unblocks |
| ---- | ------ | -------- |
| O1 | Create the PyPI and TestPyPI pending publishers (`prism-ai-lint`, owner `chrysa`, `release.yml`, env `pypi` / `testpypi`) | publishing, #8 |
| O2 | Set `DOCKERHUB_TOKEN` (account `chrys4`), then rerun the latest release run with `--failed` | Docker image, sc-5282 |
| O3 | Delete the unused `PYPI_API_TOKEN` secret (D-039) | hygiene |
| O4 | Rename the SonarCloud key to `chrysa_prism-ai-lint`, then mark draft #113 ready and merge it | sc-5824 |
| O5 | Switch the default branch to `main`, or delete `develop`; then close or merge draft #112 | issue auto-close, audits read the right branch |
| O6 | Decide the 86 open align PRs (merge with `--admin`, or merge by hand) and the `no-story` label rule for shortcut-link | align rollout |
| O7 | Decide the 7 padam repos (neutrality hook) | align rollout |

### Track H — hygiene (small dev chores)

- H1 Issue triage: close #108 (shipped by #109 on `main`); check #17, #18 against the code and close
  or narrow them; narrow #8 to "owner publishing config" once O1-O2 are done. Needs owner OK to
  close issues.
- H2 Fix `.claude/skills/plan-start/SKILL.md` and the audit text that call `develop` the default
  branch, once O5 is decided.
- H3 Before any public announcement: compare against agnix (rule count, SARIF) and write the
  differentiation (portfolio coherence, multi-LLM behind a router). Market-study task, not code.

### Phase P0 — security and quality foundations (parallel PRs)

| Step | Spec | Depends on | Parallel with |
| ---- | ---- | ---------- | ------------- |
| P0.1 | [plugin-trust-gate](../../reports/specs/plugin-trust-gate.md) | — | P0.3, P0.4, P0.5 |
| P0.2 | [security-test-matrix](../../reports/specs/security-test-matrix.md) | P0.1 (for SEC-05) | P0.3, P0.4, P0.5 |
| P0.3 | [quality-ratchet](../../reports/specs/quality-ratchet.md) | — | all P0 |
| P0.4 | [design-contract-sections](../../reports/specs/design-contract-sections.md) | — | all P0 |
| P0.5 | [dated-references](../../reports/specs/dated-references.md) | — | all P0 |

P0 exit criteria (from the audit): zero CLI regression; never-loosen tests green; read-only scan
output unchanged except for documented new findings; no write outside the scanned scope; guard
proven fail-closed as a real hook.

### Phase P1 — reporting and safe apply

| Step | Spec | Depends on | Parallel with |
| ---- | ---- | ---------- | ------------- |
| P1.1 | [structured-findings](../../reports/specs/structured-findings.md) | P0.3 (typing) | P1.4 |
| P1.2 | [sarif-output](../../reports/specs/sarif-output.md) | P1.1 | P1.3 |
| P1.3 | [baseline-suppressions](../../reports/specs/baseline-suppressions.md) | P1.1 | P1.2 |
| P1.4 | [fix-plan-transactions](../../reports/specs/fix-plan-transactions.md) | P0.2 | P1.1 |
| P1.5 | [canonical-agent-model](../../reports/specs/canonical-agent-model.md) | P1.1, P0.2 (SEC-09) | P1.2, P1.3 |

P1 exit criteria: versioned JSON, SARIF accepted by GitHub code scanning, round-trip conversion
tested, rollback demonstrated by tests.

### Phase P2 — policy, sovereignty, cost (specs after P1 starts)

- Policy packs: versioned schema, rule provenance, unknown keys reported as info. Move CHRYSA
  signals out of the core (`project_profile.py` detection of `standards/STANDARDS.chrysa.md`;
  `critical_content_policy.py` defaults for chrysa files). Needs decision QST-0466 (boundary with
  guideline-checker).
- Execution class per check: `scripted` / `ai_assisted` / `ai_required` with a cost/gain reason
  (project DoD, "Script > IA" rule). Field lands in P1.1; populating it is P2.
- Sovereignty checks (opt-in): external endpoints, telemetry, retention, residency, offline
  capability. "Unknown provider" is never reported as "proven leak".
- Cost analysis: separate estimates from measured values; loaded context, skills, MCP, double
  compression. Needs a decision on D-030 (generated settings default to haiku/low), which the
  audit asks not to impose.
- New rules from the ideas archive: `AGENT_PERSONA_BOILERPLATE`, `AGENT_CAPABILITY_OVERGRANT`,
  `AGENT_DESTRUCTIVE_UNGATED`, `AGENT_PROMISE_UNBACKED`; contradiction, rule-that-should-be-a-hook,
  vendor reference in a neutral source, hand-edited generated output; MCP/skill pruning
  recommendations.

### Phase P3 — extensibility (no spec in V1)

Local API, community catalogue, richer TUI (#7), portfolio dashboard, desktop runtime verification
(#26, `runtime_verified=false` today), config sync architecture (Q079: CLI + git first). Criteria
from the audit: authentication and permissions fit for purpose, no engine duplication.

### Cross-cutting — engine extraction (#3)

No big-bang refactor. Each P0/P1 PR moves the code it touches out of `_engine.py` into a one-class
module (repo standard: one class per file, methods not free functions, messages out of
`_engine.py`). `RunState` becomes an injected `RunContext` inside P1.4, where apply needs it.
Track `_engine.py` line count in each PR body.

## Verification per step

- `make check` (ruff, mypy, pytest) and `make selfcheck` green locally.
- CI runs the tools directly (`python -m ruff`, `python -m mypy`, `python -m pytest`,
  `python tests/_selfcheck.py`, coverage), never `make`.
- Security steps: the new tests fail on the vulnerable behaviour before the fix (red first).

## Decisions needed before or during the plan

1. Plugin trust default (P0.1): repo-local plugins off unless trusted — proposed in the spec.
2. Backup retention and location policy (P1.4; audit §11).
3. Security exception policy and suppression expiry rules (P1.3).
4. Python compatibility strategy beyond 3.13/3.14 (P0.3).
5. D-030 vs audit §8 on default model and effort (P2 cost).
6. QST-0466: prism-ai-lint and guideline-checker boundary (P2 policy packs).
7. Tracking: GitHub issues per step (proposed; no Shortcut epic exists) or a new Shortcut epic
   (Q-V3-46).

## Risks

- Scope creep toward an orchestrator: each spec states non-goals.
- New findings raise noise on the 120+ aligned repos: new rules start at `info` or behind policy
  flags, and the baseline (P1.3) lands before stricter defaults.
- JSON consumers: schema changes are additive and versioned; old fields stay.
