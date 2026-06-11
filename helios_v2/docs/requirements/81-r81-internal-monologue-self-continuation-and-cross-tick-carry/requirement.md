# Requirement 81 - R81 Internal Monologue Self-Continuation and Cross-Tick Carry

## 1. Background and Problem

R80 closed the **second-order stimulus gap**: the v3 prompt contract (R79-A) lets the LLM
emit `i_want_to_think_more: true` / `think_more_about: "..."` in the JSON envelope, and the
`InternalMonologueSource` re-injects that self-talk output into the `02 → 03 → 04` pipeline
as a stimulus on the next tick. R80's appraisal contribution is novelty 0.3 + uncertainty
0.7 — a real `04` increment, but a one-shot signal: the LLM's rumination intent dissipates
the moment the tick ends.

R80 is also **stateless across process restarts**: the LLM's previous-tick envelope lives
only in the `internal_monologue_carry_provider` lambda supplied at `assemble_runtime` time;
no part of the runtime writes it into the `42` `RuntimeContinuitySnapshot`, so a restart
loses the rumination thread entirely. R80's `R80` deliverable is **first-order** — stimulus
+ appraisal + `04` increment — but the cross-tick **self-continuation** and the cross-restart
**envelope persistence** are deferred to this requirement (R81).

End-to-end R79-D baseline observations (2026-06-11, 4 scenarios × 20 ticks) confirm that
rumination threads are short-lived: the LLM emits `i_want_to_think_more` on 70% of A_praise
ticks, but the signal evaporates at the next stimulus because there is no owner that
**carries** the LLM's prior envelope into the next tick's `09` gate. The
`RuntimeContinuitySnapshot` v3 does not include any LLM-envelope field, and the
`ContinuationPressureState` reason field is still a constant.

## 2. Goals and Non-Goals

### 2.1 Goals

1. **Cross-tick carry of the LLM envelope** — The previous tick's LLM JSON envelope
   (verbatim subset: `what_i_think` + `i_want_to_say` + `i_send_through` +
   `i_want_to_think_more` + `think_more_about` + `i_want_to_act` + `act_type` +
   `remember_this` + `remember_because`) is persisted on the `RuntimeHandle` as
   `_carry_internal_monologue` and made available to the next tick.
2. **`09` self-continuation signal** — A new `self_continuation_signal: float ∈ [0.0, 1.0]`
   field on `ThoughtGateSignalSnapshot`, derived from
   `0.5 * i_want_to_think_more (bool→0/1) + 0.5 * (think_more_about non-empty bool→0/1)`,
   is read by the `09` policy engine as a non-decaying additive gate input. This is the
   first gate input that **survives** between ticks (carried in the snapshot).
3. **`18` source_kind for rumination continuity** — `DeferredContinuityRecord` gains a
   `source_kind: Literal["external_stimulus", "retrieval", "internal_monologue"]` field
   (with a default of `"external_stimulus"` for backward compat). The autonomy owner
   uses this to distinguish rumination continuity (self-originated) from environmental
   continuity (externally-driven) in `proactive_drive_urgency` computation.
4. **`42` checkpoint v4** — `RuntimeContinuitySnapshot` schema bumps to v4 and gains a
   new `internal_monologue: InternalMonologueCarryState | None` field that captures the
   last LLM envelope verbatim subset, so a restarted runtime can resume the rumination
   thread.

### 2.2 Non-Goals

1. **LLM envelope mutation** — R81 carries the envelope verbatim, not reinterpreted
   or summarized. R82 (drift evaluator) is the slice that re-interprets the envelope.
2. **Multi-envelope carry** — Only the most recent envelope is carried. A history of
   envelopes is out of scope.
3. **`14` identity** — The LLM envelope is carried as a `02`-side artifact, not as
   `14` identity state. R81 is not a `14` change.
4. **Cross-session persistence** — The v4 snapshot is in-process + checkpoint-file; no
   database durability beyond what the `42` `CheckpointStoreBackend` already provides.

## 3. Functional Requirements

### 3.1 `RuntimeHandle._carry_internal_monologue`

A new owner-neutral seam in `helios_v2.composition.runtime_assembly` (sibling of
`_carry_recall_directive` and `_carry_temporal`) that:

- Captures the current tick's LLM envelope from the `result.stage_results["internal_thought_path"]`
  payload (or whichever stage the v3 prompt path's `AggressiveRadicalEmbodiedPromptPath`
  writes its post-LLM envelope into). For v1 envelopes, the seam leaves the carry
  unchanged.
- Stores the envelope in a new `RuntimeHandle._internal_monologue_carry` private field
  (`InternalMonologueCarryState` frozen dataclass, see §3.4).
- Reads it on the next tick at the `02` `SensoryIngress._collect_internal_monologue` step
  (or a new `02`-owned ingestion hook), so the LLM envelope influences the next tick's
  stimulus set even without a provider lambda being re-supplied.
- Default carry is empty; the seam is opt-in via `assemble_runtime(internal_monologue_carry_provider=...)`
  already provided by R80, but R81 makes the carry **survive** across ticks without
  requiring the provider to be re-invoked.

