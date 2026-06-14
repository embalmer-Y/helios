"""R93: focused tests for the composition-side `_current_operator_id(frame)` helper and the
`current_operator_id` key on the `prompt_contract_summary` of both internal-thought
request bridges.

Asserts:
  - The earliest external stimulus's `source_name` wins.
  - Internal-modality stimuli (`body` / `interoceptive` / `background`) are skipped — they
    never become a "speaker" reply target (mirrors the R91 / R92 filter).
  - Empty stimuli content is skipped.
  - Empty `source_name` on a candidate is skipped (continues looking down the list).
  - Returns `""` when no `02` stage result is published (honest absence).
  - Returns `""` when only internal stimuli are present.
"""

from __future__ import annotations

from helios_v2.composition.bridges import _current_operator_id
from helios_v2.runtime.contracts import RuntimeFrame
from helios_v2.runtime.stages import SensoryIngressStageResult
from helios_v2.sensory.contracts import Stimulus, StimulusBatch


def _stimulus(*, stim_id: str, modality: str, source: str, content: str) -> Stimulus:
    return Stimulus(
        stimulus_id=stim_id,
        source_name=source,
        modality=modality,
        content=content,
        channel="cli" if modality == "cli" else None,
        metadata=None,
        provenance_signal_id=f"signal:{stim_id}",
    )


def _frame(*stimuli: Stimulus) -> RuntimeFrame:
    batch = StimulusBatch(batch_id="batch:r93", stimuli=stimuli)
    return RuntimeFrame(
        tick_id=1,
        stage_results={
            "sensory_ingress": SensoryIngressStageResult(batch=batch, publish_op=None)
        },
    )


# ---------------------------------------------------------------------------
# Earliest external stimulus's source_name wins
# ---------------------------------------------------------------------------


def test_earliest_external_stimulus_source_name_wins() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="operator-a", content="first"),
        _stimulus(stim_id="b", modality="cli", source="operator-b", content="second"),
    )
    assert _current_operator_id(frame) == "operator-a"


def test_single_external_stimulus_source_name_returned() -> None:
    frame = _frame(_stimulus(stim_id="a", modality="cli", source="cli", content="hello"))
    assert _current_operator_id(frame) == "cli"


# ---------------------------------------------------------------------------
# Internal-modality stimuli are skipped (mirrors R91 / R92 filter)
# ---------------------------------------------------------------------------


def test_internal_modality_stimuli_are_skipped() -> None:
    """A body/interoceptive stimulus must not become a "speaker" reply target."""
    frame = _frame(
        _stimulus(stim_id="bod", modality="body", source="heart", content="heartbeat"),
        _stimulus(stim_id="ext", modality="cli", source="cli-operator", content="hello"),
    )
    assert _current_operator_id(frame) == "cli-operator"


def test_only_internal_stimuli_yields_empty() -> None:
    frame = _frame(
        _stimulus(stim_id="bod", modality="body", source="heart", content="heartbeat"),
        _stimulus(stim_id="bg", modality="background", source="ambient", content="hum"),
    )
    assert _current_operator_id(frame) == ""


def test_interoceptive_modality_is_skipped() -> None:
    frame = _frame(
        _stimulus(stim_id="i1", modality="interoceptive", source="cpu", content="pressure"),
        _stimulus(stim_id="ext", modality="cli", source="real-op", content="ok"),
    )
    assert _current_operator_id(frame) == "real-op"


# ---------------------------------------------------------------------------
# Empty content / empty source_name skipped
# ---------------------------------------------------------------------------


def test_empty_content_stimuli_are_skipped() -> None:
    frame = _frame(
        _stimulus(stim_id="empty", modality="cli", source="early-op", content=""),
        _stimulus(stim_id="real", modality="cli", source="late-op", content="content"),
    )
    assert _current_operator_id(frame) == "late-op"


def test_empty_source_name_continues_looking() -> None:
    """If the first external stimulus has an empty source_name, the helper continues looking
    rather than returning empty (honest fall-through)."""
    frame = _frame(
        _stimulus(stim_id="anon", modality="cli", source="", content="anonymous content"),
        _stimulus(stim_id="real", modality="cli", source="known-op", content="content"),
    )
    assert _current_operator_id(frame) == "known-op"


# ---------------------------------------------------------------------------
# Honest absence
# ---------------------------------------------------------------------------


def test_no_sensory_stage_result_returns_empty() -> None:
    frame = RuntimeFrame(tick_id=1, stage_results={})
    assert _current_operator_id(frame) == ""


def test_empty_stimulus_batch_returns_empty() -> None:
    frame = _frame()  # no stimuli
    assert _current_operator_id(frame) == ""


# ---------------------------------------------------------------------------
# Both bridges add `current_operator_id` to prompt_contract_summary
# ---------------------------------------------------------------------------


def test_both_request_bridges_include_current_operator_id_key() -> None:
    """A static-import audit confirming the cross-file rule that both internal-thought
    request bridges add the `current_operator_id` key into their summary dict. This is the
    contract that lets `11` `_emit_proposal` read the operator id from the request without
    importing `02`."""
    import inspect

    from helios_v2.composition.bridges import (
        FirstVersionInternalThoughtRequestBridge,
        SemanticInternalThoughtRequestBridge,
    )

    for bridge_cls in (
        FirstVersionInternalThoughtRequestBridge,
        SemanticInternalThoughtRequestBridge,
    ):
        source = inspect.getsource(bridge_cls)
        assert "current_operator_id" in source, (
            f"{bridge_cls.__name__} must include 'current_operator_id' in its "
            "prompt_contract_summary so `11` can read it as the implicit-reply target."
        )
        assert "_current_operator_id" in source, (
            f"{bridge_cls.__name__} must call `_current_operator_id(frame)` to project "
            "the value owner-neutrally."
        )
