"""Optional `DESIGN.md` product design contracts: discovery, size, imports, local links and wiring.

A design contract is only read by an agent when an instruction file points to it: Claude Code and the
other agents load `CLAUDE.md`, `AGENTS.md` and rules by name, never a `DESIGN.md`. So this checker
keeps four facts apart and reports each one for what it is:

- **present**: a `DESIGN.md` was found (root or nested; dependency, build, cache, hidden and
  git-ignored trees are skipped; symlinks are never followed out of the project);
- **analysed**: its size, `@` imports and local Markdown links were checked;
- **referenced**: an instruction file, or a contract that is itself referenced, names it;
- **loaded**: an always-loaded instruction file `@`-imports it, so it enters every session.

It never requires a contract, never edits one, and judges neither the design nor its accessibility:
static checks can not certify a user interface. Reports only.

- DESIGN_LONG: an on-demand contract past its own size budget (larger than an always-loaded file's).
- DESIGN_UNREFERENCED: no instruction file points to the contract, so agents will not read it.
- DESIGN_ALWAYS_LOADED: an always-loaded instruction file imports the contract into every session.
- DESIGN_EXTERNAL: a `DESIGN.md` symlink resolves outside the project; it is not analysed.
- DESIGN_DEAD_LINK: a local Markdown link in the contract resolves to nothing inside the project.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from prism_ai_lint._markup import import_targets, split_frontmatter, strip_code, strip_html_comments
from prism_ai_lint._runtime import is_ignored, log, read_text
from prism_ai_lint.report import Report

if TYPE_CHECKING:
    from prism_ai_lint.instruction_checker import InstructionChecker

DESIGN_NAME = "DESIGN.md"
# Directories that hold dependencies, build output, caches or engine-generated trees. Hidden
# directories (`.git`, `.venv`, `.next`, ...) are skipped as a whole.
SKIPPED_DIRS = frozenset(
    {
        "node_modules",
        "bower_components",
        "vendor",
        "dist",
        "build",
        "out",
        "site",
        "storybook-static",
        "coverage",
        "venv",
        "target",
        "__pycache__",
        "graphify-out",
        "Library",  # Unity
        "Temp",  # Unity
        "obj",  # .NET / Unity
        "Pods",  # CocoaPods
        "DerivedData",  # Xcode
    }
)
MAX_DEPTH = 8  # a design contract sits next to a frontend, not twelve levels down
# Always-loaded project instruction files (relative to the repository root).
ALWAYS_LOADED = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md", ".claude/AGENTS.md", "CLAUDE.local.md")
# Further files that agents read as instructions: other tools' renders and nested instruction files.
RENDERS = (".github/copilot-instructions.md", "GEMINI.md", ".cursorrules", ".windsurfrules")
NESTED_INSTRUCTIONS = ("CLAUDE.md", "AGENTS.md")
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*<?(\S+?)>?(?:\s+.*)?$", re.M)
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
MAX_LISTED = 5


@dataclass
class _Source:
    """A file agents read, with what it says about design contracts."""

    path: Path
    always_loaded: bool
    text: str
    imports: set[Path] = field(default_factory=set)
    mentions: set[Path] = field(default_factory=set)


class DesignContractChecker:
    """Discover and check optional DESIGN.md contracts; records findings, never writes."""

    # -- discovery -------------------------------------------------------------------------------
    def discover(self, repo: Path) -> list[Path]:
        """Every analysable DESIGN.md under `repo`, sorted. Deterministic and bounded: hidden,
        dependency, build and cache directories are pruned, the walk stops at MAX_DEPTH, linked
        directories are not followed, git-ignored files are skipped, and a symlinked DESIGN.md is kept
        only when it resolves inside the project (once, under its own path)."""
        return list(self._walk(repo)[0])

    def external_links(self, repo: Path) -> list[Path]:
        """DESIGN.md symlinks that resolve outside the project: listed, never read."""
        return list(self._walk(repo)[1])

    def _walk(self, repo: Path) -> tuple[list[Path], list[Path]]:
        key = repo.resolve()
        found: list[Path] = []
        external: list[Path] = []
        seen: set[Path] = set()
        base = len(Path(os.path.normpath(repo)).parts)
        git = (repo / ".git").exists()
        for directory, dirs, files in os.walk(repo, followlinks=False):
            here = Path(directory)
            depth = len(Path(os.path.normpath(here)).parts) - base
            keep = sorted(d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRS)
            dirs[:] = keep if depth < MAX_DEPTH else []
            if DESIGN_NAME not in files:
                continue
            path = here / DESIGN_NAME
            target = path.resolve()
            if not self._inside(target, key):
                external.append(path)
                continue
            if not target.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if git and is_ignored(repo, rel):
                log(2, f"{rel}: git-ignored, not a design contract source", 2)
                continue
            if target not in seen:
                seen.add(target)
                found.append(path)
        return sorted(found), sorted(external)

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    # -- checks ----------------------------------------------------------------------------------
    def check_repo(self, repo: Path, policy: dict, rep: Report, imports_checker: InstructionChecker) -> None:
        designs, external = self._walk(repo)
        for link in external:
            rep.add("info", "DESIGN_EXTERNAL", link, "symlink to a file outside the project: not analysed")
        if not designs:
            return  # a contract is optional: absence is not a finding
        rep.stats["design contracts"] = rep.stats.get("design contracts", 0) + len(designs)
        pol = policy["instructions"]
        for path in designs:
            text = read_text(path)
            if text is None:
                continue
            effective = strip_html_comments(text)
            lines, tokens = effective.count("\n") + 1, len(effective.encode()) // 4
            if lines > pol["design_warn_lines"] or tokens > pol["design_warn_tokens"]:
                rep.add(
                    "info",
                    "DESIGN_LONG",
                    path,
                    f"{lines} lines (~{tokens} tokens): move journeys or evidence into linked files",
                )
            imports_checker.check_imports(path, text, rep, policy, repo)
            self._dead_links(repo, path, text, rep)
        self._wiring(repo, designs, rep)

    def _dead_links(self, repo: Path, doc: Path, text: str, rep: Report) -> None:
        prose = strip_html_comments(strip_code(text))
        dead: list[str] = []
        for target in [*LINK_RE.findall(prose), *REF_DEF_RE.findall(prose)]:
            resolved = self._local_target(repo, doc, target)
            if resolved is not None and not resolved.exists():
                dead.append(target)
        dead = list(dict.fromkeys(dead))
        if dead:
            shown = ", ".join(dead[:MAX_LISTED]) + (
                f" (+{len(dead) - MAX_LISTED} more)" if len(dead) > MAX_LISTED else ""
            )
            rep.add("info", "DESIGN_DEAD_LINK", doc, f"{len(dead)} local link(s) resolve to nothing: {shown}")

    @staticmethod
    def _local_target(repo: Path, doc: Path, target: str) -> Path | None:
        """The in-project file a Markdown link points to, or None when it is not judged
        (URL, anchor, e-mail, template placeholder, or a path that leaves the project)."""
        ref = unquote(target.split("#", 1)[0].split("?", 1)[0]).strip()
        if not ref or SCHEME_RE.match(ref) or ref.startswith(("//", "<", "{", "$")) or "<" in ref:
            return None
        resolved = (repo / ref.lstrip("/")) if ref.startswith("/") else (doc.parent / ref)
        resolved = Path(os.path.normpath(resolved))
        return resolved if DesignContractChecker._inside(resolved, Path(os.path.normpath(repo))) else None

    # -- wiring: referenced / loaded -------------------------------------------------------------
    def _sources(self, repo: Path, designs: list[Path]) -> list[_Source]:
        paths: list[tuple[Path, bool]] = [(repo / rel, True) for rel in ALWAYS_LOADED]
        paths += [(repo / rel, False) for rel in RENDERS]
        rules = repo / ".claude" / "rules"
        if rules.is_dir():
            for rule in sorted(rules.rglob("*.md")):
                meta, _offset = split_frontmatter(read_text(rule) or "")
                paths.append((rule, not (meta and "paths" in meta)))  # an unscoped rule loads every session
        for design in designs:
            if design.parent != repo:
                paths += [(design.parent / name, False) for name in NESTED_INSTRUCTIONS]  # load on demand
        sources: list[_Source] = []
        seen: set[Path] = set()
        for path, always in paths:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            sources.append(_Source(path, always, read_text(path) or ""))
        return sources

    @staticmethod
    def _scope_dir(repo: Path, path: Path) -> Path:
        """Where a bare `DESIGN.md` in this file points: the project root for root-level, `.claude/`
        and `.github/` instruction files, the file's own directory for a nested one."""
        rel = path.relative_to(repo).parts
        return repo if len(rel) == 1 or rel[0] in (".claude", ".github") else path.parent

    def _resolve_mentions(self, repo: Path, src: _Source, designs: list[Path]) -> None:
        by_resolved = {d.resolve(): d for d in designs}
        for _ref, target in import_targets(src.path, src.text):
            hit = by_resolved.get(target.resolve()) if target.exists() else None
            if hit is not None:
                src.imports.add(hit)
        body = strip_html_comments(src.text)
        scope = self._scope_dir(repo, src.path)
        for design in designs:
            if design == src.path:
                continue
            rel_src = os.path.relpath(design, src.path.parent).replace(os.sep, "/")
            spellings = {design.relative_to(repo).as_posix(), rel_src, f"./{rel_src}"}
            if design.parent == scope:
                spellings.add(DESIGN_NAME)
            if any(re.search(rf"(?<![\w./-]){re.escape(s)}(?![\w-])", body) for s in spellings):
                src.mentions.add(design)

    def _wiring(self, repo: Path, designs: list[Path], rep: Report) -> None:
        sources = self._sources(repo, designs)
        for src in sources:
            self._resolve_mentions(repo, src, designs)
        referenced: set[Path] = set()
        for src in sources:
            referenced |= src.mentions | src.imports
            for design in sorted(src.imports):
                if src.always_loaded:
                    rep.add(
                        "info",
                        "DESIGN_ALWAYS_LOADED",
                        design,
                        f"imported by {src.path.relative_to(repo).as_posix()}: loads in every session; "
                        "an on-demand reference costs no context until UI work",
                    )
        # A contract that a referenced contract links to is reachable too (root -> frontend spec).
        frontier = list(referenced)
        while frontier:
            current = frontier.pop()
            src = _Source(current, False, read_text(current) or "")
            self._resolve_mentions(repo, src, designs)
            for design in (src.mentions | src.imports) - referenced:
                referenced.add(design)
                frontier.append(design)
        for design in designs:
            status = "referenced" if design in referenced else "not referenced"
            log(1, f"{design.relative_to(repo).as_posix()}: present, analysed, {status}", 1)
            if design not in referenced:
                rep.add(
                    "info",
                    "DESIGN_UNREFERENCED",
                    design,
                    "no instruction file points here, and agents do not load DESIGN.md by its name: "
                    "reference it from AGENTS.md / CLAUDE.md, a rule, or the root contract",
                )
