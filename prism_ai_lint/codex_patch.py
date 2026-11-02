"""Codex `apply_patch` envelopes: parse them and rebuild the edited file text, so the guard can
judge a Codex edit the same way it judges a Claude Code Edit/Write.

Parsing and application follow the Codex implementation (codex-rs `apply-patch`): blank lines
before a chunk are skipped, `@@ <text>` keeps its text verbatim as a cursor anchor, an added-lines-only
chunk goes to the end of the file, chunks are located from a moving cursor on the original lines
(exact, then trailing-space, then trimmed, then punctuation-normalised match), sorted stably and
applied from the end. With `strict`, a chunk must match exactly, its text must occur once in the
whole file under the loosest comparison, and no two chunks may touch the same place, so the
rebuilt text cannot depend on a detail where two readings could differ."""

from __future__ import annotations

import re
from collections.abc import Callable

from prism_ai_lint.patch_chunk import PatchChunk
from prism_ai_lint.patch_error import PatchError
from prism_ai_lint.patch_op import PatchOp


class CodexPatch:
    BEGIN, END, EOF_MARKER = "*** Begin Patch", "*** End Patch", "*** End of File"
    HEADER = re.compile(r"^\*\*\* (Add File|Delete File|Update File|Move to): (.+)$")
    WRAPPER = re.compile(r"\s*(?:(apply_?patch)(?:\s+<<-?\s*(['\"]?)(\w+)\2)?)?\s*")
    # Rust's char::is_whitespace set (Unicode White_Space). Python's str.strip also removes
    # U+001C-U+001F, so using it could make the guard match a line Codex does not.
    RUST_WS = "\t\n\x0b\x0c\r \x85\xa0                　"
    # Punctuation Codex folds to ASCII in its loosest match pass.
    PUNCT = str.maketrans(
        {
            **dict.fromkeys("‐‑‒–—―−", "-"),
            **dict.fromkeys("‘’‚‛", "'"),
            **dict.fromkeys("“”„‟", '"'),
            **dict.fromkeys("            　", " "),
        }
    )
    MAX_WORK = 10_000_000  # line comparisons a rebuild may cost before it is refused (keeps the guard fast)

    def __init__(self) -> None:
        ws = self.RUST_WS
        self.passes: tuple[Callable[[str], str], ...] = (
            lambda s: s,
            lambda s: s.rstrip(ws),
            lambda s: s.strip(ws),
            lambda s: s.strip(ws).translate(self.PUNCT),
        )
        self._left = self.MAX_WORK

    # ---- reading -----------------------------------------------------------------------------

    @staticmethod
    def _text(command: object) -> str:
        return "\n".join(map(str, command)) if isinstance(command, list) else str(command or "")

    def envelope(self, command: object) -> str:
        """The patch text inside a tool_input.command value (string, or argv list ending with it)."""
        text = self._text(command)
        start, stop = text.find(self.BEGIN), text.rfind(self.END)
        if start < 0 or stop < start:
            raise PatchError("no '*** Begin Patch' ... '*** End Patch' envelope")
        return text[start : stop + len(self.END)]

    def check_wrapper(self, command: object) -> None:
        """Refuse text around the envelope other than `apply_patch` and a heredoc marker: anything
        else (a `cd`, another program) could apply the patch somewhere the guard does not look."""
        text = self._text(command)
        start, stop = text.find(self.BEGIN), text.rfind(self.END)
        if start < 0 or stop < start:
            raise PatchError("no '*** Begin Patch' ... '*** End Patch' envelope")
        head = self.WRAPPER.fullmatch(text[:start])
        if head is None:
            raise PatchError("unexpected text before '*** Begin Patch'")
        tail = text[stop + len(self.END) :].strip()
        if tail and tail != (head.group(3) or ""):
            raise PatchError("unexpected text after '*** End Patch'")

    def _parse_chunk(self, lines: list[str], i: int, first: bool, path: str) -> tuple[PatchChunk, int]:
        line = lines[i]
        if line == "@@":
            chunk, i = PatchChunk(), i + 1
        elif line.startswith("@@ "):
            chunk, i = PatchChunk(anchor=line[3:]), i + 1
        elif first:
            chunk = PatchChunk()
        else:
            raise PatchError(f"{path}: expected '@@' before a chunk, got {line[:40]!r}")
        parsed = 0
        while i < len(lines):
            raw = lines[i]
            if raw == self.EOF_MARKER:
                chunk.eof, i = True, i + 1
                break
            tag = raw[:1]
            if tag in ("", " "):
                chunk.old.append(raw[1:])
                chunk.new.append(raw[1:])
            elif tag == "-":
                chunk.old.append(raw[1:])
            elif tag == "+":
                chunk.new.append(raw[1:])
            elif parsed == 0:
                raise PatchError(f"{path}: unexpected patch line {raw[:40]!r}")
            else:
                break  # start of the next chunk or file section
            parsed += 1
            i += 1
        if not chunk.old and not chunk.new:
            raise PatchError(f"{path}: empty chunk")
        return chunk, i

    def _parse_update(self, op: PatchOp, lines: list[str], i: int) -> int:
        if i < len(lines) and (mv := self.HEADER.match(lines[i])) and mv.group(1) == "Move to":
            op.move_to = mv.group(2).strip()
            i += 1
        while i < len(lines):
            if not lines[i].strip():
                i += 1  # blank lines before a chunk are skipped
                continue
            if lines[i].startswith("***"):
                break
            chunk, i = self._parse_chunk(lines, i, not op.chunks, op.path)
            op.chunks.append(chunk)
        if not op.chunks and not op.move_to:
            raise PatchError(f"{op.path}: update without changes")
        return i

    def parse(self, command: object) -> list[PatchOp]:
        lines = self.envelope(command).replace("\r\n", "\n").split("\n")[1:-1]
        ops: list[PatchOp] = []
        i = 0
        while i < len(lines):
            m = self.HEADER.match(lines[i])
            if not m:
                if lines[i].strip():
                    raise PatchError(f"text outside a file section: {lines[i][:40]!r}")
                i += 1
                continue
            kind, path = m.group(1), m.group(2).strip()
            if kind == "Move to":
                raise PatchError("'*** Move to' must follow '*** Update File'")
            op = PatchOp({"Add File": "add", "Delete File": "delete", "Update File": "update"}[kind], path)
            ops.append(op)
            i += 1
            if op.kind == "add":
                while i < len(lines) and lines[i].startswith("+"):
                    op.lines.append(lines[i][1:])
                    i += 1
            elif op.kind == "update":
                i = self._parse_update(op, lines, i)
        if not ops:
            raise PatchError("the patch changes no file")
        return ops

    # ---- rebuilding --------------------------------------------------------------------------

    def _spend(self, cost: int) -> None:
        self._left -= cost
        if self._left < 0:
            raise PatchError("the patch is too costly to verify")

    def _matches(self, lines: list[str], pattern: list[str], i: int, fold: Callable[[str], str]) -> bool:
        self._spend(len(pattern))
        return all(fold(lines[i + k]) == fold(p) for k, p in enumerate(pattern))

    def _seek(self, lines: list[str], pattern: list[str], start: int, eof: bool) -> tuple[int, int] | None:
        """(index, pass number) of the first match from `start`, trying each comparison in turn."""
        if not pattern:
            return start, 0
        if len(pattern) > len(lines):
            return None
        last = len(lines) - len(pattern)
        starts = [last, start] if eof else [start]
        for n, fold in enumerate(self.passes):
            for begin in starts:
                for i in range(begin, last + 1):
                    if self._matches(lines, pattern, i, fold):
                        return i, n
        return None

    def _count_loose(self, lines: list[str], pattern: list[str], limit: int = 2) -> int:
        found = 0
        for i in range(len(lines) - len(pattern) + 1):
            if self._matches(lines, pattern, i, self.passes[-1]):
                found += 1
                if found >= limit:
                    break
        return found

    def apply_update(self, old: str, chunks: list[PatchChunk], strict: bool = False) -> str:
        """The file text Codex writes after `chunks`. The work budget is shared by every call on this
        instance, so one guard decision stays bounded however many sections a patch has."""
        lines = old.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        cursor = 0
        replacements: list[tuple[int, int, list[str]]] = []
        for c in chunks:
            if c.anchor is not None:
                hit = self._seek(lines, [c.anchor], cursor, False)
                if hit is None:
                    raise PatchError(f"anchor {c.anchor[:40]!r} not found")
                cursor = hit[0] + 1
            if not c.old:
                at = len(lines) - 1 if lines and lines[-1] == "" else len(lines)
                replacements.append((at, 0, list(c.new)))
                continue
            pattern, new = list(c.old), list(c.new)
            hit = self._seek(lines, pattern, cursor, c.eof)
            if hit is None and pattern[-1] == "":
                pattern = pattern[:-1]
                new = new[:-1] if new and new[-1] == "" else new
                hit = self._seek(lines, pattern, cursor, c.eof)
            if hit is None:
                raise PatchError("a chunk does not match the current file")
            at, how = hit
            if strict and (how != 0 or self._count_loose(lines, pattern) != 1):
                raise PatchError("a chunk matches the current file in several places or only approximately")
            replacements.append((at, len(pattern), new))
            cursor = at + len(pattern)
        ordered = sorted(replacements, key=lambda r: r[0])  # stable, as Codex sorts them
        if strict:
            for (a, size, _), (b, _, _) in zip(ordered, ordered[1:], strict=False):
                if b < a + max(size, 1):
                    raise PatchError("two chunks change the same place; the result depends on their order")
        for at, size, new in reversed(ordered):  # Codex applies the sorted list from the end
            lines[at : at + size] = new
        if not lines or lines[-1] != "":
            lines.append("")
        return "\n".join(lines)
