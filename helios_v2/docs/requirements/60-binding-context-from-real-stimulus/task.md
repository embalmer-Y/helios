# Requirement 60 - Memory Binding Context Derived from the Real Perceived Stimulus

## 1. Task Breakdown

### T1 - Add the owner-neutral tokenizer and internal-modality constant
In `composition/bridges.py`, add a module-level `_tokens_from(text: str) -> tuple[str, ...]`
(lowercase, split on non-alphanumeric, drop empties, de-duplicate order-preserving, bounded to a
small cap) and an `_INTERNAL_MODALITIES` frozenset (`{"body", "interoceptive", "background"}`).
The tokenizer fabricates nothing — every token is a substring of the real input.

### T2 - Derive the binding context from the real `02` batch
Rewrite `FirstVersionMemoryBindingContextBridge.build_binding_context(frame, feeling_result)` to
read the real `sensory_ingress` `StimulusBatch` from the frame, prefer external stimuli (fall
back to the whole batch for interoceptive-only ticks), pick the deterministic primary stimulus,
and project it into `MemoryBindingContext`/`MemoryContentPacket` (`source_kind="perceived_stimulus"`,
`content_kind="perceived-stimulus-summary"`, `summary_ref=primary.stimulus_id`,
`context_ref=batch.batch_id`, `salient_tokens=_tokens_from(primary.content)`). Return `None` on an
empty perceived batch (honest absence). Remove the `("hello","novelty")` / `summary:runtime`
constant.

### T3 - Update existing tests that assert the old constant
Find and update stage-chain/composition tests asserting the old binding-context constant
(`situational-summary`, `("hello","novelty")`, `summary:runtime`) to assert real-percept-derived
content/provenance instead.

### T4 - Add focused tests
In `test_runtime_composition.py`: a varying R59 external source drives different formed-memory
content/provenance across ticks (constant absent); an empty-percept tick forms an honest
no-percept memory and completes; the default placeholder percept ("hello runtime") flows into
the content.

### T5 - Documentation
Update `index.md` (row 60), both `OWNER_GUIDE` files (`06`/`02` entries: memory content now from
the real percept), both `PROGRESS_FLOW` maps (status note + sync line), and
`BRAIN_ARCHITECTURE_COMPARISON.md` (FG-1 memory-content honesty).

## 2. Dependencies

1. T1 -> T2 (the bridge uses the helper).
2. T3 + T4 after T2. T5 after T1-T4.
3. External requirement dependencies: 06 (memory owner + `AffectGroundedMemoryFormationPath`), 45
   (affect-grounded formation + durability), 52 (recalled replay), 59 (real external stimulus
   feeding `02`), 02 (`StimulusBatch`/`Stimulus`). No new owner, no contract change.

## 3. Files and Modules

1. `src/helios_v2/composition/bridges.py` (T1, T2)
2. `tests/test_runtime_stage_chain.py` and/or `tests/test_runtime_composition.py` (T3, T4)
3. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (T5)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5. Helper, derivation, fix existing tests, add focused tests, document.

## 5. Validation Plan

1. After T2 (no stale constant + chain runs):
   `pytest helios_v2/tests/test_runtime_stage_chain.py helios_v2/tests/test_runtime_composition.py -q`
   green (existing tests updated for the real-percept content).
2. After T4 (new behavior):
   `pytest helios_v2/tests/test_runtime_composition.py -q` green, including the
   real-percept-content, empty-percept, and default-percept tests.
3. `06` mechanism regression:
   `pytest helios_v2/tests/test_memory_engine.py helios_v2/tests/test_memory_contracts.py -q`
   green (affect tag / salience gate / recall unchanged).
4. Guards + full suite:
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   and `pytest helios_v2/tests -q` green; count = prior baseline (728) + added tests (minus any
   updated-in-place).

## 6. Completion Criteria

1. The binding-context content is derived from the real `02` percept (provenance + tokenized real
   content); no hardcoded `("hello","novelty")`/`summary:runtime` constant remains in composition.
2. A varying external stimulus produces different formed-memory content across ticks; an
   empty-percept tick forms an honest no-percept memory and completes the chain.
3. The `06` affect tag, salience gate, durability, and recalled replay are unchanged in mechanism
   (their tests stay green).
4. The full network-free suite is green; owner-boundary and ad-hoc-logging guards stay green.
5. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `BRAIN_ARCHITECTURE_COMPARISON.md` record that memory binding-context content is now derived
   from the real percept, with sync lines naming R60.
