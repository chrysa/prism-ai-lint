"""Contract tests for the optional provider-agnostic model registry."""

from __future__ import annotations

import pytest

from prism_ai_lint.model_registry import Capability, ModelRegistry, ModelSpec


def test_unknown_model_is_not_assumed_deprecated():
    registry = ModelRegistry()
    model = registry.resolve("future-model-42")
    assert model.model_id == "future-model-42"
    assert model.status == "unknown"
    assert not model.verified


def test_alias_resolves_without_mutating_requested_id():
    registry = ModelRegistry()
    registry.register(ModelSpec(model_id="provider/model-1", aliases=("friendly",), verified=True))
    model = registry.resolve("friendly")
    assert model.model_id == "provider/model-1"
    assert registry.resolve("friendly").model_id == model.model_id


def test_capabilities_are_tristate():
    registry = ModelRegistry()
    registry.register(ModelSpec(model_id="provider/a", capabilities={"tools": True, "vision": False}))
    assert registry.supports("provider/a", "tools") is Capability.YES
    assert registry.supports("provider/a", "vision") is Capability.NO
    assert registry.supports("provider/a", "json_schema") is Capability.UNKNOWN


def test_duplicate_alias_fails_closed():
    registry = ModelRegistry()
    registry.register(ModelSpec(model_id="provider/a", aliases=("same",)))
    with pytest.raises(ValueError, match="alias"):
        registry.register(ModelSpec(model_id="provider/b", aliases=("same",)))


def test_model_ids_are_namespaced_by_provider():
    registry = ModelRegistry()
    registry.register(ModelSpec(model_id="vendor-a/model"))
    registry.register(ModelSpec(model_id="vendor-b/model"))
    assert registry.resolve("vendor-a/model").model_id != registry.resolve("vendor-b/model").model_id


def test_invalid_status_is_rejected():
    with pytest.raises(ValueError, match="status"):
        ModelSpec(model_id="vendor/model", status="definitely-best")


def test_invalid_capability_is_rejected():
    with pytest.raises(ValueError, match="capability"):
        ModelSpec(model_id="vendor/model", capabilities={"tools": "maybe"})
