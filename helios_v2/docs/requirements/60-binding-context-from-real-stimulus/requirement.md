# Requirement 60 - Memory Binding Context Derived from the Real Perceived Stimulus

## 1. Background and Problem

The `06` memory owner forms an affect-tagged memory each fired tick. Since R45 the memory's
affect tag is the real `05` feeling vector, but the memory's **content** is whatever the
composition binding-context bridge supplies. Today that bridge,
`FirstVersionMemoryBindingContextBridge`, returns a hardcoded constant in every assembly
(it does not read any switch):

```
MemoryContentPacket(
    content_kind="situational-summary",
    summary_ref=f"summary:runtime:{tick_id}",
    context_ref=f"context:runtime:{tick_id}",
    salient_tokens=("hello", "novelty"),
)
```

The `06` formation path (`AffectGroundedMemoryFormationPath`) copies
`binding_context.content` verbatim into the formed `AffectTaggedMemoryItem`. So the memory
the system forms — and (since R45) durably persists and (since R52) recalls back into the
`07` workspace — is *about* a fixed `("hello", "novelty")` content regardless of what the
system actually perceived this tick.

Two concrete consequences:

1. Under `FG-1`, the memory-formation content is a composition-injected constant, not a real
   signal. Now that R59 makes a real, tick-varying external stimulus reach `02`/`03`, the
   binding-context constant is the next position in the perception-affect chain still
   fabricated: a real stimulus drives `03`/`04`/`05`, but the memory formed from that tick is
   labelled with fixed tokens unrelated to the real percept.
2. The durable affect-memory store (R45) and the recalled-replay workspace multiplicity (R52)
   therefore accumulate and re-compete on constant content, so the episodic memory is not a
   record of real experience. This weakens the `FG-5`/`FG-2` claim that memory genuinely
   accumulates real experience and that a recalled past memory is *about* something real.

The honest fix is to derive the binding-context content from the real perceived stimulus this
tick (the `02` sensory batch / `03` appraisal already in the frame), with honest absence when
there is no stimulus — never a fabricated constant, and never inventing tokens that were not
in the real percept (`ARCHITECTURE_PHILOSOPHY` §4.3/§8).

## 2. Goal

Derive the memory binding-context content each tick from the real perceived stimulus (the
`02` sensory batch already present in the frame) so the affect-tagged memory `06` forms,
persists, and recalls is a record of what the system actually perceived, replacing the
hardcoded `("hello", "novelty")` constant; and when no stimulus was perceived this tick,
produce an explicit honest-absence binding context (or no binding context) rather than a
fabricated one.

## 3. Functional Requirements

### 3.1 Binding context from the real percept

1. When the runtime perceives at least one stimulus this tick, the binding-context content
   must be derived from the real `02` stimulus batch in the frame: the content packet's
   `summary_ref`/`context_ref` must reference the real stimulus/batch provenance ids, and its
   `salient_tokens` must be derived mechanically from the real stimulus content (the actual
   perceived text), not hardcoded.
2. The derivation must be owner-neutral transport: composition projects real upstream facts
   into the `06` `MemoryBindingContext`/`MemoryContentPacket` contract; it must not invent
   tokens absent from the percept, score salience, or compute any `06` memory policy.
3. The derived binding context must preserve the real stimulus provenance so a later reader
   (evaluation, recall) can trace the formed memory back to the stimulus it records.

### 3.2 Honest absence

1. When no stimulus was perceived this tick (a completely empty `02` batch — no external and
   no interoceptive stimulus, e.g. R59 honest-absence or a channel no-input tick), the bridge
   must not fabricate external stimulus content. It must produce an explicit honest no-percept
   binding context anchored to the real `05` feeling state of this tick (an honest marker that
   nothing was perceived, carrying real feeling-state provenance and no invented tokens).
