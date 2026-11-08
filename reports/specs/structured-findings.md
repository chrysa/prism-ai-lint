---
name: structured-findings
status: draft
author: chrysa
created: 2026-11-08
---

# Spec — Structured findings and a versioned JSON report

## Context / problem

`Finding` has five fields: `level`, `code`, `path`, `message`, `fixable`. Consumers (CI, SARIF,
baseline, TUI, portfolio views) need more: a stable rule identity, a location range, the evidence
that triggered the rule, why it matters, how to fix it, and where the rule came from. The feedback
JSON (`feedback_schema_version: 1`) already adds `fix_mode` and `next_action` at report level; the
audit V1 (refactoring C) and issue #17 ask for this per finding. The project DoD also asks each
check to declare whether it is `scripted`, `ai_assisted` or `ai_required`.

## Goals

- Every finding carries the fields below, filled by the check or by a rule registry default.
- JSON output gets a new schema version, additive: existing fields keep their names and meaning.
- SARIF (sarif-output) and baseline (baseline-suppressions) build on these fields only.

## Non-goals

- Changing which findings are emitted or their levels.
- SARIF and baseline themselves (separate specs).

## Functional requirements

- FR1: New `Finding` fields: `rule_id` (stable, equals `code` for existing rules), `rule_version`,
  `severity` (error/warning/info mapped from `level`), `confidence` (high/medium/low), `range`
  (optional start/end line and column), `evidence` (short, secret-redacted excerpt or key path),
  `rationale`, `remediation`, `fixability` (auto/interactive/manual, aligned with `fix_mode`),
  `policy_source` (built-in, policy file path, plugin name), `execution_class`
  (`scripted`/`ai_assisted`/`ai_required`, default `scripted`).
- FR2: A rule registry holds per-rule defaults (rationale, remediation, version, execution class)
  so checks do not repeat them; messages stay out of `_engine.py`.
- FR3: JSON report gains `report_schema_version: 2` with the fields; version 1 fields are still
  present.
- FR4: Text output is unchanged by default; `-v` shows rationale and remediation.
- FR5: A stable fingerprint per finding (rule_id + normalised path + evidence key), for baseline.
- FR6: Evidence never contains a secret value (reuse the existing redaction).

## Acceptance criteria

- [ ] Every rule code in the codebase has a registry entry (test fails on a missing one).
- [ ] JSON schema v2 documented in `docs/user/` with an example; v1 consumers still parse.
- [ ] A golden-file test on a fixture repo pins the JSON v2 output.
- [ ] Fingerprints are identical across two runs and across machines (path normalisation test).
- [ ] Text output of the existing tests is unchanged.

## Constraints & dependencies

- Benefits from quality-ratchet (typing) landing first.
- `Finding` stays a dataclass in its own module; the registry is its own class.
- Plugins can set the new fields; missing fields get defaults.

## Risks / open questions

- `range` is not known for many checks (whole-file findings): optional by design.
- Severity mapping for the existing `level` values must be agreed once and recorded in DECISIONS.md.
