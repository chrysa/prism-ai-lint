"""Provider contract and deny-by-default tests."""

from __future__ import annotations

import pytest

from prism_ai_lint.model_providers import (
    ExecutionPolicy,
    InferenceRequest,
    InferenceResponse,
    ModelProvider,
    ProviderRegistry,
)
from prism_ai_lint.model_registry import Capability, ModelSpec


class FakeProvider:
    provider_id = "fake"
    calls = 0

    def list_models(self) -> tuple[ModelSpec, ...]:
        return (ModelSpec(model_id="fake/example"),)

    def supports(self, model_id: str, capability: str) -> Capability:
        return Capability.UNKNOWN

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        self.calls += 1
        return InferenceResponse(model_id=request.model_id, text="ok")


def test_provider_protocol():
    assert isinstance(FakeProvider(), ModelProvider)


def test_inference_disabled_by_default():
    fake = FakeProvider()
    registry = ProviderRegistry()
    registry.register(fake, cloud=False)
    with pytest.raises(PermissionError, match="disabled"):
        registry.infer("fake", InferenceRequest(model_id="fake/example", prompt="test"), ExecutionPolicy())
    assert fake.calls == 0


def test_cloud_denied_even_when_provider_allowed():
    fake = FakeProvider()
    registry = ProviderRegistry()
    registry.register(fake, cloud=True)
    policy = ExecutionPolicy(allow_inference=True, allowed_providers=frozenset({"fake"}))
    with pytest.raises(PermissionError, match="cloud"):
        registry.infer("fake", InferenceRequest(model_id="fake/example", prompt="test"), policy)
    assert fake.calls == 0


def test_provider_must_be_allowlisted():
    fake = FakeProvider()
    registry = ProviderRegistry()
    registry.register(fake, cloud=False)
    with pytest.raises(PermissionError, match="explicitly"):
        registry.infer(
            "fake",
            InferenceRequest(model_id="fake/example", prompt="test"),
            ExecutionPolicy(allow_inference=True),
        )
    assert fake.calls == 0


def test_local_provider_explicit_opt_in():
    fake = FakeProvider()
    registry = ProviderRegistry()
    registry.register(fake, cloud=False)
    policy = ExecutionPolicy(allow_inference=True, allowed_providers=frozenset({"fake"}))
    result = registry.infer("fake", InferenceRequest(model_id="fake/example", prompt="test"), policy)
    assert result.text == "ok"
    assert fake.calls == 1


def test_duplicate_provider_is_rejected():
    registry = ProviderRegistry()
    registry.register(FakeProvider(), cloud=False)
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(FakeProvider(), cloud=False)


def test_invalid_request_budget_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        InferenceRequest(model_id="fake/example", prompt="test", max_output_tokens=0)
