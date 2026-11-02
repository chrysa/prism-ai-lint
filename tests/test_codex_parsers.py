"""Codex `.rules` and `apply_patch` parsers: read statically, rebuild exactly or refuse."""

from __future__ import annotations

import pytest

from prism_ai_lint.codex_patch import CodexPatch
from prism_ai_lint.codex_rules import CodexRules
from prism_ai_lint.patch_error import PatchError
from prism_ai_lint.rules_parse_error import RulesParseError

parse_rules, decision_for, render_rule = CodexRules.parse, CodexRules.decision_for, CodexRules.render


def parse_patch(command):
    return CodexPatch().parse(command)


def apply_update(old, chunks, strict=False):
    return CodexPatch().apply_update(old, chunks, strict=strict)


def test_rules_default_decision_is_allow_and_unions_expand():
    rules = parse_rules('prefix_rule(pattern = ["gh", "pr", ["view", "list"]])\n')
    assert [(r.command, r.decision) for r in rules] == [("gh pr view", "allow"), ("gh pr list", "allow")]


def test_rules_most_restrictive_decision_wins():
    rules = parse_rules(
        'prefix_rule(pattern = ["git"], decision = "allow")\nprefix_rule(pattern = ["git", "push"], decision = "forbidden")\n'
    )
    assert decision_for(rules, ("git", "push", "origin")) == "forbidden"
    assert decision_for(rules, ("git", "status")) == "allow"
    assert decision_for(rules, ("ls",)) is None


@pytest.mark.parametrize(
    "text",
    [
        "prefix_rule(pattern = some_var)\n",  # not a literal: would need executing the file
        'prefix_rule(["git"])\n',  # positional form is not documented
        'prefix_rule(pattern = ["git"], decision = "maybe")\n',
        "prefix_rule(pattern = [])\n",
        "prefix_rule(\n",  # syntax error
        'prefix_rule(pattern = [["a","b","c","d","e","f"],["a","b","c","d","e","f"]])\n',  # 36 > 32 prefixes
    ],
)
def test_rules_unreadable_forms_raise(text):
    with pytest.raises(RulesParseError):
        parse_rules(text)


def test_render_rule_roundtrips_and_escapes():
    text = render_rule(("echo", 'say "hi"'), "forbidden", "it's a test")
    (rule,) = parse_rules(text)
    assert rule.prefix == ("echo", 'say "hi"') and rule.decision == "forbidden"
    with pytest.raises(ValueError):
        render_rule(("x",), "allow-all", "nope")


def _patch(body: str) -> str:
    return f"*** Begin Patch\n{body}*** End Patch\n"


def test_patch_update_rebuilds_text():
    (op,) = parse_patch(_patch("*** Update File: a.txt\n@@\n one\n-two\n+TWO\n three\n"))
    assert op.kind == "update"
    assert apply_update("one\ntwo\nthree\n", op.chunks) == "one\nTWO\nthree\n"
    assert op.added_text() == "TWO"


def test_patch_add_delete_move_and_heredoc_envelope():
    ops = parse_patch(
        "apply_patch <<'EOF'\n"
        + _patch("*** Add File: n.txt\n+hello\n*** Delete File: old.txt\n*** Update File: m.txt\n*** Move to: m2.txt\n")
        + "EOF\n"
    )
    assert [(o.kind, o.path, o.move_to) for o in ops] == [
        ("add", "n.txt", None),
        ("delete", "old.txt", None),
        ("update", "m.txt", "m2.txt"),
    ]
    assert ops[0].lines == ["hello"]


def test_patch_argv_list_form():
    (op,) = parse_patch(["apply_patch", _patch("*** Add File: x\n+1\n")])
    assert op.path == "x"


@pytest.mark.parametrize(
    "command",
    [
        "no envelope",
        _patch(""),
        _patch("stray text\n"),
        _patch("*** Add File: a\nnot-plus\n"),
        _patch("*** Update File: a\n"),
        _patch("*** Move to: b\n"),
        _patch("*** Update File: a\n@@\n?weird\n"),
    ],
)
def test_patch_malformed_raises(command):
    with pytest.raises(PatchError):
        parse_patch(command)


def test_patch_unique_rejects_ambiguous_chunk():
    (op,) = parse_patch(_patch("*** Update File: a\n@@\n-x\n+y\n"))
    assert apply_update("x\nx\n", op.chunks) == "y\nx\n"
    with pytest.raises(PatchError):
        apply_update("x\nx\n", op.chunks, strict=True)


def test_patch_chunk_that_does_not_match_raises():
    (op,) = parse_patch(_patch("*** Update File: a\n@@\n-missing\n+y\n"))
    with pytest.raises(PatchError):
        apply_update("x\n", op.chunks)


def test_patch_anchor_and_end_of_file():
    (op,) = parse_patch(_patch("*** Update File: a\n@@ [b]\n-k = 1\n+k = 2\n*** End of File\n"))
    assert apply_update("[a]\nk = 1\n[b]\nk = 1\n", op.chunks) == "[a]\nk = 1\n[b]\nk = 2\n"
    with pytest.raises(PatchError):  # the anchor decides between two equal lines: not certain enough
        apply_update("[a]\nk = 1\n[b]\nk = 1\n", op.chunks, strict=True)
    (pure_add,) = parse_patch(_patch("*** Update File: a\n@@\n+tail\n"))
    assert apply_update("x\n", pure_add.chunks) == "x\ntail\n"


