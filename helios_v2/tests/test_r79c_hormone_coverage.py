"""R79-C T6: Verify 5-HT / Oxy / Opioid drivers are non-constant under non-empty appraisal batches.

Owner: 04 neuromodulator (R79-C)
"""
from __future__ import annotations

from helios_v2.appraisal.contracts import (
    RapidAppraisal,
    RapidAppraisalBatch,
    RapidSalienceVector,
)
from helios_v2.neuromodulation.contracts import (
    NeuromodulatorConfig,
    NeuromodulatorLevels,
)
from helios_v2.neuromodulation.engine import AppraisalDerivedNeuromodulatorUpdatePath


def _build_levels(value: float) -> NeuromodulatorLevels:
    return NeuromodulatorLevels(
        dopamine=value,
        norepinephrine=value,
        serotonin=value,
        acetylcholine=value,
        cortisol=value,
        oxytocin=value,
        opioid_tone=value,
        excitation=value,
        inhibition=value,
    )


def _build_config() -> NeuromodulatorConfig:
    return NeuromodulatorConfig(
        tonic_baseline=_build_levels(0.3),
        legal_min=_build_levels(0.0),
        legal_max=_build_levels(1.0),
        mandatory_learned_parameters=(
            "channel_gain_sensitivity",
            "cross_channel_coupling_strength",
            "decay_speed_persistence",
            "gate_influence_strength",
            "hormone_predict_coupling",
        ),
    )


def _build_appraisal(
    batch_id: str,
    threat: float = 0.0,
    reward: float = 0.0,
    novelty: float = 0.0,
    social: float = 0.0,
    uncertainty: float = 0.0,
) -> RapidAppraisal:
    aggregate = max(threat, reward, novelty, social, uncertainty)
    return RapidAppraisal(
        appraisal_id=f"appraisal:{batch_id}:1",
        stimulus_id=f"stimulus:{batch_id}:1",
        source_name="synthetic",
        salience=RapidSalienceVector(
            threat=threat,
            reward=reward,
            novelty=novelty,
            social=social,
            uncertainty=uncertainty,
            aggregate=aggregate,
        ),
        provenance_signal_id=f"signal:{batch_id}:1",
    )


def _build_batch(*appraisals: RapidAppraisal) -> RapidAppraisalBatch:
    return RapidAppraisalBatch(
        batch_id="batch:1",
        appraisals=tuple(appraisals),
    )


def test_5ht_varies_on_threat_and_social() -> None:
    """5-HT must vary as threat and social vary in the appraisal batch."""
    config = _build_config()
    path = AppraisalDerivedNeuromodulatorUpdatePath()

    # high safety + high social -> 5-HT should rise above baseline
    high_batch = _build_batch(
        _build_appraisal("b1", threat=0.0, social=1.0)
    )
    # low safety + low social -> 5-HT should stay at baseline
    low_batch = _build_batch(
        _build_appraisal("b2", threat=1.0, social=0.0)
    )

    high_levels = path.update_levels(high_batch, config, tick_id=1, prior_levels=None)
    low_levels = path.update_levels(low_batch, config, tick_id=1, prior_levels=None)

    assert high_levels.serotonin > low_levels.serotonin, (
        f"5-HT should rise with safety + social, but high={high_levels.serotonin}, "
        f"low={low_levels.serotonin}"
    )
    # And high should be above baseline
    assert high_levels.serotonin > config.tonic_baseline.serotonin
    # And low should be at baseline (threat=1.0 -> (1-1)*0 = 0; threat=0.0+social=0 -> 0)
    assert low_levels.serotonin == pytest.approx(config.tonic_baseline.serotonin)


def test_oxytocin_varies_on_social_and_uncertainty() -> None:
    """Oxytocin must vary as social and uncertainty vary in the appraisal batch."""
    config = _build_config()
    path = AppraisalDerivedNeuromodulatorUpdatePath()

    # high social + low uncertainty -> Oxy should rise above baseline
    high_batch = _build_batch(
        _build_appraisal("b1", social=1.0, uncertainty=0.0)
    )
    # low social + high uncertainty -> Oxy should stay at baseline
    low_batch = _build_batch(
        _build_appraisal("b2", social=0.0, uncertainty=1.0)
    )

    high_levels = path.update_levels(high_batch, config, tick_id=1, prior_levels=None)
    low_levels = path.update_levels(low_batch, config, tick_id=1, prior_levels=None)

    assert high_levels.oxytocin > low_levels.oxytocin
    assert high_levels.oxytocin > config.tonic_baseline.oxytocin
    assert low_levels.oxytocin == pytest.approx(config.tonic_baseline.oxytocin)


def test_opioid_varies_on_threat_and_uncertainty() -> None:
    """Opioid_tone must vary as threat and uncertainty vary in the appraisal batch."""
    config = _build_config()
    path = AppraisalDerivedNeuromodulatorUpdatePath()

    # low threat + low uncertainty + social (signal present) -> Opioid should rise above baseline
    high_batch = _build_batch(
        _build_appraisal("b1", threat=0.0, uncertainty=0.0, social=1.0)
    )
    # high threat + high uncertainty + social -> Opioid should stay at baseline
    low_batch = _build_batch(
        _build_appraisal("b2", threat=1.0, uncertainty=1.0, social=1.0)
    )

    high_levels = path.update_levels(high_batch, config, tick_id=1, prior_levels=None)
    low_levels = path.update_levels(low_batch, config, tick_id=1, prior_levels=None)

    assert high_levels.opioid_tone > low_levels.opioid_tone
    assert high_levels.opioid_tone > config.tonic_baseline.opioid_tone
    assert low_levels.opioid_tone == pytest.approx(config.tonic_baseline.opioid_tone)


