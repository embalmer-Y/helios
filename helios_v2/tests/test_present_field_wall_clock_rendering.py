"""R92: tests for the present-field `last input: X.Xs ago` clause.

Asserts:
  - With `frame.tick_wall_seconds` and at least one rendered stimulus's `received_at_wall`,
    the helper produces a `last input: X.Xs ago` clause appended after the stimuli/focal
    clauses but BEFORE the `pacing:` clause.
  - With either side absent, the clause is omitted (the existing R91 behavior is unchanged).
  - When two external stimuli arrived at different times, the EARLIEST stamp drives the
    elapsed value (the prompt reads "the message arrived X.X seconds ago", not "the most
    recent metadata stamp").
  - An NTP-rewind (frame.tick_wall_seconds < earliest received_at) clamps to `0.0s ago`
    rather than producing a negative number.
  - Internal-modality stimuli (`body` / `interoceptive` / `background`) are not eligible to
    contribute their `received_at_wall` to the elapsed clause, mirroring the R91 stimuli
    filter.
  - The pacing clause continues to render side-by-side with the elapsed clause when both
    sources are present.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.composition.bridges import (
    _present_field_elapsed_clause,
    _present_field_summary_text,
)
from helios_v2.runtime.contracts import RuntimeFrame
from helios_v2.runtime.stages import SensoryIngressStageResult
from helios_v2.sensory.contracts import Stimulus, StimulusBatch
from helios_v2.temporal import TemporalPacingSample, TemporalSource
from helios_v2.wall_clock import RECEIVED_AT_WALL_METADATA_KEY


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------


def _stimulus(
    *,
    stim_id: str,
    modality: str,
    source: str,
    content: str,
    received_at: float | None = None,
) -> Stimulus:
    metadata: dict[str, object] = {}
    if received_at is not None:
        metadata[RECEIVED_AT_WALL_METADATA_KEY] = received_at
    return Stimulus(
        stimulus_id=stim_id,
        source_name=source,
        modality=modality,
        content=content,
        channel="cli" if modality == "cli" else None,
        metadata=metadata or None,
        provenance_signal_id=f"signal:{stim_id}",
    )


def _frame(
    *stimuli: Stimulus,
    tick_wall_seconds: float | None,
) -> RuntimeFrame:
    batch = StimulusBatch(batch_id="batch:r92", stimuli=stimuli)
    return RuntimeFrame(
        tick_id=1,
        stage_results={
            "sensory_ingress": SensoryIngressStageResult(batch=batch, publish_op=None)
        },
        tick_wall_seconds=tick_wall_seconds,
    )


@dataclass
class _StubTemporalSource(TemporalSource):
    signal: float = 0.4

    def sample(self, external_stimulus_present: bool) -> TemporalPacingSample:
        return TemporalPacingSample(temporal_signal=self.signal, dmn_available=True)

    def observe_tick(self, fired: bool) -> None:
        return None


# ---------------------------------------------------------------------------
# _present_field_elapsed_clause directly
# ---------------------------------------------------------------------------


def test_elapsed_clause_renders_when_both_ends_present() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="operator", content="hello", received_at=10.0),
        tick_wall_seconds=13.0,
    )
    assert _present_field_elapsed_clause(frame) == "last input: 3.0s ago"


def test_elapsed_clause_omits_when_no_tick_wall_seconds() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="operator", content="hello", received_at=10.0),
        tick_wall_seconds=None,
    )
    assert _present_field_elapsed_clause(frame) is None


def test_elapsed_clause_omits_when_no_received_at_wall_on_any_stimulus() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="operator", content="hello", received_at=None),
        tick_wall_seconds=13.0,
    )
    assert _present_field_elapsed_clause(frame) is None


def test_elapsed_clause_omits_when_no_sensory_stage_result() -> None:
    frame = RuntimeFrame(tick_id=1, stage_results={}, tick_wall_seconds=13.0)
    assert _present_field_elapsed_clause(frame) is None


def test_elapsed_clause_uses_earliest_stamp_among_stimuli() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="op1", content="hi", received_at=20.0),
        _stimulus(stim_id="b", modality="cli", source="op2", content="yo", received_at=10.0),
        _stimulus(stim_id="c", modality="cli", source="op3", content="hey", received_at=15.0),
        tick_wall_seconds=30.0,
    )
    # Earliest is 10.0; elapsed = 30 - 10 = 20.0s
    assert _present_field_elapsed_clause(frame) == "last input: 20.0s ago"


def test_elapsed_clause_clamps_negative_delta_to_zero() -> None:
    """If the wall-clock rewinds (NTP correction), elapsed must be 0.0, never negative."""
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="op", content="hi", received_at=20.0),
        tick_wall_seconds=15.0,  # earlier than received_at
    )
    assert _present_field_elapsed_clause(frame) == "last input: 0.0s ago"


def test_elapsed_clause_ignores_internal_modality_stamps() -> None:
    """Interoceptive/body/background stimuli should not contribute their stamp; even if they
    have a `received_at_wall`, only external stimuli count for "last input"."""
    frame = _frame(
        _stimulus(stim_id="body1", modality="body", source="heart", content="heartbeat", received_at=5.0),
        _stimulus(stim_id="ext1", modality="cli", source="op", content="hello", received_at=20.0),
        tick_wall_seconds=30.0,
    )
    # Body stimulus's 5.0 must be ignored; earliest external is 20.0; elapsed = 30 - 20 = 10.0
    assert _present_field_elapsed_clause(frame) == "last input: 10.0s ago"


def test_elapsed_clause_ignores_stimulus_without_stamp() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="op1", content="no stamp", received_at=None),
        _stimulus(stim_id="b", modality="cli", source="op2", content="stamped", received_at=25.0),
        tick_wall_seconds=30.0,
    )
    # Only the stamped one contributes; elapsed = 30 - 25 = 5.0
    assert _present_field_elapsed_clause(frame) == "last input: 5.0s ago"


def test_elapsed_clause_ignores_non_numeric_metadata_value() -> None:
    """Defensive: a malformed metadata value is treated as absent (not crashing)."""
    bad_stimulus = Stimulus(
        stimulus_id="bad",
        source_name="op",
        modality="cli",
        content="hi",
        channel="cli",
        metadata={RECEIVED_AT_WALL_METADATA_KEY: "ten o'clock"},
        provenance_signal_id="signal:bad",
    )
    frame = _frame(bad_stimulus, tick_wall_seconds=30.0)
    assert _present_field_elapsed_clause(frame) is None


# ---------------------------------------------------------------------------
# _present_field_summary_text composition
# ---------------------------------------------------------------------------


def test_summary_includes_elapsed_clause_when_present() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="cli", content="家里现在静得让我害怕", received_at=10.0),
        tick_wall_seconds=14.5,
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    # The stimulus clause comes first, then the elapsed clause; no temporal clause when no source.
    assert 'cli via cli said: "家里现在静得让我害怕"' in text
    assert "last input: 4.5s ago" in text
    assert "pacing:" not in text


def test_summary_renders_pacing_independently_of_elapsed() -> None:
    """Both clauses can coexist: real elapsed seconds + unitless rest pacing."""
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="cli", content="hello", received_at=10.0),
        tick_wall_seconds=13.0,
    )
    text = _present_field_summary_text(frame, temporal_source=_StubTemporalSource(signal=0.6))
    assert text is not None
    assert "last input: 3.0s ago" in text
    assert "pacing: 0.6" in text
    # Order: stimuli; (focal omitted, no 08 in this frame); last input; pacing
    assert text.index("last input:") < text.index("pacing:")


def test_summary_omits_elapsed_when_only_pacing_available() -> None:
    """No wall-clock + pacing source => `pacing:` only, no elapsed clause."""
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="cli", content="hello", received_at=None),
        tick_wall_seconds=None,
    )
    text = _present_field_summary_text(frame, temporal_source=_StubTemporalSource(signal=0.4))
    assert text is not None
    assert "last input:" not in text
    assert "pacing: 0.4" in text


def test_summary_renders_only_elapsed_when_no_temporal() -> None:
    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="cli", content="hello", received_at=10.0),
        tick_wall_seconds=12.0,
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    assert "last input: 2.0s ago" in text
    assert "pacing:" not in text


def test_summary_byte_for_byte_unchanged_when_no_clock_no_temporal() -> None:
    """The R91 default (no wall-clock, no temporal) must continue producing the legacy clause set
    only — i.e. just the stimuli clause for this fixture."""

    frame = _frame(
        _stimulus(stim_id="a", modality="cli", source="cli", content="hello", received_at=None),
        tick_wall_seconds=None,
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text == 'cli via cli said: "hello"'


def test_summary_returns_none_when_everything_absent() -> None:
    """No external stimulus, no `08`, no wall-clock, no temporal => None (honest absence)."""
    frame = RuntimeFrame(tick_id=1, stage_results={}, tick_wall_seconds=None)
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is None
