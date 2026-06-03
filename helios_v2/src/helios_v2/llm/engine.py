"""Owner: LLM inference gateway.

Provides the named-profile registry, the backend-neutral gateway owner, and the
first-version OpenAI-compatible provider. The gateway resolves a request's target profile,
reads the profile's api key from an injected environment mapping, dispatches to the injected
provider, and assembles a formal completion. It holds no cognitive policy and never
interprets completion text.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Mapping

from .contracts import (
    LlmCompletion,
    LlmError,
    LlmGatewayAPI,
    LlmProfile,
    LlmProfileReadiness,
    LlmProvider,
    LlmReadinessReport,
    LlmRequest,
    LlmUsage,
    ProviderCompletion,
)

# Stable id for the minimal live-probe request issued per profile during a live readiness
# check. The probe is opt-in and never part of the mandatory startup gate.
_LIVE_PROBE_REQUEST_PREFIX = "llm-live-probe"


@dataclass(frozen=True)
class LlmProfileRegistry:
    """Owner: LLM inference gateway.

    Purpose:
        Hold the named LLM profiles and resolve a profile by name.

    Failure semantics:
        Construction raises `LlmError` when no profile is provided or when two profiles
        share a name. `resolve` raises `LlmError` on an unknown name.

    Notes:
        Profile-to-consumer binding is a composition concern. The registry keys only on
        profile name and is ignorant of which owner consumes which profile.
    """

    profiles: tuple[LlmProfile, ...]

    def __post_init__(self) -> None:
        if not self.profiles:
            raise LlmError("LlmProfileRegistry requires at least one profile")
        seen: set[str] = set()
        for profile in self.profiles:
            if not isinstance(profile, LlmProfile):
                raise LlmError("LlmProfileRegistry must contain LlmProfile values only")
            if profile.profile_name in seen:
                raise LlmError(
                    f"LlmProfileRegistry must declare unique profile names: '{profile.profile_name}'"
                )
            seen.add(profile.profile_name)

    def resolve(self, profile_name: str) -> LlmProfile:
        """Owner: LLM inference gateway.

        Purpose:
            Return the profile registered under `profile_name`.

        Inputs:
            `profile_name` - the profile name to resolve.

        Returns:
            The matching `LlmProfile`.

        Raises:
            LlmError when no profile is registered under the name.
        """

        for profile in self.profiles:
            if profile.profile_name == profile_name:
                return profile
        raise LlmError(f"LlmProfileRegistry has no profile named '{profile_name}'")

    def has(self, profile_name: str) -> bool:
        """Owner: LLM inference gateway.

        Purpose:
            Report whether a profile is registered under `profile_name`.

        Returns:
            True when the profile exists, False otherwise.
        """

        return any(profile.profile_name == profile_name for profile in self.profiles)

    def names(self) -> tuple[str, ...]:
        """Owner: LLM inference gateway.

        Purpose:
            Return the registered profile names in declaration order.

        Returns:
            An immutable tuple of profile names.
        """

        return tuple(profile.profile_name for profile in self.profiles)


@dataclass
class LlmGateway(LlmGatewayAPI):
    """Owner: LLM inference gateway.

    Purpose:
        Turn a neutral inference request into a formal completion through a named profile,
        and report static and (opt-in) live readiness for bound profiles.

    Failure semantics:
        `complete` raises `LlmError` on an unknown profile, a missing or empty api key, or
        any provider failure. There is no degraded or fabricated completion path.

    Notes:
        The injected `env` mapping defaults to `os.environ` but is overridable, so tests
        drive readiness and key resolution deterministically without touching the real
        environment or the network.
    """

    provider: LlmProvider
    registry: LlmProfileRegistry
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    _completion_counter: int = field(default=0, init=False, repr=False)

    def _resolve_api_key(self, profile: LlmProfile) -> str:
        api_key = self.env.get(profile.api_key_env, "")
        if not api_key:
            raise LlmError(
                f"LLM profile '{profile.profile_name}' api key env '{profile.api_key_env}' is not set"
            )
        return api_key

    def complete(self, request: LlmRequest) -> LlmCompletion:
        """Owner: LLM inference gateway.

        Purpose:
            Resolve the request's target profile, dispatch to the provider, and return one
            formal completion preserving the request id and resolved profile/model.

        Inputs:
            `request` - a validated neutral `LlmRequest`.

        Returns:
            An `LlmCompletion` carrying the provider output, finish reason, optional usage,
            and measured latency.

        Raises:
            LlmError on an unknown profile, a missing api key, or a provider failure.

        Notes:
            The gateway measures latency around the provider call only. It does not retry
            and does not interpret the completion text.
        """

        profile = self.registry.resolve(request.target_profile)
        api_key = self._resolve_api_key(profile)
        started_at = time.perf_counter()
        try:
            provider_completion = self.provider.complete(profile, request, api_key)
        except LlmError:
            raise
        except Exception as error:  # noqa: BLE001 - surfaced explicitly as a hard stop
            raise LlmError(
                f"LLM provider failed for profile '{profile.profile_name}': {error}"
            ) from error
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        if not isinstance(provider_completion, ProviderCompletion):
            raise LlmError("LLM provider must return a ProviderCompletion")
        self._completion_counter += 1
        return LlmCompletion(
            completion_id=f"llm-completion:{request.request_id}:{self._completion_counter}",
            source_request_id=request.request_id,
            profile_name=profile.profile_name,
            model=profile.model,
            output_text=provider_completion.output_text,
            finish_reason=provider_completion.finish_reason,
            usage=provider_completion.usage,
            latency_ms=round(latency_ms, 4),
        )

    def check_static_readiness(self, profile_names: tuple[str, ...]) -> LlmReadinessReport:
        """Owner: LLM inference gateway.

        Purpose:
            Report, for each requested profile, whether it exists in the registry and
            whether its declared api-key env var resolves to a non-empty value.

        Inputs:
            `profile_names` - the bound profile names to check.

        Returns:
            An `LlmReadinessReport` with `checked_live=False`; each entry's `live_ready` is
            None because no live call is issued.

        Raises:
            None. This is a query: an unknown profile is reported as not existing rather
            than raising.

        Notes:
            Performs no network call and is deterministic given the injected env mapping.
        """

        entries: list[LlmProfileReadiness] = []
        for profile_name in profile_names:
            if not self.registry.has(profile_name):
                entries.append(
                    LlmProfileReadiness(
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
                    LlmProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=True,
                        live_ready=None,
                        detail=f"api key env '{profile.api_key_env}' is set",
                    )
                )
            else:
                entries.append(
                    LlmProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=False,
                        live_ready=None,
                        detail=f"api key env '{profile.api_key_env}' is not set",
                    )
                )
        return LlmReadinessReport(
            report_id=f"llm-static-readiness:{'+'.join(profile_names) or 'none'}",
            checked_live=False,
            entries=tuple(entries),
        )

    def probe_live_readiness(self, profile_names: tuple[str, ...]) -> LlmReadinessReport:
        """Owner: LLM inference gateway.

        Purpose:
            Issue a minimal real completion for each statically-ready profile and report
            per-profile live readiness.

        Inputs:
            `profile_names` - the bound profile names to probe.

        Returns:
            An `LlmReadinessReport` with `checked_live=True`. A statically-unready profile is
            reported with `live_ready=False` and is not probed.

        Raises:
            None. A provider failure during a probe is captured into the per-profile entry
            rather than aborting the whole report.

        Notes:
            This is opt-in and must never be invoked by the mandatory startup gate. It is
            the only gateway method that issues a real network call.
        """

        entries: list[LlmProfileReadiness] = []
        for profile_name in profile_names:
            if not self.registry.has(profile_name):
                entries.append(
                    LlmProfileReadiness(
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
                    LlmProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=False,
                        live_ready=False,
                        detail=f"api key env '{profile.api_key_env}' is not set",
                    )
                )
                continue
            probe_request = LlmRequest(
                request_id=f"{_LIVE_PROBE_REQUEST_PREFIX}:{profile_name}",
                target_profile=profile_name,
                messages=(
                    _probe_message(),
                ),
                response_format="text",
                metadata={"probe": True},
            )
            try:
                self.provider.complete(profile, probe_request, api_key)
            except Exception as error:  # noqa: BLE001 - captured per-profile, not aborting
                entries.append(
                    LlmProfileReadiness(
                        profile_name=profile_name,
                        exists=True,
                        static_ready=True,
                        live_ready=False,
                        detail=f"live probe failed: {error}",
                    )
                )
                continue
            entries.append(
                LlmProfileReadiness(
                    profile_name=profile_name,
                    exists=True,
                    static_ready=True,
                    live_ready=True,
                    detail="live probe succeeded",
                )
            )
        return LlmReadinessReport(
            report_id=f"llm-live-readiness:{'+'.join(profile_names) or 'none'}",
            checked_live=True,
            entries=tuple(entries),
        )


def _probe_message():
    from .contracts import LlmMessage

    return LlmMessage(role="user", content="ping")


@dataclass
class OpenAICompatibleProvider(LlmProvider):
    """Owner: LLM inference gateway (first-version provider).

    Purpose:
        Issue one synchronous chat completion against an OpenAI-compatible endpoint.

    Failure semantics:
        Translates any SDK import error or transport error into `LlmError`. Never returns a
        fabricated completion to mask a failure.

    Notes:
        The `openai` SDK is imported lazily inside `complete`, so importing this module
        never requires the SDK to be installed. Tests inject a deterministic fake provider
        and never reach this code path.
    """

    def complete(
        self,
        profile: LlmProfile,
        request: LlmRequest,
        api_key: str,
    ) -> ProviderCompletion:
        """Owner: LLM inference gateway (first-version provider).

        Purpose:
            Build the chat-completion payload from the profile and request, call the
            endpoint, and return a `ProviderCompletion`.

        Raises:
            LlmError on a missing SDK or any transport failure.
        """

        try:
            from openai import OpenAI
        except ImportError as error:
            raise LlmError(
                "OpenAICompatibleProvider requires the 'openai' package to be installed"
            ) from error

        client = OpenAI(api_key=api_key, base_url=profile.base_url)
        payload: dict[str, object] = {
            "model": profile.model,
            "messages": [message.to_record() for message in request.messages],
            "temperature": profile.temperature,
            "max_tokens": profile.max_tokens,
            "timeout": profile.timeout,
        }
        if request.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}

        try:
            response = client.chat.completions.create(**payload)
        except Exception as error:  # noqa: BLE001 - surfaced explicitly as a hard stop
            raise LlmError(
                f"OpenAI-compatible request failed for model '{profile.model}': {error}"
            ) from error

        choice = response.choices[0]
        output_text = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"
        usage = _extract_usage(response)
        return ProviderCompletion(
            output_text=output_text,
            finish_reason=finish_reason,
            usage=usage,
        )


def _extract_usage(response: object) -> LlmUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return LlmUsage(
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )
