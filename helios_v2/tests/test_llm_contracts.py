from __future__ import annotations

import pytest

from helios_v2.llm import (
    LlmCompletion,
    LlmError,
    LlmMessage,
    LlmProfile,
    LlmProfileReadiness,
    LlmReadinessReport,
    LlmRequest,
    LlmUsage,
)
from helios_v2.llm.contracts import ProviderCompletion


def _message() -> LlmMessage:
    return LlmMessage(role="user", content="hello")


def test_llm_message_rejects_unknown_role() -> None:
    with pytest.raises(LlmError):
        LlmMessage(role="tool", content="x")  # type: ignore[arg-type]


def test_llm_message_rejects_empty_content() -> None:
    with pytest.raises(LlmError):
        LlmMessage(role="user", content="")


def test_llm_message_to_record_shape() -> None:
    assert _message().to_record() == {"role": "user", "content": "hello"}


def test_llm_request_requires_messages() -> None:
    with pytest.raises(LlmError):
        LlmRequest(request_id="r1", target_profile="p", messages=())


def test_llm_request_requires_non_empty_profile() -> None:
    with pytest.raises(LlmError):
        LlmRequest(request_id="r1", target_profile="", messages=(_message(),))


def test_llm_request_rejects_unknown_response_format() -> None:
    with pytest.raises(LlmError):
        LlmRequest(
            request_id="r1",
            target_profile="p",
            messages=(_message(),),
            response_format="xml",  # type: ignore[arg-type]
        )


def test_llm_request_freezes_metadata() -> None:
    request = LlmRequest(
        request_id="r1",
        target_profile="p",
        messages=(_message(),),
        metadata={"tick_id": 3},
    )
    with pytest.raises(TypeError):
        request.metadata["tick_id"] = 4  # type: ignore[index]


def test_llm_usage_rejects_negative_counts() -> None:
    with pytest.raises(LlmError):
        LlmUsage(prompt_tokens=-1)


def test_llm_usage_allows_none() -> None:
    usage = LlmUsage()
    assert usage.to_record() == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def test_llm_completion_requires_finish_reason() -> None:
    with pytest.raises(LlmError):
        LlmCompletion(
            completion_id="c1",
            source_request_id="r1",
            profile_name="p",
            model="m",
            output_text="ok",
            finish_reason="",
            usage=None,
            latency_ms=1.0,
        )


def test_llm_completion_rejects_negative_latency() -> None:
    with pytest.raises(LlmError):
        LlmCompletion(
            completion_id="c1",
            source_request_id="r1",
            profile_name="p",
            model="m",
            output_text="ok",
            finish_reason="stop",
            usage=None,
            latency_ms=-0.1,
        )


def test_llm_profile_validation() -> None:
    with pytest.raises(LlmError):
        LlmProfile(profile_name="", model="m", api_key_env="K", base_url="u")
    with pytest.raises(LlmError):
        LlmProfile(profile_name="p", model="m", api_key_env="K", base_url="u", max_tokens=0)
    with pytest.raises(LlmError):
        LlmProfile(profile_name="p", model="m", api_key_env="K", base_url="u", timeout=0.0)
    with pytest.raises(LlmError):
        LlmProfile(profile_name="p", model="m", api_key_env="K", base_url="u", temperature=-0.1)


def test_llm_profile_does_not_store_key() -> None:
    profile = LlmProfile(profile_name="p", model="m", api_key_env="OPENAI_API_KEY", base_url="u")
    assert profile.api_key_env == "OPENAI_API_KEY"
    assert not hasattr(profile, "api_key")


def test_readiness_report_rejects_duplicate_profiles() -> None:
    entry = LlmProfileReadiness(
        profile_name="p",
        exists=True,
        static_ready=True,
        live_ready=None,
        detail="ok",
    )
    with pytest.raises(LlmError):
        LlmReadinessReport(report_id="rid", checked_live=False, entries=(entry, entry))


def test_readiness_report_all_static_ready() -> None:
    ready = LlmProfileReadiness(
        profile_name="p1", exists=True, static_ready=True, live_ready=None, detail="ok"
    )
    not_ready = LlmProfileReadiness(
        profile_name="p2", exists=True, static_ready=False, live_ready=None, detail="missing"
    )
    assert LlmReadinessReport(report_id="r", checked_live=False, entries=(ready,)).all_static_ready()
    assert not LlmReadinessReport(
        report_id="r", checked_live=False, entries=(ready, not_ready)
    ).all_static_ready()
    assert not LlmReadinessReport(report_id="r", checked_live=False, entries=()).all_static_ready()


def test_provider_completion_requires_finish_reason() -> None:
    with pytest.raises(LlmError):
        ProviderCompletion(output_text="x", finish_reason="")
