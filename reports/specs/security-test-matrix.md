---
name: security-test-matrix
status: approved
author: chrysa
created: 2026-11-08
---

# Spec — Hostile-input test matrix for the fixer and the guard

## Context / problem

The audit V1 (2026-11-08) lists ten security scenarios (SEC-01..SEC-10) for the fixer, the guard,
conversions and plugins. They are hypotheses, not confirmed bugs. Some are partly covered today
(symlink handling in 8 test files, fail-closed in 3, idempotence in 1); none is covered as a
systematic matrix, and there is no hostile-plugin test. A security tool needs proof, not intent.

## Goals

- One test module per scenario family, with hostile fixtures, that states the expected safe outcome.
- Each scenario either passes (documented as covered) or reproduces a bug that gets its own fix PR.
- The matrix runs in CI on 3.13 and 3.14, Linux; the path scenario also covers Windows-style paths.

## Non-goals

- Fixing every reproduced bug in this PR: each confirmed bug gets a focused fix PR with its test.
- Fuzzing infrastructure or new dependencies.
- Transaction design (that is fix-plan-transactions; this spec only tests today's apply).

## Functional requirements

Scenarios, each with at least one fixture:

- FR1 (SEC-01): path traversal, symlinks and absolute paths in config and targets: no write outside
  the scanned scope or `~/.cache/prism-ai-lint/`.
- FR2 (SEC-02): a file changed between scan and apply: apply aborts for that file, nothing is
  overwritten.
- FR3 (SEC-03): failure in the middle of apply (simulated write error, `ENOSPC`): previous files
  are restored or the restore path is reported, and the restore log is consistent.
- FR4 (SEC-04): `--fix` run twice: the second run changes nothing.
- FR5 (SEC-05): hostile plugin (raises, loops, mutates the report, imports at load): the scan
  degrades safely; the guard is unaffected. Depends on plugin-trust-gate for the loading rules.
- FR6 (SEC-06): the guard run as a real hook process with malformed input, internal exceptions and
  timeouts: it exits with the blocking code, never allows.
- FR7 (SEC-07): secrets in scanned files never appear in text, JSON, backups, logs or issue
  reports; backup files are not world-readable.
- FR8 (SEC-08): pathological inputs (huge files, deep nesting, recursion, symlink loops, very long
  lines): bounded time and memory, a finding instead of a crash.
- FR9 (SEC-09): Claude ↔ Codex ↔ AGENTS conversion and `--align`: no permission becomes wider in
  the output than in the input.
- FR10 (SEC-10): Windows and POSIX path forms (drive letters, backslashes, UNC, case) are classified
  the same way by scope checks.

## Acceptance criteria

- [ ] `tests/security/` (or `tests/test_sec_*.py`) holds one module per scenario, named by SEC id.
- [ ] Each test documents the expected outcome in its docstring.
- [ ] A coverage table in TESTING.md maps SEC-01..10 to tests and states covered / bug filed.
- [ ] Every reproduced bug has a GitHub issue linked from the table.
- [ ] CI runs the matrix; no test is skipped without a reason string.

## Constraints & dependencies

- Fixtures use dummy secrets that `API_KEY_LEAK` treats as test values only through the existing
  `claude-secret-ok` marker; no real-looking live key is committed.
- Tests write only to `tmp_path`; `CLAUDE_CONFIG_DIR` and `CODEX_HOME` point to temp dirs.
- Depends on plugin-trust-gate for FR5.

## Risks / open questions

- Some scenarios may need small seams (injectable writer, clock) to be testable; those seams belong
  to the fix PRs, not to this one.
- Timeout values for FR6/FR8 must stay stable on slow CI runners.
