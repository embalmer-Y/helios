from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.embedding import (
    EmbeddingError,
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    EmbeddingRequest,
    ProviderEmbedding,
)


@dataclass
class FakeEmbeddingProvider:
    """Deterministic, network-free embedding provider for tests.

    Maps text to a small fixed-dimension vector by hashing characters into buckets, so
    similarity ordering is predictable: similar text yields similar vectors.
    """

    dimensions: int = 8
    calls: list[str] = field(default_factory=list)

    def embed(self, profile, request, api_key) -> ProviderEmbedding:
        self.calls.append(profile.profile_name)
        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        # Ensure a non-zero norm even for unusual inputs.
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)


@dataclass
class RaisingEmbeddingProvider:
    def embed(self, profile, request, api_key) -> ProviderEmbedding:
        raise RuntimeError("transport boom")


def _profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )


def _gateway(provider=None, env=None) -> EmbeddingGateway:
    return EmbeddingGateway(
        provider=provider or FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(_profile(),)),
        env=env if env is not None else {"OPENAI_API_KEY": "sk-test"},
    )


def test_registry_rejects_empty_and_duplicate_profiles() -> None:
    with pytest.raises(EmbeddingError, match="at least one profile"):
        EmbeddingProfileRegistry(profiles=())
    with pytest.raises(EmbeddingError, match="unique profile names"):
        EmbeddingProfileRegistry(profiles=(_profile(), _profile()))


def test_gateway_returns_vector_via_provider() -> None:
    provider = FakeEmbeddingProvider()
    gateway = _gateway(provider=provider)
    result = gateway.embed(
        EmbeddingRequest(request_id="req-1", target_profile="experience-embedding", input_text="hello")
    )
    assert result.source_request_id == "req-1"
    assert result.profile_name == "experience-embedding"
    assert result.dimensions == 8
    assert len(result.vector) == 8
    assert provider.calls == ["experience-embedding"]


def test_gateway_unknown_profile_raises() -> None:
    gateway = _gateway()
    with pytest.raises(EmbeddingError, match="no profile named"):
        gateway.embed(EmbeddingRequest(request_id="r", target_profile="missing", input_text="x"))


def test_gateway_missing_key_raises() -> None:
    gateway = _gateway(env={})
    with pytest.raises(EmbeddingError, match="api key env"):
        gateway.embed(
            EmbeddingRequest(request_id="r", target_profile="experience-embedding", input_text="x")
        )


def test_gateway_provider_failure_is_hard_stop() -> None:
    gateway = _gateway(provider=RaisingEmbeddingProvider())
    with pytest.raises(EmbeddingError, match="provider failed"):
        gateway.embed(
            EmbeddingRequest(request_id="r", target_profile="experience-embedding", input_text="x")
        )


def test_static_readiness_network_free() -> None:
    ready = _gateway().check_static_readiness(("experience-embedding",))
    assert ready.all_static_ready()
    assert ready.checked_live is False

    unready = _gateway(env={}).check_static_readiness(("experience-embedding",))
    assert not unready.all_static_ready()

    unknown = _gateway().check_static_readiness(("missing",))
    assert not unknown.all_static_ready()
    assert unknown.entries[0].exists is False


def test_live_probe_opt_in_via_fake_provider() -> None:
    provider = FakeEmbeddingProvider()
    report = _gateway(provider=provider).probe_live_readiness(("experience-embedding",))
    assert report.checked_live is True
    assert report.entries[0].live_ready is True
    # The probe issued a real (fake) call.
    assert "experience-embedding" in provider.calls
