"""Error raised when a Codex `.rules` file cannot be read statically."""

from __future__ import annotations


class RulesParseError(ValueError):
    """The rules text cannot be read statically (shape, syntax, non-literal values, bad decision)."""
