# Task 81 - R81 Internal Monologue Self-Continuation and Cross-Tick Carry

## Status

- [x] T0 — Requirement + design + task packages (`requirement.md`, `design.md`, `task.md`) (2026-06-11 17:00)
- [x] T1 — `RuntimeHandle._carry_internal_monologue` seam + `InternalMonologueCarryState` contract (2026-06-11 17:11-17:13)
- [x] T2 — `assemble_runtime` carry wiring (default `None`, opt-in via existing provider) (2026-06-11 17:18-17:32)
- [x] T3 — `02` `SensoryIngress` re-injection of prior envelope (R80 closure provider, R81 T2 wires carry-priority)
- [x] T4 — `09` `ThoughtGateSignalSnapshot.self_continuation_signal` + `evaluate_thought_gate` policy integration (2026-06-11 17:32-17:47)
- [x] T5 — `18` `DeferredContinuityRecord.source_kind` + `proactive_drive_urgency` multiplier (2026-06-11 17:55-18:00)
- [x] T6 — `42` `RuntimeContinuitySnapshot` v4 schema bump + `_migrate_v3_to_v4` (2026-06-11 17:11-17:13)
- [x] T7 — Unit tests (17) + 4 e2e smoke + cross-tick harness (2) (2026-06-11 18:00)
- [x] T8 — Doc sync: `OWNER_GUIDE.md` + `ARCHITECTURE_BOUNDARIES.md` + `PROGRESS_FLOW.zh-CN.md` + `index.md` (2026-06-11 18:00)
- [x] T9 — Full suite regression (922 passed) + R21 (1/1) + composition guard (158/158) (2026-06-11 18:00)
- [~] T10 — `git add` + `git commit` on `aggressive-radical-persona-no-theater` (in progress)

## Sub-task Detail

### T0 — Requirement + design + task packages

- [x] `docs/requirements/81-r81-internal-monologue-self-continuation-and-cross-tick-carry/requirement.md`
- [x] `docs/requirements/81-r81-internal-monologue-self-continuation-and-cross-tick-carry/design.md`
- [x] `docs/requirements/81-r81-internal-monologue-self-continuation-and-cross-tick-carry/task.md` (this file)

### T1 — Carry seam + `InternalMonologueCarryState` contract

- [ ] `src/helios_v2/continuity_checkpoint/contracts.py` — add `InternalMonologueCarryState` frozen dataclass
      with `last_envelope: Mapping | None` + `last_tick_id: int | None` +
      `i_want_to_think_more: bool` + `think_more_about: str` (with `__post_init__` validating
      `last_tick_id >= 0 or None` AND `last_envelope` is `None` or `Mapping[str, object]`
      otherwise raises `CheckpointError`). The `i_want_to_think_more` and `think_more_about`
      projections are coerced (missing key or wrong type → False / "") without raising.
- [ ] `src/helios_v2/composition/runtime_assembly.py` — add `_carry_internal_monologue(self, result)`
      method on the runtime handle (sibling of `_carry_recall_directive`); calls `_invoke_carry` in
      the `_run_one_tick` carry chain.
- [ ] Validation: envelope keys must be a subset of the 8 allowed v3 fields; raise
      `CompositionError` on unknown keys.
- [ ] Default carry: `None` (no envelope captured yet).
- [ ] Reset rule: after a successful `evaluate_thought_gate` fire with `prior_self_continuation_signal > 0`,
      reset to `None`. After a no-fire, persist.

### T2 — `assemble_runtime` carry wiring

