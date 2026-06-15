"""Requirement 98 - Post-LLM appraisal adjustment unit tests.

Network-free, deterministic, fail-fast tests for the R98
`PostLLMHormoneAdjuster` translation rules.

The adjuster is the bound between LLM `hormone_response_i_predict`
forecasts and the appraisal owner's `threat` / `reward` / `social` /
`uncertainty` drive deltas. The translation rules (numeric thresholds,
phrase lexicons, magnitude caps, channel mapping) are all owner-owned
by `appraisal.post_llm_hormone_adjuster`; these tests pin them down
to a fail-fast, network-free surface so future refactors cannot drift
the contract.

R98 plan: 13+ unit tests. The exact count below is 16 (covers each
channel × each input kind × each edge case).
"""

from __future__ import annotations

import pytest

from helios_v2.appraisal import (
    LLM_HORMONE_DELTA_MAX,
    LLM_HORMONE_DELTA_MIN,
    PostLLMHormoneAdjuster,
)


@pytest.fixture
def adjuster() -> PostLLMHormoneAdjuster:
    return PostLLMHormoneAdjuster()


# --------------------------------------------------------------------------- #
# Silent-default: missing / malformed input must never throw.                 #
# --------------------------------------------------------------------------- #


def test_none_prediction_returns_zero(adjuster: PostLLMHormoneAdjuster) -> None:
    # The composition glue calls `adjust(prediction)` on every tick;
    # when the LLM emitted no prediction, the adjuster must return a
    # zero adjustment (silent default) and never raise.
    result = adjuster.adjust(None)
    assert result.threat_delta == 0.0
    assert result.reward_delta == 0.0
    assert result.social_delta == 0.0
    assert result.uncertainty_delta == 0.0
    assert result.confidence == 0.0


def test_empty_dict_returns_zero(adjuster: PostLLMHormoneAdjuster) -> None:
    result = adjuster.adjust({})
    assert result.confidence == 0.0
    assert result.threat_delta == 0.0


# --------------------------------------------------------------------------- #
# Numeric forecasts: per-channel primary-magnitude translation.              #
# --------------------------------------------------------------------------- #


def test_cortisol_high_raises_threat(adjuster: PostLLMHormoneAdjuster) -> None:
    # The textbook case: LLM says cortisol is high (>= 0.6) → the
    # appraisal owner's threat channel should be raised by ±0.10 with
    # full confidence. This is what would have saved the B2/B3
    # anxiety fixture ("心跳加速...+0.025") on the real-cloud probe.
    result = adjuster.adjust({"cortisol": 0.8})
    assert result.threat_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.confidence == pytest.approx(1.0)
    # All other deltas must be zero (no cross-contamination).
    assert result.reward_delta == 0.0
    assert result.social_delta == 0.0
    assert result.uncertainty_delta == 0.0


def test_dopamine_low_lowers_reward(adjuster: PostLLMHormoneAdjuster) -> None:
    # LLM says dopamine is low (≤ 0.4) → reward channel goes DOWN
    # (the LLM predicts suppression of reward-seeking).
    result = adjuster.adjust({"dopamine": 0.2})
    assert result.reward_delta == pytest.approx(LLM_HORMONE_DELTA_MIN)
    assert result.confidence == pytest.approx(1.0)


def test_dopamine_high_raises_reward(adjuster: PostLLMHormoneAdjuster) -> None:
    result = adjuster.adjust({"dopamine": 0.9})
    assert result.reward_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.confidence == pytest.approx(1.0)


def test_norepinephrine_high_raises_uncertainty(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # NE is the alertness / vigilance channel; "high" maps to
    # uncertainty_delta (not threat_delta) because the appraisal owner
    # treats NE as the source of "this is uncertain" not "this is
    # threatening" — the threat channel is owned by cortisol.
    result = adjuster.adjust({"norepinephrine": 0.7})
    assert result.uncertainty_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.threat_delta == 0.0


def test_oxytocin_high_raises_social(adjuster: PostLLMHormoneAdjuster) -> None:
    result = adjuster.adjust({"oxytocin": 0.85})
    assert result.social_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)