def test_empty_batch_keeps_5ht_oxy_opioid_at_baseline() -> None:
    """Empty appraisal batch must keep 5-HT / Oxy / Opioid at tonic baseline."""
    config = _build_config()
    path = AppraisalDerivedNeuromodulatorUpdatePath()

    empty_batch = _build_batch()  # no appraisals
    levels = path.update_levels(empty_batch, config, tick_id=1, prior_levels=None)

    assert levels.serotonin == pytest.approx(config.tonic_baseline.serotonin)
    assert levels.oxytocin == pytest.approx(config.tonic_baseline.oxytocin)
    assert levels.opioid_tone == pytest.approx(config.tonic_baseline.opioid_tone)
    # And the other 3 de-shimmed channels should still be at baseline too
    assert levels.acetylcholine == pytest.approx(config.tonic_baseline.acetylcholine)
    assert levels.excitation == pytest.approx(config.tonic_baseline.excitation)
    assert levels.inhibition == pytest.approx(config.tonic_baseline.inhibition)


def test_dual_timescale_10_ticks_5ht_oxy_increase_under_praise() -> None:
    """Under a constant A_praise-like stimulus (social=1.0, threat=0.0, uncertainty=0.0),
    the dual-timescale wrapper should show 5-HT and Oxy rising across 10 ticks
    (because the formula-derived drive is above baseline and the integrator
    moves the levels toward it phasically)."""
    from helios_v2.neuromodulation.engine import DualTimescaleNeuromodulatorUpdatePath

    config = _build_config()
    inner = AppraisalDerivedNeuromodulatorUpdatePath()
    wrapper = DualTimescaleNeuromodulatorUpdatePath(drive_path=inner)

    praise_batch = _build_batch(
        _build_appraisal("praise", threat=0.0, social=1.0, uncertainty=0.0)
    )

    prior = None
    first_5ht = None
    first_oxy = None
    last_5ht = None
    last_oxy = None
    for tick in range(1, 11):
        levels = wrapper.update_levels(praise_batch, config, tick_id=tick, prior_levels=prior)
        if tick == 1:
            first_5ht = levels.serotonin
            first_oxy = levels.oxytocin
        if tick == 10:
            last_5ht = levels.serotonin
            last_oxy = levels.oxytocin
        prior = levels

    assert last_5ht is not None and first_5ht is not None
    assert last_oxy is not None and first_oxy is not None
    assert last_5ht > first_5ht, (
        f"5-HT should rise across ticks under praise, but first={first_5ht}, last={last_5ht}"
    )
    assert last_oxy > first_oxy, (
        f"Oxytocin should rise across ticks under praise, but first={first_oxy}, last={last_oxy}"
    )


def test_v3_prompt_schema_includes_12th_hormone_predict_field() -> None:
    """The v3 system prompt must include the 12th field `hormone_response_i_predict`."""
    from helios_v2.prompt_contract import (
        AggressiveRadicalEmbodiedPromptPath,
        EmbodiedPromptConfig,
        EmbodiedPromptConsumerKind,
        EmbodiedPromptRequest,
    )

    # Build a minimal request matching the v3 contract
    request = EmbodiedPromptRequest(
        request_id="r79c-schema-test",
        consumer_kind="thought",
        source_conscious_state_id="cs-r79c",
        source_gate_result_id="gr-r79c",
        source_retrieval_bundle_id="rb-r79c",
        stimulus_summary={
            "focused": "a stimulus",
            "peripheral": (),
            "filtered": (),
        },
        state_summary={"body_state": "calm"},
        retrieval_summary={"retrieval_context": "(none)", "continuity_context": "continue"},
        capability_summary={
            "available_channels": ("reply_cli",),
            "ready_channels": ("reply_cli",),
            "forbidden_capabilities": (),
        },
        identity_boundary_summary={"identity_boundary": "stay consistent with prior self-narrative"},
        tick_id=1,
    )
    config = EmbodiedPromptConfig(
        prompt_bootstrap_id="embodied-prompt-bootstrap:v3-aggressive-radical",
        max_layer_count=8,
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )
    contract = AggressiveRadicalEmbodiedPromptPath().build(request, config)
    # The 6th layer is v3_system_prompt
    v3_layer = contract.layers[5].content
    assert "hormone_response_i_predict" in v3_layer
    # The 12th field is the LAST field in the JSON schema
    assert "null if you do not want to predict" in v3_layer
    # The 12 fields include all 11 legacy + hormone_response_i_predict
    for field in (
        "what_i_feel",
        "what_i_think",
        "i_want_to_say",
        "i_will_send_it",
        "i_send_through",
        "i_want_to_act",
        "act_type",
        "remember_this",
        "remember_because",
        "i_want_to_think_more",
        "think_more_about",
        "hormone_response_i_predict",
    ):
        assert field in v3_layer, f"missing 12th-or-existing field {field} in v3 system prompt"
    # The new hard rule about the 12th field
    assert "9-key dict" in v3_layer


import pytest  # noqa: E402  (import at end so other tests don't need it)
