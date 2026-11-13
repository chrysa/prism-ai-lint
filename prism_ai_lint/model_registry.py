"""Provider-neutral model metadata with conservative capability resolution.

Pure stdlib, no network I/O. Unknown models remain valid and unverified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Capability(Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


_STATUSES = frozenset({"known", "unknown", "deprecated", "retired"})


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    aliases: tuple[str, ...] = ()
    status: str = "known"
    verified: bool = False
    capabilities: dict[str, bool] = field(default_factory=dict)
    source_url: str | None = None
    verified_at: str | None = None

    def __post_init__(self) -> None:
        if not self.model_id or not self.model_id.strip():
            raise ValueError("model_id must not be empty")
        if self.status not in _STATUSES:
            raise ValueError("invalid model status")
        if any(not key or type(value) is not bool for key, value in self.capabilities.items()):
            raise ValueError("invalid capability value")


class ModelRegistry:
    """Exact-ID registry. Aliases never override another model ID or alias."""

    def __init__(self) -> None:
        self._models: dict[str, ModelSpec] = {}
        self._aliases: dict[str, str] = {}

    def register(self, spec: ModelSpec) -> None:
        names = (spec.model_id, *spec.aliases)
        if len(names) != len(set(names)):
            raise ValueError("duplicate alias in model specification")
        if spec.model_id in self._models or spec.model_id in self._aliases:
            raise ValueError("duplicate model ID or alias")
        if any(name in self._models or name in self._aliases or not name.strip() for name in spec.aliases):
            raise ValueError("duplicate or empty alias")
        self._models[spec.model_id] = spec
        for alias in spec.aliases:
            self._aliases[alias] = spec.model_id

    def resolve(self, model_id: str) -> ModelSpec:
        canonical = self._aliases.get(model_id, model_id)
        return self._models.get(canonical, ModelSpec(model_id=canonical, status="unknown"))

    def supports(self, model_id: str, capability: str) -> Capability:
        value = self.resolve(model_id).capabilities.get(capability)
        if value is None:
            return Capability.UNKNOWN
        return Capability.YES if value else Capability.NO
