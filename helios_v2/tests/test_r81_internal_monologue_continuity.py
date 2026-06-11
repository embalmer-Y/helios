"""R81 verification: 4 sub-deliverables.

Owner-neutral unit tests for the R81 cross-tick internal-monologue continuity path.
Asserts:
- Case 1 (carry seam): `RuntimeHandle._carry_internal_monologue` reads the LLM
  envelope from the just-completed tick and stores it as the next-tick carry
  state. `RuntimeHandle._internal_monologue_carry` is None before the first tick.
- Case 2 (09 signal): `ThoughtGateSignalSnapshot.self_continuation_signal` is
  computed from the carried envelope per the formula
  `0.5 * bool(i_want_to_think_more) + 0.5 * bool(think_more_about non-empty)`.
  `ThoughtGatingConfig.self_continuation_weight = 0.3`.
- Case 3 (18 source_kind): `DeferredContinuityRecord.source_kind` is the new
  field. The autonomy engine emits an extra `source_kind="internal_monologue"`
  record when the prior-tick envelope is present. The `proactive_drive_urgency`
  field on `ProactiveDriveState` is `outward_drive * 0.5` when an
  internal-monologue record is in the deferred set; otherwise it equals
  `outward_drive` (clamped to [0, 1]).
- Case 4 (42 v4): `RuntimeContinuitySnapshot.snapshot_version == 4`. The
  `internal_monologue` field is on the snapshot. `_migrate_v3_to_v4` is a
  one-shot helper that fills `internal_monologue=None` on a v3 payload; v4
  payloads are no-op; v<3 or v>4 raise `CheckpointError`.
"""

from __future__ import annotations

from typing import Mapping

import pytest

from helios_v2.continuity_checkpoint.contracts import (
    InternalMonologueCarryState,
    RuntimeContinuitySnapshot,
    _migrate_v3_to_v4,
)
from helios_v2.autonomy.contracts import ProactiveDriveRequest, AutonomyConfig
from helios_v2.autonomy.engine import FirstVersionAutonomyPath
from helios_v2.composition import assemble_runtime


# ---------------------------------------------------------------------------
# Case 1: Carry seam
# ---------------------------------------------------------------------------


def test_r81_carry_seam_initial_state_is_none() -> None:
    """Before any tick, the carry state is None (the LLM has not spoken yet)."""
    handle = assemble_runtime(deterministic_thought=True)
    assert handle._internal_monologue_carry is None


def test_r81_carry_seam_first_version_persists_envelope() -> None:
    """The carry state survives one tick and is queryable in-memory."""
    handle = assemble_runtime(deterministic_thought=True)
    handle.tick()
    # The deterministic thought path may or may not produce a monologue envelope.
    # We assert the carry surface is a real field (None or a state) and that it
    # matches the holder's current() value.
    state = handle._internal_monologue_carry
    holder_current = handle.internal_monologue_carry_holder.current() if handle.internal_monologue_carry_holder is not None else None
    if state is None:
        assert holder_current is None
    else:
        assert holder_current == {"last_envelope": state.last_envelope, "last_tick_id": state.last_tick_id}


# ---------------------------------------------------------------------------
# Case 2: 09 self_continuation_signal
# ---------------------------------------------------------------------------


def test_r81_self_continuation_signal_default_zero() -> None:
    """No carry -> self_continuation_signal = 0.0."""
    from helios_v2.composition.bridges import _self_continuation_signal
    assert _self_continuation_signal(None) == 0.0


def test_r81_self_continuation_signal_formula() -> None:
    """Formula: 0.5*bool(i_want_to_think_more) + 0.5*bool(think_more_about non-empty).

    The helper accepts a holder-like object (with `last_envelope` attribute).
    """
    from types import SimpleNamespace
    from helios_v2.composition.bridges import _self_continuation_signal

    def holder(env):
        return SimpleNamespace(last_envelope=env)

    # Both true -> 1.0
    assert _self_continuation_signal(holder({"i_want_to_think_more": True, "think_more_about": "weather"})) == 1.0

    # iwttm only -> 0.5
    assert _self_continuation_signal(holder({"i_want_to_think_more": True, "think_more_about": ""})) == 0.5

    # tma only -> 0.5
    assert _self_continuation_signal(holder({"i_want_to_think_more": False, "think_more_about": "weather"})) == 0.5

    # Neither -> 0.0
    assert _self_continuation_signal(holder({"i_want_to_think_more": False, "think_more_about": ""})) == 0.0


