from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import (
    LLM_PROFILES_READY,
    LlmReadinessDependencyProvider,
    default_critical_dependency_specs,
    llm_critical_dependency_spec,
)
from helios_v2.llm import LlmGateway, LlmProfile, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.runtime.dependencies import RuntimeStartupError, validate_critical_dependencies
from helios_v2.runtime.kernel import RuntimeKernel


@dataclass
class FakeProvider:
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        return ProviderCompletion(output_text="ok", finish_reason="stop")


def _gateway(env: dict[str, str], provider: FakeProvider | None = None) -> LlmGateway:
    profile = LlmProfile(
        profile_name="thought-default",
        model="test-model",
        api_key_env="OPENAI_API_KEY",
        base_url="https://example.invalid/v1",
    )
    return LlmGateway(
        provider=provider or FakeProvider(),
        registry=LlmProfileRegistry(profiles=(profile,)),
        env=env,
    )


def test_dependency_provider_reports_ready_when_key_present() -> None:
    provider = LlmReadinessDependencyProvider(
        gateway=_gateway({"OPENAI_API_KEY": "sk-test"}),
        bound_profile_names=("thought-default",),
    )
    status = provider.get_dependency_status(LLM_PROFILES_READY)
    assert status.available is True


def test_dependency_provider_reports_not_ready_when_key_missing() -> None:
    provider = LlmReadinessDependencyProvider(
        gateway=_gateway({}),
        bound_profile_names=("thought-default",),
    )
    status = provider.get_dependency_status(LLM_PROFILES_READY)
    assert status.available is False
    assert "thought-default" in status.detail


def test_dependency_provider_defers_other_capabilities_to_baseline() -> None:
    provider = LlmReadinessDependencyProvider(
        gateway=_gateway({"OPENAI_API_KEY": "sk-test"}),
        bound_profile_names=("thought-default",),
    )
    from helios_v2.composition import RUNTIME_COGNITION_BASELINE

    status = provider.get_dependency_status(RUNTIME_COGNITION_BASELINE)
    assert status.available is True


def test_static_readiness_gate_does_not_issue_live_call() -> None:
    fake = FakeProvider()
    provider = LlmReadinessDependencyProvider(
        gateway=_gateway({"OPENAI_API_KEY": "sk-test"}, provider=fake),
        bound_profile_names=("thought-default",),
    )
    provider.get_dependency_status(LLM_PROFILES_READY)
    # Static readiness must not call the provider; only a live probe would.
    assert fake.calls == []


def test_startup_gate_fails_fast_when_llm_profile_unready() -> None:
    specs = default_critical_dependency_specs() + [llm_critical_dependency_spec()]
    provider = LlmReadinessDependencyProvider(
        gateway=_gateway({}),
        bound_profile_names=("thought-default",),
    )
    kernel = RuntimeKernel(dependency_specs=specs, dependency_provider=provider)
    with pytest.raises(RuntimeStartupError) as exc_info:
        kernel.startup()
    assert LLM_PROFILES_READY in exc_info.value.missing_dependencies


def test_startup_gate_passes_when_llm_profile_ready() -> None:
    specs = default_critical_dependency_specs() + [llm_critical_dependency_spec()]
    provider = LlmReadinessDependencyProvider(
        gateway=_gateway({"OPENAI_API_KEY": "sk-test"}),
        bound_profile_names=("thought-default",),
    )
    # Should not raise.
    validate_critical_dependencies(specs, provider)
