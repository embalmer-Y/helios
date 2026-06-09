"""Owner: embedding inference gateway.

Provides the named-profile registry, the backend-neutral gateway owner, and the first-version
OpenAI-compatible embedding provider. The gateway resolves a request's target profile, reads
the profile's api key from an injected environment mapping, dispatches to the injected
provider, and assembles a formal result. It holds no cognitive policy and never interprets the
embedding vector. This mirrors the `25` LLM inference gateway.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Mapping

from .contracts import (
    EmbeddingError,
    EmbeddingGatewayAPI,
    EmbeddingProfile,
    EmbeddingProfileReadiness,
    EmbeddingProvider,
    EmbeddingReadinessReport,
    EmbeddingRequest,
    EmbeddingResult,
    ProviderEmbedding,
)

# Stable id prefix for the minimal live-probe request issued per profile during a live
# readiness check. The probe is opt-in and never part of the mandatory startup gate.
_LIVE_PROBE_REQUEST_PREFIX = "embedding-live-probe"


@dataclass(frozen=True)
class EmbeddingProfileRegistry:
    """Owner: embedding inference gateway.

    Purpose:
        Hold the named embedding profiles and resolve a profile by name.

    Failure semantics:
        Construction raises `EmbeddingError` when no profile is provided or when two profiles
        share a name. `resolve` raises `EmbeddingError` on an unknown name.

    Notes:
        Profile-to-consumer binding is a composition concern. The registry keys only on
        profile name and is ignorant of which owner consumes which profile.
    """

    profiles: tuple[EmbeddingProfile, ...]

    def __post_init__(self) -> None:
        if not self.profiles:
            raise EmbeddingError("EmbeddingProfileRegistry requires at least one profile")
        seen: set[str] = set()
        for profile in self.profiles:
            if not isinstance(profile, EmbeddingProfile):
                raise EmbeddingError("EmbeddingProfileRegistry must contain EmbeddingProfile values only")
            if profile.profile_name in seen:
                raise EmbeddingError(
                    f"EmbeddingProfileRegistry must declare unique profile names: '{profile.profile_name}'"
                )
            seen.add(profile.profile_name)

    def resolve(self, profile_name: str) -> EmbeddingProfile:
        """Owner: embedding inference gateway.

        Purpose:
            Return the profile registered under `profile_name`.

        Inputs:
            `profile_name` - the profile name to resolve.

        Returns:
            The matching `EmbeddingProfile`.

        Raises:
            EmbeddingError when no profile is registered under the name.
        """

        for profile in self.profiles:
            if profile.profile_name == profile_name:
                return profile
        raise EmbeddingError(f"EmbeddingProfileRegistry has no profile named '{profile_name}'")

    def has(self, profile_name: str) -> bool:
        """Owner: embedding inference gateway.

        Purpose:
            Report whether a profile is registered under `profile_name`.

        Returns:
            True when the profile exists, False otherwise.
        """

        return any(profile.profile_name == profile_name for profile in self.profiles)


@dataclass
class EmbeddingGateway(EmbeddingGatewayAPI):
    """Owner: embedding inference gateway.

    Purpose:
        Turn a neutral embedding request into a formal result through a named profile, and
        report static and (opt-in) live readiness for bound profiles.

    Failure semantics:
        `embed` raises `EmbeddingError` on an unknown profile, a missing or empty api key, or
        any provider failure. There is no degraded or fabricated vector path.

    Notes:
        The injected `env` mapping defaults to `os.environ` but is overridable, so tests drive
        readiness and key resolution deterministically without touching the real environment
        or the network.
    """

    provider: EmbeddingProvider
    registry: EmbeddingProfileRegistry
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    _result_counter: int = field(default=0, init=False, repr=False)

    def _resolve_api_key(self, profile: EmbeddingProfile) -> str:
        api_key = self.env.get(profile.api_key_env, "")
        if not api_key:
            raise EmbeddingError(
                f"Embedding profile '{profile.profile_name}' api key env '{profile.api_key_env}' is not set"
            )
        return api_key

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Owner: embedding inference gateway.

        Purpose:
            Resolve the request's target profile, dispatch to the provider, and return one
            formal result preserving the request id and resolved profile/model.

        Inputs:
            `request` - a validated neutral `EmbeddingRequest`.

        Returns:
            An `EmbeddingResult` carrying the provider vector, dimensions, optional usage, and
            measured latency.

        Raises:
            EmbeddingError on an unknown profile, a missing api key, or a provider failure.

        Notes:
            The gateway measures latency around the provider call only. It does not retry and
            does not interpret the vector.
        """

        profile = self.registry.resolve(request.target_profile)
        api_key = self._resolve_api_key(profile)
        started_at = time.perf_counter()
        try:
            provider_embedding = self.provider.embed(profile, request, api_key)
        except EmbeddingError:
            raise
        except Exception as error:  # noqa: BLE001 - surfaced explicitly as a hard stop
            raise EmbeddingError(
                f"Embedding provider failed for profile '{profile.profile_name}': {error}"
            ) from error
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        if not isinstance(provider_embedding, ProviderEmbedding):
            raise EmbeddingError("Embedding provider must return a ProviderEmbedding")
        self._result_counter += 1
        return EmbeddingResult(
            result_id=f"embedding-result:{request.request_id}:{self._result_counter}",
            source_request_id=request.request_id,
            profile_name=profile.profile_name,
            model=profile.model,
            vector=tuple(float(component) for component in provider_embedding.vector),
            dimensions=provider_embedding.dimensions,
            usage=provider_embedding.usage,
            latency_ms=round(latency_ms, 4),
        )

    def check_static_readiness(self, profile_names: tuple[str, ...]) -> EmbeddingReadinessReport:
        """Owner: embedding inference gateway.

        Purpose:
            Report, for each requested profile, whether it exists in the registry and whether
            its declared api-key env var resolves to a non-empty value.

        Inputs:
            `profile_names` - the bound profile names to check.

        Returns:
            An `EmbeddingReadinessReport` with `checked_live=False`; each entry's `live_ready`
            is None because no live call is issued.

        Raises:
            None. This is a query: an unknown profile is reported as not existing rather than
            raising.

        Notes:
            Performs no network call and is deterministic given the injected env mapping.
        """

        entries: list[EmbeddingProfileReadiness] = []
        for profile_name in profile_names:
            if not self.registry.has(profile_name):
                entries.append(
                    EmbeddingProfileReadiness(
                        profile_name=profile_name,
                        exists=False,
                        static_ready=False,
                        live_ready=None,
                        detail="profile is not registered",
                    )
                )
                continue
            profile = self.registry.resolve(profile_name)
            api_key = self.env.get(profile.api_key_env, "")
            if api_key:
                entries.append(
                    EmbeddingProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=True,
                        live_ready=None,
                        detail=f"api key env '{profile.api_key_env}' is set",
                    )
                )
            else:
                entries.append(
                    EmbeddingProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=False,
                        live_ready=None,
                        detail=f"api key env '{profile.api_key_env}' is not set",
                    )
                )
        return EmbeddingReadinessReport(
            report_id=f"embedding-static-readiness:{'+'.join(profile_names) or 'none'}",
            checked_live=False,
            entries=tuple(entries),
        )

    def probe_live_readiness(self, profile_names: tuple[str, ...]) -> EmbeddingReadinessReport:
        """Owner: embedding inference gateway.

        Purpose:
            Issue a minimal real embedding for each statically-ready profile and report
            per-profile live readiness.

        Inputs:
            `profile_names` - the bound profile names to probe.

        Returns:
            An `EmbeddingReadinessReport` with `checked_live=True`. A statically-unready
            profile is reported with `live_ready=False` and is not probed.

        Raises:
            None. A provider failure during a probe is captured into the per-profile entry
            rather than aborting the whole report.

        Notes:
            This is opt-in and must never be invoked by the mandatory startup gate. It is the
            only gateway method that issues a real network call.
        """

        entries: list[EmbeddingProfileReadiness] = []
        for profile_name in profile_names:
            if not self.registry.has(profile_name):
                entries.append(
                    EmbeddingProfileReadiness(
                        profile_name=profile_name,
                        exists=False,
                        static_ready=False,
                        live_ready=False,
                        detail="profile is not registered",
                    )
                )
                continue
            profile = self.registry.resolve(profile_name)
            api_key = self.env.get(profile.api_key_env, "")
            if not api_key:
                entries.append(
                    EmbeddingProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=False,
                        live_ready=False,
                        detail=f"api key env '{profile.api_key_env}' is not set",
                    )
                )
                continue
            probe_request = EmbeddingRequest(
                request_id=f"{_LIVE_PROBE_REQUEST_PREFIX}:{profile_name}",
                target_profile=profile_name,
                input_text="ping",
                metadata={"probe": True},
            )
            try:
                self.provider.embed(profile, probe_request, api_key)
            except Exception as error:  # noqa: BLE001 - captured per-profile, not aborting
                entries.append(
                    EmbeddingProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=True,
                        live_ready=False,
                        detail=f"live probe failed: {error}",
                    )
                )
                continue
            entries.append(
                EmbeddingProfileReadiness(
                    profile_name=profile_name,
                    exists=True,
                    static_ready=True,
                    live_ready=True,
                    detail="live probe succeeded",
                )
            )
        return EmbeddingReadinessReport(
            report_id=f"embedding-live-readiness:{'+'.join(profile_names) or 'none'}",
            checked_live=True,
            entries=tuple(entries),
        )


@dataclass
class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Owner: embedding inference gateway (first-version provider).

    Purpose:
        Issue one synchronous embedding against an OpenAI-compatible endpoint.

    Failure semantics:
        Translates any SDK import error or transport error into `EmbeddingError`. Never
        returns a fabricated vector to mask a failure.

    Notes:
        The `openai` SDK is imported lazily inside `embed`, so importing this module never
        requires the SDK to be installed. Tests inject a deterministic fake provider and never
        reach this code path.
    """

    def embed(
        self,
        profile: EmbeddingProfile,
        request: EmbeddingRequest,
        api_key: str,
    ) -> ProviderEmbedding:
        """Owner: embedding inference gateway (first-version provider).

        Purpose:
            Build the embedding payload from the profile and request, call the endpoint, and
            return a `ProviderEmbedding`.

        Raises:
            EmbeddingError on a missing SDK or any transport failure.
        """

        try:
            from openai import OpenAI
        except ImportError as error:
            raise EmbeddingError(
                "OpenAICompatibleEmbeddingProvider requires the 'openai' package to be installed"
            ) from error

        client = OpenAI(api_key=api_key, base_url=profile.base_url)
        payload: dict[str, object] = {
            "model": profile.model,
            "input": request.input_text,
            "timeout": profile.timeout,
        }
        if profile.dimensions is not None:
            payload["dimensions"] = profile.dimensions

        try:
            response = client.embeddings.create(**payload)
        except Exception as error:  # noqa: BLE001 - surfaced explicitly as a hard stop
            raise EmbeddingError(
                f"OpenAI-compatible embedding failed for model '{profile.model}': {error}"
            ) from error

        vector = tuple(float(component) for component in response.data[0].embedding)
        if not vector:
            raise EmbeddingError(
                f"OpenAI-compatible embedding returned an empty vector for model '{profile.model}'"
            )
        usage = _extract_usage(response)
        return ProviderEmbedding(vector=vector, dimensions=len(vector), usage=usage)


def _extract_usage(response: object):
    from .contracts import EmbeddingUsage

    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return EmbeddingUsage(
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


@dataclass(frozen=True)
class DeterministicHashEmbeddingProvider:
    """Owner: embedding inference gateway (default no-network provider).

    Purpose:
        Produce deterministic, fixed-dimension embedding vectors from input text using a
        character-hash-to-bucket algorithm. No network, no model, no randomness.

    Failure semantics:
        Never raises for valid inputs. Never fabricates a vector to mask a failure (the
        protocol rule applies to provider-level failures; this provider has none).

    Notes:
        Similar texts produce similar vectors because shared characters at shared positions
        contribute to the same buckets. The embedding quality is intentionally minimal — it
        provides a meaningful cosine-similarity ordering for the default assembly's novelty
        and retrieval computations, but is not a substitute for a real embedding model.
        Callers who need higher-quality embeddings inject an `OpenAICompatibleEmbeddingProvider`
        or a custom `EmbeddingProvider` through the existing `embedding_gateway` seam.
    """

    dimensions: int = 16

    def embed(
        self,
        profile: EmbeddingProfile,
        request: EmbeddingRequest,
        api_key: str,
    ) -> ProviderEmbedding:
        """Owner: embedding inference gateway (default no-network provider).

        Purpose:
            Build a deterministic, fixed-dimension vector from the request input text using
            a character-hash-to-bucket algorithm. The same input text always produces the
            same vector, regardless of the profile or api key.

        Inputs:
            `profile` - the resolved target profile (ignored; no network call is made).
            `request` - the neutral embedding request whose `input_text` is hashed.
            `api_key` - the resolved api key (ignored; no authentication is needed).

        Returns:
            A `ProviderEmbedding` with a deterministic `dimensions`-length vector.
        """

        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)