def test_added_only_chunk_goes_to_end_of_file_even_with_anchor():
    (op,) = parse_patch(_patch("*** Update File: c\n@@ [tui]\n+hooks = false\n"))
    text = "[tui]\nanimations = true\n[features]\nfast_mode = true\n"
    assert apply_update(text, op.chunks, strict=True).endswith("[features]\nfast_mode = true\nhooks = false\n")


def test_blank_line_before_chunk_is_skipped():
    (op,) = parse_patch(_patch("*** Update File: c\n\n@@\n-a\n+b\n"))
    assert op.chunks[0].old == ["a"] and apply_update("a\n", op.chunks) == "b\n"


def test_anchor_text_is_kept_verbatim():
    (op,) = parse_patch(_patch("*** Update File: c\n@@   # x\n-k\n+K\n"))
    assert op.chunks[0].anchor == "  # x"


def test_fuzzy_match_is_refused_in_strict_mode():
    (op,) = parse_patch(_patch("*** Update File: c\n@@\n-a = 1\n+a = 2\n"))
    assert apply_update("a = 1   \n", op.chunks) == "a = 2\n"  # Codex matches ignoring trailing spaces
    with pytest.raises(PatchError):
        apply_update("a = 1   \n", op.chunks, strict=True)


def test_same_text_inside_a_string_is_ambiguous_in_strict_mode():
    (op,) = parse_patch(
        _patch('*** Update File: c\n@@\n-sandbox_mode = "read-only"\n+sandbox_mode = "danger-full-access"\n')
    )
    text = 'sandbox_mode = "read-only"\n\ndeveloper_instructions = """\nsandbox_mode = "read-only"\n"""\n'
    with pytest.raises(PatchError):
        apply_update(text, op.chunks, strict=True)


@pytest.mark.parametrize(
    "text",
    [
        'def _keep():\n    prefix_rule(pattern = ["rm"], decision = "forbidden")\n',
        'def prefix_rule(**kw):\n    pass\nprefix_rule(pattern = ["rm"], decision = "forbidden")\n',
        'DANGER = ["rm"]\nprefix_rule(pattern = DANGER, decision = "forbidden")\n',
        '\uff50refix_rule(pattern = ["rm"], decision = "forbidden")\n',
        'prefix_rule(pattern = [b"rm"], decision = "forbidden")\n',
        'prefix_rule(pattern = ["r" "m"], decision = "forbidden")\n',
        'prefix_rule(pattern = ["rm"], decision = [])\n',
        'prefix_rule(pattern = ["rm"], decision = "forbidden", match = ["ls -la"])\n',
        'prefix_rule(pattern = ["rm"], decision = "forbidden", not_match = ["rm -rf /"])\n',
        'prefix_rule(pattern = ["rm"], color = "red")\n',
        "prefix_rule(pattern = " + "[" * 200 + "]" * 200 + ")\n",
        "import os\n",
    ],
)
def test_rules_that_codex_could_read_differently_raise(text):
    with pytest.raises(RulesParseError):
        parse_rules(text)


def test_rules_docstring_comments_and_valid_examples_are_read():
    text = (
        '"""team rules"""\n# comment\n'
        'prefix_rule(pattern = ["gh", "pr", "view"], decision = "prompt", justification = "ok",\n'
        '            match = ["gh pr view 1", ["gh", "pr", "view"]], not_match = ["gh pr --repo x view 1"])\n'
    )
    assert [r.command for r in parse_rules(text)] == ["gh pr view"]


def test_chunks_at_the_same_place_follow_codex_order_and_are_refused_in_strict_mode():
    (op,) = parse_patch(_patch("*** Update File: c\n@@\n+[features]\n@@\n+hooks = false\n"))
    text = 'sandbox_mode = "read-only"\n[tui]\nanimations = true\n'
    assert apply_update(text, op.chunks).endswith("[features]\nhooks = false\n")
    with pytest.raises(PatchError):
        apply_update(text, op.chunks, strict=True)


def test_rust_whitespace_set_is_used():
    (op,) = parse_patch(_patch("*** Update File: c\n@@\n-{\n"))
    with pytest.raises(PatchError):  # U+001C is not whitespace for Codex: "{\x1c" is not "{"
        apply_update("{\x1c\n", op.chunks)


def test_too_costly_rebuild_is_refused():
    big = "a\n" * 200_000
    (op,) = parse_patch(_patch("*** Update File: c\n@@\n" + "-a\n" * 1000 + "-b\n"))
    with pytest.raises(PatchError, match="costly"):
        apply_update(big, op.chunks)


@pytest.mark.parametrize(
    "text",
    [
        'prefix_rule(pattern = ["\\N{BULLET}"])\n',
        'prefix_rule(pattern = ["\\q"])\n',
        'prefix_rule(pattern = \\\n["a"])\n',
    ],
)
def test_rules_with_non_starlark_escapes_raise(text):
    with pytest.raises(RulesParseError):
        parse_rules(text)
