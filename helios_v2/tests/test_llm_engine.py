from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.llm import (
    LlmError,
    LlmGateway,
    LlmMessage,
    LlmProfile,
    LlmProfileRegistry,
    LlmRequest,
)
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.llm.contracts import LlmUsage


def _profile(name: str = "thought-default", api_key_env: str = "OPENAI_API_KEY") -> LlmProfile:
    return LlmProfile(
        profile_name=name,
        model="test-model",
        api_key_env=api_key_env,
        base_url="https://example.invalid/v1",
    )


def _request(profile: str = "thought-default") -> LlmRequest:
    return LlmRequest(
        request_id="req-1",
        target_profile=profile,
        messages=(LlmMessage(role="user", content="hello"),),
    )


@dataclass
class FakeProvider:
    """Deterministic provider double; records calls, never touches the network."""

    output_text: str = "deterministic completion"
    finish_reason: str = "stop"
    usage: LlmUsage | None = field(default_factory=lambda: LlmUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8))
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append((profile.profile_name, api_key))
        return ProviderCompletion(
            output_text=self.output_text,
            finish_reason=self.finish_reason,
            usage=self.usage,
        )


@dataclass
class RaisingProvider:
    def complete(self, profile, request, api_key) -> ProviderCompletion:
        raise RuntimeError("transport boom")


def test_registry_resolve_and_unknown() -> None:
    registry = LlmProfileRegistry(profiles=(_profile(),))
    assert registry.resolve("thought-default").model == "test-model"
    assert registry.has("thought-default")
    assert not registry.has("missing")
    assert registry.names() == ("thought-default",)
    with pytest.raises(LlmError):
        registry.resolve("missing")


def test_registry_rejects_empty_and_duplicate() -> None:
    with pytest.raises(LlmError):
        LlmProfileRegistry(profiles=())
    with pytest.raises(LlmError):
        LlmProfileRegistry(profiles=(_profile(), _profile()))


def test_complete_returns_completion_preserving_identity() -> None:
    provider = FakeProvider()
    gateway = LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={"OPENAI_API_KEY": "sk-test"},
    )

    completion = gateway.complete(_request())

    assert completion.source_request_id == "req-1"
    assert completion.profile_name == "thought-default"
    assert completion.model == "test-model"
    assert completion.output_text == "deterministic completion"
    assert completion.finish_reason == "stop"
    assert completion.usage is not None and completion.usage.total_tokens == 8
    assert completion.latency_ms >= 0.0
    assert provider.calls == [("thought-default", "sk-test")]


def test_complete_unknown_profile_raises() -> None:
    gateway = LlmGateway(
        provider=FakeProvider(),
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={"OPENAI_API_KEY": "sk-test"},
    )
    with pytest.raises(LlmError):
        gateway.complete(_request(profile="other"))


def test_complete_missing_api_key_raises() -> None:
    gateway = LlmGateway(
        provider=FakeProvider(),
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={},
    )
    with pytest.raises(LlmError):
        gateway.complete(_request())


def test_complete_provider_failure_becomes_llm_error() -> None:
    gateway = LlmGateway(
        provider=RaisingProvider(),
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={"OPENAI_API_KEY": "sk-test"},
    )
    with pytest.raises(LlmError):
        gateway.complete(_request())


def test_static_readiness_is_deterministic_and_network_free() -> None:
    provider = FakeProvider()
    gateway = LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={"OPENAI_API_KEY": "sk-test"},
    )

    report = gateway.check_static_readiness(("thought-default", "missing"))

    assert report.checked_live is False
    by_name = {entry.profile_name: entry for entry in report.entries}
    assert by_name["thought-default"].static_ready is True
    assert by_name["thought-default"].live_ready is None
    assert by_name["missing"].exists is False
    assert by_name["missing"].static_ready is False
    assert not report.all_static_ready()
    # No provider call was made for a static readiness check.
    assert provider.calls == []


def test_static_readiness_reports_missing_key() -> None:
    gateway = LlmGateway(
        provider=FakeProvider(),
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={},
    )
    report = gateway.check_static_readiness(("thought-default",))
    assert report.all_static_ready() is False
    assert report.entries[0].static_ready is False


def test_live_probe_calls_provider_only_when_invoked() -> None:
    provider = FakeProvider()
    gateway = LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={"OPENAI_API_KEY": "sk-test"},
    )

    report = gateway.probe_live_readiness(("thought-default",))

    assert report.checked_live is True
    assert report.entries[0].live_ready is True
    assert provider.calls == [("thought-default", "sk-test")]


def test_live_probe_skips_unready_profile() -> None:
    provider = FakeProvider()
    gateway = LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={},
    )

    report = gateway.probe_live_readiness(("thought-default",))

    assert report.entries[0].static_ready is False
    assert report.entries[0].live_ready is False
    assert provider.calls == []


def test_live_probe_captures_provider_failure() -> None:
    gateway = LlmGateway(
        provider=RaisingProvider(),
        registry=LlmProfileRegistry(profiles=(_profile(),)),
        env={"OPENAI_API_KEY": "sk-test"},
    )

    report = gateway.probe_live_readiness(("thought-default",))

    assert report.entries[0].static_ready is True
    assert report.entries[0].live_ready is False
    assert "live probe failed" in report.entries[0].detail
