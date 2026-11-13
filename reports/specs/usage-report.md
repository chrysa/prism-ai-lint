---
name: usage-report
status: approved
author: chrysa
created: 2026-11-13
---

# Spec — Measured token use (`--usage`)

## Context / problem

Owner request 2026-11-13: save tokens. The TOKENS block estimates always-loaded context only; it cannot see
per-call hook injections, tool output size, repeated reads or cache writes. Audit V1 §8 asks to separate estimates
from measurements.

## Goals

- Report what recent sessions really sent, ranked so the costliest lever comes first.

## Non-goals

- Sending data anywhere; reading prompt or tool content; judging (no findings, exit 0).

## Functional requirements

- FR1: `--usage` reads `<config dir>/projects/<slug>/*.jsonl` (slug: every non-alphanumeric character of the absolute
  project path becomes `-`), newest `--usage-sessions N` first (default 10).
- FR2: totals per API response (deduplicated by message id): calls, input, cache read, cache write, output; compactions.
- FR3: hook-injected texts (`hook_additional_context`) grouped by hook and first 60 chars, ranked by tokens.
- FR4: tool output size per tool; Read paths read more than once; MCP servers failing to connect (sessions).
- FR5: text and JSON (`usage_schema_version: 1`); malformed or oversized lines skipped.

## Acceptance criteria

- [x] `tests/test_usage_report.py` (6 tests, red before), including "tool output never printed".
- [x] D-050, DESIGN.md J4, README, `docs/user/tokens.md`, ARCHITECTURE.
