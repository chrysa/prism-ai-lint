"""A repair keeps a JSON file's keys sorted when the file had them sorted."""

from __future__ import annotations

import json

from prism_ai_lint.json_key_order import JsonKeyOrder
from prism_ai_lint.report import Report


def _dump(data, sort_keys=False):
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=sort_keys) + "\n"


SORTED_HOOK = {"command": "node", "name": "guard", "timeout": 10, "type": "command"}


def _settings(hook):
    return {"hooks": {"PreToolUse": [{"hooks": [hook], "matcher": "Bash"}]}, "permissions": {"deny": ["Read(.env)"]}}


def test_a_key_added_to_a_sorted_file_is_written_back_sorted():
    original = _dump(_settings(SORTED_HOOK))
    repaired = _dump(_settings({**SORTED_HOOK, "args": ["${CLAUDE_PROJECT_DIR}/guard.cjs"]}))
    out = JsonKeyOrder.preserve(original, repaired)
    assert out == _dump(json.loads(repaired), sort_keys=True)
    assert list(json.loads(out)["hooks"]["PreToolUse"][0]["hooks"][0]) == ["args", "command", "name", "timeout", "type"]


def test_an_unsorted_file_keeps_insertion_order():
    original = _dump({"type": "command", "command": "node", "name": "guard"})
    repaired = _dump({"type": "command", "command": "node", "name": "guard", "args": ["x"]})
    assert JsonKeyOrder.preserve(original, repaired) == repaired


def test_too_little_evidence_of_sorting_keeps_insertion_order():
    original = _dump({"permissions": {"deny": ["Read(.env)"]}})
    repaired = _dump({"permissions": {"deny": ["Read(.env)"]}, "$schema": "https://example.test/s.json"})
    assert JsonKeyOrder.preserve(original, repaired) == repaired


def test_jsonc_or_hand_shaped_text_is_left_alone():
    sorted_text = _dump(_settings(SORTED_HOOK))
    repaired = _dump(_settings({**SORTED_HOOK, "args": ["x"]}))
    assert JsonKeyOrder.preserve("// comment\n" + sorted_text, repaired) == repaired
    compact = json.dumps(_settings({**SORTED_HOOK, "args": ["x"]}))
    assert JsonKeyOrder.preserve(sorted_text, compact) == compact


def test_ordered_pairs_counts_and_detects_disorder():
    assert JsonKeyOrder.ordered_pairs(_settings(SORTED_HOOK)) == 5
    assert JsonKeyOrder.ordered_pairs([{"b": 1, "a": 2}]) is None
    assert JsonKeyOrder.ordered_pairs("scalar") == 0


def test_report_edit_sorts_against_the_on_disk_original(tmp_path):
    path = tmp_path / ".claude" / "settings.json"
    original = _dump(_settings(SORTED_HOOK))
    step1 = _dump(_settings({**SORTED_HOOK, "args": ["x"]}))
    rep = Report()
    rep.edit(path, original, step1)
    assert rep.edits[path] == (original, _dump(json.loads(step1), sort_keys=True))
    chained = json.loads(rep.edits[path][1])
    chained["permissions"]["ask"] = ["Bash(git push *)"]
    rep.edit(path, rep.edits[path][1], _dump(chained))
    assert rep.edits[path][1] == _dump(chained, sort_keys=True)


def test_report_edit_leaves_non_json_and_new_files_alone(tmp_path):
    rep = Report()
    md = tmp_path / "CLAUDE.md"
    rep.edit(md, "a\n", "b\n")
    assert rep.edits[md] == ("a\n", "b\n")
    new = tmp_path / "new.json"
    rep.new_files[new] = (_dump({"b": 1}), 0o644)
    rep.edit(new, "", _dump({"b": 1, "a": 2}))
    assert rep.new_files[new][0] == _dump({"b": 1, "a": 2})


def test_exec_form_repair_of_a_sorted_settings_file_stays_sorted(linter_module, tmp_path):
    m = linter_module
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "guard.cjs").write_text("process.exit(0)\n")
    p = tmp_path / ".claude" / "settings.json"
    hook = {"command": "node .claude/hooks/guard.cjs", "name": "guard", "timeout": 10, "type": "command"}
    p.write_text(_dump(_settings(hook)))
    rep = m.Report()
    m.check_settings(p, tmp_path, "project", m.load_policy(None, [tmp_path]), rep)
    assert p in rep.edits
    new = rep.edits[p][1]
    fixed = json.loads(new)["hooks"]["PreToolUse"][0]["hooks"][0]
    assert "args" in fixed
    assert new == _dump(json.loads(new), sort_keys=True)
