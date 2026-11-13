"""INSTR_IMPORT_OVERLAP: lines an always-loaded instruction file repeats from a file it imports (D-048)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prism_ai_lint._markup import import_targets, strip_code, strip_html_comments
from prism_ai_lint._runtime import read_text


class ImportOverlapChecker:
    """Report an always-loaded instruction file that repeats lines of a file it `@imports`.

    Both files load at session start (Claude Code expands imports into the same context), so every
    repeated line is paid twice in every session. Typical cause: a generated standards block written
    into both `CLAUDE.md` and `AGENTS.md` while `CLAUDE.md` imports `AGENTS.md`. Report only: the fix
    is to keep the text in the imported file (or in the generator) and drop the copy.
    """

    ROOTS = ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md")
    MIN_SHARED = 5  # significant lines (>= min_duplicate_line_len chars) before reporting
    MIN_COUNTED = 8  # shorter lines (headings, "- Merge") are not counted at all
    MAX_DEPTH = 4

    @staticmethod
    def _lines(text: str) -> set[str]:
        body = strip_html_comments(strip_code(text))
        return {line.strip() for line in body.splitlines() if len(line.strip()) >= ImportOverlapChecker.MIN_COUNTED}

    def _imported(self, path: Path, root: Path, depth: int, seen: set[Path]) -> list[tuple[Path, str]]:
        """(file, text) of every in-repo file `path` imports, transitively (as Claude Code expands them)."""
        if depth > self.MAX_DEPTH:
            return []
        out: list[tuple[Path, str]] = []
        for _, target in import_targets(path, read_text(path) or ""):
            try:
                resolved = target.resolve()
                resolved.relative_to(root.resolve())
            except (OSError, ValueError):
                continue  # outside the project: not this check's business (IMPORT_EXTERNAL covers it)
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            text = read_text(resolved) or ""
            out.append((resolved, text))
            out += self._imported(resolved, root, depth + 1, seen)
        return out

    def check_repo(self, repo: Path, policy: dict, rep: Any) -> None:
        min_len = int(policy["instructions"].get("min_duplicate_line_len", 30))
        for rel in self.ROOTS:
            path = repo / rel
            if not path.is_file() or path.is_symlink():
                continue
            own = self._lines(read_text(path) or "")
            for target, text in self._imported(path, repo, 1, {path.resolve()}):
                shared = own & self._lines(text)
                significant = [line for line in shared if len(line) >= min_len]
                if len(significant) < self.MIN_SHARED:
                    continue
                tokens = sum(len(line) + 1 for line in shared) // 4
                rep.add(
                    "warn",
                    "INSTR_IMPORT_OVERLAP",
                    path,
                    f"{len(shared)} lines repeated from imported {target.relative_to(repo.resolve())}: "
                    f"~{tokens} tokens loaded twice every session",
                )
