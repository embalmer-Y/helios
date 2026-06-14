# Requirement 92 - Wall-Clock Real Timestamps — Task

## 1. Task Breakdown

R92 is decomposed into nine ordered slices. Each slice lands as a self-contained
commit (or a small group of commits) with its own focused validation. The owner
package is created first; consumption points wire up one at a time; documentation
sync closes the change set.

### T1 — `helios_v2.wall_clock` owner package

Create the contracts, protocol, and two implementations. No consumer is touched in
this slice.

- New: `src/helios_v2/wall_clock/__init__.py`, `contracts.py`, `engine.py`.
- Defines: `WallClockError`, `WallClockReading` (validates finite + non-negative),
  `WallClock` protocol, `RECEIVED_AT_WALL_METADATA_KEY` reserved key,
  `SystemWallClock`, `FixedWallClock` (auto-advance + sequence + `manual_advance`).
- New test: `tests/test_wall_clock_contracts.py` (≈ 8–10 cases).
- Validation: `pytest tests/test_wall_clock_contracts.py -q` is green.

### T2 — `RuntimeFrame.tick_wall_seconds` + kernel seeding

Add the additive optional field on `RuntimeFrame` and have the kernel seed it once
per tick from an injected `WallClock`. Add `tick_wall_seconds` to
`RuntimeTickResult`.

- Modified: `src/helios_v2/runtime/contracts.py`,
  `src/helios_v2/runtime/kernel.py`.
- Default behavior unchanged: with no clock injected, every frame carries
  `tick_wall_seconds=None`.
- New test: `tests/test_runtime_frame_wall_clock.py` (≈ 5 cases).
- Validation: existing `tests/test_runtime_kernel*.py` stay green;
  `pytest tests/test_runtime_frame_wall_clock.py tests/test_runtime_kernel*.py -q`.

### T3 — CLI driver `submit_line` arrival stamp

Make `CliChannelDriver` accept an optional `wall_clock` and stamp
`received_at_wall` in the inbound packet's metadata at `submit_line` time. Backlog
becomes `deque[tuple[str, float | None]]`.

- Modified: `src/helios_v2/channel/drivers/cli.py`.
- Default behavior unchanged: with no clock injected, no metadata key is added.
- New test: `tests/test_cli_driver_wall_clock_stamp.py` (≈ 5 cases including
  arrival-vs-drain timing).
- Validation: existing `tests/test_channel_*` stay green;
  `pytest tests/test_cli_*.py tests/test_channel_*.py -q`.

### T4 — `RuntimeProfile.wall_clock` + assembly threading

Add `wall_clock` to `RuntimeProfile` and the loose-kwarg surface on
`assemble_runtime`. Thread one resolved instance into kernel, CLI driver (when
channel-bound), and the runtime handle. Add `wall_clock=SystemWallClock()` as the
default in `assemble_production_runtime`.

- Modified: `src/helios_v2/composition/runtime_assembly.py`.
- Includes: `_RUNTIME_PROFILE_FIELD_NAMES` extended with `"wall_clock"`; conflict
  detection routes `wall_clock` through the existing `_resolve_profile` rule.
- New test: `tests/test_assemble_runtime_wall_clock_profile.py` (≈ 6 cases:
  default-off, kwarg, profile, both-raise, identity threading,
  `assemble_production_runtime` default).
- Validation: existing `tests/test_runtime_assembly*.py`,
  `tests/test_composition_*.py` stay green.

### T5 — Present-field `last input: X.Xs ago` rendering

Extend `_present_field_summary_text` to emit the new clause when both ends are
present. Add `_present_field_elapsed_clause` helper. Keep `pacing: <signal>` clause
unchanged.

- Modified: `src/helios_v2/composition/bridges.py`.
- Behavior:
  - Pick the earliest rendered stimulus's `received_at_wall`; ignore stimuli with
    no stamp; if all rendered stimuli lack the stamp, omit the elapsed clause.
  - Format: `last input: <X.X>s ago` with one decimal; clamp negative to `0.0s`.
  - Order: `stimuli; focal; last input: ...; pacing: ...`.
- New test: `tests/test_present_field_wall_clock_rendering.py` (≈ 8 cases including
  both-present, only-frame, only-stimulus, neither-present, NTP-rewind clamp,
  earliest-of-multiple, internal-only modality stripping).
- Validation: existing `tests/test_semantic_thought_request_bridge_present_field.py`
  stays green;
  `pytest tests/test_present_field_*.py tests/test_internal_thought_engine_present_field.py -q`.

### T6 — `PersistedExperienceRecord.created_at_wall` field + write seam

Add the additive optional field on the record and have the runtime handle's
`_persist_experience` / `_persist_memory` carry seam read
`result.tick_wall_seconds` into it. The in-memory backend trivially preserves it.

- Modified: `src/helios_v2/persistence/contracts.py`,
  `src/helios_v2/composition/runtime_assembly.py` (`RuntimeHandle._persist_*`).
