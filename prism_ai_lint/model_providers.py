"""Opt-in inference provider contracts; no network access in this module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from prism_ai_lint.model_registry import Capability, ModelSpec


@dataclass(frozen=True)
class InferenceRequest:
    model_id: str
    prompt: str
    max_output_tokens: int = 1024
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be empty")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")


@dataclass(frozen=True)
class InferenceResponse:
    model_id: str
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@runtime_checkable
class ModelProvider(Protocol):
    """Providers must never be invoked unless an explicit policy permits it."""

    @property
    def provider_id(self) -> str: ...

    def list_models(self) -> tuple[ModelSpec, ...]: ...

    def supports(self, model_id: str, capability: str) -> Capability: ...

    def infer(self, request: InferenceRequest) -> InferenceResponse: ...


@dataclass(frozen=True)
class ExecutionPolicy:
    """Hard eligibility constraints applied before provider invocation."""

    allow_inference: bool = False
    allow_cloud: bool = False
    allowed_providers: frozenset[str] = frozenset()


class ProviderRegistry:
    """Explicitly registered providers, never auto-imported from scanned repos."""

    def __init__(self) -> None:
        self._providers: dict[str, tuple[ModelProvider, bool]] = {}

    def register(self, provider: ModelProvider, *, cloud: bool) -> None:
        name = provider.provider_id
        if not name or name in self._providers:
            raise ValueError("empty or duplicate provider_id")
        self._providers[name] = (provider, cloud)

    def infer(self, provider_id: str, request: InferenceRequest, policy: ExecutionPolicy) -> InferenceResponse:
        if not policy.allow_inference:
            raise PermissionError("model inference is disabled")
        if provider_id not in policy.allowed_providers:
            raise PermissionError("provider not explicitly allowed")
        provider, cloud = self._providers[provider_id]
        if cloud and not policy.allow_cloud:
            raise PermissionError("cloud inference is disabled")
        return provider.infer(request)
