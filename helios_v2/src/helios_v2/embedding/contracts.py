"""Owner: embedding inference gateway.

Owns:
- backend-neutral embedding request and result contracts
- the named embedding profile contract
- the embedding provider protocol (vendor-neutral dispatch seam)
- readiness-report contracts and the embedding gateway API

Does not own:
- text assembly or what to embed (owned by the consuming owner)
- cognitive interpretation of an embedding vector
- vector storage or similarity ranking (owned by `33` persistence)
- consumer identity or which owner a request serves
- cross-owner state transport

This owner is a capability owner, not a cognitive owner. It turns text into a vector through
a named profile and reports readiness. It never interprets meaning and holds no cognitive
policy, mirroring the `25` LLM inference gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable


class EmbeddingError(RuntimeError):
    """Hard-stop error raised when embedding gateway invariants fail.

    This covers an unknown profile name, a missing or empty api key at call time, empty
    input text, an empty or malformed provider vector, and any provider or transport failure.
    The gateway never substitutes a fabricated vector for an error.
    """


def _freeze_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    frozen = MappingProxyType(dict(mapping))
    for key in frozen:
        if not key:
            raise EmbeddingError("Embedding mappings must not contain empty keys")
    return frozen


@dataclass(frozen=True)
class EmbeddingProfile:
    """Immutable named embedding profile declaring one model/endpoint configuration.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` on empty profile name, model, api-key env var,
        or base URL; a non-positive timeout; or a non-positive declared dimensions.

    Notes:
        The api key itself is never stored on the profile. The profile only names the
        environment variable (`api_key_env`) from which the gateway resolves the key at call
        time. `dimensions`, when set, is the documented expected vector length; it is not
        enforced on the provider here but lets a consumer validate downstream.
    """

    profile_name: str
    model: str
    api_key_env: str
    base_url: str
    dimensions: int | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise EmbeddingError("EmbeddingProfile must declare a non-empty profile_name")
        if not self.model:
            raise EmbeddingError("EmbeddingProfile must declare a non-empty model")
        if not self.api_key_env:
            raise EmbeddingError("EmbeddingProfile must declare a non-empty api_key_env")
        if not self.base_url:
            raise EmbeddingError("EmbeddingProfile must declare a non-empty base_url")
        if self.dimensions is not None and (not isinstance(self.dimensions, int) or self.dimensions <= 0):
            raise EmbeddingError("EmbeddingProfile dimensions must be a positive integer when set")
        if not isinstance(self.timeout, (int, float)) or self.timeout <= 0.0:
            raise EmbeddingError("EmbeddingProfile timeout must be a positive number")


@dataclass(frozen=True)
class EmbeddingRequest:
    """Immutable backend-neutral embedding request for one synchronous vector.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` on an empty request id, empty target profile, or
        empty input text.

    Notes:
        The request keys the target model only by `target_profile`. The gateway never learns
        which owner built the request; `metadata` is opaque provenance the gateway forwards
        but does not interpret.
    """

    request_id: str
    target_profile: str
    input_text: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            raise EmbeddingError("EmbeddingRequest must declare a non-empty request_id")
        if not self.target_profile:
            raise EmbeddingError("EmbeddingRequest must declare a non-empty target_profile")
        if not self.input_text:
            raise EmbeddingError("EmbeddingRequest must declare non-empty input_text")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class EmbeddingUsage:
    """Immutable token-usage facts reported by a provider for one embedding.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` when any present token count is negative.
    """

    prompt_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in ("prompt_tokens", "total_tokens"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or value < 0):
                raise EmbeddingError(f"EmbeddingUsage {name} must be a non-negative integer when present")


@dataclass(frozen=True)
class ProviderEmbedding:
    """Immutable provider-internal embedding value returned by an `EmbeddingProvider`.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` on an empty vector, a non-finite component, or a
        `dimensions` that disagrees with the vector length.

    Notes:
        This is the narrow value a provider returns. The gateway wraps it into the public
        `EmbeddingResult` by adding the resolved profile/model identity and measured latency.
    """

    vector: tuple[float, ...]
    dimensions: int
    usage: EmbeddingUsage | None = None

    def __post_init__(self) -> None:
        if not self.vector:
            raise EmbeddingError("ProviderEmbedding must declare a non-empty vector")
        for component in self.vector:
            if not isinstance(component, (int, float)):
                raise EmbeddingError("ProviderEmbedding vector components must be numeric")
        if self.dimensions != len(self.vector):
            raise EmbeddingError("ProviderEmbedding dimensions must equal the vector length")
        if self.usage is not None and not isinstance(self.usage, EmbeddingUsage):
            raise EmbeddingError("ProviderEmbedding usage must be an EmbeddingUsage when present")


@dataclass(frozen=True)
class EmbeddingResult:
    """Immutable embedding result published by the gateway for one request.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` on empty ids, an empty resolved profile or model,
        an empty vector, a `dimensions` that disagrees with the vector length, or a negative
        latency.

    Notes:
        Embedding facts (model, dimensions, usage, latency) travel through this contract,
        never through the log channel. The gateway does not interpret the vector's meaning.
    """

    result_id: str
    source_request_id: str
    profile_name: str
    model: str
    vector: tuple[float, ...]
    dimensions: int
    usage: EmbeddingUsage | None
    latency_ms: float

    def __post_init__(self) -> None:
        if not self.result_id:
            raise EmbeddingError("EmbeddingResult must declare a non-empty result_id")
        if not self.source_request_id:
            raise EmbeddingError("EmbeddingResult must declare a non-empty source_request_id")
        if not self.profile_name:
            raise EmbeddingError("EmbeddingResult must declare a non-empty profile_name")
        if not self.model:
            raise EmbeddingError("EmbeddingResult must declare a non-empty model")
        if not self.vector:
            raise EmbeddingError("EmbeddingResult must declare a non-empty vector")
        if self.dimensions != len(self.vector):
            raise EmbeddingError("EmbeddingResult dimensions must equal the vector length")
        if not isinstance(self.latency_ms, (int, float)) or self.latency_ms < 0.0:
            raise EmbeddingError("EmbeddingResult latency_ms must be a non-negative number")
        if self.usage is not None and not isinstance(self.usage, EmbeddingUsage):
            raise EmbeddingError("EmbeddingResult usage must be an EmbeddingUsage when present")


@dataclass(frozen=True)
class EmbeddingProfileReadiness:
    """Immutable per-profile readiness fact in a readiness report.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` on an empty profile name or empty detail.
    """

    profile_name: str
    exists: bool
    static_ready: bool
    live_ready: bool | None
    detail: str

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise EmbeddingError("EmbeddingProfileReadiness must declare a non-empty profile_name")
        if not self.detail:
            raise EmbeddingError("EmbeddingProfileReadiness must declare a non-empty detail")


@dataclass(frozen=True)
class EmbeddingReadinessReport:
    """Immutable readiness report distinguishing static from live readiness.

    Owner: embedding inference gateway.

    Failure semantics:
        Construction raises `EmbeddingError` on an empty report id or duplicate profile entries.

    Notes:
        `checked_live` is True only when a live probe was actually issued. A static-only
        report sets `checked_live=False` and leaves each entry's `live_ready` as None.
    """

    report_id: str
    checked_live: bool
    entries: tuple[EmbeddingProfileReadiness, ...]

    def __post_init__(self) -> None:
        if not self.report_id:
            raise EmbeddingError("EmbeddingReadinessReport must declare a non-empty report_id")
        seen: set[str] = set()
        for entry in self.entries:
            if not isinstance(entry, EmbeddingProfileReadiness):
                raise EmbeddingError(
                    "EmbeddingReadinessReport entries must be EmbeddingProfileReadiness values"
                )
            if entry.profile_name in seen:
                raise EmbeddingError(
                    "EmbeddingReadinessReport entries must be keyed by unique profile names"
                )
            seen.add(entry.profile_name)

    def all_static_ready(self) -> bool:
        """Owner: embedding inference gateway.

        Purpose:
            Report whether every entry in the report is statically ready.

        Returns:
            True when there is at least one entry and all entries are statically ready;
            False otherwise (including an empty report).
        """

        return bool(self.entries) and all(entry.static_ready for entry in self.entries)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Vendor-neutral provider dispatch seam consumed by the gateway.

    Owner: embedding inference gateway.
    """

    def embed(
        self,
        profile: EmbeddingProfile,
        request: EmbeddingRequest,
        api_key: str,
    ) -> ProviderEmbedding:
        """Owner: embedding inference gateway (provider seam).

        Purpose:
            Issue one synchronous embedding against the resolved profile.

        Inputs:
            `profile` - the resolved target profile (model, endpoint).
            `request` - the neutral embedding request with input text.
            `api_key` - the resolved non-empty api key for the profile.

        Returns:
            A `ProviderEmbedding` carrying the vector, its dimensions, and optional usage.

        Raises:
            EmbeddingError on any provider or transport failure. Providers must not return a
            fabricated vector to mask a failure.
        """

        ...


@runtime_checkable
class EmbeddingGatewayAPI(Protocol):
    """Public API for the embedding inference gateway owner.

    Owner: embedding inference gateway.
    """

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Resolve the target profile and return one embedding, raising on failure."""

        ...

    def check_static_readiness(self, profile_names: tuple[str, ...]) -> EmbeddingReadinessReport:
        """Return a deterministic, network-free static-readiness report for the named profiles."""

        ...

    def probe_live_readiness(self, profile_names: tuple[str, ...]) -> EmbeddingReadinessReport:
        """Issue a minimal real embedding per ready profile and report live readiness."""

        ...
