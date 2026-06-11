"""R80 verification: InternalMonologueSource + InternalMonologueAppraisalEstimator + dispatch.

Owner-neutral unit tests for the R80 second-order stimulus path. Asserts:
- Case 1: InternalMonologueSource emits exactly one RawSignal with the right
  provenance (signal_type='internal_monologue', source_name='internal_monologue',
  signal_id='internal_monologue:active') when the monologue_provider returns a
  non-empty mapping; empty tuple when the provider returns None or empty dict.
- Case 2: 02 sensory normalization preserves `signal_type='internal_monologue'`
  -> `Stimulus.modality='internal_monologue'` and preserves the provenance
  signal_id, with no special-casing in the 02 owner.
- Case 3: InternalMonologueAppraisalEstimator returns the fixed 5-dim vector
  (novelty=0.3, uncertainty=0.7, social=0.0, threat=0.0, reward=0.0) regardless
  of stimulus content.
- Case 4: assemble_runtime without `internal_monologue_carry_provider` is
  bit-identical to the pre-R80 default assembly (no `internal_monologue` source
  registered, no R80 estimator injected into the appraisal engine).
- Case 5: End-to-end assemble_runtime + 1 tick with a non-None
  `internal_monologue_carry_provider` produces a `RapidAppraisalBatch` whose
  `appraisals` tuple contains an `internal_monologue` appraisal with the
  fixed 5-dim vector.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping

ROOT = Path("/root/project/helios/helios_v2")
sys.path.insert(0, str(ROOT / "src"))

from helios_v2.appraisal.r80_internal_monologue import InternalMonologueAppraisalEstimator
from helios_v2.composition import assemble_runtime
from helios_v2.sensory import Stimulus
from helios_v2.sensory.ingress import _normalize_signal
from helios_v2.sensory.internal_monologue import (
    INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID,
    INTERNAL_MONOLOGUE_CHANNEL,
    INTERNAL_MONOLOGUE_SOURCE_NAME,
    InternalMonologueSource,
)


def _static_provider(monologue: Mapping[str, object] | None):
    """Build a zero-arg closure that returns a fixed monologue mapping or None."""

    captured = monologue

    def provider() -> Mapping[str, object] | None:
        return captured

    return provider


def test_r80_internal_monologue_source_emits_internal_monologue_signal() -> None:
    """Case 1: source emits the right RawSignal on a non-empty monologue, empty on None/empty."""

    # 1a) Non-empty monologue -> one RawSignal with the right provenance + content + metadata
    src = InternalMonologueSource(
        monologue_provider=_static_provider(
            {"i_want_to_think_more": True, "think_more_about": "earlier topic"}
        )
    )
    out = src.emit_raw_signals()
    assert len(out) == 1
    s = out[0]
    assert s.signal_id == INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID
    assert s.source_name == INTERNAL_MONOLOGUE_SOURCE_NAME
    assert s.signal_type == "internal_monologue"
    assert s.channel == INTERNAL_MONOLOGUE_CHANNEL
    assert s.required is False
    parsed = json.loads(s.content)
    assert parsed == {
        "i_want_to_think_more": True,
        "think_more_about": "earlier topic",
    }
    # metadata carries the key list for downstream consumers / observability
    assert s.metadata is not None
    assert s.metadata["monologue_keys"] == ("i_want_to_think_more", "think_more_about")

    # 1b) None -> empty tuple (no active monologue this tick)
    src_none = InternalMonologueSource(monologue_provider=_static_provider(None))
    assert src_none.emit_raw_signals() == ()

    # 1c) Empty dict -> empty tuple (no keys, no signal)
    src_empty = InternalMonologueSource(monologue_provider=_static_provider({}))
    assert src_empty.emit_raw_signals() == ()

    # 1d) source_name property is stable
    assert src.source_name == INTERNAL_MONOLOGUE_SOURCE_NAME


def test_r80_internal_monologue_normalization_preserves_modality() -> None:
    """Case 2: 02 sensory normalization preserves signal_type -> modality verbatim."""

    src = InternalMonologueSource(
        monologue_provider=_static_provider(
            {"i_want_to_think_more": True, "think_more_about": "the earlier user message"}
        )
    )
    raw = src.emit_raw_signals()[0]
    stimulus = _normalize_signal(raw)
    # modality is the verbatim signal_type (no special-casing in 02)
    assert stimulus.modality == "internal_monologue"
    # provenance is preserved
    assert stimulus.source_name == INTERNAL_MONOLOGUE_SOURCE_NAME
    assert stimulus.provenance_signal_id == INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID
    assert stimulus.stimulus_id == f"stimulus:{INTERNAL_MONOLOGUE_SOURCE_NAME}:{INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID}"
    # channel is preserved
    assert stimulus.channel == INTERNAL_MONOLOGUE_CHANNEL


def test_r80_internal_monologue_appraisal_returns_fixed_dimensions() -> None:
    """Case 3: estimator returns the hand-authored 5-dim vector regardless of content."""

    est = InternalMonologueAppraisalEstimator()
    # Provide a synthetic internal_monologue stimulus; the estimator is content-independent
    # by design (the dispatch is what filters by modality, not the estimator itself).
    stimulus = Stimulus(
        stimulus_id=f"stimulus:{INTERNAL_MONOLOGUE_SOURCE_NAME}:synthetic",
        source_name=INTERNAL_MONOLOGUE_SOURCE_NAME,
        modality="internal_monologue",
        content='{"i_want_to_think_more": true}',
        channel=INTERNAL_MONOLOGUE_CHANNEL,
        metadata={"monologue_keys": ("i_want_to_think_more",)},
        provenance_signal_id=INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID,
    )
    d = est.estimate_dimensions(stimulus)
    assert d.threat == 0.0
    assert d.reward == 0.0
    assert d.novelty == 0.3
    assert d.social == 0.0
    assert d.uncertainty == 0.7

    # Custom-override: the constants are fields, not hardcoded, so callers can tune
    # them in tests (R80 design §2.2; a future P5 / R81 slice can do this for real).
    custom = InternalMonologueAppraisalEstimator(
        novelty=0.5, uncertainty=0.4, threat=0.1, reward=0.05, social=0.0
    )
    d2 = custom.estimate_dimensions(stimulus)
    assert d2.novelty == 0.5
    assert d2.uncertainty == 0.4
    assert d2.threat == 0.1
    assert d2.reward == 0.05
    assert d2.social == 0.0


def test_r80_internal_monologue_no_provider_no_source() -> None:
    """Case 4: bit-identical default assembly when no internal_monologue_carry_provider is set."""

    handle = assemble_runtime(deterministic_thought=True)
    # No internal_monologue source registered
    assert "internal_monologue" not in handle.ingress._sources
    # Only the baseline source is present (cli)
    assert list(handle.ingress._sources.keys()) == ["cli"]


def test_r80_internal_monologue_end_to_end_tick_produces_appraisal() -> None:
    """Case 5: 1-tick end-to-end run with a non-None provider produces an internal_monologue appraisal."""

    def active_monologue() -> Mapping[str, object]:
        return {"i_want_to_think_more": True, "think_more_about": "the earlier user message"}

    handle = assemble_runtime(
        deterministic_thought=True,
        internal_monologue_carry_provider=active_monologue,
    )
    # Source is registered
    assert "internal_monologue" in handle.ingress._sources

    # One tick: the sensory stage emits a StimulusBatch containing the internal_monologue
    # stimulus, and the rapid_salience_appraisal stage routes it through the R80 estimator.
    result = handle.tick()
    appraisal_result = result.stage_results["rapid_salience_appraisal"]
    appraisals = appraisal_result.batch.appraisals

    # Find the internal_monologue appraisal (there may also be a baseline cli appraisal
    # if the deterministic thought profile registers one; we only assert the R80 appraisal).
    im_appraisals = [a for a in appraisals if a.source_name == INTERNAL_MONOLOGUE_SOURCE_NAME]
    assert len(im_appraisals) == 1, (
        f"expected exactly 1 internal_monologue appraisal, got {len(im_appraisals)}: "
        f"source_names={[a.source_name for a in appraisals]}"
    )
    a = im_appraisals[0]
    assert a.salience.threat == 0.0
    assert a.salience.reward == 0.0
    assert a.salience.novelty == 0.3
    assert a.salience.social == 0.0
    assert a.salience.uncertainty == 0.7
    # Provenance is preserved through normalization + appraisal
    assert a.provenance_signal_id == INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID
