from __future__ import annotations

import pytest

from helios_v2.appraisal import (
    AssessStimulusBatchOp,
    PublishRapidAppraisalBatchOp,
    RapidAppraisal,
    RapidAppraisalError,
    RapidSalienceVector,
)
from helios_v2.sensory import Stimulus


def test_rapid_salience_vector_rejects_scores_outside_unit_range() -> None:
    with pytest.raises(RapidAppraisalError, match="Salience score 'threat'"):
        RapidSalienceVector(
            threat=1.1,
            reward=0.1,
            novelty=0.2,
            social=0.3,
            uncertainty=0.2,
            aggregate=0.4,
        )


def test_rapid_appraisal_from_stimulus_preserves_provenance() -> None:
    stimulus = Stimulus(
        stimulus_id="stimulus:cli:001",
        source_name="cli",
        modality="text",
        content="hello",
        channel="cli",
        metadata={"user_id": "u1"},
        provenance_signal_id="001",
    )
    salience = RapidSalienceVector(
        threat=0.1,
        reward=0.2,
        novelty=0.3,
        social=0.4,
        uncertainty=0.5,
        aggregate=0.4,
    )

    appraisal = RapidAppraisal.from_stimulus(stimulus, salience)

    assert appraisal.appraisal_id == "rapid-appraisal:stimulus:cli:001"
    assert appraisal.source_name == "cli"
    assert appraisal.provenance_signal_id == "001"
    assert appraisal.salience.aggregate == 0.4


def test_rapid_appraisal_requires_complete_stimulus_provenance() -> None:
    stimulus = Stimulus(
        stimulus_id="",
        source_name="cli",
        modality="text",
        content="hello",
        channel="cli",
        metadata=None,
        provenance_signal_id="001",
    )
    salience = RapidSalienceVector(
        threat=0.0,
        reward=0.0,
        novelty=0.1,
        social=0.0,
        uncertainty=0.2,
        aggregate=0.1,
    )

    with pytest.raises(RapidAppraisalError, match="Stimulus must include complete provenance"):
        RapidAppraisal.from_stimulus(stimulus, salience)


def test_ops_contracts_expose_stable_summary_fields() -> None:
    assess_op = AssessStimulusBatchOp(
        op_name="assess_stimulus_batch",
        owner="rapid_salience_appraisal",
        stimulus_batch_id="stimulus-batch:2:1",
        stimulus_count=2,
        source_names=("body", "cli"),
    )
    publish_op = PublishRapidAppraisalBatchOp(
        op_name="publish_rapid_appraisal_batch",
        owner="rapid_salience_appraisal",
        appraisal_batch_id="rapid-appraisal-batch:2",
        appraisal_count=2,
        source_names=("body", "cli"),
    )

    assert assess_op.op_name == "assess_stimulus_batch"
    assert assess_op.stimulus_count == 2
    assert publish_op.op_name == "publish_rapid_appraisal_batch"
    assert publish_op.appraisal_count == 2


def test_low_salience_appraisal_is_a_valid_output_not_an_error() -> None:
    stimulus = Stimulus(
        stimulus_id="stimulus:body:bg-01",
        source_name="body",
        modality="interoceptive",
        content="baseline",
        channel=None,
        metadata={"kind": "background"},
        provenance_signal_id="bg-01",
    )
    salience = RapidSalienceVector(
        threat=0.01,
        reward=0.01,
        novelty=0.02,
        social=0.0,
        uncertainty=0.03,
        aggregate=0.02,
    )

    appraisal = RapidAppraisal.from_stimulus(stimulus, salience)

    assert appraisal.source_name == "body"
    assert appraisal.salience.aggregate == 0.02
    assert appraisal.salience.uncertainty == 0.03