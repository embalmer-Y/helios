# Requirement 65 - Zero-Percept Pre-Gate Closure

## 1. Background and Problem

The `06` memory owner forms an affect-tagged memory each tick. The `07` workspace owner
consumes `06`'s replay candidates and **raises** if it receives zero candidates
(`validate_memory_replay_candidates` in `workspace/contracts.py` L227). This forces the
pre-gate `06→07→08` chain to produce at least one memory and one workspace candidate every
tick, even when the system perceived nothing.

R60 addressed the "memory content is a constant" problem by deriving binding-context content
from the real `02` sensory batch. On a completely empty percept (no external and no
interoceptive stimulus), R60 binds an honest no-percept marker (`content_kind="no-perceived-stimulus"`,
empty tokens, real feeling-state provenance) so the chain stays valid — but it still forces a
memory to form. The R60 requirement explicitly noted: "a genuine zero-percept pre-gate closure
(so a tick can form no memory at all) is a separate, larger future requirement."

R54 solved the analogous problem for post-gate stages: when `09` gate decides `no_fire`, each
post-gate stage returns an `activated=False` inactive result without invoking its owner. The
pattern is mature — additive `activated: bool = True` discriminator plus an `inactive(tick_id)`
factory on each stage result, with the runtime stage adapter checking the upstream gate
decision and short-circuiting.

R65 is the pre-gate mirror: when the tick has zero perceived stimulus, the `06`/`07`/`08`
stages return inactive results without invoking their owners, and the tick closes through the
existing `09` gate no-fire path.

## 2. Goal

Allow a zero-percept tick (no external and no interoceptive stimulus in the `02` batch) to
legitimately skip `06` memory formation, `07` workspace competition, and `08` consciousness
ignition, closing through `09` gate's no-fire decision — the pre-gate mirror of R54's post-gate
no-fire closure. No owner code changes; no contract changes.

## 3. Functional Requirements

### 3.1 Zero-percept detection

1. Zero percept must be detected by checking the `02` sensory batch in the runtime frame:
   when `frame.stage_results["sensory_ingress"].batch.stimuli` is empty, the tick has zero
   percept. The detection is performed at the `06` memory runtime stage adapter, which runs
   immediately after `05` feeling in the canonical order.
2. The detection must not invent any percept, fabricate content, or score salience; it reads
   only the already-published `02` fact.

### 3.2 Pre-gate stage inactive results

1. `06` memory stage (`MemoryAffectReplayRuntimeStage`): when zero percept is detected, must
   return a `MemoryAffectReplayStageResult` with `activated=False` without invoking the memory
   engine. The inactive result carries empty state, no record op, no replay candidates.
2. `07` workspace stage (`WorkspaceCompetitionRuntimeStage`): when the upstream `06` result
   has `activated=False`, must return a `WorkspaceCompetitionStageResult` with `activated=False`
   without invoking the workspace engine.
3. `08` consciousness stage (`ConsciousContentRuntimeStage`): when the upstream `07` result
   has `activated=False`, must return a `ConsciousContentStageResult` with `activated=False`
   without invoking the consciousness engine.

### 3.3 Gate consumption

1. `09` gate (`ThoughtGatingRuntimeStage`): when the upstream `08` consciousness result has
   `activated=False`, the gate must produce a valid no-fire decision. The natural mechanism:
   the gate signal's `global_activation_level` is `0.0` (no ignition source → no activation →
   gate score below threshold → `no_fire`). No new gate input signal is needed.
2. The post-gate no-fire closure (R54) already handles the remaining stages.

### 3.4 Behavioral scope

1. Ticks with at least one perceived stimulus (including the default assembly's
   `FirstVersionSensorySource` placeholder "hello runtime") must behave identically to the
   current implementation — the inactive path is never reached.
2. The R60 no-percept marker path in the binding-context bridge is preserved as a defensive
   fallback but annotated as unreachable from the runtime path after R65.

## 4. Non-Functional Requirements

1. Performance: one additional empty-tuple check (`if not stimuli`) at the `06` stage entry;
   no measurable overhead.
2. Reliability: no new failure mode; the inactive results are valid default-constructed
   dataclasses with no owner call.
3. Observability and logging: no new logging mechanism; the `21` owner stays the single
   logging mechanism.
4. Compatibility and migration: each stage result gains additive fields with defaults
   (`activated: bool = True`, `inactive_id: str | None = None`), so all existing constructors
   and tests remain valid.

## 5. Code Behavior Constraints

1. Forbidden: the zero-percept detection fabricating content, scoring salience, or inventing
   stimuli to fill the gap (`ARCHITECTURE_PHILOSOPHY` §4.3/§8).
2. Forbidden: relaxing the `07` workspace owner's `validate_memory_replay_candidates`
   invariant; the fix is at the runtime stage adapter layer, not the owner layer.
3. Boundary rule: the zero-percept detection is runtime-owned adapter logic reading published
   upstream facts; it computes no owner policy.
4. Failure mode: a missing `sensory_ingress` stage result is the existing hard fail
   (`_require_stage_result`); `02` always runs before `06` in canonical order.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/runtime/stages.py` — add `activated`/`inactive_id` fields and
   `inactive(tick_id)` factories to `MemoryAffectReplayStageResult`,
   `WorkspaceCompetitionStageResult`, `ConsciousContentStageResult`; add zero-percept
   short-circuit logic to the three runtime stage adapters; add gate consumption of inactive
   consciousness.
2. `helios_v2/tests/test_zero_percept_pregate_closure.py` — new focused test file.
3. `helios_v2/tests/test_runtime_composition.py` — verify existing tests remain green; update
   any test asserting specific field counts on stage results.
4. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`.

## 7. Acceptance Criteria

1. With an R59 empty `SequenceExternalSignalSource` and no interoceptive sampler, a tick
   completes end to end: `06`/`07`/`08` return `activated=False`, `09` gate decides `no_fire`,
   and the tick produces all 19 canonical stage results without raising.
2. The default assembly (with `FirstVersionSensorySource` placeholder) behaves identically —
   `06`/`07`/08` all activate and the gate fires as before.
3. The semantic assembly with a real external stimulus behaves identically — all pre-gate
   stages activate.
4. An interoceptive-only tick (no external but with body pressure stimuli) still forms memory,
   competes workspace, and commits consciousness.
5. The full network-free suite is green; owner-boundary and ad-hoc-logging guards stay green.
6. `index.md` has a row 65; both `OWNER_GUIDE` files record the zero-percept item as delivered;
   both `PROGRESS_FLOW` maps have sync lines naming R65.