- Default behavior unchanged: with no clock injected, every record carries
  `created_at_wall=None`.
- New test (partial in this slice): `tests/test_persistence_wall_clock_field.py`
  in-memory cases (≈ 4 cases).

### T7 — SQLite migration + round-trip

Add the PRAGMA-guarded `ALTER TABLE` migration; `_row_to_record` /
`_record_to_row` r/w the new column; existing files migrate in place.

- Modified: `src/helios_v2/persistence/engine.py`.
- New test (rest of T6 file): SQLite cases for new file with column; old file
  migration; mixed read with old rows `None` and new rows populated.
- Validation: existing `tests/test_persistence_engine.py`,
  `tests/test_persistence_contracts.py` stay green;
  `pytest tests/test_persistence_*.py -q`.

### T8 — Real-LLM probe + implementation-time smoke

Per §8.2 of the authoring standard, validate the new prompt shape against the real
configured model.

- New: `scripts/r92_probes/01_with_wall_clock.json` (a probe with the expected
  `Present field: ...; last input: 4.3s ago` line and a positive must-contain
  pattern + a negative-control variant `02_no_wall_clock.json` without the line).
- Run: `python scripts/run_llm_prompt_probe.py --case-file ... --strip-reasoning
  --max-tokens 2048 --save-json logs/prerun/r92_probes/`.
- Capture observed PASS + key observations into `design.md` §10.3.
- Smoke: run a short channel-bound dialogue with `assemble_production_runtime` +
  `--llm-log` and confirm the captured `11` user prompt contains the literal
  `last input: <X.X>s ago` line under real-time conditions. Record outcome in
  `design.md` §10.4.

### T9 — Documentation + index sync

Cross-file rule §8 closure. Land in the same change set as the code.

- `docs/requirements/index.md` — new R92 row, maturity `infra_done` per §5.11
  (capability owner; baseline implementation passes the §10 acceptance gate).
- `docs/OWNER_GUIDE.md` and `OWNER_GUIDE.zh-CN.md` — new infrastructure section
  describing `helios_v2.wall_clock` and the three additive consumption points;
  status-header sync (R91 → R92, baseline test count → new total).
- `docs/PROGRESS_FLOW.en.md` and `PROGRESS_FLOW.zh-CN.md` — new `infra_done` blue
  box adjacent to existing 21/22/25/30/33/34/42 capability owners; `Last synced`
  sync.
- `docs/ARCHITECTURE_BOUNDARIES.md` — new "wall-clock capability owner" row in the
  core owner map and a new boundary section listing rules (no cognitive owner
  imports; one instance threaded by composition; honest absence as the default).
