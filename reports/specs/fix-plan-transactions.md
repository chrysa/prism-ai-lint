---
name: fix-plan-transactions
status: draft
author: chrysa
created: 2026-11-08
---

# Spec — Immutable fix plans and transactional apply

## Context / problem

Today a scan fills the report with pending writes (`new_files`, chmods and edits), and `apply()`
then writes them, with backups under `~/.cache/prism-ai-lint/` and a `restore.sh` / restore log.
Proposal and execution are close together: there is no explicit plan object, no check that a file
is unchanged since it was read, no all-or-nothing guarantee, and no check after writing. The audit
V1 (refactoring D, §9, SEC-02/03) asks to separate the proposed change from its execution, with
hash preconditions, a diff, approval and post-verification, and to harden backups.

## Goals

- `--fix` builds an immutable `FixPlan` first; applying it is a separate step.
- Apply is all-or-nothing per run, or reports exactly what was rolled back.
- Backups are a verifiable store, not a loose cache.

## Non-goals

- New fixes or new fix types.
- Changing which fixes are allowed (FIXER_POLICY.md is unchanged).

## Functional requirements

- FR1: `FixPlan` lists operations (create, replace, edit, chmod) with target path, the hash of the
  content read at scan time, the new content hash and a unified diff.
- FR2: The existing read-only `--audit` mode (which already lists every file `--fix --generate`
  would change) can write the plan as JSON (for example `--audit --plan-out <f>`); `--fix
  --plan-file <f>` applies a previously reviewed plan. No second read-only mode is added (the
  Notion open question on a separate `--plan` mode is answered by reusing `--audit`).
- FR3: Before each write, the current file hash must equal the planned precondition; on a mismatch
  the whole apply aborts before any write (or rolls back writes already done).
- FR4: Writes go to temp files and are renamed into place; on any failure, all writes of the run
  are rolled back from backups, and the run reports the rollback.
- FR5: After apply, a re-scan verifies that each fixed finding is gone and that no new finding
  appeared in touched files; otherwise the run reports it (and rolls back, if the policy says so).
- FR6: Backups: a manifest per run (paths, hashes, modes), files created `0600` in a `0700`
  directory, a retention policy, and `--restore <run>` tested end to end.
- FR7: `RunState` becomes an injected `RunContext` for the apply path (audit refactoring B), without
  a global rewrite.

## Acceptance criteria

- [ ] SEC-02, SEC-03 and SEC-04 tests from security-test-matrix pass through the new path.
- [ ] A plan written by `--audit` and applied later produces the same files as a direct `--fix`.
- [ ] A changed file between plan and apply aborts with no write (test).
- [ ] Injected failure on the third write leaves all files as before (test).
- [ ] Backup permissions and manifest are checked by tests; restore round-trips.
- [ ] FIXER_POLICY.md and ARCHITECTURE.md describe the plan/apply split.

## Constraints & dependencies

- Sensitive zone: `apply()` and the re-scan fix loop. Never-loosen and fail-closed apply.
- Depends on security-test-matrix for the scenarios. Moves the apply code out of `_engine.py`
  into one-class modules.

## Risks / open questions

- Audit §11: backup retention duration is undecided (proposal: last 20 runs or 30 days).
- Cross-filesystem renames (user config on another mount) need a copy-then-verify fallback.
