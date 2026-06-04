from __future__ import annotations

import pytest

from helios_v2.embedding import (
    EmbeddingError,
    EmbeddingProfile,
    EmbeddingProfileReadiness,
    EmbeddingReadinessReport,
    EmbeddingRequest,
    EmbeddingResult,
    ProviderEmbedding,
)


def test_profile_rejects_empty_required_fields() -> None:
    with pytest.raises(EmbeddingError, match="profile_name"):
        EmbeddingProfile(profile_name="", model="m", api_key_env="K", base_url="u")
    with pytest.raises(EmbeddingError, match="model"):
        EmbeddingProfile(profile_name="p", model="", api_key_env="K", base_url="u")
    with pytest.raises(EmbeddingError, match="api_key_env"):
        EmbeddingProfile(profile_name="p", model="m", api_key_env="", base_url="u")
    with pytest.raises(EmbeddingError, match="base_url"):
        EmbeddingProfile(profile_name="p", model="m", api_key_env="K", base_url="")


def test_profile_rejects_non_positive_dimensions_and_timeout() -> None:
    with pytest.raises(EmbeddingError, match="dimensions"):
        EmbeddingProfile(profile_name="p", model="m", api_key_env="K", base_url="u", dimensions=0)
    with pytest.raises(EmbeddingError, match="timeout"):
        EmbeddingProfile(profile_name="p", model="m", api_key_env="K", base_url="u", timeout=0.0)


def test_request_rejects_empty_fields() -> None:
    with pytest.raises(EmbeddingError, match="request_id"):
        EmbeddingRequest(request_id="", target_profile="p", input_text="hi")
    with pytest.raises(EmbeddingError, match="target_profile"):
        EmbeddingRequest(request_id="r", target_profile="", input_text="hi")
    with pytest.raises(EmbeddingError, match="input_text"):
        EmbeddingRequest(request_id="r", target_profile="p", input_text="")


def test_provider_embedding_validates_dimensions() -> None:
    with pytest.raises(EmbeddingError, match="non-empty vector"):
        ProviderEmbedding(vector=(), dimensions=0)
    with pytest.raises(EmbeddingError, match="dimensions"):
        ProviderEmbedding(vector=(1.0, 2.0), dimensions=3)
    ok = ProviderEmbedding(vector=(1.0, 2.0, 3.0), dimensions=3)
    assert ok.dimensions == 3


def test_result_validates_vector_and_latency() -> None:
    with pytest.raises(EmbeddingError, match="vector"):
        EmbeddingResult(
            result_id="r",
            source_request_id="req",
            profile_name="p",
            model="m",
            vector=(),
            dimensions=0,
            usage=None,
            latency_ms=1.0,
        )
    with pytest.raises(EmbeddingError, match="latency_ms"):
        EmbeddingResult(
            result_id="r",
            source_request_id="req",
            profile_name="p",
            model="m",
            vector=(1.0,),
            dimensions=1,
            usage=None,
            latency_ms=-1.0,
        )


def test_readiness_report_rejects_duplicate_profiles() -> None:
    entry = EmbeddingProfileReadiness(
        profile_name="p", exists=True, static_ready=True, live_ready=None, detail="ok"
    )
    with pytest.raises(EmbeddingError, match="unique profile names"):
        EmbeddingReadinessReport(report_id="r", checked_live=False, entries=(entry, entry))


def test_readiness_report_all_static_ready() -> None:
    ready = EmbeddingProfileReadiness(
        profile_name="a", exists=True, static_ready=True, live_ready=None, detail="ok"
    )
    not_ready = EmbeddingProfileReadiness(
        profile_name="b", exists=True, static_ready=False, live_ready=None, detail="no key"
    )
    assert EmbeddingReadinessReport(report_id="r", checked_live=False, entries=(ready,)).all_static_ready()
    assert not EmbeddingReadinessReport(
        report_id="r", checked_live=False, entries=(ready, not_ready)
    ).all_static_ready()
    assert not EmbeddingReadinessReport(report_id="r", checked_live=False, entries=()).all_static_ready()
