"""Codex `.rules` files: `prefix_rule(...)` calls in Starlark, read statically and never executed.

Only the plain documented shape is read: a module made of top-level `prefix_rule(...)` calls with
literal keyword arguments (plus comments and a docstring). Anything else -- variables, functions,
a redefined `prefix_rule`, non-ASCII names, Python-only literals, `match` examples that contradict
the pattern -- could make Codex register different rules than a static reading sees, or refuse
the file, so it raises RulesParseError: the lint reports it and the guard blocks it."""

from __future__ import annotations

import ast
import io
import itertools
import json
import re
import shlex
import tokenize

from prism_ai_lint.prefix_rule import PrefixRule
from prism_ai_lint.rules_parse_error import RulesParseError


class CodexRules:
    # Least to most restrictive; Codex applies the most restrictive matching decision.
    DECISIONS = ("allow", "prompt", "forbidden")
    STRICTNESS = {d: i for i, d in enumerate(DECISIONS)}
    MAX_EXPANSION = 32  # a union pattern expanding to more prefixes than this is not read
    KEYWORDS = frozenset({"pattern", "decision", "justification", "match", "not_match"})

    @staticmethod
    def _expand(pattern: object, line: int) -> list[tuple[str, ...]]:
        if not isinstance(pattern, list) or not pattern:
            raise RulesParseError(f"line {line}: pattern must be a non-empty list")
        choices: list[list[str]] = []
        for item in pattern:
            if isinstance(item, str) and item:
                choices.append([item])
            elif isinstance(item, list) and item and all(isinstance(x, str) and x for x in item):
                choices.append(list(item))
            else:
                raise RulesParseError(f"line {line}: pattern items must be strings or lists of strings")
        total = 1
        for c in choices:
            total *= len(c)
        if total > CodexRules.MAX_EXPANSION:
            raise RulesParseError(
                f"line {line}: pattern expands to {total} prefixes (more than {CodexRules.MAX_EXPANSION})"
            )
        return [tuple(p) for p in itertools.product(*choices)]

    @staticmethod
    def _check_tokens(text: str) -> None:
        """Reject what Python reads but Starlark does not: non-ASCII names, string prefixes other
        than r, implicitly concatenated strings."""
        if "\\\n" in text:
            raise RulesParseError("backslash line continuations are not read")
        previous = None
        try:
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.NAME and not tok.string.isascii():
                    raise RulesParseError(f"line {tok.start[0]}: non-ASCII name {tok.string!r}")
                if tok.type == tokenize.STRING:
                    prefix = tok.string[: len(tok.string) - len(tok.string.lstrip("rRbBuUfF"))]
                    if set(prefix) - {"r", "R"}:
                        raise RulesParseError(f"line {tok.start[0]}: string prefix {prefix!r} is not Starlark")
                    if not prefix and re.search(r"\\(?![abfnrtv\\'\"0-7xuU])", tok.string):
                        raise RulesParseError(f"line {tok.start[0]}: escape sequence Starlark does not accept")
                    if previous == tokenize.STRING:
                        raise RulesParseError(f"line {tok.start[0]}: implicit string concatenation")
                if tok.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                    previous = tok.type
        except (tokenize.TokenError, SyntaxError) as e:
            raise RulesParseError(f"cannot tokenize: {e}") from e

    @staticmethod
    def _example_tokens(example: object, line: int) -> tuple[str, ...]:
        if isinstance(example, str):
            try:
                return tuple(shlex.split(example))
            except ValueError as e:
                raise RulesParseError(f"line {line}: unreadable match example {example!r}") from e
        if isinstance(example, list) and all(isinstance(x, str) for x in example):
            return tuple(example)
        raise RulesParseError(f"line {line}: match examples must be strings or lists of strings")

    @staticmethod
    def _rule_from_call(node: ast.Call) -> list[PrefixRule]:
        line = node.lineno
        if not (isinstance(node.func, ast.Name) and node.func.id == "prefix_rule"):
            raise RulesParseError(f"line {line}: only prefix_rule() calls are read")
        if node.args or any(k.arg is None for k in node.keywords):
            raise RulesParseError(f"line {line}: prefix_rule takes keyword arguments only")
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        if set(kw) - CodexRules.KEYWORDS:
            raise RulesParseError(
                f"line {line}: unknown argument(s) {', '.join(sorted(set(kw) - CodexRules.KEYWORDS))}"
            )
        if "pattern" not in kw:
            raise RulesParseError(f"line {line}: prefix_rule without pattern")
        try:
            values = {k: ast.literal_eval(v) for k, v in kw.items()}
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e:
            raise RulesParseError(f"line {line}: arguments must be literals") from e
        decision = values.get("decision", "allow")
        if not isinstance(decision, str) or decision not in CodexRules.STRICTNESS:
            raise RulesParseError(f"line {line}: unknown decision {decision!r}")
        if "justification" in values and not (isinstance(values["justification"], str) and values["justification"]):
            raise RulesParseError(f"line {line}: justification must be a non-empty string")
        rules = [PrefixRule(prefix, decision, line) for prefix in CodexRules._expand(values["pattern"], line)]
        for key, expected in (("match", True), ("not_match", False)):
            examples = values.get(key, [])
            if not isinstance(examples, list):
                raise RulesParseError(f"line {line}: {key} must be a list")
            for example in examples:
                tokens = CodexRules._example_tokens(example, line)
                if any(r.matches(tokens) for r in rules) is not expected:
                    # Codex validates these examples when it loads the file and rejects it on a mismatch.
                    raise RulesParseError(f"line {line}: {key} example {example!r} contradicts the pattern")
        return rules

    @staticmethod
    def parse(text: str) -> list[PrefixRule]:
        """Every `prefix_rule()` of a rules file, one entry per expanded prefix."""
        try:
            CodexRules._check_tokens(text)
            tree = ast.parse(text)
        except RulesParseError:
            raise
        except (SyntaxError, ValueError, MemoryError, RecursionError) as e:
            raise RulesParseError(f"cannot parse: {e}") from e
        rules: list[PrefixRule] = []
        for n, stmt in enumerate(tree.body):
            if n == 0 and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    continue  # module docstring
            if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
                raise RulesParseError(f"line {stmt.lineno}: only top-level prefix_rule() calls are read")
            rules.extend(CodexRules._rule_from_call(stmt.value))
        return rules

    @staticmethod
    def decision_for(rules: list[PrefixRule], tokens: tuple[str, ...]) -> str | None:
        """The decision Codex applies to `tokens` (most restrictive match), or None when no rule matches."""
        found = [r.decision for r in rules if r.matches(tokens)]
        return max(found, key=CodexRules.STRICTNESS.__getitem__) if found else None

    @staticmethod
    def render(prefix: tuple[str, ...], decision: str, justification: str) -> str:
        """One `prefix_rule()` block; JSON string literals are valid Starlark string literals."""
        if decision not in CodexRules.STRICTNESS:
            raise ValueError(f"unknown decision {decision!r}")
        pattern = ", ".join(json.dumps(t, ensure_ascii=False) for t in prefix)
        return (
            "prefix_rule(\n"
            f"    pattern = [{pattern}],\n"
            f"    decision = {json.dumps(decision)},\n"
            f"    justification = {json.dumps(justification, ensure_ascii=False)},\n"
            ")\n"
        )
