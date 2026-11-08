---
name: plugin-trust-gate
status: approved
author: chrysa
created: 2026-11-08
---

# Spec — Load plugins only from trusted locations

## Context / problem

`PluginRegistry.load()` imports and runs every top-level `*.py` found in three directories on every
scan (not the guard):

- `$CLAUDE_CONFIG_DIR/plugins` (default `~/.claude/plugins`, a directory Claude Code also owns);
- `./.prism-ai-lint/plugins` and `./.ai-lint/plugins`, relative to the current working directory.

Nothing asks for consent. Running `prism-ai-lint .` inside a cloned repository, or as a pre-commit
hook or CI step on a pull request, can therefore run Python code that the repository supplies. For a
tool whose job is to secure agent configuration, scanning an untrusted repo must never execute it.

Status: found by reading `plugin_registry.py:35-66` and `_engine.py:7656`; a harmless reproduction is
part of the acceptance criteria (audit rule: no bug is claimed before reproduction).

## Goals

- A scan never executes code from the scanned repository or the current directory unless the user
  opted in for that exact location.
- User-level plugins keep working, from a directory prism-ai-lint owns.
- The guard stays independent of plugins (it already returns before loading them).

## Non-goals

- Sandboxing trusted plugins (a trusted plugin is trusted code).
- Declarative, non-executable rules: that is the policy-packs work (P2).
- Changing the plugin API (`register(api)`).

## Functional requirements

- FR1: Repo-local and cwd-relative plugin directories are never loaded without consent.
- FR2 (owner decision 2026-11-08: ask interactively): in an interactive run (TTY, text output),
  prism-ai-lint lists the plugins found in a repo-local or cwd-relative directory and asks before
  importing them (default answer: no). CI, pre-commit, JSON output, pipes and every other
  non-interactive run never load them and report them instead (FR4). `--plugin-dir <dir>` is the
  explicit, prompt-free opt-in for one directory. A repo's own config file cannot opt itself in.
- FR3: The user plugin directory moves to a prism-ai-lint-owned path (for example
  `~/.config/prism-ai-lint/plugins`); the old `~/.claude/plugins` top-level `*.py` keep loading for
  one deprecation window, with a warning finding.
- FR4: When plugins exist in a skipped location, the report says so (an `info` finding with the
  path and how to opt in), so the behaviour change is visible.
- FR5: `--plugin-dir <dir>` keeps working and counts as an explicit opt-in for that directory.
- FR6: `--list-plugins` shows each discovered plugin and whether it was loaded or skipped, and why.

## Acceptance criteria

- [ ] A test repo with `.prism-ai-lint/plugins/probe.py` writing a marker file: a default scan run
      from inside it leaves no marker (red before the change, green after).
- [ ] Same repo with the explicit opt-in: the plugin loads and its checks run.
- [ ] A plugin placed in the scanned repo by a pre-commit run (cwd = repo) is not loaded.
- [ ] Old user plugin location still loads, with a deprecation warning finding.
- [ ] `--guard` never imports any plugin (regression test).
- [ ] README and `docs/user/` explain plugin locations, the opt-in and the migration.
- [ ] DECISIONS.md records the trust model.

## Constraints & dependencies

- Never-loosen and fail-closed rules (CLAUDE.md). Default is the safe behaviour.
- Stdlib only. One class per file; messages outside `_engine.py`.
- This is a behaviour change for anyone with repo-local plugins: release as `feat!` or document a
  migration path; the owner decides the bump.

## Risks / open questions

- Is there any known user of repo-local plugins (fleet repos)? A quick search across the aligned
  repos for `.prism-ai-lint/plugins` decides how long the deprecation lasts.
- Audit §11 open question "isolation level of third-party plugins": this spec answers only "where
  from"; isolation stays open.