2. The no-percept binding context keeps the tick valid: the pre-gate `02-08` chain currently
   requires a memory to form each tick (the `07` workspace owner needs at least one replay
   candidate; a zero-percept pre-gate closure is a separate future requirement), so the honest
   marker forms a real memory of "perceived nothing this tick" tagged with the real affect,
   rather than breaking the chain or fabricating an external percept.

### 3.3 Behavioral scope

1. The change must affect only the binding-context content source. The `06` affect tag (R45),
   the salience gate (R45), durability (R45), and recalled replay (R52) are unchanged in
   mechanism; they now operate on real-percept content instead of the constant.
2. The interoceptive-only / no-external-stimulus assemblies must still form memory from
   whatever real stimuli exist (e.g. interoceptive stimuli), or honestly form none, never from
   the old constant.

## 4. Non-Functional Requirements

1. Performance: no measurable per-tick overhead beyond reading the already-present `02` batch.
2. Reliability: a malformed `02` batch is already a hard stop upstream; the bridge adds no new
   failure branch and fabricates no content on absence.
3. Observability and logging: no new logging mechanism; the `21` owner stays the single logging
   mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: the `06` `MemoryBindingContext`/`MemoryContentPacket` contracts
   are unchanged in shape. This replaces the content *source* inside the composition bridge.
   Because the default assembly's `02` source is itself a constant placeholder
   (`FirstVersionSensorySource`, "hello runtime"), the default memory content becomes "derived
   from that placeholder" rather than the separate `("hello","novelty")` constant — a defined,
   documented change in the default's memory content, still driven by `02` rather than a second
   hardcoded constant. Tests asserting the old tokens are updated.

## 5. Code Behavior Constraints

1. Forbidden: a hardcoded binding-context content constant in composition (the
   `("hello","novelty")` / `summary:runtime` literals) once the real-percept derivation lands.
2. Forbidden: inventing salient tokens or summary content not present in the real perceived
   stimulus; tokenization of the real content is allowed, fabrication is not
   (`ARCHITECTURE_PHILOSOPHY` §4.3/§8).
3. Boundary rule: the binding-context bridge is owner-neutral composition glue projecting real
   `02` facts into the `06` contract; it computes no `06` memory policy and imports no owner it
   should not.
4. Failure mode: an empty perceived batch yields honest absence (no binding context or an
   explicit empty one), never a fabricated content packet.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` — replace
   `FirstVersionMemoryBindingContextBridge`'s constant content with derivation from the real
   `02` sensory batch in the frame, with honest absence on an empty batch.
2. `helios_v2/tests/test_runtime_composition.py` and/or `tests/test_runtime_stage_chain.py` —
   tests: real perceived stimulus drives the formed memory's content/provenance; an
   empty-percept tick forms an honest no-percept memory without crashing; the default
   placeholder percept flows into the content (no separate constant).
3. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (FG-1 memory-content honesty).

## 7. Acceptance Criteria

1. With a real external stimulus (R59 `SequenceExternalSignalSource`) whose content varies, the
   `06`-formed memory item's content (`summary_ref`/`context_ref`/`salient_tokens`) is derived
   from that real stimulus and differs across ticks with different stimulus content; the
   hardcoded `("hello","novelty")` constant no longer appears.
2. On an empty-percept tick (no external and no interoceptive stimulus), `06` forms an honest
   no-percept memory anchored to the real `05` feeling state (`content_kind="no-perceived-stimulus"`,
   empty tokens, `summary_ref` = the real feeling-state id) and the tick completes through the
   chain without crashing. The bridge fabricates no external content on this path.
3. The `06` affect tag, salience gate, durability, and recalled replay are unchanged in
   mechanism (their tests stay green); only the binding-context content source changed.
4. No hardcoded binding-context content constant remains in composition; the full network-free
   suite is green with updated/added tests; owner-boundary and ad-hoc-logging guards stay green.
5. `index.md` has a row 60; the `06`/`02` `OWNER_GUIDE` entries and the
   `BRAIN_ARCHITECTURE_COMPARISON` FG-1 note record that memory content is now derived from the
   real percept (not a constant), with sync lines naming R60.
