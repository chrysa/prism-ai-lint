"""Checks on a repo's agent instruction files and its skill/subagent listing. Reports only.

- INSTR_DEAD_REF: an instruction file names a command or a file that does not exist, so the agent
  reads a false instruction and pays round trips to find out.
- TOKEN_LISTING_BUDGET: the skill and subagent descriptions are sent every turn; flag a listing
  that is large and name the biggest entries that could be switched to manual invocation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from prism_ai_lint._runtime import read_text
from prism_ai_lint.report import Report

INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md")
FENCE_RE = re.compile(r"^(```|~~~)[^\n]*\n(.*?)^\1[ \t]*$", re.S | re.M)
INLINE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
MAKE_RE = re.compile(r"(?:^|[\s;&|(])make\s+([A-Za-z][\w.-]*)")
SCRIPT_RE = re.compile(r"(?:^|[\s;&|(])(?:npm|pnpm|yarn|bun)\s+run\s+([\w:.-]+)")
PATH_RE = re.compile(r"^(?:\./)?[\w.-]+(?:/[\w.-]+)+\.[A-Za-z0-9]{1,5}$")
GENERATED_DIRS = {
    "node_modules",
    "dist",
    "build",
    "out",
    "coverage",
    ".venv",
    "venv",
    ".cache",
    "graphify-out",
    "target",
    "__pycache__",
    ".next",
}
PLACEHOLDERS = ("path/to", "your-", "your_", "example", "foo/", "my-", "xxx")
MAX_LISTED = 5

SKILL_LISTING_TOKENS = 2000
AGENT_LISTING_TOKENS = 15000
DESCRIPTION_CAP = 1536
KEY_RE = re.compile(r"^([A-Za-z][\w-]*):\s*(.*)$")


def _frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar keys of a YAML frontmatter block; continuation lines join the previous key."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    meta: dict[str, str] = {}
    key = ""
    for line in text[3:end].splitlines():
        m = KEY_RE.match(line)
        if m:
            key = m.group(1)
            meta[key] = m.group(2).strip().strip(">|-").strip()
        elif key and line.startswith((" ", "\t")):
            meta[key] = (meta[key] + " " + line.strip()).strip()
    return meta


def _make_targets(makefile: Path) -> set[str] | None:
    """Targets defined in a Makefile, or None when it includes other files (we can not know them all)."""
    text = read_text(makefile)
    if text is None or re.search(r"^-?include\s", text, re.M):
        return None
    targets = set()
    for m in re.finditer(r"^([A-Za-z0-9_.-]+(?:\s+[A-Za-z0-9_.-]+)*)\s*:(?![=:])", text, re.M):
        targets.update(m.group(1).split())
    for m in re.finditer(r"^\.PHONY\s*:\s*(.+)$", text, re.M):
        targets.update(m.group(1).split())
    return targets


def _package_scripts(package: Path) -> set[str] | None:
    text = read_text(package)
    if text is None:
        return None
    try:
        scripts = json.loads(text).get("scripts")
    except (ValueError, AttributeError):
        return None
    return set(scripts) if isinstance(scripts, dict) else set()


class ClaudeFilesChecker:
    """Reports only: nothing here edits an instruction file or a skill."""

    def check_repo(self, repo: Path, rep: Report) -> None:
        self._dead_references(repo, rep)
        self._listing_budget(repo, rep)

    # -- dead references -------------------------------------------------------------------------
    def _instruction_paths(self, repo: Path) -> list[Path]:
        paths = [repo / name for name in INSTRUCTION_FILES]
        rules = repo / ".claude" / "rules"
        if rules.is_dir():
            paths += sorted(rules.rglob("*.md"))
        return [p for p in paths if p.is_file()]

    def _dead_references(self, repo: Path, rep: Report) -> None:
        makefile = repo / "Makefile"
        targets = _make_targets(makefile) if makefile.is_file() else None
        scripts = _package_scripts(repo / "package.json") if (repo / "package.json").is_file() else None
        if not scripts:  # no scripts here: the app may live in a workspace or subfolder, so do not judge
            scripts = None
        for path in self._instruction_paths(repo):
            text = read_text(path)
            if not text:
                continue
            fences = [m.group(2) for m in FENCE_RE.finditer(text)]
            prose = FENCE_RE.sub("", text)
            inline = [m.group(1) for m in INLINE_RE.finditer(prose)]
            dead: list[str] = []
            for span in fences + inline:
                for line in span.splitlines():
                    if targets is not None:
                        dead += [
                            f"make {t}"
                            for t in MAKE_RE.findall(line)
                            if t not in targets and "$" not in t and "%" not in t
                        ]
                    if scripts is not None:
                        dead += [f"npm run {s}" for s in SCRIPT_RE.findall(line) if s not in scripts]
            for span in inline:
                ref = span.strip()
                if self._missing_path(repo, path, ref):
                    dead.append(ref)
            dead = list(dict.fromkeys(dead))
            if dead:
                shown = ", ".join(dead[:MAX_LISTED]) + (
                    f" (+{len(dead) - MAX_LISTED} more)" if len(dead) > MAX_LISTED else ""
                )
                rep.add(
                    "info",
                    "INSTR_DEAD_REF",
                    path,
                    f"{len(dead)} command(s) or file(s) named here do not exist: {shown}",
                )

    @staticmethod
    def _missing_path(repo: Path, doc: Path, ref: str) -> bool:
        if not PATH_RE.match(ref) or any(p in ref.lower() for p in PLACEHOLDERS):
            return False
        if GENERATED_DIRS & set(Path(ref).parts):
            return False
        # Only judge a path whose first directory exists here: otherwise it points at another repo
        # or at a synced file, and we can not tell that from a dead reference.
        first = Path(ref).parts[0] if not ref.startswith("./") else Path(ref).parts[1]
        if not ((repo / first).is_dir() or (doc.parent / first).is_dir()):
            return False
        return not ((repo / ref).exists() or (doc.parent / ref).exists())

    # -- listing budget --------------------------------------------------------------------------
    def _listing_budget(self, repo: Path, rep: Report) -> None:
        claude = repo / ".claude"
        skills: list[tuple[int, Path]] = []
        for sk in sorted(claude.glob("skills/*/SKILL.md")):
            meta = _frontmatter(read_text(sk) or "")
            if meta.get("disable-model-invocation", "").lower() in ("true", "yes", "on", "1"):
                continue
            desc = meta.get("description", "") + meta.get("when_to_use", "")
            skills.append(((len(sk.parent.name) + min(len(desc), DESCRIPTION_CAP) + 20) // 4, sk))
        total = sum(t for t, _ in skills)
        if total > SKILL_LISTING_TOKENS:
            top = sorted(skills, reverse=True)[:3]
            names = ", ".join(f"{p.parent.name} (~{t})" for t, p in top)
            rep.add(
                "info",
                "TOKEN_LISTING_BUDGET",
                claude / "skills",
                f"{len(skills)} skills listed every turn, ~{total} tokens (target <= {SKILL_LISTING_TOKENS}); "
                f"biggest: {names}. A skill only run by hand can set disable-model-invocation: true",
            )
        agents = 0
        for ag in sorted(claude.glob("agents/**/*.md")):
            meta = _frontmatter(read_text(ag) or "")
            agents += (len(meta.get("name", "")) + len(meta.get("description", "")) + 20) // 4
        if agents > AGENT_LISTING_TOKENS:
            rep.add(
                "warn",
                "TOKEN_LISTING_BUDGET",
                claude / "agents",
                f"subagent descriptions total ~{agents} tokens (Claude Code warns above {AGENT_LISTING_TOKENS})",
            )
