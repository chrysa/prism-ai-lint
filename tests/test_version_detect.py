"""The version lookup never crashes the CLI: a missing, failing or slow git falls back to the dev placeholder."""

from __future__ import annotations

import subprocess
from importlib import metadata

import pytest

from prism_ai_lint import _engine


def _no_package(name: str) -> str:
    raise metadata.PackageNotFoundError(name)


@pytest.mark.parametrize(
    "error",
    [subprocess.TimeoutExpired(["git", "describe"], 2), subprocess.SubprocessError("boom"), OSError("no git")],
)
def test_version_falls_back_when_git_fails(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def fail(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr(metadata, "version", _no_package)
    monkeypatch.setattr(_engine.subprocess, "run", fail)
    assert _engine._detect_version() == "0.0.0-dev"


def test_version_uses_the_git_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    def tag(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout="v9.8.7\n", stderr="")

    monkeypatch.setattr(metadata, "version", _no_package)
    monkeypatch.setattr(_engine.subprocess, "run", tag)
    assert _engine._detect_version() == "9.8.7"
