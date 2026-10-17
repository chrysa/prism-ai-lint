"""Checks for mods: plugins whose hooks/hooks.json lists TypeScript/JavaScript `modules`.

A mod runs inside the engine and can rewrite tool calls, run processes and write files, so the
checks that look at what a module does are reports only: nothing here edits a mod."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from prism_ai_lint._runtime import read_text
from prism_ai_lint.report import Report

MODULE_EXT = (".ts", ".tsx", ".js", ".mjs")
REGISTER_RE = re.compile(r"export\s+(?:const|function|async\s+function)\s+register\b")
STATE_RE = re.compile(r"\$\.state\b")
PROCESS_RE = re.compile(r"\$\.process\.")
FS_WRITE_RE = re.compile(r"\$\.fs\.(?:write|append|remove|rm|mkdir|rename|move|copy|delete|unlink|chmod)\w*")
MODEL_RE = re.compile(r"\$\.model\.")
TOOL_CALL_HOOK_RE = re.compile(r"""\bon\(\s*['"]tool\.call['"]""")
TOOL_REWRITE_RE = re.compile(r"\bnext\(\s*\{\s*\.\.\.\s*e\b")
TEST_RE = re.compile(r".*\.test\.[cm]?[jt]sx?$")


class ModChecker:
    """Validate the `modules` of a plugin's hooks.json and flag risky behaviour in the module source."""

    def check(self, root: Path, hooks_file: Path, hooks_data: Any, manifest: Any, rep: Report) -> None:
        if not isinstance(hooks_data, dict) or "modules" not in hooks_data:
            return
        rep.stats["mods"] = rep.stats.get("mods", 0) + 1
        modules = hooks_data["modules"]
        if not isinstance(modules, list) or not modules or not all(isinstance(m, str) for m in modules):
            rep.add("error", "MOD_MODULE", hooks_file, "modules must be a non-empty list of paths")
            return
        resolved_root = root.resolve()
        sources: list[tuple[Path, str]] = []
        for m in modules:
            if not m.startswith("./") or m.startswith("/"):
                rep.add(
                    "error",
                    "MOD_MODULE",
                    hooks_file,
                    f"module {m!r} must be a path relative to hooks/ starting with ./",
                )
                continue
            target = (hooks_file.parent / m).resolve()
            if resolved_root not in target.parents:
                rep.add("error", "MOD_MODULE", hooks_file, f"module {m!r} escapes the plugin root")
                continue
            if target.suffix not in MODULE_EXT:
                rep.add("warn", "MOD_MODULE", hooks_file, f"module {m!r} is not a {'/'.join(MODULE_EXT)} file")
            text = read_text(target)
            if text is None:
                rep.add("error", "MOD_MODULE", hooks_file, f"module {m!r} does not exist")
                continue
            if not REGISTER_RE.search(text):
                rep.add("error", "MOD_MODULE", target, "no `export const register` : the engine finds nothing to call")
            sources.append((target, text))
        self._check_types(root, manifest, sources, rep)
        self._check_behaviour(sources, rep)
        if not any(TEST_RE.match(p.name) for p in root.rglob("*.test.*") if "node_modules" not in p.parts):
            rep.add("info", "MOD_NO_TEST", root, "no *.test.ts: `claude plugin test` has nothing to run")

    @staticmethod
    def _check_types(root: Path, manifest: Any, sources: list[tuple[Path, str]], rep: Report) -> None:
        declared = manifest.get("types") if isinstance(manifest, dict) else None
        if declared is not None:
            if not isinstance(declared, str) or not (root / declared).is_file():
                rep.add(
                    "error",
                    "MOD_TYPES",
                    root / ".claude-plugin" / "plugin.json",
                    f"types {declared!r} is not a file of the plugin",
                )
        elif any(STATE_RE.search(text) for _, text in sources):
            rep.add(
                "warn",
                "MOD_TYPES",
                root / ".claude-plugin" / "plugin.json",
                "the module keeps values in $.state but plugin.json declares no `types` contract",
            )

    @staticmethod
    def _check_behaviour(sources: list[tuple[Path, str]], rep: Report) -> None:
        for path, text in sources:
            if PROCESS_RE.search(text):
                rep.add(
                    "warn", "MOD_PROCESS", path, "the mod runs processes through $.process: review what it can start"
                )
            if FS_WRITE_RE.search(text):
                rep.add(
                    "warn",
                    "MOD_FS_WRITE",
                    path,
                    "the mod writes or deletes files through $.fs: review the paths it touches",
                )
            if MODEL_RE.search(text):
                rep.add("info", "MOD_MODEL", path, "the mod calls a model through $.model: each call costs tokens")
            if TOOL_CALL_HOOK_RE.search(text) and TOOL_REWRITE_RE.search(text):
                rep.add(
                    "warn",
                    "MOD_TOOL_REWRITE",
                    path,
                    "a tool.call hook rewrites the call with next({ ...e }): it can change a command after the permission rules matched",
                )