- `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — short row comparing the wall-clock
  owner to the brain timing-system afferent stamp (`C_engineering_hypothesis`).
- `docs/ROADMAP.zh-CN.md` — mark R92 as delivered; close W1 status; advance the
  one-sentence-排序 line.

## 2. Dependencies

| Task | Depends on |
| --- | --- |
| T1 | (none — owner package is the foundation) |
| T2 | T1 |
| T3 | T1 |
| T4 | T1, T2, T3 |
| T5 | T1, T2, T3 (frames + stimulus stamps both available) |
| T6 | T1, T2, T4 (carry seam needs `RuntimeTickResult.tick_wall_seconds`) |
| T7 | T6 |
| T8 | T5 (probe demonstrates the new prompt clause); T7 (smoke uses production assembly with persistence) |
| T9 | T1–T8 (sync after the code is settled) |

## 3. Files and Modules

### 3.1 New code

- `src/helios_v2/wall_clock/__init__.py`
- `src/helios_v2/wall_clock/contracts.py`
- `src/helios_v2/wall_clock/engine.py`

### 3.2 Modified code

- `src/helios_v2/runtime/contracts.py`
- `src/helios_v2/runtime/kernel.py`
- `src/helios_v2/channel/drivers/cli.py`
- `src/helios_v2/composition/runtime_assembly.py`
- `src/helios_v2/composition/bridges.py`
- `src/helios_v2/persistence/contracts.py`
- `src/helios_v2/persistence/engine.py`

### 3.3 New tests

- `tests/test_wall_clock_contracts.py`
- `tests/test_runtime_frame_wall_clock.py`
- `tests/test_cli_driver_wall_clock_stamp.py`
- `tests/test_present_field_wall_clock_rendering.py`
- `tests/test_persistence_wall_clock_field.py`
- `tests/test_assemble_runtime_wall_clock_profile.py`

### 3.4 New scripts

- `scripts/r92_probes/01_with_wall_clock.json`
- `scripts/r92_probes/02_no_wall_clock.json`

### 3.5 Documentation

- `docs/requirements/92-wall-clock-timestamps/{requirement.md, design.md, task.md}`
- `docs/requirements/index.md`
- `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`
- `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`
- `docs/ARCHITECTURE_BOUNDARIES.md`
- `docs/BRAIN_ARCHITECTURE_COMPARISON.md`
- `docs/ROADMAP.zh-CN.md`

## 4. Implementation Order

1. T1 — owner package (foundation; everything else imports from it)
2. T2 — runtime frame + kernel seeding (simplest consumer)
3. T3 — CLI driver stamping (parallel to T2; both depend only on T1)
4. T4 — `RuntimeProfile` + assembly threading (T2 + T3 must be in place)
5. T5 — present-field rendering (consumes T2 frame field + T3 metadata key)
6. T6 — persistence contract + write seam (consumes T2 result field; in-memory only)
7. T7 — SQLite migration (extends T6 to the durable backend)
8. T8 — real-LLM probe + smoke (validates T5 end-to-end with T4 assembly)
9. T9 — docs + index sync (close cross-file rule §8)

## 5. Validation Plan

### 5.1 Per-task focused validation

| Task | Command |
| --- | --- |
| T1 | `pytest helios_v2/tests/test_wall_clock_contracts.py -q` |
| T2 | `pytest helios_v2/tests/test_runtime_frame_wall_clock.py helios_v2/tests/test_runtime_kernel*.py -q` |
| T3 | `pytest helios_v2/tests/test_cli_driver_wall_clock_stamp.py helios_v2/tests/test_channel_*.py helios_v2/tests/test_cli_*.py -q` |
| T4 | `pytest helios_v2/tests/test_assemble_runtime_wall_clock_profile.py helios_v2/tests/test_runtime_assembly*.py -q` |
| T5 | `pytest helios_v2/tests/test_present_field_wall_clock_rendering.py helios_v2/tests/test_semantic_thought_request_bridge_present_field.py helios_v2/tests/test_internal_thought_engine_present_field.py -q` |
| T6 | `pytest helios_v2/tests/test_persistence_wall_clock_field.py helios_v2/tests/test_persistence_contracts.py -q` |
| T7 | `pytest helios_v2/tests/test_persistence_*.py -q` |
| T8 | `python helios_v2/scripts/run_llm_prompt_probe.py --case-file helios_v2/scripts/r92_probes/01_with_wall_clock.json --strip-reasoning --max-tokens 2048 --save-json helios_v2/logs/prerun/r92_probes/` |
| T9 | doc-only; full-suite gate at end |

### 5.2 Full-suite gate (closes the change set)

```powershell
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests -q
```

Expected outcome: ≥ 1019 + new-tests passed, 4 skipped, 0 failed, 0 errors. The
composition owner-boundary guard and the no-ad-hoc-logging guard must both stay
green. Existing R83 long-run scale tier is not part of this gate (long-running),
but a quick R83 CI-tier run after T9 is encouraged to confirm the JSONL trace
gains the new field shape without breaking R88 drift evaluation.

## 6. Completion Criteria

R92 is complete when ALL of the following hold:

1. The `helios_v2.wall_clock` owner package exists and ships `WallClockError`,
   `WallClockReading`, `WallClock` protocol, `SystemWallClock`, `FixedWallClock`,
   and `RECEIVED_AT_WALL_METADATA_KEY`.
2. The kernel seeds `RuntimeFrame.tick_wall_seconds` and
   `RuntimeTickResult.tick_wall_seconds` exactly once per tick from the injected
   `WallClock`. With no clock injected, both stay `None`.
3. The CLI driver stamps `received_at_wall` in inbound packet metadata at
   `submit_line` time when wired; absent when not wired.
4. `_present_field_summary_text` renders `last input: X.Xs ago` when both ends are
   present; falls back to the existing `pacing:` clause otherwise; clamps a
   negative delta to `0.0s ago`; does not regress R91.
5. `PersistedExperienceRecord.created_at_wall` is persisted and read back exactly
   on both backends. SQLite migrates an existing file in place; old rows read with
   `None`; new rows carry the value.
6. `RuntimeProfile.wall_clock` is honored end-to-end; profile + loose-kwarg overlap
   raises `CompositionError`. `assemble_production_runtime()` defaults to
   `SystemWallClock()`. The same instance reaches kernel, CLI driver, and runtime
   handle (identity-checked).
7. Every change is additive and default-off in `assemble_runtime()`. The pre-R92
   network-free test suite (1019 passed / 4 skipped) is green; the new R92 tests
   are green; the composition owner-boundary guard and the no-ad-hoc-logging guard
   are green.
8. The real-LLM probe (`scripts/r92_probes/01_with_wall_clock.json`) shows the
   model engaging the elapsed-seconds fact; the negative-control probe
   (`02_no_wall_clock.json`) shows the model does not fabricate a time. The
   implementation-time CLI smoke captures a real `11` user prompt that contains the
   literal `last input: <X.X>s ago` line.
9. `docs/requirements/index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW`
   maps, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, and
   `ROADMAP.zh-CN.md` are updated in the same change set.
