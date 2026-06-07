# Requirement 65 - Zero-Percept Pre-Gate Closure

## 1. Design Overview

Mirror R54's post-gate no-fire closure for the pre-gate `06→07→08` chain. When the `02`
sensory batch is empty (zero perceived stimulus), the `06` memory runtime stage adapter
returns an `activated=False` inactive result without invoking the memory engine. The `07`
workspace adapter checks the upstream `06` result and short-circuits similarly. The `08`
consciousness adapter checks `07`. The `09` gate reads the inactive `08` result and produces
a no-fire decision (the post-gate R54 closure handles the remaining stages). No owner code,
no contract, no engine change.

## 2. Current State and Gap

Three pre-gate stage results (`MemoryAffectReplayStageResult`, `WorkspaceCompetitionStageResult`,
`ConsciousContentStageResult`) lack the `activated: bool` discriminator that R54 added to the
post-gate stage results. Their runtime adapters unconditionally invoke the owner engine. The
`07` workspace engine's `validate_memory_replay_candidates` raises on zero candidates, forcing
the chain to always produce at least one memory.

R60's binding-context bridge handles zero percept by emitting an honest no-percept marker,
keeping the chain valid but not allowing the tick to genuinely skip memory formation.

Gap: no short-circuit path exists for a zero-percept tick at the pre-gate stages.

## 3. Target Architecture

```
MemoryAffectReplayRuntimeStage.run(frame):
    feeling_result = _require_stage_result(frame, "interoceptive_feeling_layer", ...)
    # R65: zero-percept detection
    sensory = frame.stage_results.get("sensory_ingress")
    stimuli = sensory.batch.stimuli if isinstance(sensory, SensoryIngressStageResult) else ()
    if not stimuli:
        return MemoryAffectReplayStageResult.inactive(frame.tick_id)
    # ... existing path (binding context, memory engine, replay candidates)

WorkspaceCompetitionRuntimeStage.run(frame):
    memory_result = _require_stage_result(frame, "memory_affect_and_replay", ...)
    # R65: upstream inactive check
    if not memory_result.activated:
        return WorkspaceCompetitionStageResult.inactive(frame.tick_id)
    # ... existing path (compete, retain)

ConsciousContentRuntimeStage.run(frame):
    ws_result = _require_stage_result(frame, "workspace_competition_and_working_state", ...)
    # R65: upstream inactive check
    if not ws_result.activated:
        return ConsciousContentStageResult.inactive(frame.tick_id)
    # ... existing path (commit ignition)

ThoughtGatingRuntimeStage.run(frame):
    conscious_result = _require_stage_result(frame, "reportable_conscious_content", ...)
    # R65: inactive consciousness -> gate sees no ignition source
    if not conscious_result.activated:
        # Force global_activation_level=0.0 in the gate signal, which produces no_fire
    # ... existing path (evaluate gate)
```

The design keeps every owner engine's invariants intact: `07` still requires >=1 candidates
(the runtime adapter just never calls it when there are none), `08` still requires a workspace
result, and `09` still evaluates its signal snapshot.

## 4. Data Structures

### Stage result additions (additive, with defaults)

```python
@dataclass(frozen=True)
class MemoryAffectReplayStageResult:
    # ... existing fields ...
    activated: bool = True
    inactive_id: str | None = None

    @classmethod
    def inactive(cls, tick_id: int | None) -> "MemoryAffectReplayStageResult":
        return cls(
            record_op=None,
            state=MemoryFormationState(memory_items=(), replay_candidates=(), ...),
            publish_replay_candidates_op=None,
            publish_state_op=None,
            activated=False,
            inactive_id=f"memory-affect-no-percept:{tick_id if tick_id is not None else 'na'}",
        )
```

Same pattern for `WorkspaceCompetitionStageResult` and `ConsciousContentStageResult`.

## 5. Module Changes

1. `runtime/stages.py`
   - Add `activated`/`inactive_id` + `inactive(tick_id)` to three stage results.
   - Add zero-percept short-circuit to `MemoryAffectReplayRuntimeStage.run`.
   - Add upstream-inactive short-circuit to `WorkspaceCompetitionRuntimeStage.run`.
   - Add upstream-inactive short-circuit to `ConsciousContentRuntimeStage.run`.
   - Add inactive-consciousness handling to `ThoughtGatingRuntimeStage.run`.
2. `composition/bridges.py`
   - Annotate R60's `_build_no_percept_binding_context` as defensive fallback unreachable
     from the runtime path after R65 (no code change, docstring annotation only).
3. Tests (see Validation Strategy).

## 6. Migration Plan

1. Add `activated`/`inactive_id` fields with defaults to the three stage results. Run the full
   suite to confirm no regression (default `True` keeps every existing path active).
2. Add `inactive(tick_id)` factories. Run the full suite again (no new callers yet).
3. Add zero-percept short-circuit logic to the three runtime adapters. Run the full suite.
4. Add gate consumption of inactive consciousness. Run the full suite.
5. Add focused tests. Run the full suite.
6. Update documentation.

Each step is independently green: step 1 adds only default-valued fields; step 2 adds unused
factories; step 3 activates the new path only on genuinely empty batches.

## 7. Failure Modes and Constraints

1. Zero percept: `06` returns inactive → `07` returns inactive → `08` returns inactive → `09`
   sees no ignition source → `no_fire` → R54 handles post-gate. The tick completes with all
   19 canonical stage results.
2. Missing `sensory_ingress` stage result: the existing `_require_stage_result` hard fail
   applies. This cannot happen in canonical order (`02` runs before `06`).
3. Default assembly: `FirstVersionSensorySource` emits `"hello runtime"` — the batch is never
   empty, so the inactive path is never reached. Behavior unchanged.
4. R59 empty source: an explicitly empty `SequenceExternalSignalSource(batches=())` with no
   interoceptive sampler produces a genuinely empty `02` batch. The inactive path activates.
5. R59 exhausted source: after the source's batches are exhausted, it emits an empty batch per
   tick. With no interoceptive sampler, the inactive path activates for those ticks.
6. Interoceptive-only tick: body pressure stimuli exist in the `02` batch, so the batch is
   not empty. Memory formation proceeds normally.

## 8. Rollout (Default-On vs Default-Off)

Default-on and unconditional. The zero-percept path activates only when the `02` batch is
genuinely empty — a condition that never occurs in the default, semantic, interoceptive,
channel-bound, or temporal assemblies (each registers at least one stimulus source). The
change is a correctness fix enabling a new valid tick outcome, not an opt-in capability.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. The
short-circuit paths use neither `logging` nor `print`; the ad-hoc-logging guard stays green.

## 10. Validation Strategy

1. Zero-percept tick: an R59 empty source + no interoceptive sampler → `06`/`07`/`08` all
   `activated=False`; `09` gate decides `no_fire`; tick completes with 19 stage results.
2. Default assembly unchanged: `_assemble()` → `06`/`07`/`08` all `activated=True`; gate
   fires as before; every existing test stays green.
3. Semantic assembly unchanged: `_assemble(experience_store=..., embedding_gateway=...)`
   with a real external stimulus → all pre-gate stages activate.
4. Interoceptive-only tick: `_assemble(interoceptive_sampler=...)` with body pressure →
   the `02` batch has interoceptive stimuli → memory forms normally.
5. R59 source exhaustion: a source with one batch, tick 2 onward → empty batch → inactive
   pre-gate path activates.
6. Full suite green; owner-boundary and ad-hoc-logging guards green.
