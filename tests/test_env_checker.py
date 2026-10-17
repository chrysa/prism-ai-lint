"""Settings `env` block and sandbox keys: reports only, nothing is edited."""

from __future__ import annotations

from pathlib import Path

from prism_ai_lint.env_checker import EnvChecker
from prism_ai_lint.report import Report

P = Path("settings.json")


def _run(settings):
    rep = Report()
    EnvChecker().check(settings, P, rep)
    return {(f.level, f.code) for f in rep.findings}


def test_clean_env_reports_nothing():
    assert _run({"env": {"FOO": "1", "MAX_MCP_OUTPUT_TOKENS": "10000"}}) == set()


def test_weakening_variable_is_a_warning():
    assert _run({"env": {"CLAUDE_CODE_DISABLE_DANGEROUS_RM_TIMEOUT": "1"}}) == {("warn", "ENV_WEAKENS_SECURITY")}


def test_weakening_variable_switched_off_is_fine():
    assert _run({"env": {"CLAUDE_CODE_DISABLE_ADMIN_ENV_UNION": "0"}}) == set()


def test_deprecated_variable():
    assert _run({"env": {"ANTHROPIC_SMALL_FAST_MODEL": "haiku"}}) == {("info", "ENV_DEPRECATED")}


def test_raised_caps_and_long_cache_ttl():
    assert _run({"env": {"BASH_MAX_OUTPUT_LENGTH": "100000", "CLAUDE_CODE_PROMPT_CACHE_TTL": "1h"}}) == {
        ("info", "ENV_TOKEN_CAP")
    }


def test_cap_at_or_below_default_and_junk_values_are_quiet():
    assert _run({"env": {"BASH_MAX_OUTPUT_LENGTH": "30000", "MAX_MCP_OUTPUT_TOKENS": "lots"}}) == set()


def test_weaker_nested_sandbox():
    assert _run({"sandbox": {"enableWeakerNestedSandbox": True}}) == {("warn", "ENV_SANDBOX_WEAK")}
    assert _run({"sandbox": {"enableWeakerNestedSandbox": False}}) == set()


def test_non_dict_input_is_ignored():
    assert _run(None) == set()
    assert _run({"env": "x", "sandbox": []}) == set()
