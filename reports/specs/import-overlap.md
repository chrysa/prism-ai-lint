---
name: import-overlap
status: approved
author: chrysa
created: 2026-11-13
---

# Spec — Lines repeated from an imported instruction file

## Context / problem

`CLAUDE.md` imports `AGENTS.md`, and the shared-standards generator writes the same standards block into both.
Both load at launch, so the block is paid twice every session (~1,550 tokens in this repository; same pattern across
the fleet). `INSTR_DUPLICATED` only compares user and project scope. Owner request 2026-11-13: token savings first.

## Goals

- Report an always-loaded file that repeats lines of a file it imports, with the tokens paid twice.

## Non-goals

- Editing `CLAUDE.md` or `AGENTS.md` (critical content; the fix belongs to the generator).

## Functional requirements

- FR1: `INSTR_IMPORT_OVERLAP` (warn) when `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` shares at least 5
  lines of `min_duplicate_line_len` chars or more with a file it imports, directly or transitively, inside the repo.
- FR2: code blocks and HTML comments do not count; imports outside the repo are ignored.
- FR3: the message names the imported file, the number of repeated lines and the tokens loaded twice.

## Acceptance criteria

- [x] `tests/test_import_overlap.py` (8 tests, red before).
- [x] DECISIONS D-048, `docs/user/tokens.md`.
