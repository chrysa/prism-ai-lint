"""Error raised when a Codex patch cannot be read or rebuilt with certainty."""

from __future__ import annotations


class PatchError(ValueError):
    """The patch cannot be read, or cannot be applied unambiguously to the current text."""
