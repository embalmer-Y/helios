# Requirement 60 - Memory Binding Context Derived from the Real Perceived Stimulus

## 1. Design Overview

Replace the constant content inside `FirstVersionMemoryBindingContextBridge` with a derivation
from the real `02` sensory batch already present in the runtime frame. The memory stage runs
after `02`/`03`/`04`/`05` and before `06`, so the frame's `sensory_ingress` stage result holds
the real perceived `StimulusBatch` this tick. The bridge projects that real percept into the
`06` `MemoryBindingContext`/`MemoryContentPacket` contract: provenance ids from the real
stimulus/batch, and `salient_tokens` mechanically tokenized from the real perceived content.
When the batch is empty (R59 honest-absence or a no-input tick), the bridge returns `None`
(no binding context), so `06` forms no memory that tick — a defined outcome, never a fabricated
content packet. No `06` contract changes; only the content source inside the bridge changes.

## 2. Current State and Gap

`FirstVersionMemoryBindingContextBridge.build_binding_context(frame, feeling_result)` returns a
fixed `MemoryContentPacket(content_kind="situational-summary", summary_ref="summary:runtime:{tick}",
context_ref="context:runtime:{tick}", salient_tokens=("hello","novelty"))` every tick, in every
assembly. `AffectGroundedMemoryFormationPath` copies `binding_context.content` verbatim into the
formed `AffectTaggedMemoryItem`, so the memory content is the constant.

The frame already carries the real percept: `RapidSalienceAppraisalRuntimeStage` reads
`frame.stage_results["sensory_ingress"]` (a `SensoryIngressStageResult` with `.batch`, a
`StimulusBatch` of normalized `Stimulus` with real `content`, `stimulus_id`, `source_name`,
`provenance_signal_id`). The bridge has the same `frame`, so it can read the real batch. Gap:
it ignores the percept and emits the constant.

## 3. Target Architecture

```
FirstVersionMemoryBindingContextBridge.build_binding_context(frame, feeling_result):
    batch = frame.stage_results["sensory_ingress"].batch          # real perceived stimuli
    external = [s for s in batch.stimuli if s.modality not in INTERNAL_MODALITIES]
    # Prefer the external percept (what the world presented); fall back to the whole batch
    # (e.g. interoceptive-only ticks) so an interoceptive tick still binds a real percept.
    perceived = external or list(batch.stimuli)
    if not perceived:
        # Honest absence: nothing perceived. The pre-gate 02-08 chain still requires a memory
        # (07 needs >=1 replay candidate), so bind an explicit no-percept marker anchored to the
        # REAL feeling state -- no fabricated external content, no invented tokens.
        return MemoryBindingContext(
            context_id=f"binding:runtime:{tick_id}",
            source_kind="no_perceived_stimulus",
            content=MemoryContentPacket(
                content_kind="no-perceived-stimulus",
                summary_ref=feeling_result.state.state_id,   # real feeling provenance
                context_ref=None,
                salient_tokens=(),
            ),
        )
    primary = perceived[0]                                        # deterministic: first by batch order
    return MemoryBindingContext(
        context_id=f"binding:runtime:{tick_id}",
        source_kind="perceived_stimulus",
        content=MemoryContentPacket(
            content_kind="perceived-stimulus-summary",
            summary_ref=primary.stimulus_id,                      # real provenance
            context_ref=batch.batch_id,                           # real batch provenance
            salient_tokens=_tokens_from(primary.content),         # mechanical tokenization
        ),
    )
```

Design note (surfaced during implementation): the pre-gate `02-08` chain currently requires a
memory to form every tick — the `07` workspace owner raises if it receives zero
`MemoryReplayCandidate`s, and R54's no-fire closure only covers the post-gate stages. Returning
`None` on an empty percept therefore breaks the chain. The honest resolution is to bind a real
no-percept memory anchored to the always-present real feeling state (not a fabricated external
percept, and not `None`). A genuine zero-percept pre-gate closure (so a tick can form no memory
at all) is a separate, larger future requirement.

`_tokens_from(text)` is a deterministic, bounded, owner-neutral tokenizer: lowercase, split on
non-alphanumeric, drop empties, de-duplicate preserving order, cap at a small bound (e.g. 8
tokens). It invents nothing — every token is a substring of the real perceived content. If the
real content tokenizes to nothing (e.g. punctuation-only), `salient_tokens` is empty but
`summary_ref`/`context_ref` are still real, so the `MemoryContentPacket` invariant (at least one
of summary/context/tokens) holds.

`INTERNAL_MODALITIES = {"body", "interoceptive", "background"}` mirrors the `05` filter and the
`03` social-source classification, so "external percept" means a real outward stimulus; an
interoceptive-only tick falls back to binding the interoceptive percept (still real), and a
fully empty tick binds nothing.

## 4. Data Structures

