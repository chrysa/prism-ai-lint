---
name: design-contract-sections
status: approved
author: chrysa
created: 2026-11-08
---

# Spec — DESIGN.md contract content checks for UI projects

## Context / problem

`DesignContractChecker` (#109) checks that DESIGN.md files exist, are wired into the instruction
files, stay small, are not always loaded, and have no dead or external links. The audit V1 §5 asks
for more, for projects that have a user interface:

- activation by project profile (web, mobile, desktop, game UI), never imposed on repos without UI;
- a configurable contract path;
- expected sections (UX principles, navigation, responsive, accessibility, design tokens,
  components, empty/loading/error states, interactions, animation, assets, licence/provenance,
  visual tests);
- separate findings for "contract absent", "rule not tested" and "contradiction observed";
- `--generate` as a proposal only.

A known limitation from #109 also applies: `design_files` is a free function and the repo is walked
twice per run (repo standard: methods, not free functions).

## Goals

- UI projects get actionable findings on what their design contract is missing.
- Non-UI projects see no new finding.
- One repository walk per run for design discovery.

## Non-goals

- Judging design quality or certifying accessibility: static inspection cannot guarantee real UX
  (stated in the report).
- Writing or rewriting a DESIGN.md without human approval.
- Copying an inherited external design contract into the repo.

## Functional requirements

- FR1: The checker runs only when the project profile detects a UI stack (React, Vue, Angular,
  Svelte, React Native or other mobile, Electron/Tauri/Qt desktop, Godot/Unity/Unreal game UI).
- FR2: The contract path is configurable in the policy (`[design] path`, default `DESIGN.md`); an
  inherited contract (link to external standards) satisfies presence.
- FR3 (owner decision 2026-11-08: opt-in): D-044 stays the default — no section schema is imposed.
  Section checks run only when the policy sets `[design] sections = [...]`; missing sections are then
  reported per section at `info`. D-044 is amended (opt-in sections), not reversed.
- FR4: Three distinct finding codes: contract absent (UI project, no contract), rule not tested
  (contract states a rule that no test or tool config enforces, where an adapter can tell), and
  contradiction observed (contract vs a real file, where an adapter exists, for example declared
  tokens vs a theme file).
- FR5: `--generate` proposes a skeleton DESIGN.md with the expected headings and no invented
  content; writing it follows the critical-content approval flow.
- FR6: Discovery is a method of the checker, walks the repo once and is shared with
  `claude_files_checker`.

## Acceptance criteria

- [ ] Fixtures: React web app, mobile app, desktop app, game, plus a CLI/library repo with no UI.
- [ ] The no-UI fixture produces zero design findings.
- [ ] Each FR4 code has a positive and a negative test.
- [ ] `--generate` output is a proposal; nothing is written without approval (test).
- [ ] A test asserts a single walk (for example by counting `os.walk` calls).
- [ ] `docs/user/checks.md`, README and `prism-ai-lint.example.toml` (regenerated with
      `--print-policy`) document the new codes and policy keys.

## Constraints & dependencies

- Project profile detection (`project_profile.py`, `desktop_checker.py`) is the source of UI
  detection; extend it rather than duplicating detection.
- Stdlib only. One class per file. Messages outside `_engine.py`.

## Risks / open questions

- "Rule not tested" needs per-stack adapters; V1 may ship only one adapter (for example accessibility
  lint config present for a React app). The owner picks which.
- Section names vary by language (FR/EN headings): matching must accept both.
