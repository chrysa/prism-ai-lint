---
name: dated-references
status: approved
author: chrysa
created: 2026-11-08
---

# Spec — Dated, sourced reference data with a staleness signal

## Context / problem

The rules mirror official docs through `prism_ai_lint/_reference.py`. Today the dating is two
module constants (`DOCS_SNAPSHOT = "2026-10"`, `MODEL_SNAPSHOT = "2026-10"`) plus comments. Nothing
records, per reference, which page it came from and when it was observed, and nothing warns when
the snapshot is old. The Notion project notes also record that the snapshot came from a partial read
of the official pages, and that a DECISIONS.md sentence about refreshing is out of date. The audit
V1 asks for a "dated snapshot/reference mechanism" in P0.

## Goals

- Each reference group carries its source URL and observation date.
- Reports can say how old the reference data is, and flag it when it is past a threshold.
- Updating a reference is a reviewable, dated change.

## Non-goals

- Fetching docs at run time (the tool stays offline and deterministic).
- Automatically refreshing the snapshot.

## Functional requirements

- FR1: Reference groups (hooks events, settings keys, permission modes, model lineup, Codex config
  keys, and so on) declare `source` (URL) and `observed` (ISO date).
- FR2: `-v` and JSON output show the oldest observation date used by the run.
- FR3: When the oldest date is older than a policy threshold (default 120 days), the run emits an
  `info` finding with the stale groups.
- FR4: Unknown keys in user config stay `info` by default, never `error`, when the only reason is
  a missing reference (audit §7).
- FR5: A maintainer script lists groups by age to plan refreshes.
- FR6: DECISIONS.md and ARCHITECTURE.md describe the mechanism; the outdated sentence about
  snapshot refresh is fixed.

## Acceptance criteria

- [ ] Every group in `_reference.py` has `source` and `observed`; a test fails if one is missing.
- [ ] A test with a fake "today" checks the stale finding threshold.
- [ ] JSON exposes the oldest observation date under a versioned key.
- [ ] Selfcheck stays at `traces in repo: 0`.

## Constraints & dependencies

- `_reference.py` is a sensitive zone: any value change needs a doc reference and a date.
- Deterministic output: the "today" used for staleness is injectable for tests.

## Risks / open questions

- Granularity: per group (proposed) or per key. Per key is heavy to maintain.
- Threshold default: 120 days is a proposal; the owner sets it.
