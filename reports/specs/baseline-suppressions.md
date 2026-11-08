---
name: baseline-suppressions
status: draft
author: chrysa
created: 2026-11-08
---

# Spec — Baseline and justified, expiring suppressions

## Context / problem

The linter runs on 120+ repositories. New rules (design contract, references, agent rules) will
raise findings on all of them at once, and there is no way to accept existing findings while
blocking new ones. The audit V1 (§7) asks for a baseline with a stable fingerprint, a PR diff, and
suppressions that are justified, validated and expire, without ever hiding a new critical
regression.

## Goals

- Teams can adopt new rules without a flag day: known findings are baselined, new ones fail.
- Every suppression has a reason, an owner and an expiry date.
- A critical security finding can never be silenced by the baseline alone.

## Non-goals

- Inline `# noqa`-style comments inside agent config files.
- A server-side store; the baseline is a file in the repo.

## Functional requirements

- FR1: `--baseline-create` writes `.prism-ai-lint.baseline.json` with the fingerprints of current
  findings, the tool version and the date.
- FR2: With a baseline present, findings whose fingerprint is in it are reported as `baselined`
  (still visible in JSON/SARIF) and do not affect the exit code; new findings do.
- FR3: Suppression entries need `reason`, `owner` and `expires` (ISO date); an expired entry stops
  suppressing and is itself reported.
- FR4: Findings flagged critical (secret leak, permission loosening, guard bypass) are never
  suppressed by a baseline entry; they need an explicit, separately listed exception the owner
  approves.
- FR5: `--baseline-diff <ref>` reports findings added and removed against a git ref (for PRs).
- FR6: The baseline file is critical content: changes to it go through the approval flow.

## Acceptance criteria

- [ ] Tests: create, apply, new finding fails, baselined finding passes, expiry, critical not
      suppressible.
- [ ] Fingerprints survive unrelated edits to the same file (test).
- [ ] Docs explain adoption on an existing repo in three commands.

## Constraints & dependencies

- Depends on structured-findings (fingerprints, severity).
- Never-loosen: the baseline changes reporting and exit codes, never what `--fix` does.

## Risks / open questions

- Audit §11: the exact policy for security exceptions is undecided; FR4 proposes "critical is never
  baselined". The owner confirms the critical list.
- Default expiry length (proposal: 90 days, maximum 180).
