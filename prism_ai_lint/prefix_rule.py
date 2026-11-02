"""One Codex `prefix_rule()`, expanded to a single literal command prefix."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrefixRule:
    prefix: tuple[str, ...]
    decision: str
    line: int

    @property
    def command(self) -> str:
        return " ".join(self.prefix)

    def matches(self, tokens: tuple[str, ...]) -> bool:
        """True when this rule applies to a command whose argument list starts with `tokens`."""
        return tokens[: len(self.prefix)] == self.prefix
