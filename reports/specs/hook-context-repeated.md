---
name: hook-context-repeated
status: approved
author: chrysa
created: 2026-11-13
---

# Spec — Hooks that inject context on every call

## Context / problem

Owner request 2026-11-13 (token savings first). A measured session carried ~975 copies of a graphify hint injected
on Bash calls (the same hook declared in user and project settings, so it ran twice), ~200 prompt reminders and ~135
pytest hints. Each injection stays in context and is re-read every later turn.

## Goals

- Report hooks that inject text on high-frequency events, with the size when known.
- Report the same hook declared in user and project scope.

## Non-goals

- Running hooks, or editing settings (report only).

## Functional requirements

- FR1: `HOOK_CONTEXT_REPEATED` (info) for PreToolUse, PostToolUse, PostToolUseFailure, UserPromptSubmit handlers with
  inline `additionalContext`, an echo/printf on UserPromptSubmit, or a script emitting `additionalContext`.
- FR2: `HOOK_DUPLICATE_SCOPE` (warn) for an identical event/matcher/command in user and project settings.
- FR3: SessionStart and other once-per-session events are never reported.

## Acceptance criteria

- [x] `tests/test_hook_context.py` (9 tests, red before).
- [x] DECISIONS D-049, `docs/user/tokens.md`.
