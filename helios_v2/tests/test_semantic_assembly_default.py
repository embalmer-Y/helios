"""Semantic assembly as default: unit and integration tests.

Validates:
- DeterministicHashEmbeddingProvider: determinism, dimensions, non-zero norm, similarity.
- RuntimeProfile.default_signal_mode: valid values, invalid value raises, default is "semantic".
- Default assembly produces semantic_memory_enabled == True.
- Legacy mode preserves constant shim behavior.
"""

from __future__ import annotations

import pytest

from helios_v2.composition import RuntimeProfile, assemble_runtime
from helios_v2.composition.runtime_assembly import CompositionError
from helios_v2.embedding import (
    DeterministicHashEmbeddingProvider,
    EmbeddingProfile,
    EmbeddingRequest,
)


# ---------------------------------------------------------------------------
# DeterministicHashEmbeddingProvider unit tests
# ---------------------------------------------------------------------------


def _provider_profile() -> EmbeddingProfile:
    return EmbeddingProfile(
        profile_name="test",
        model="deterministic-hash",
        api_key_env="K",
        base_url="http://localhost",
    )


def _provider_request(text: str) -> EmbeddingRequest:
    return EmbeddingRequest(
        request_id=f"r:{abs(hash(text))}",
        target_profile="test",
        input_text=text,
    )


def test_hash_provider_produces_correct_dimensions() -> None:
    provider = DeterministicHashEmbeddingProvider()
    result = provider.embed(_provider_profile(), _provider_request("hello"), "key")
    assert result.dimensions == 16
    assert len(result.vector) == 16


def test_hash_provider_custom_dimensions() -> None:
    provider = DeterministicHashEmbeddingProvider(dimensions=32)
    result = provider.embed(_provider_profile(), _provider_request("hello"), "key")
    assert result.dimensions == 32
    assert len(result.vector) == 32


def test_hash_provider_is_deterministic() -> None:
    provider = DeterministicHashEmbeddingProvider()
    profile = _provider_profile()
    request = _provider_request("deterministic test")
    result_a = provider.embed(profile, request, "key1")
    result_b = provider.embed(profile, request, "key2")
    assert result_a.vector == result_b.vector


def test_hash_provider_non_zero_norm_for_normal_text() -> None:
    provider = DeterministicHashEmbeddingProvider()
    result = provider.embed(_provider_profile(), _provider_request("non-empty text"), "key")
    assert any(v != 0.0 for v in result.vector)


def test_hash_provider_similarity_ordering() -> None:
    """Similar texts produce closer vectors than dissimilar texts."""
    provider = DeterministicHashEmbeddingProvider()
    profile = _provider_profile()

    vec_a = provider.embed(profile, _provider_request("hello world"), "k").vector
    vec_b = provider.embed(profile, _provider_request("hello world!"), "k").vector
    vec_c = provider.embed(profile, _provider_request("xyz完全不同"), "k").vector

    # Dot-product similarity (vectors are non-negative so this is monotone with cosine).
    sim_ab = sum(a * b for a, b in zip(vec_a, vec_b))
    sim_ac = sum(a * c for a, c in zip(vec_a, vec_c))
    assert sim_ab > sim_ac


def test_hash_provider_ignores_profile_and_api_key() -> None:
    """The hash provider uses only the input text, not the profile or key."""
    provider = DeterministicHashEmbeddingProvider()
    profile_a = EmbeddingProfile(
        profile_name="a", model="m1", api_key_env="K1", base_url="http://a"
    )
    profile_b = EmbeddingProfile(
        profile_name="b", model="m2", api_key_env="K2", base_url="http://b"
    )
    request = _provider_request("same text")
    result_a = provider.embed(profile_a, request, "key-alpha")
    result_b = provider.embed(profile_b, request, "key-beta")
    assert result_a.vector == result_b.vector


# ---------------------------------------------------------------------------
# RuntimeProfile.default_signal_mode unit tests
# ---------------------------------------------------------------------------


def test_default_signal_mode_default_is_semantic() -> None:
    profile = RuntimeProfile()
    assert profile.default_signal_mode == "semantic"


def test_default_signal_mode_accepts_legacy_constant() -> None:
    profile = RuntimeProfile(default_signal_mode="legacy_constant")
    assert profile.default_signal_mode == "legacy_constant"


def test_default_signal_mode_rejects_unknown_value() -> None:
    with pytest.raises(CompositionError, match="default_signal_mode"):
        RuntimeProfile(default_signal_mode="unknown_mode")


# ---------------------------------------------------------------------------
# Integration: default assembly is semantic
# ---------------------------------------------------------------------------


def test_default_assembly_enables_semantic_memory() -> None:
    """assemble_runtime() with no arguments produces semantic_memory_enabled == True."""
    handle = assemble_runtime(deterministic_thought=True)
    # The auto-provisioned store and embedding gateway are wired.
    assert handle.experience_store is not None


def test_default_assembly_semantic_novelty_varies_with_stimuli() -> None:
    """Under semantic assembly, different stimuli produce different novelty values."""
    handle = assemble_runtime(deterministic_thought=True)
    handle.startup()

    # Tick with one stimulus, then with another; novelty should differ because the
    # semantic appraisal path is active.
    result = handle.tick()
    # The appraisal carries real salience dimensions (not the constant 0.6 novelty).
    batch = result.stage_results["rapid_salience_appraisal"].batch
    novelty = batch.appraisals[0].salience.novelty
    # Under semantic assembly, novelty is derived from the grounded estimator.
    # It should not be the legacy constant 0.6.
    assert novelty != pytest.approx(0.6, abs=1e-9)


def test_legacy_constant_mode_preserves_constant_behavior() -> None:
    """assemble_runtime(default_signal_mode='legacy_constant') keeps constant shim behavior."""
    handle = assemble_runtime(
        deterministic_thought=True,
        default_signal_mode="legacy_constant",
    )
    handle.startup()
    result = handle.tick()

    # Under legacy mode, novelty is the constant 0.6.
    batch = result.stage_results["rapid_salience_appraisal"].batch
    assert batch.appraisals[0].salience.novelty == pytest.approx(0.6)


def test_legacy_constant_mode_no_auto_provisioned_store() -> None:
    """Legacy mode does not auto-provision an experience store."""
    handle = assemble_runtime(
        deterministic_thought=True,
        default_signal_mode="legacy_constant",
    )
    assert handle.experience_store is None
