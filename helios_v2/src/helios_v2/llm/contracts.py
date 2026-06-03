"""Owner: LLM inference gateway.

Owns:
- backend-neutral inference request and completion contracts
- the named LLM profile contract
- the LLM provider protocol (vendor-neutral dispatch seam)
- readiness-report contracts and the LLM gateway API

Does not own:
- prompt assembly (owned by `prompt_contract`)
- cognitive interpretation of completion text (owned by the consuming cognitive owner)
- consumer identity or which cognitive stage a request serves
- cross-owner state transport
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable


class LlmError(RuntimeError):
    """Hard-stop error raised when LLM inference gateway invariants fail.

    This covers an unknown profile name, a missing or empty api key at call time,
    empty messages, and any provider or transport failure surfaced during inference.
    The gateway never substitutes a fabricated completion for an error.
    """


LlmMessageRole = Literal["system", "user", "assistant"]
LlmResponseFormat = Literal["text", "json_object"]

_MESSAGE_ROLES = {"system", "user", "assistant"}
_RESPONSE_FORMATS = {"text", "json_object"}


def _freeze_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    frozen = MappingProxyType(dict(mapping))
    for key in frozen:
        if not key:
            raise LlmError("LLM mappings must not contain empty keys")
    return frozen


@dataclass(frozen=True)
class LlmMessage:
    """Immutable role-tagged message in one inference request.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on an unknown role or empty content.
    """

    role: LlmMessageRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in _MESSAGE_ROLES:
            raise LlmError("LlmMessage role must use the fixed taxonomy")
        if not self.content:
            raise LlmError("LlmMessage must declare non-empty content")

    def to_record(self) -> dict[str, str]:
        """Owner: LLM inference gateway.

        Purpose:
            Return the provider-facing role/content pair for one message.

        Returns:
            A plain dict with `role` and `content`, ready for an OpenAI-compatible payload.
        """

        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class LlmRequest:
    """Immutable backend-neutral inference request for one synchronous completion.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on an empty request id, empty target profile,
        empty message tuple, or an unknown response format.

    Notes:
        The request keys the target model only by `target_profile`. The gateway never
        learns which cognitive consumer built the request; `metadata` is opaque provenance
        the gateway forwards but does not interpret.
    """

    request_id: str
    target_profile: str
    messages: tuple[LlmMessage, ...]
    response_format: LlmResponseFormat = "text"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id:
            raise LlmError("LlmRequest must declare a non-empty request_id")
        if not self.target_profile:
            raise LlmError("LlmRequest must declare a non-empty target_profile")
        if not self.messages:
            raise LlmError("LlmRequest must declare at least one message")
        for message in self.messages:
            if not isinstance(message, LlmMessage):
                raise LlmError("LlmRequest messages must contain LlmMessage values only")
        if self.response_format not in _RESPONSE_FORMATS:
            raise LlmError("LlmRequest response_format must use the fixed taxonomy")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class LlmUsage:
    """Immutable token-usage facts reported by a provider for one completion.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` when any present token count is negative.
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or value < 0):
                raise LlmError(f"LlmUsage {name} must be a non-negative integer when present")

    def to_record(self) -> dict[str, object]:
        """Owner: LLM inference gateway.

        Purpose:
            Return a compact projection of usage facts.

        Returns:
            A plain dict with the three token counts (each possibly None).
        """

        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class LlmCompletion:
    """Immutable completion result published by the gateway for one request.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on empty ids, an empty resolved profile or model,
        an empty finish reason, or a negative latency.

    Notes:
        Completion facts (model, usage, latency, finish reason) travel through this
        contract, never through the log channel. The gateway does not interpret
        `output_text`; that is the consuming cognitive owner's responsibility.
    """

    completion_id: str
    source_request_id: str
    profile_name: str
    model: str
    output_text: str
    finish_reason: str
    usage: LlmUsage | None
    latency_ms: float

    def __post_init__(self) -> None:
        if not self.completion_id:
            raise LlmError("LlmCompletion must declare a non-empty completion_id")
        if not self.source_request_id:
            raise LlmError("LlmCompletion must declare a non-empty source_request_id")
        if not self.profile_name:
            raise LlmError("LlmCompletion must declare a non-empty profile_name")
        if not self.model:
            raise LlmError("LlmCompletion must declare a non-empty model")
        if not self.finish_reason:
            raise LlmError("LlmCompletion must declare a non-empty finish_reason")
        if not isinstance(self.latency_ms, (int, float)) or self.latency_ms < 0.0:
            raise LlmError("LlmCompletion latency_ms must be a non-negative number")
        if self.usage is not None and not isinstance(self.usage, LlmUsage):
            raise LlmError("LlmCompletion usage must be an LlmUsage when present")


@dataclass(frozen=True)
class LlmProfile:
    """Immutable named LLM profile declaring one model/endpoint configuration.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on empty profile name, model, api-key env var, or
        base URL; a negative temperature; a non-positive max-token count or timeout; or an
        unknown default response format.

    Notes:
        The api key itself is never stored on the profile. The profile only names the
        environment variable (`api_key_env`) from which the gateway resolves the key at
        call time, so secrets are not captured into an immutable contract.
    """

    profile_name: str
    model: str
    api_key_env: str
    base_url: str
    temperature: float = 0.2
    max_tokens: int = 800
    timeout: float = 30.0
    default_response_format: LlmResponseFormat = "text"

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise LlmError("LlmProfile must declare a non-empty profile_name")
        if not self.model:
            raise LlmError("LlmProfile must declare a non-empty model")
        if not self.api_key_env:
            raise LlmError("LlmProfile must declare a non-empty api_key_env")
        if not self.base_url:
            raise LlmError("LlmProfile must declare a non-empty base_url")
        if not isinstance(self.temperature, (int, float)) or self.temperature < 0.0:
            raise LlmError("LlmProfile temperature must be a non-negative number")
        if not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            raise LlmError("LlmProfile max_tokens must be a positive integer")
        if not isinstance(self.timeout, (int, float)) or self.timeout <= 0.0:
            raise LlmError("LlmProfile timeout must be a positive number")
        if self.default_response_format not in _RESPONSE_FORMATS:
            raise LlmError("LlmProfile default_response_format must use the fixed taxonomy")


@dataclass(frozen=True)
class LlmProfileReadiness:
    """Immutable per-profile readiness fact in a readiness report.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on an empty profile name or empty detail.
    """

    profile_name: str
    exists: bool
    static_ready: bool
    live_ready: bool | None
    detail: str

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise LlmError("LlmProfileReadiness must declare a non-empty profile_name")
        if not self.detail:
            raise LlmError("LlmProfileReadiness must declare a non-empty detail")


@dataclass(frozen=True)
class LlmReadinessReport:
    """Immutable readiness report distinguishing static from live readiness.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on an empty report id or duplicate profile entries.

    Notes:
        `checked_live` is True only when a live probe was actually issued. A static-only
        report sets `checked_live=False` and leaves each entry's `live_ready` as None.
    """

    report_id: str
    checked_live: bool
    entries: tuple[LlmProfileReadiness, ...]

    def __post_init__(self) -> None:
        if not self.report_id:
            raise LlmError("LlmReadinessReport must declare a non-empty report_id")
        seen: set[str] = set()
        for entry in self.entries:
            if not isinstance(entry, LlmProfileReadiness):
                raise LlmError("LlmReadinessReport entries must be LlmProfileReadiness values")
            if entry.profile_name in seen:
                raise LlmError("LlmReadinessReport entries must be keyed by unique profile names")
            seen.add(entry.profile_name)

    def all_static_ready(self) -> bool:
        """Owner: LLM inference gateway.

        Purpose:
            Report whether every entry in the report is statically ready.

        Returns:
            True when there is at least one entry and all entries are statically ready;
            False otherwise (including an empty report).
        """

        return bool(self.entries) and all(entry.static_ready for entry in self.entries)


@dataclass(frozen=True)
class ProviderCompletion:
    """Immutable provider-internal completion value returned by an `LlmProvider`.

    Owner: LLM inference gateway.

    Failure semantics:
        Construction raises `LlmError` on an empty finish reason.

    Notes:
        This is the narrow value a provider returns. The gateway wraps it into the public
        `LlmCompletion` by adding the resolved profile/model identity and measured latency.
    """

    output_text: str
    finish_reason: str
    usage: LlmUsage | None = None

    def __post_init__(self) -> None:
        if not self.finish_reason:
            raise LlmError("ProviderCompletion must declare a non-empty finish_reason")
        if self.usage is not None and not isinstance(self.usage, LlmUsage):
            raise LlmError("ProviderCompletion usage must be an LlmUsage when present")


@runtime_checkable
class LlmProvider(Protocol):
    """Vendor-neutral provider dispatch seam consumed by the gateway.

    Owner: LLM inference gateway.
    """

    def complete(
        self,
        profile: LlmProfile,
        request: LlmRequest,
        api_key: str,
    ) -> ProviderCompletion:
        """Owner: LLM inference gateway (provider seam).

        Purpose:
            Issue one synchronous completion against the resolved profile.

        Inputs:
            `profile` - the resolved target profile (model, endpoint, sampling params).
            `request` - the neutral inference request with role-tagged messages.
            `api_key` - the resolved non-empty api key for the profile.

        Returns:
            A `ProviderCompletion` carrying output text, finish reason, and optional usage.

        Raises:
            LlmError on any provider or transport failure. Providers must not return a
            fabricated completion to mask a failure.
        """

        ...


@runtime_checkable
class LlmGatewayAPI(Protocol):
    """Public API for the LLM inference gateway owner.

    Owner: LLM inference gateway.
    """

    def complete(self, request: LlmRequest) -> LlmCompletion:
        """Resolve the target profile and return one completion, raising on failure."""

        ...

    def check_static_readiness(self, profile_names: tuple[str, ...]) -> LlmReadinessReport:
        """Return a deterministic, network-free static-readiness report for the named profiles."""

        ...

    def probe_live_readiness(self, profile_names: tuple[str, ...]) -> LlmReadinessReport:
        """Issue a minimal real completion per ready profile and report live readiness."""

        ...