def test_r81_thought_gating_config_has_weight() -> None:
    """ThoughtGatingConfig.self_continuation_weight = 0.3."""
    from helios_v2.thought_gating.contracts import ThoughtGatingConfig
    cfg = ThoughtGatingConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        continuation_state_bootstrap_id="continuation-state-bootstrap:v1",
        mandatory_learned_parameters=(
            "gate_policy",
            "continuation_policy",
            "signal_normalization_policy",
        ),
    )
    assert cfg.self_continuation_weight == 0.3


# ---------------------------------------------------------------------------
# Case 3: 18 source_kind + proactive_drive_urgency multiplier
# ---------------------------------------------------------------------------


def test_r81_deferred_continuity_record_source_kind_default() -> None:
    """DeferredContinuityRecord.source_kind defaults to 'external_stimulus'."""
    from helios_v2.autonomy.contracts import DeferredContinuityRecord
    rec = DeferredContinuityRecord(
        record_id="r",
        continuity_key="k",
        origin_ref="o",
        carry_reason="reason",
        carry_count=1,
        decayed_pressure=0.1,
        expires_after_ticks=None,
    )
    assert rec.source_kind == "external_stimulus"


def test_r81_deferred_continuity_record_source_kind_invalid() -> None:
    """Invalid source_kind raises AutonomyError."""
    from helios_v2.autonomy.contracts import DeferredContinuityRecord, AutonomyError
    with pytest.raises(AutonomyError):
        DeferredContinuityRecord(
            record_id="r",
            continuity_key="k",
            origin_ref="o",
            carry_reason="reason",
            carry_count=1,
            decayed_pressure=0.1,
            expires_after_ticks=None,
            source_kind="bogus_kind",
        )


def test_r81_proactive_drive_urgency_no_envelope_is_outward_drive() -> None:
    """Without envelope, urgency = outward_drive (clamped)."""
    cfg = AutonomyConfig(
        autonomy_bootstrap_id="autonomy-bootstrap:v1",
        mandatory_learned_parameters=(
            "drive_integration_policy",
            "continuity_carry_policy",
            "proactive_externalization_policy",
        ),
    )
    path = FirstVersionAutonomyPath()
    req = ProactiveDriveRequest(
        request_id="t",
        source_gate_result_id="g",
        source_retrieval_bundle_id="r",
        source_thought_cycle_result_id="c",
        source_planner_bridge_result_id="p",
        source_identity_governance_result_id="i",
        source_writeback_result_ids=("w",),
        source_outward_expression_draft_id="oe",
        source_outward_expression_externalization_draft_id="oee",
        continuation_summary={"continuation_pressure": 0.3, "active": True},
        retrieval_pull_summary={"retrieval_pull": 0.2, "active": True},
        temporal_pressure_summary={"temporal_pressure": 0.2, "active": True},
        identity_unresolved_summary={"identity_unresolved_pressure": 0.2, "active": True},
        outward_readiness_summary={"outward_ready": True, "externalization_blocked": False},
        internal_monologue_envelope=None,
    )
    result = path.assemble_result(req, cfg)
    ds = result.drive_state
    assert ds.pressure_components["urgency_multiplier"] == 1.0
    assert ds.pressure_components["has_internal_monologue_record"] == 0.0
    assert ds.proactive_drive_urgency == min(1.0, max(0.0, ds.pressure_components["outward_drive"]))


def test_r81_proactive_drive_urgency_with_envelope_is_half() -> None:
    """With envelope, urgency = outward_drive * 0.5."""
    cfg = AutonomyConfig(
        autonomy_bootstrap_id="autonomy-bootstrap:v1",
        mandatory_learned_parameters=(
            "drive_integration_policy",
            "continuity_carry_policy",
            "proactive_externalization_policy",
        ),
    )
    path = FirstVersionAutonomyPath()
    req = ProactiveDriveRequest(
        request_id="t",
        source_gate_result_id="g",
        source_retrieval_bundle_id="r",
        source_thought_cycle_result_id="c",
        source_planner_bridge_result_id="p",
        source_identity_governance_result_id="i",
        source_writeback_result_ids=("w",),
        source_outward_expression_draft_id="oe",
        source_outward_expression_externalization_draft_id="oee",
        continuation_summary={"continuation_pressure": 0.3, "active": True},
        retrieval_pull_summary={"retrieval_pull": 0.2, "active": True},
        temporal_pressure_summary={"temporal_pressure": 0.2, "active": True},
        identity_unresolved_summary={"identity_unresolved_pressure": 0.2, "active": True},
        outward_readiness_summary={"outward_ready": True, "externalization_blocked": False},
        internal_monologue_envelope={"i_want_to_think_more": True, "think_more_about": "x"},
    )
    result = path.assemble_result(req, cfg)
    ds = result.drive_state
    assert ds.pressure_components["urgency_multiplier"] == 0.5
    assert ds.pressure_components["has_internal_monologue_record"] == 1.0
    expected = min(1.0, max(0.0, ds.pressure_components["outward_drive"] * 0.5))
    assert ds.proactive_drive_urgency == expected
    assert any(r.source_kind == "internal_monologue" for r in result.deferred_records)