No contract changes. The bridge keeps returning the existing `MemoryBindingContext` /
`MemoryContentPacket` (or `None`). The only shape note: `content_kind` becomes
`"perceived-stimulus-summary"` (was `"situational-summary"`) and `source_kind` becomes
`"perceived_stimulus"` (was `"runtime_chain"`), both honest descriptions of the new real source.

`_tokens_from` contract:
- input: the real `Stimulus.content` string
- output: `tuple[str, ...]`, each token a lowercased alphanumeric substring of the input,
  de-duplicated, order-preserving, length-bounded; possibly empty.

## 5. Module Changes

1. `composition/bridges.py`
   - Rewrite `FirstVersionMemoryBindingContextBridge.build_binding_context` to read the real
     `02` batch from the frame and project the primary perceived stimulus into the binding
     context; return `None` on an empty perceived batch.
   - Add a module-level `_tokens_from(text: str) -> tuple[str, ...]` owner-neutral tokenizer and
     an `_INTERNAL_MODALITIES` constant (or reuse an existing one).
   - Import `SensoryIngressStageResult` lazily inside the method (the existing bridge pattern for
     stage-result types) or read `.batch` structurally; keep composition's existing import
     discipline.
2. Tests (see Validation Strategy).

No change to `MemoryAffectReplayRuntimeStage`, the `06` engine, or the `06` formation path: they
already consume whatever `MemoryBindingContext` the provider returns (including `None`).

## 6. Migration Plan

1. Add `_tokens_from` and `_INTERNAL_MODALITIES`.
2. Rewrite the bridge method to derive from the real batch with honest-absence `None`.
3. Update the existing stage-chain/composition tests that assert the old `("hello","novelty")`
   tokens or `situational-summary` kind to assert real-percept-derived content instead.
4. Add focused tests: real external stimulus drives memory content; empty percept forms no
   memory; default placeholder percept ("hello runtime") flows into content (no separate
   constant).
5. Run the full suite; confirm `06` affect/salience/durability/recall tests stay green.
6. Update documentation truth.

This is a localized change inside one composition bridge method plus a small helper; no contract
or owner change, no stage reorder.

## 7. Failure Modes and Constraints

1. Empty perceived batch -> an honest no-percept binding context anchored to the real `05`
   feeling state (`content_kind="no-perceived-stimulus"`, empty tokens, `summary_ref` = the real
   feeling-state id). `06` forms a real "perceived nothing" memory tagged with the real affect;
   the tick proceeds. This is required because the pre-gate `02-08` chain (the `07` workspace
   owner) needs at least one replay candidate every tick; returning `None` would break it. No
   fabricated external content on this path.
2. The bridge reads only already-published `02` facts; a missing/wrong-typed `sensory_ingress`
   result is the existing hard fail (`_require_stage_result` semantics) — but `02` always runs
   before `06` in the canonical order, so the result is present.
3. `_tokens_from` is total and deterministic; punctuation-only content yields empty tokens but a
   still-valid packet (real summary/context refs present).
4. No fabricated content on any path: tokens are substrings of the real percept; absence yields
   `None`, never a synthetic packet.

## 8. Rollout (Default-On vs Default-Off)

Default-on and unconditional (the bridge is used by every assembly). This is a correctness/honesty
change to the binding-context source, not an opt-in capability. Behavior change is intended and
documented: the formed memory content is now the real percept instead of the
`("hello","novelty")` constant. In the default assembly the percept is the
`FirstVersionSensorySource` placeholder ("hello runtime"), so the default memory content becomes
derived from that placeholder — still `02`-driven, not a second hardcoded constant. In the R59
external-source / interoceptive / channel assemblies it is the real stimulus.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. The bridge and
the tokenizer use neither `logging` nor `print`; the ad-hoc-logging guard stays green.

## 10. Validation Strategy

1. Real-percept content: with an R59 `SequenceExternalSignalSource` emitting two distinct-content
   batches, the `06`-formed memory item's `content.summary_ref`/`salient_tokens` derive from each
   tick's real stimulus and differ across the two ticks; the `("hello","novelty")` constant is
   absent.
2. Provenance: the formed memory's `content.summary_ref` equals the real stimulus id and
   `context_ref` equals the real batch id (traceable to the percept).
3. Honest absence: an empty-percept tick (R59 empty source) forms an honest no-percept memory
   (`content_kind="no-perceived-stimulus"`, empty tokens, real feeling-state `summary_ref`) and
   completes the chain without crashing; the bridge fabricates no external content.
4. Default percept: the default assembly's formed memory content derives from the placeholder
   percept ("hello runtime" tokenizes to `("hello","runtime")`), proving no separate hardcoded
   binding constant remains.
5. `06` mechanism unchanged: the existing R45 affect-tag/salience-gate/durability and R52
   recalled-replay tests stay green (they operate on the new real content without mechanism
   change). Full network-free suite green; owner-boundary and ad-hoc-logging guards green.
