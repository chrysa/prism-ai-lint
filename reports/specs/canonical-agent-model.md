---
name: canonical-agent-model
status: draft
author: chrysa
created: 2026-11-08
---

# Spec — Canonical agent-config model with loss reports

## Context / problem

`AgentContract`, `AgentConverter` and the Claude / Codex / AGENTS adapters produce read-only
conversion previews (#35), and `--align` mirrors Claude Code deny/ask rules to Codex
(`.codex/rules/prism-ai-lint.rules`) across 120+ repos. The mapping is spread over adapters and the
aligner; there is no single canonical representation, no report of what each target cannot express,
and no round-trip proof. The audit V1 (§6, P1) asks for a canonical model of permissions, hooks,
skills, agents, instructions, models, MCP servers and scopes, versioned adapters, a semantic-loss
report and round-trip tests, without promising "lossless".

## Goals

- One canonical, versioned model that every adapter reads from and writes to.
- Every conversion states what was lost or approximated, per item.
- No conversion ever widens a permission (SEC-09).

## Non-goals

- New target tools in this spec (Gemini, Cursor, Windsurf come later, once the model holds).
- Writing critical instruction files without approval (unchanged).

## Functional requirements

- FR1: Canonical model covers instructions (with imports), permissions (allow/deny/ask with scope),
  hooks (event, matcher, command), skills, subagents, model and effort settings, MCP servers
  (transport, env refs, scope) and their provenance.
- FR2: Adapters for Claude Code, Codex and AGENTS read into and render from the model; each adapter
  declares its version and the target docs snapshot date.
- FR3: Each conversion returns a loss report: items dropped, approximated or tightened, with the
  reason; it appears in JSON (conversion schema version 2) and in the TUI.
- FR4: Permission rendering only ever keeps or tightens: an item that cannot be expressed safely is
  dropped and reported, never widened.
- FR5: `--align` uses the model, and its output for the current fleet stays byte-identical unless a
  change is documented.

## Acceptance criteria

- [ ] Round-trip tests: Claude → model → Claude and Codex → model → Codex are identity on
      fixtures, or the loss report explains each difference.
- [ ] Property-style test: for generated permission sets, the rendered output is never wider than
      the input.
- [ ] `--align` golden tests on the existing fixtures are unchanged.
- [ ] docs/agent-conversion.md describes the model, adapters and loss report.

## Constraints & dependencies

- Depends on structured-findings (loss items reuse finding fields) and on the SEC-09 tests.
- Permission logic is a sensitive zone: never loosen.
- Stdlib only.

## Risks / open questions

- Hooks semantics differ deeply between tools; expect many "approximated" items.
- Re-running `--align` across the fleet after this change needs owner approval (open PRs).