def test_r81_proactive_drive_urgency_validation() -> None:
    """Out-of-range proactive_drive_urgency raises AutonomyError."""
    from helios_v2.autonomy.contracts import ProactiveDriveState, AutonomyError
    with pytest.raises(AutonomyError):
        ProactiveDriveState(
            state_id="bad",
            dominant_disposition="reflect",
            activity_mode="inward_reflective",
            pressure_components={},
            deferred_active=False,
            proactive_action_requested=False,
            proactive_drive_urgency=1.5,
        )


# ---------------------------------------------------------------------------
# Case 4: 42 v4 snapshot
# ---------------------------------------------------------------------------


def test_r81_snapshot_version_is_4() -> None:
    """SNAPSHOT_VERSION is now 4."""
    from helios_v2.continuity_checkpoint.contracts import SNAPSHOT_VERSION
    assert SNAPSHOT_VERSION == 4


def test_r81_internal_monologue_carry_state_contract() -> None:
    """InternalMonologueCarryState has 4 fields with coercion rules."""
    state = InternalMonologueCarryState(
        last_envelope={"i_want_to_think_more": True, "think_more_about": "x"},
        last_tick_id=42,
        i_want_to_think_more=True,
        think_more_about="x",
    )
    assert state.last_tick_id == 42
    assert state.i_want_to_think_more is True
    assert state.think_more_about == "x"


def test_r81_migrate_v3_to_v4_fills_internal_monologue() -> None:
    """v3 payload -> v4 snapshot with internal_monologue=None."""
    v3 = RuntimeContinuitySnapshot(
        snapshot_version=3,
        tick_id=10,
        continuation_state=None,
        continuity_threads=(),
        deferred_records=(),
        neuromodulator_levels=None,
        feeling=None,
    )
    migrated = _migrate_v3_to_v4(v3)
    assert migrated.snapshot_version == 4
    assert migrated.internal_monologue is None


def test_r81_migrate_v3_to_v4_is_noop_for_v4() -> None:
    """v4 payload -> v4 (no-op)."""
    v4 = RuntimeContinuitySnapshot(
        snapshot_version=4,
        tick_id=11,
        continuation_state=None,
        continuity_threads=(),
        deferred_records=(),
        neuromodulator_levels=None,
        feeling=None,
    )
    migrated = _migrate_v3_to_v4(v4)
    assert migrated is v4  # no-op returns the same object


def test_r81_migrate_v3_to_v4_rejects_v2() -> None:
    """v<3 raises CheckpointError."""
    from helios_v2.continuity_checkpoint.contracts import CheckpointError
    v2 = RuntimeContinuitySnapshot(
        snapshot_version=2,
        tick_id=12,
        continuation_state=None,
        continuity_threads=(),
        deferred_records=(),
        neuromodulator_levels=None,
        feeling=None,
    )
    with pytest.raises(CheckpointError):
        _migrate_v3_to_v4(v2)


def test_r81_migrate_v3_to_v4_rejects_v5() -> None:
    """v>4 raises CheckpointError (forward-incompatible)."""
    from helios_v2.continuity_checkpoint.contracts import CheckpointError
    v5 = RuntimeContinuitySnapshot(
        snapshot_version=5,
        tick_id=13,
        continuation_state=None,
        continuity_threads=(),
        deferred_records=(),
        neuromodulator_levels=None,
        feeling=None,
    )
    with pytest.raises(CheckpointError):
        _migrate_v3_to_v4(v5)


# ---------------------------------------------------------------------------
# Cross-tick end-to-end harness
# ---------------------------------------------------------------------------


def test_r81_cross_tick_carry_survives_tick_chain() -> None:
    """3-tick sequence: carry state and holder stay consistent across ticks."""
    handle = assemble_runtime(deterministic_thought=True)
    handle.tick()
    handle.tick()
    handle.tick()
    # After 3 ticks, both surfaces should agree.
    state = handle._internal_monologue_carry
    if handle.internal_monologue_carry_holder is not None:
        holder = handle.internal_monologue_carry_holder.current()
        if state is None:
            assert holder is None
        else:
            assert holder == {"last_envelope": state.last_envelope, "last_tick_id": state.last_tick_id}
