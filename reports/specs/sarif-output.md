---
name: sarif-output
status: draft
author: chrysa
created: 2026-11-08
---

# Spec — SARIF export and CI annotations

## Context / problem

Results are available as text and JSON only. GitHub code scanning, IDEs and most CI dashboards read
SARIF 2.1.0. Competing tools (agnix) already export SARIF. The audit V1 (§7, P1) asks for SARIF,
stable JSON and CI annotations.

## Goals

- The existing `--format` option (today `text` or `json`) gains `sarif`, which writes a valid
  SARIF 2.1.0 log.
- GitHub code scanning accepts the upload and shows findings on the right files and lines.
- A GitHub Actions annotation mode for runs without code scanning.

## Non-goals

- A bundled GitHub Action or upload step (documented example only).
- Changing finding content.

## Functional requirements

- FR1: One SARIF `run` per invocation, `tool.driver` named `prism-ai-lint` with version and rules
  (id, short and full description, help text from remediation, default level).
- FR2: Each finding maps to a `result` with `ruleId`, `level`, message, location (path relative to
  the repo root, region from `range` when known) and `partialFingerprints` from the finding
  fingerprint.
- FR3: Suppressed findings (baseline-suppressions) appear with `suppressions` entries, not dropped.
- FR4: `--format github` prints `::error` / `::warning` / `::notice` workflow commands.
- FR5: Output is deterministic (stable ordering) and never contains secret values.

## Acceptance criteria

- [ ] SARIF output validates against the SARIF 2.1.0 JSON schema in tests (schema file vendored
      under `tests/`, no runtime dependency).
- [ ] A golden SARIF file for a fixture repo.
- [ ] A documented workflow example uploads it with `github/codeql-action/upload-sarif`.
- [ ] `--format github` covered by a test.

## Constraints & dependencies

- Depends on structured-findings (rule ids, ranges, fingerprints).
- Stdlib `json` only.

## Risks / open questions

- User-scope findings (`~/.claude`) have no repo path: either skipped in SARIF or reported against a
  synthetic location; the owner picks.
