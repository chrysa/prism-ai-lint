# prism-ai-lint — Design contract

> Contract for Prism's human-facing surfaces: the terminal report, the interactive review
> (`-i`) and the JSON output read by other tools. Read it before changing what Prism prints,
> asks or emits; update it in the same change.
>
> Status: **[implemented]** links the code · **[decided]** names the decision · **[proposed]**
> is not agreed. This file documents the current surfaces; it does not redesign them.

## 1. Surface and status

- **Surfaces:** command-line report (`text`, default), machine output (`--format json`), and an
  interactive terminal review (`-i`). No graphical UI. **[implemented]**
  ([_engine.py](prism_ai_lint/_engine.py), [tui_app.py](prism_ai_lint/tui_app.py),
  [terminal_view.py](prism_ai_lint/terminal_view.py))
- **Lifecycle:** shipped, public, generic: no organisation's policy is built into these surfaces.

## 2. Users, devices and priority tasks

| User | Context and device | Priority tasks |
| ---- | ------------------ | -------------- |
| Developer maintaining agent config | Terminal, often 80–140 columns, local or over SSH | 1. see what is broken, by severity and file · 2. understand what a repair would change · 3. tell an applied fix from a report-only finding |
| CI job / pre-commit hook | Non-interactive, no TTY | fail or pass with a stable exit code and readable log |
| Another tool | Parses `--format json` | stable fields: level, code, path, message, category, fix mode |

Primary action: read the highest-severity findings first; in `-i`, accept or skip each proposed
change.

## 3. Journeys and navigation

- **J1 — Audit:** `prism-ai-lint --audit` → grouped findings, most severe first, each with code,
  path and message → exit code reflects the result. Read-only. **[implemented]**
- **J2 — Repair:** `--fix` → repairs applied with a backup → the report separates what was fixed
  from what is left for the human. **[implemented]** (D-001: automatic actions only tighten)
- **J3 — Review interactively:** `-i` → sections → each change shown as a diff → explicit
  accept/skip; critical files ask for human validation. **[implemented]**
- **Density:** repeated codes collapse into groups unless `--all`; the brief summary comes first.

- **J4 — Measure:** `prism-ai-lint --usage` → totals, then hook-injected context, tool output, repeated reads and
  failing MCP servers, most costly first; read only, exit 0; `--format json` carries `usage_schema_version`.
  Counts and short hook previews only, never prompt or tool content. **[implemented]**

## 4. Identity

A plain terminal tool: no logo, no banner art, no brand palette. Colour only reinforces severity
already given by a word or symbol. **[implemented]**

## 5. Tokens and components (owned elsewhere)

| Concern | Source of truth | Rules of use |
| ------- | --------------- | ------------ |
| Colour roles (bold, dim, red, green, yellow, cyan) | [terminal_view.py](prism_ai_lint/terminal_view.py) `Tty` | severity first by text/symbol, colour second |
| Width | `Tty.width`: terminal width capped at 140 | wrap and shorten paths, never overflow |
| Wording per code | `HINTS`, `BRIEF_FR`, `BRIEF_EN` in [_engine.py](prism_ai_lint/_engine.py) | one finding = what it means + what to do |

## 6. Interaction and states

- **Feedback:** each finding names its code and file; a fix states the file it changed and where
  the backup is. A failure to apply is listed, never reported as fixed. **[implemented]**
- **Empty state:** a clean run says so explicitly. **[implemented]**
- **Unreadable input:** a file that can not be read is listed (`FILE_NOT_SCANNED`), never counted
  as clean. **[implemented]**
- **Progress:** shown on stderr only on a TTY, never in JSON or quiet output. **[implemented]**
- **Motion:** none — terminal output does not animate.

## 7. Responsive and support conventions

Output stays readable at 80 columns and is plain text without a TTY (CI logs, pipes). The
interactive review needs a TTY and refuses to start without one.

## 8. Accessibility

Meaning never relies on colour alone; `NO_COLOR` disables colour in the interactive review;
French and English wording (`--lang`). Screen-reader use of the terminal output has not been
tested.

## 9. Assets

None: no fonts, icons or images are shipped.

## 10. Acceptance criteria and evidence

- **Criteria:** the most severe finding is visible without scrolling in the brief; every finding
  has a code, a path and an action; `--format json` stays parseable and its fields stable; no
  colour code appears when stdout is not a TTY.
- **Evidence:** the test suite (`tests/`) covers the report shapes, JSON output and interactive
  flows; no manual terminal review was run for this contract.

## 11. Open choices, known gaps and maintenance

- **Known gap:** the non-interactive report decides colour from `isatty()` only; `NO_COLOR` is not
  consulted there. **[proposed]** honour it in both renderers.
- **Maintenance:** any change to printed wording, grouping, exit codes or JSON fields updates this
  file and the matching tests.
