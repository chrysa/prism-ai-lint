"""Measured token use from local Claude Code session transcripts (D-050). Offline, read only, counts only."""

from __future__ import annotations

import json
import re
from pathlib import Path

from prism_ai_lint.usage_totals import UsageTotals

MAX_LINE_BYTES = 8 * 1024 * 1024  # a transcript line above this is skipped, never parsed


class UsageAnalyzer:
    """Read Claude Code transcripts (`<config dir>/projects/<project slug>/*.jsonl`) and add up what was sent.

    The transcript format is internal to Claude Code and may change: every field is read defensively and anything
    unknown is skipped. Only counts, sizes, tool names, file paths read and hook names are reported, plus the first
    characters of hook-injected text (written by the user's own hooks) so the hook can be identified. Prompt text,
    tool output and model output are never returned.
    """

    @staticmethod
    def project_dir(repo: Path, config_dir: Path) -> Path:
        return config_dir / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))

    @classmethod
    def sessions_for(cls, repo: Path, config_dir: Path, limit: int) -> list[Path]:
        d = cls.project_dir(repo, config_dir)
        files = [p for p in d.glob("*.jsonl") if p.is_file()] if d.is_dir() else []
        return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[: max(1, limit)]

    @staticmethod
    def _records(path: Path):
        try:
            with path.open("rb") as fh:
                for raw in fh:
                    if len(raw) > MAX_LINE_BYTES:
                        continue
                    try:
                        rec = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(rec, dict):
                        yield rec
        except OSError:
            return

    def analyze(self, paths: list[Path]) -> dict:
        state = UsageTotals()
        for path in paths:
            failed: set[str] = set()
            for rec in self._records(path):
                state.add(rec, failed)
            for name in failed:
                state.mcp_failures[name] += 1
        return state.result(len(paths))
