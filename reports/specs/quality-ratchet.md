---
name: quality-ratchet
status: approved
author: chrysa
created: 2026-11-08
---

# Spec — Ratchet typing, coverage and lint suppressions

## Context / problem

Quality gates are looser than the tool's own security role needs:

- mypy disables 11 error codes (`type-arg`, `no-untyped-def`, `no-untyped-call`, `var-annotated`,
  `no-any-return`, `attr-defined`, `index`, `arg-type`, `assignment`, `type-var`, `misc`);
- the CI coverage floor is 60 % (`--fail-under=60`);
- the package carries 125 `noqa` comments (mostly complexity: C901, PLR09xx, PLR2004, PERF401).

The audit asks to re-enable `arg-type`, `assignment`, `index`, `attr-defined` and `no-any-return`
step by step, and to raise core coverage toward 85 %, with strong coverage of mutation paths.

## Goals

- Each step tightens one gate and never loosens another.
- The five codes named by the audit are enabled, one code per PR.
- Coverage floor rises in steps to 85 % for the core, with mutation paths (apply, guard, permission
  logic, secret scan) measured separately.
- `noqa` count goes down; new code adds none without a reason comment.

## Non-goals

- Enabling all 11 codes or `--strict` in V1.
- Refactoring for its own sake: a `noqa` is removed by splitting the function only where that file
  is already touched or the split is mechanical.

## Functional requirements

- FR1: One PR per mypy code, in this order: `no-any-return`, `attr-defined`, `index`, `arg-type`,
  `assignment`. Each PR removes the code from `disable_error_code` and fixes all resulting errors.
- FR2: Coverage floor steps: 60 → 65 → 70 → 75 → 80 → 85 (core). Each step is its own PR with the
  tests that justify it.
- FR3: A per-area floor for mutation paths (apply/fix loop, guard, permission checks, secret scan)
  at 90 % or a value the owner sets.
- FR4: A CI check (or pre-commit hook) fails when the `noqa` count in `prism_ai_lint/` grows.
- FR5: Test matrix extended: wheel install, install from a git tag, pre-commit hook usage,
  offline run, Python 3.13/3.14, Debian and Windows (WSL at minimum) runners.

## Acceptance criteria

- [ ] `pyproject.toml` no longer disables the five audit codes.
- [ ] CI `--fail-under` is 85 for the core; mutation paths meet FR3.
- [ ] `noqa` count is lower than 125 and guarded against growth.
- [ ] CI runs the FR5 install/runtime matrix, directly (no `make`).
- [ ] TESTING.md documents floors and how to raise them.

## Constraints & dependencies

- `pyproject.toml` stays the single source for tool config.
- CI keeps running tools directly (`python -m mypy`, `python -m pytest`, coverage).
- Python 3.13 minimum; no compatibility shims below.

## Risks / open questions

- `_engine.py` (7879 lines) holds most errors; fixes there may be large. Prefer moving touched code
  into one-class modules (issue #3) over annotating the monolith.
- Windows runners may expose path bugs: those go to the security matrix (SEC-10) as issues.
- Audit §11: Python compatibility strategy beyond 3.14 is undecided.
