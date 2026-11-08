---
name: plugin-trust-gate
status: approved
spec: reports/specs/plugin-trust-gate.md
created: 2026-11-08
---

# Plan — Load plugins only from trusted locations

## Summary

Add one class, `PluginTrust` (new module `prism_ai_lint/plugin_trust.py`), that classifies every
discovered plugin directory before `PluginRegistry.load()` imports anything:

| Source | Decision |
| ------ | -------- |
| `--plugin-dir DIR` (CLI) | load: explicit opt-in |
| `~/.config/prism-ai-lint/plugins` (new user dir, `$XDG_CONFIG_HOME` honoured) | load: owned by the user |
| `$CLAUDE_CONFIG_DIR/plugins/*.py` (old user dir, shared with Claude Code) | load + `PLUGIN_DIR_DEPRECATED` warning, one minor-release window |
| `./.prism-ai-lint/plugins`, `./.ai-lint/plugins` (current directory) | interactive run: ask, default "no"; otherwise skip + `PLUGIN_SKIPPED_UNTRUSTED` info |

A run is interactive only when stdin and stderr are TTYs, `--format text`, not `--quiet`, and
neither `CI` nor `PRE_COMMIT` is set (same rule as `SelfUpdater._skip_for_run`, plus `PRE_COMMIT`,
which pre-commit sets for its hooks). The prompt goes through an injected input function so tests
drive it. The guard path is unchanged: `main()` returns from `--guard` before plugins load.

## Files to touch

| File | Change |
| ---- | ------ |
| `prism_ai_lint/plugin_trust.py` (new) | `PluginTrust`: `sources(extra)`, `decide(source)`, `is_interactive(args)`, injected `ask_fn` |
| `prism_ai_lint/plugin_registry.py` | `plugin_dirs()` returns tagged sources; `load()` takes the trust decisions; new `skipped: list[tuple[Path, str]]` |
| `prism_ai_lint/_engine.py` | wire `PluginTrust` in `main()` before `load_plugins`; `--list-plugins` shows loaded / skipped and why; emit the two findings |
| message tables (`HINTS`, `feedback_renderer.py` FR/EN) | `PLUGIN_SKIPPED_UNTRUSTED`, `PLUGIN_DIR_DEPRECATED` hints and messages (kept out of `_engine.py` where the table allows) |
| `tests/test_plugin_trust.py` (new) | see Tests |
| `tests/test_plugins.py` | keep passing (`load_plugins([dir])` = explicit opt-in) |
| `docs/user/plugins.md`, `README.md` | locations, prompt, CI/pre-commit behaviour, migration; fix the doc that says `<repo>/.prism-ai-lint/plugins` (code reads the current directory) |
| `DECISIONS.md` | D-046 plugin trust model |
| `context-map.json`, `llms-full.txt` | regenerated with `scripts/gen_context_files.py` |

## Steps

1. Red test: a probe plugin in `./.prism-ai-lint/plugins` writes a marker file on import; a
   non-interactive scan run from that directory must leave no marker (fails today).
2. Add `PluginTrust` with source classification and `is_interactive`; unit tests per source.
3. Change `PluginRegistry.plugin_dirs/load` to load only allowed sources and record skipped ones
   with a reason; keep `load(extra)` loading `extra` (explicit) for API compatibility.
4. Wire it in `main()`: build `PluginTrust(args, ask_fn=input-on-stderr)`, pass decisions to
   `load_plugins`; add the two findings to the report of the first scanned repo (once per run).
5. `--list-plugins`: print sources with `loaded` / `skipped (reason)` / `deprecated`.
6. New user dir: discover `~/.config/prism-ai-lint/plugins`; old `$CLAUDE_CONFIG_DIR/plugins/*.py`
   still load with `PLUGIN_DIR_DEPRECATED`.
7. Docs (user page, README, D-046) and regenerated context files in the same commit.

## Tests

- `test_cwd_plugin_not_imported_without_consent` — marker absent (AC1, red first).
- `test_interactive_yes_loads_and_no_skips` — injected `ask_fn` (AC2, FR2).
- `test_pre_commit_and_ci_never_load_even_with_tty` — `PRE_COMMIT=1` / `CI=1` with a fake TTY (AC3).
- `test_plugin_dir_flag_is_explicit_opt_in` — `--plugin-dir` loads without a prompt (FR5).
- `test_old_user_dir_loads_with_deprecation_finding` (AC4, FR3).
- `test_guard_never_imports_plugins` — `--guard` with a probe plugin present: no marker (AC5).
- `test_list_plugins_shows_skipped_reason` (FR6).
- Existing `tests/test_plugins.py` stays green.

## Risks & rollback

- Behaviour change: CI or pre-commit setups that rely on cwd plugins stop loading them and get an
  info finding telling them to pass `--plugin-dir`. Proposed commit type `fix!:` with a
  `BREAKING CHANGE:` footer (major bump) — owner decides; `fix:` keeps a minor/patch bump.
- `$CLAUDE_CONFIG_DIR/plugins` is also Claude Code's plugin cache: only top-level `*.py` are
  considered, as today.
- Rollback: revert the PR; no data or config migration is written.

## Standards checklist

- [ ] One class per file (`PluginTrust`), methods not free functions, messages out of `_engine.py`
- [ ] ≤40 lines/function, ≤5 args, complexity ≤10 in new code
- [ ] ruff-check + ruff-format clean; mypy clean
- [ ] `make check` and `make selfcheck` (`traces in repo: 0`) green