def test_serotonin_high_uses_secondary_magnitude(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # Serotonin is reward-leaning but also affects anxiety. The
    # secondary magnitude (±0.05) prevents serotonin from overdriving
    # the dopamine-style reward signal. This is the deliberate
    # boundary that keeps the secondary channels from dominating.
    result = adjuster.adjust({"serotonin": 0.9})
    assert result.reward_delta == pytest.approx(0.05)
    assert result.confidence == pytest.approx(1.0)


def test_opioid_tone_high_uses_secondary_magnitude(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    result = adjuster.adjust({"opioid_tone": 0.8})
    assert result.social_delta == pytest.approx(0.05)


# --------------------------------------------------------------------------- #
# Phrase forecasts: lower confidence + bilingual lexicons.                   #
# --------------------------------------------------------------------------- #


def test_phrase_elevated_english(adjuster: PostLLMHormoneAdjuster) -> None:
    # Real-cloud probe saw "likely elevated due to social bonding" in
    # the LLM's `hormone_response_i_predict`. The English phrase must
    # trigger an elevated classification with PHRASE confidence 0.7.
    result = adjuster.adjust({"oxytocin": "likely elevated due to social bonding"})
    assert result.social_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.confidence == pytest.approx(0.7)


def test_phrase_elevated_chinese(adjuster: PostLLMHormoneAdjuster) -> None:
    # Bilingual lexicon: Chinese "升高" must classify as elevated.
    # This was a real gap in the R96 probe — the LLM sometimes wrote
    # Chinese phrases and the old test would have ignored them.
    result = adjuster.adjust({"cortisol": "应激水平升高"})
    assert result.threat_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.confidence == pytest.approx(0.7)


def test_phrase_low(adjuster: PostLLMHormoneAdjuster) -> None:
    result = adjuster.adjust({"dopamine": "low, user seems deflated"})
    assert result.reward_delta == pytest.approx(LLM_HORMONE_DELTA_MIN)
    assert result.confidence == pytest.approx(0.7)


# --------------------------------------------------------------------------- #
# No-comment zone and unparseable values.                                    #
# --------------------------------------------------------------------------- #


def test_no_comment_zone_returns_zero(adjuster: PostLLMHormoneAdjuster) -> None:
    # Between LOW and HIGH (0.4..0.6) is the LLM's "no comment" zone;
    # the adjuster must return zero (NOT mid-magnitude, which would
    # be a free-floating prior that contaminates the drive).
    result = adjuster.adjust({"cortisol": 0.5})
    assert result.threat_delta == 0.0
    assert result.confidence == 0.0


def test_unparseable_value_returns_zero(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # Lists / dicts / None as a value must be silently dropped; the
    # appraisal contract is "I read only numeric or phrase signals".
    result = adjuster.adjust({"cortisol": [0.7, 0.8]})  # type: ignore[dict-item]
    assert result.confidence == 0.0
    result = adjuster.adjust({"dopamine": {"level": "high"}})  # type: ignore[dict-item]
    assert result.confidence == 0.0


def test_unknown_channel_silently_ignored(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # `gaba` / `histamine` / arbitrary extras are not in the R81 nine
    # neuromodulators. The adjuster must silently drop them so a
    # future LLM model that invents new channel names does not crash
    # the appraisal pipeline.
    result = adjuster.adjust({"gaba": 0.9, "histamine": "elevated"})
    assert result.confidence == 0.0
    assert result.threat_delta == 0.0
    assert result.reward_delta == 0.0


def test_bool_value_silently_ignored(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # `True` is a numeric 1 in Python; a stray `{"dopamine": True}`
    # would otherwise classify as 1.0 >= HIGH. Reject bool explicitly.
    result = adjuster.adjust({"dopamine": True})  # type: ignore[dict-item]
    assert result.confidence == 0.0


# --------------------------------------------------------------------------- #
# Multi-channel: combined payloads and confidence-honest-min rule.           #
# --------------------------------------------------------------------------- #


def test_multi_channel_combined_deltas(adjuster: PostLLMHormoneAdjuster) -> None:
    # A single payload with multiple channels must produce combined
    # deltas (each channel contributes to its own field, not all to
    # one). This is the primary use case: the LLM forecasts several
    # hormones in one shot.
    result = adjuster.adjust({
        "cortisol": 0.8,           # +0.10 threat
        "dopamine": 0.2,           # -0.10 reward
        "norepinephrine": 0.7,     # +0.10 uncertainty
        "oxytocin": 0.85,          # +0.10 social
    })
    assert result.threat_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.reward_delta == pytest.approx(LLM_HORMONE_DELTA_MIN)
    assert result.uncertainty_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.social_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.confidence == pytest.approx(1.0)


def test_confidence_takes_min_of_mixed_signals(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # A payload with one numeric (confidence 1.0) and one phrase
    # (confidence 0.7) signal must take confidence=0.7 (the honest
    # min). The drive formula multiplies delta by confidence, so a
    # lower confidence correctly attenuates the whole adjustment.
    result = adjuster.adjust({
        "cortisol": 0.8,                          # numeric, c=1.0
        "dopamine": "likely elevated",            # phrase,  c=0.7
    })
    assert result.confidence == pytest.approx(0.7)


def test_no_comment_channel_does_not_drag_confidence(
    adjuster: PostLLMHormoneAdjuster,
) -> None:
    # A channel in the no-comment zone is a non-event and must not
    # contaminate the overall confidence. A payload with one
    # no-comment entry and one high-confidence numeric entry should
    # still be confidence=1.0 (NOT 0.0 from the no-comment entry).
    result = adjuster.adjust({
        "cortisol": 0.5,    # no-comment zone
        "dopamine": 0.9,    # numeric high
    })
    assert result.reward_delta == pytest.approx(LLM_HORMONE_DELTA_MAX)
    assert result.confidence == pytest.approx(1.0)
