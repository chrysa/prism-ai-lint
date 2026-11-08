# Custom checks

Add a `.py` file to `~/.config/prism-ai-lint/plugins/` (`$XDG_CONFIG_HOME` honoured) or to any directory you pass
with `--plugin-dir DIR`:

```python
def register(api):
    @api.check("MY_RULE", scope="project")  # or scope="user"
    def _rule(ctx):
        p = ctx.path("forbidden.txt")
        if p.is_file():
            ctx.add(
                "warn",
                "MY_RULE",
                p,
                "forbidden.txt must not be committed",
                action_en="delete it or add it to .gitignore",
            )
```

`ctx` provides `root`, `path(*parts)`, `read(path)`, `glob(pattern)` and
`add(level, code, path, message, action_fr=..., action_en=..., fixable=...)`. Plugin findings
appear in the normal report and obey the catalogue. A plugin that raises is reported and
skipped; it never crashes a run. `prism-ai-lint --list-plugins` shows what loaded.

## Where plugins load from (D-046)

Plugins are Python code, so a scan never imports them from the scanned repository without consent:

| Location | Loaded |
| -------- | ------ |
| `--plugin-dir DIR` | yes: explicit trust |
| `~/.config/prism-ai-lint/plugins/` | yes |
| `<Claude config dir>/plugins/*.py` (old location) | yes, with a `PLUGIN_DIR_DEPRECATED` warning (not in CI or pre-commit): move them |
| `./.prism-ai-lint/plugins/`, `./.ai-lint/plugins/` (current directory) | only after you answer `y` to the prompt of an interactive run |

CI (`CI` set), pre-commit (`PRE_COMMIT` set), `--format json`, `-q` and any run without a terminal never
load current-directory plugins: they report `PLUGIN_SKIPPED_UNTRUSTED` instead. To keep a repo-local plugin
in such a run, pass its directory explicitly: `prism-ai-lint . --plugin-dir .prism-ai-lint/plugins`.
`--list-plugins` shows each directory and why it was skipped. Plugins never run in guard mode.

Also treated as current-directory plugins (prompt, never automatic): a user or Claude config directory that
resolves inside the current directory (for example `CLAUDE_CONFIG_DIR` pointed into a CI checkout). In those
directories symlinked `*.py` files are ignored, a directory whose file names contain control characters is
refused without a prompt, and only the files listed in the prompt are imported. A relative `XDG_CONFIG_HOME`
is ignored, as the XDG specification requires.
