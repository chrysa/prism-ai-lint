"""Product surface names (Claude Code CLI/IDE, Codex CLI/IDE/cloud, ChatGPT) map to one adapter each."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from prism_ai_lint.agent_converter import ADAPTERS, ALIASES, ECOSYSTEMS, canonical

ROOT = Path(__file__).resolve().parents[1]


def test_every_alias_points_to_a_real_adapter():
    assert set(ALIASES.values()) <= set(ADAPTERS)
    assert set(ECOSYSTEMS) == set(ADAPTERS) | set(ALIASES)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("claude-code", "claude"),
        ("claude-code-cli", "claude"),
        ("codex-cli", "codex"),
        ("codex-ide", "codex"),
        ("codex-cloud", "codex"),
        ("chatgpt", "codex"),
        ("claude", "claude"),
        ("agents", "agents"),
        (None, None),
    ],
)
def test_canonical_name(name, expected):
    assert canonical(name) == expected


@pytest.mark.parametrize(("surface", "target"), [("codex-cli", "AGENTS.md"), ("chatgpt", "AGENTS.md")])
def test_cli_preview_accepts_a_surface_name(tmp_path, surface, target):
    (tmp_path / "CLAUDE.md").write_text("Never loosen security rules.\n")
    before = sorted(p.name for p in tmp_path.iterdir())
    args = [sys.executable, str(ROOT / "prism-ai-lint.py"), str(tmp_path), "--convert-from", "claude-code-cli"]
    result = subprocess.run(
        [*args, "--convert-to", surface, "--format", "json"], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["conversion_plans"][0]["output"]["path"] == target
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_unknown_surface_is_refused(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "prism-ai-lint.py"), str(tmp_path), "--convert-to", "claude-desktop"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
