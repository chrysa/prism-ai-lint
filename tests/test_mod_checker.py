"""Mods: plugins whose hooks/hooks.json lists TypeScript `modules`."""

from __future__ import annotations

import json

from prism_ai_lint.mod_checker import ModChecker
from prism_ai_lint.report import Report

GOOD = "import type { Register } from 'claude-code'\nexport const register: Register = (on) => {}\n"


def _mod(tmp_path, source=GOOD, modules=("./register.tsx",), manifest=None):
    (tmp_path / ".claude-plugin").mkdir()
    manifest = manifest if manifest is not None else {"name": "demo", "version": "0.1.0"}
    (tmp_path / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest))
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "hooks.json").write_text(json.dumps({"modules": list(modules)}))
    if source is not None:
        (tmp_path / "hooks" / "register.tsx").write_text(source)
    return tmp_path


def _run(root):
    rep = Report()
    hooks = root / "hooks" / "hooks.json"
    ModChecker().check(
        root,
        hooks,
        json.loads(hooks.read_text()),
        json.loads((root / ".claude-plugin" / "plugin.json").read_text()),
        rep,
    )
    return {(f.level, f.code) for f in rep.findings}


def test_clean_mod_only_misses_a_test(tmp_path):
    assert _run(_mod(tmp_path)) == {("info", "MOD_NO_TEST")}


def test_missing_module_file(tmp_path):
    assert ("error", "MOD_MODULE") in _run(_mod(tmp_path, source=None))


def test_module_path_must_stay_inside_plugin(tmp_path):
    assert ("error", "MOD_MODULE") in _run(_mod(tmp_path, modules=("../../x.ts",)))


def test_module_path_must_start_with_dot_slash(tmp_path):
    assert ("error", "MOD_MODULE") in _run(_mod(tmp_path, modules=("register.tsx",)))


def test_module_without_register_export(tmp_path):
    assert ("error", "MOD_MODULE") in _run(_mod(tmp_path, source="export const other = 1\n"))


def test_state_without_types_contract_and_declared_types_must_exist(tmp_path):
    assert ("warn", "MOD_TYPES") in _run(_mod(tmp_path, source=GOOD + "const x = $.state\n"))


def test_declared_types_file_missing(tmp_path):
    root = _mod(tmp_path, manifest={"name": "demo", "types": "./types/index.d.ts"})
    assert ("error", "MOD_TYPES") in _run(root)


def test_behaviour_reports_are_warnings_not_fixes(tmp_path):
    src = (
        GOOD
        + "$.process.run('x'); $.fs.write('a','b'); $.model.ask('q')\non('tool.call', {tool:'Bash'}, ($, e, next) => next({ ...e }))\n"
    )
    rep = Report()
    root = _mod(tmp_path, source=src)
    hooks = root / "hooks" / "hooks.json"
    ModChecker().check(root, hooks, json.loads(hooks.read_text()), {"name": "demo", "types": None}, rep)
    codes = {f.code for f in rep.findings}
    assert {"MOD_PROCESS", "MOD_FS_WRITE", "MOD_MODEL", "MOD_TOOL_REWRITE"} <= codes
    assert not any(f.fixable for f in rep.findings)


def test_lint_does_not_add_an_empty_hooks_key_to_a_mod(env, tmp_path):
    root = _mod(tmp_path)
    before = (root / "hooks" / "hooks.json").read_text()
    env.run(str(root), "--fix", "--no-cli", "--no-history")
    assert (root / "hooks" / "hooks.json").read_text() == before