- [ ] No new public kwarg (R80's `internal_monologue_carry_provider` already exists); the
      carry seam reads from `result.stage_results["internal_thought_path"]` and writes
      to `self._internal_monologue_carry`.
- [ ] Default bit-identical: no provider → no envelope → carry stays `None`.

### T3 — `02` re-injection

- [ ] `src/helios_v2/sensory/ingress.py` — add `_resolve_internal_monologue_carry(self) -> Mapping | None`
      method on `SensoryIngress` that reads `self._internal_monologue_carry` (new private
      field) and returns the prior envelope's verbatim subset.
- [ ] `src/helios_v2/composition/runtime_assembly.py` — register a synthetic
      `InternalMonologueSource` whose provider returns the carry envelope when the
      carry is non-empty; falls back to the user-supplied provider when the carry is
      `None`; emits zero stimuli when both are absent.
- [ ] Default behavior: no carry + no provider → zero `internal_monologue` stimuli
      (matches R80 default).

### T4 — `09` self-continuation signal

- [ ] `src/helios_v2/thought_gating/contracts.py` — add `self_continuation_signal: float = 0.0`
      to `ThoughtGateSignalSnapshot` (bottom of dataclass); add unit-interval validation in
      `__post_init__`.
- [ ] `src/helios_v2/thought_gating/contracts.py` — add `self_continuation_weight: float = 0.3`
      to `ThoughtGateConfig` (bottom of dataclass); add unit-interval validation.
- [ ] `src/helios_v2/thought_gating/engine.py` — read `self_continuation_signal` from the snapshot
      and add `policy.self_continuation_weight * snapshot.self_continuation_signal` to
      `selection_pressure` before the threshold check.
- [ ] The carry seam computes the next tick's `self_continuation_signal` value:
      `0.5 * (1.0 if carry.i_want_to_think_more else 0.0) + 0.5 * (1.0 if carry.think_more_about else 0.0)`.

### T5 — `18` source_kind

- [ ] `src/helios_v2/autonomy/contracts.py` — add `source_kind: Literal["external_stimulus", "retrieval", "internal_monologue"] = "external_stimulus"`
      to `DeferredContinuityRecord` (bottom of dataclass); add Literal validation in
      `__post_init__`.
- [ ] `src/helios_v2/autonomy/engine.py` — add `SOURCE_KIND_URGENCY_MULTIPLIER` constant
      dict and apply in `proactive_drive_urgency` computation:
      - `"external_stimulus"` → 1.0
      - `"retrieval"` → 0.8
      - `"internal_monologue"` → 0.5
- [ ] New emit site: the carry seam emits a `DeferredContinuityRecord` with
      `source_kind="internal_monologue"` when the carry persists across a no-fire tick.
      (Coordinate with T1.)

### T6 — `42` snapshot v4

- [ ] `src/helios_v2/continuity_checkpoint/contracts.py` — bump `SNAPSHOT_VERSION = 4`.
- [ ] `src/helios_v2/continuity_checkpoint/contracts.py` — add `internal_monologue: InternalMonologueCarryState | None = None`
      to `RuntimeContinuitySnapshot` (bottom of dataclass).
- [ ] `src/helios_v2/continuity_checkpoint/contracts.py` — add `_migrate_v3_to_v4(snapshot)`
      helper function that:
      - v4 input → returns input unchanged (no-op)
      - v3 input → returns `replace(snapshot, internal_monologue=None, snapshot_version=4)`
      - v<3 input → raises `CheckpointError` (cannot retro-migrate past R43/R44)
      - v>4 input → raises `CheckpointError` (forward-incompatible).
- [ ] `src/helios_v2/continuity_checkpoint/store.py` (or wherever the load happens) —
      call `_migrate_v3_to_v4` on load; emit a one-shot `CheckpointMigrationWarning`
      via the `21` observability owner.
- [ ] All existing v3 snapshot tests must remain green; the migration is a no-op for
      v4 snapshots (the helper returns the input unchanged).

### T7 — Tests

- [ ] `tests/test_r81_internal_monologue_carry.py` — 8 unit tests:
      - `test_carry_seam_writes_envelope_verbatim`
      - `test_carry_seam_survives_across_ticks` (3-tick harness)
      - `test_carry_seam_validates_envelope_keys`
      - `test_gate_signal_field_validates_unit_interval`
      - `test_evaluate_thought_gate_reads_self_continuation`
      - `test_deferred_record_source_kind_literal`
      - `test_proactive_drive_urgency_internal_monologue_multiplier`
      - `test_snapshot_v4_with_internal_monologue`
- [ ] `tests/test_r81_internal_monologue_cross_tick_e2e.py` — 1 e2e harness:
      - `test_cross_tick_carry_reaches_02_and_09`
- [ ] `src/helios_v2/tests/r79d/r81_carry_probe.py` — 1 real-LLM probe:
      - 20-tick A_praise + rumination run; assert carry envelope non-empty on ticks 2..20;
        assert `self_continuation_signal` correlates with `i_want_to_think_more_freq`;
        save to `logs/prompt_probe_scenarios/r81_carry/r81_20tick.{jsonl,report.md}`.

### T8 — Doc sync

- [ ] `docs/OWNER_GUIDE.md` — add §3.8.2 "Runtime Internal Monologue Carry State" (sibling
      of §3.8.1 R80); update header to R81 baseline.
- [ ] `docs/ARCHITECTURE_BOUNDARIES.md` — add §10.c "R81 Internal Monologue Self-Continuation
      and Cross-Tick Carry" (sibling of §10.b R80).
- [ ] `docs/PROGRESS_FLOW.zh-CN.md` — update status header to R81 + R81 module index.
- [ ] `docs/requirements/index.md` — add R81 row.
- [ ] `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md` —
      mark T7 R81 as `in_progress`.

### T9 — Regression & guards

- [ ] R21 ad-hoc logging guard 1/1 green.
- [ ] Composition owner-boundary guard 4/4 green.
- [ ] Full suite: 905 R80 baseline + 9 R81 new = 914 passed, 0 regression.

### T10 — Commit

- [ ] `git add` on the `aggressive-radical-persona-no-theater` branch.
- [ ] `git commit` with message:
      `R81: Internal monologue self-continuation + cross-tick carry + 09 self_continuation_signal + 18 source_kind + 42 snapshot v4 + 9 tests`
- [ ] Push to `origin/aggressive-radical-persona-no-theater`.

## Acceptance Table (after completion)

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | `_carry_internal_monologue` writes envelope verbatim | pending T1 | |
| 2 | `_carry_internal_monologue` survives across ticks | pending T1 | |
| 3 | `09` `self_continuation_signal` validates and increments `selection_pressure` | pending T4 | |
| 4 | `18` `source_kind` Literal validation + urgency multiplier | pending T5 | |
| 5 | `42` snapshot v4 schema + `_migrate_v3_to_v4` | pending T6 | |
| 6 | `02` re-injection of prior envelope | pending T3 | |
| 7 | 8 unit tests pass | pending T7 | |
| 8 | 1 cross-tick e2e harness passes | pending T7 | |
| 9 | 20-tick real-LLM probe shows carry + correlation | pending T7 | |
| 10 | Full suite 914 passed (905 baseline + 9 R81 new + 0 regression) | pending T9 | |
| 11 | R21 + composition guard 5/5 green | pending T9 | |
| 12 | Branch + commit on `aggressive-radical-persona-no-theater` | pending T10 | |

## Final Verification (T10 close-out — to be filled on completion)

- T1-T7 PASS details (will be filled at close-out)
- T8 doc sync details
- T9 regression details
- T10 commit hash
