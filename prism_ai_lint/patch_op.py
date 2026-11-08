"""One file section of a Codex `apply_patch` envelope (add, delete or update)."""

from __future__ import annotations

from dataclasses import dataclass, field

from prism_ai_lint.patch_chunk import PatchChunk


@dataclass
class PatchOp:
    kind: str  # "add", "delete" or "update"
    path: str
    move_to: str | None = None
    lines: list[str] = field(default_factory=list)  # content of an added file
    chunks: list[PatchChunk] = field(default_factory=list)

    def added_text(self) -> str:
        """Every line this operation introduces (added file content or '+' lines)."""
        if self.kind == "add":
            return "\n".join(self.lines)
        return "\n".join(line for c in self.chunks for line in c.new if line not in c.old)
