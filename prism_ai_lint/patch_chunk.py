"""One `@@` chunk of a Codex `*** Update File` section."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PatchChunk:
    anchor: str | None = None  # text after '@@ ', kept verbatim; moves the cursor
    old: list[str] = field(default_factory=list)  # context and removed lines, in order
    new: list[str] = field(default_factory=list)  # context and added lines, in order
    eof: bool = False  # '*** End of File': the chunk ends the file
