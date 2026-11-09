---
name: model-per-task
status: approved
author: chrysa
created: 2026-11-09
---

# Spec — Model per task

## Context / problem

Analysis of 2026-11-09 (Drive `plop`, "assignation des modèles par tâche"): D-030 sets generated project sessions to
haiku, and the generated `code-reviewer`, `security-auditor` and `infra-reviewer` set no model, so 212 review and
audit subagents in 88 fleet repositories run on the smallest model. The linter also missed `claude-sonnet-4-5`
pinned in two skills, and proposed Haiku for QA and debugging agents.

## Goals

- Security and review subagents never run on Haiku without a finding.
- Generated judgment agents pin `sonnet`; the session default stays the cheapest (D-030 kept).
- Legacy model ids are found by generation, in settings, agents and skills.
- The mechanical-subagent heuristic stops suggesting Haiku for judgment work.

## Non-goals

- Changing D-030 or any session default.
- Routing models automatically at run time.

## Functional requirements

- FR1: `--generate` writes `model: sonnet` in code-reviewer, security-auditor, infra-reviewer.
- FR2: `SUBAGENT_MODEL_UNDERSIZED` (warn) for a security or review subagent on Haiku, pinned or inherited.
- FR3: `MODEL_LEGACY` by generation, and on agent and skill frontmatter.
- FR4: `TOKEN_SUBAGENT_MODEL` excludes subagents whose name or description has a judgment word.

## Acceptance criteria

- [x] Tests in `tests/test_model_per_task.py` (red before, green after).
- [x] DECISIONS D-047, `docs/user/tokens.md`.

## Constraints & dependencies

Owner decision 2026-11-09 (Shortcut sc-6023). The fleet realignment (one PR per repository adding `model: sonnet`;
Optiways local only) follows the release.