### 3.2 `09` `ThoughtGateSignalSnapshot.self_continuation_signal`

A new optional field on `ThoughtGateSignalSnapshot`:

- Field: `self_continuation_signal: float = 0.0` (unit interval, validated by
  `_validate_unit_interval`).
- Default at assembly: `0.0` (no carry → no signal).
- The `09` `evaluate_thought_gate` policy reads the field as a non-decaying additive
  gate input. Specifically, the gate's `selection_pressure` is incremented by
  `policy.self_continuation_weight * self_continuation_signal` where
  `policy.self_continuation_weight: float ∈ [0.0, 1.0]` is a new field on
  `ThoughtGateConfig` (default `0.3`).
- The field is not consumed by the `ContinuationPressureState` evolution (it is a
  *signal*, not a *state*). The carry logic decides when to reset it (on a fire: the
  prior envelope is consumed; on no-fire: the prior envelope persists into the next
  tick's snapshot).

### 3.3 `18` `DeferredContinuityRecord.source_kind`

A new optional field on `DeferredContinuityRecord`:

- Field: `source_kind: Literal["external_stimulus", "retrieval", "internal_monologue"] = "external_stimulus"`.
- Construction validates via `__post_init__` (Literal membership check; raises
  `AutonomyError` on unknown value).
- Existing `18` constructors (R49 / R62 / R70/R78 deferred-continuity emit sites) keep
  their default; new emit sites for rumination continuity use `source_kind="internal_monologue"`.
- The `18` `proactive_drive_urgency` computation reads `source_kind` and applies a
  policy multiplier:
  - `"external_stimulus"` → `1.0` (full urgency)
  - `"retrieval"` → `0.8`
  - `"internal_monologue"` → `0.5` (rumination threads produce less drive than environmental
    ones, by design — R81 chooses `0.5` based on R79-D observation that 70% A_praise
    rumination threads do not produce downstream action).

### 3.4 `42` `RuntimeContinuitySnapshot` v4

A new `InternalMonologueCarryState` contract (in `helios_v2.continuity_checkpoint.contracts`)
with fields:

- `last_envelope: Mapping[str, object] | None` — verbatim subset of the LLM JSON envelope
  (or `None` for the v1 baseline).
- `last_tick_id: int | None` — the tick_id when the envelope was captured.
- `i_want_to_think_more: bool` — convenience projection of `last_envelope["i_want_to_think_more"]`.
- `think_more_about: str` — convenience projection (default `""`).

`RuntimeContinuitySnapshot` schema bumps:

- `SNAPSHOT_VERSION` raises from `3` to `4`.
- New field `internal_monologue: InternalMonologueCarryState | None = None` (added at the
  bottom of the dataclass to preserve default-arg backward compat).
- A loaded payload with `snapshot_version > 4` is **rejected** (R44 precedent:
  forward-incompatible). A payload with `snapshot_version == 3` is **migrated to v4 at
  load-time** by a one-shot `_migrate_v3_to_v4(snapshot) -> RuntimeContinuitySnapshot`
  helper that fills `internal_monologue=None` and bumps the version. A payload with
  `snapshot_version < 3` is rejected (cannot retro-migrate past R43/R44 additions).

### 3.5 `02` `SensoryIngress` re-injection

The `02` owner re-reads the prior tick's `InternalMonologueCarryState` on each tick and
re-registers the `InternalMonologueSource` with a provider that returns the prior envelope
verbatim (instead of re-invoking the `internal_monologue_carry_provider` lambda). This is
the wiring that makes the carry actually reach the next tick's `02 → 03 → 04` pipeline:

- If `_internal_monologue_carry.last_envelope is not None`, the `02` ingestion uses the
  carry as the source content.
- If the carry is empty (`None`), `02` falls back to the user-supplied
  `internal_monologue_carry_provider` (R80 behavior).
- If both are absent, the `02` ingestion contributes zero `internal_monologue` stimuli
  (R80 default).

## 4. Non-Functional Requirements

1. **Performance**: `_carry_internal_monologue` adds at most 1 dict-copy + 1 frozen
   dataclass construct per tick. No new I/O. No new LLM call. No new owner import.
2. **Reliability**: The `_internal_monologue_carry` seam is owner-neutral; it stores the
   envelope verbatim and never re-interprets. A failure to write the carry (e.g. on a
   non-`Mapping` value) raises `CompositionError` at the seam call site, never at the
   `02` ingestion site.
3. **Backward compat**: Default assembly without an R81-aware profile is bit-identical
   to the R80 baseline. The `self_continuation_signal` field defaults to `0.0`; the
   `source_kind` field defaults to `"external_stimulus"`; the `internal_monologue` field
   defaults to `None`. v3 snapshots are migrated to v4 at load-time, never in-place.
4. **Composition owner-boundary guard**: The new `02` re-injection step is wired inside
   the existing `assemble_runtime` `_loose` profile-pass-through; no new owner import is
   introduced. The `composition_owner_boundary_guard` test remains green.

## 5. Acceptance Criteria

1. **R81 unit tests (8)** in `tests/test_r81_internal_monologue_carry.py`:
   - `_carry_internal_monologue` writes the envelope verbatim.
   - `_carry_internal_monologue` survives across ticks (3-tick harness).
   - `ThoughtGateSignalSnapshot` accepts `self_continuation_signal` and validates it.
   - `evaluate_thought_gate` reads the new field and adds to `selection_pressure`.
   - `DeferredContinuityRecord` accepts the new `source_kind` and validates the Literal.
   - `proactive_drive_urgency` applies the source_kind multiplier (0.5 for internal_monologue).
   - `RuntimeContinuitySnapshot` v4 constructor with `internal_monologue` field passes
     the `__post_init__` validation.
   - `_migrate_v3_to_v4` produces a v4 snapshot with `internal_monologue=None`.

2. **Cross-tick e2e harness (1)** in
   `tests/test_r81_internal_monologue_cross_tick_e2e.py`:
   - `assemble_runtime(internal_monologue_carry_provider=mock_provider)` + 3-tick
     `_run_one_tick` cycle asserts that the `02` ingestion on tick 2 includes the prior
     tick's LLM envelope, and the `09` `ThoughtGateSignalSnapshot` for tick 2 has
     `self_continuation_signal >= 0.5` when the prior envelope had `i_want_to_think_more=True`
     (per the §3.2 formula `0.5 * bool + 0.5 * (think_more_about non-empty bool)`,
     `i_want_to_think_more=True` and `think_more_about=""` gives `0.5 * 1.0 + 0.5 * 0.0 = 0.5`).

3. **20-tick real-LLM probe (1)** in
   `helios_v2.tests.r79d.r81_carry_probe`:
   - 20-tick A_praise + rumination probe asserts that the carry persists across ticks
     (carry envelope is non-empty on ticks 2..20) and that the `self_continuation_signal`
     correlates with `i_want_to_think_more_freq`.

4. **Full suite regression**: all 905 pre-R81 tests remain green + 9 new R81 tests = 914
   total. R21 ad-hoc logging guard 1/1 green; composition owner-boundary guard 4/4 green.

5. **No v3 silent migration**: loading a v3 snapshot in an R81-aware runtime emits a
   one-shot `CheckpointMigrationWarning` (logged via `21` observability) and the migrated
   v4 snapshot is logged at `info` level. No silent data loss.

## 6. Owner-Boundary Impact

| Owner | New artifact | Status |
|---|---|---|
| `02` sensory ingress | re-inject prior envelope into `InternalMonologueSource` provider | opt-in via carry |
| `09` thought gating | `ThoughtGateSignalSnapshot.self_continuation_signal` + `ThoughtGateConfig.self_continuation_weight` | additive field |
| `18` autonomy | `DeferredContinuityRecord.source_kind` + `proactive_drive_urgency` multiplier | additive field + multiplier |
| `42` continuity checkpoint | `SNAPSHOT_VERSION = 4` + `InternalMonologueCarryState` + `_migrate_v3_to_v4` | version bump + migration |
| `22` composition | `RuntimeHandle._carry_internal_monologue` seam | new owner-neutral seam |
| `01` runtime kernel | carry logic in `runtime_assembly._run_one_tick` | new step in the per-tick carry chain |

No cognitive owner is modified beyond an additive field; all new logic is owner-neutral
carry glue.

## 7. Sub-Task Plan

- [ ] T0 — Requirement + design + task packages
- [ ] T1 — `RuntimeHandle._carry_internal_monologue` seam + `InternalMonologueCarryState` contract
- [ ] T2 — `assemble_runtime` carry wiring (default `None`, opt-in via existing provider)
- [ ] T3 — `02` `SensoryIngress` re-injection of prior envelope
- [ ] T4 — `09` `ThoughtGateSignalSnapshot.self_continuation_signal` + `evaluate_thought_gate` policy integration
- [ ] T5 — `18` `DeferredContinuityRecord.source_kind` + `proactive_drive_urgency` multiplier
- [ ] T6 — `42` `RuntimeContinuitySnapshot` v4 schema bump + `_migrate_v3_to_v4`
- [ ] T7 — Unit tests (8) + cross-tick e2e harness (1) + 20-tick real-LLM probe (1)
- [ ] T8 — Doc sync: `OWNER_GUIDE.md` + `ARCHITECTURE_BOUNDARIES.md` + `PROGRESS_FLOW.zh-CN.md` + `index.md`
- [ ] T9 — Full suite regression + R21 + composition guard
- [ ] T10 — `git add` + `git commit` on `aggressive-radical-persona-no-theater`

## 8. Test Plan Summary

- **8 unit tests** in `tests/test_r81_internal_monologue_carry.py`
- **1 e2e harness** in `tests/test_r81_internal_monologue_cross_tick_e2e.py`
- **1 20-tick real-LLM probe** at `logs/prompt_probe_scenarios/r81_carry/r81_20tick.{jsonl,report.md}`
- **Full suite 914 passed** (905 R80 baseline + 9 R81 new + 0 regression)
- **R21 ad-hoc logging guard** 1/1 green
- **Composition owner-boundary guard** 4/4 green
