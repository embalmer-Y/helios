# Requirement 45 - Affect-grounded memory formation and durable memory store (design)

## 1. Design Overview

R45 closes the two coupled `06` shims together: it makes memory formation real (driven by the `05` interoceptive feeling state) and makes consolidation-worthy memory durable on the shared `33`/`34` substrate, recalled semantically through `10` across a restart.

Five additive, opt-in pieces:

1. A `06`-owned `AffectGroundedMemoryFormationPath` (implements the existing `MemoryFormationPath` protocol) that forms items from the real `05` feeling vector and binding context.
2. A `06`-owned `SalienceGatedReplayCandidateSelector` (implements the existing `ReplayCandidateSelector` protocol) that computes a bounded affect-intensity salience from the real feeling vector and optional mismatch evidence, and sets `forced_consolidation` + `priority_hint` from it - so a flat tick consolidates nothing.
3. An additive `record_kind` discriminator and optional opaque `metadata` mapping on `PersistedExperienceRecord`, default-preserving, with a back-compatible SQLite column.
4. An owner-neutral composition `MemoryRecordBridge` that projects exactly the `forced_consolidation` memory items from the published `06` stage result into durable `PersistedExperienceRecord`s tagged `record_kind="affect_memory"`, and a memory-persistence carry seam in `RuntimeHandle.tick` mirroring the existing `_persist_experience`.
5. Recall: the existing `SemanticStoreBackedDirectedMemoryCandidateProvider` already ranks all embedded records, so affect-memory records become recallable for free once persisted with an embedding; only the tier mapping needs to read the stored family.

Everything stays within the existing memory, persistence, and directed-retrieval contracts. No stage-order change. No directed-retrieval contract change.

## 2. Current State and Gap

Current state (verified in code):

1. `06` `MemoryAffectReplayEngine` calls injected `MemoryFormationPath` + `ReplayCandidateSelector`. In composition those are `FirstVersionMemoryFormationPath` (returns `()` when binding context is None, else copies `binding_context.content` into one episodic item; the `05` feeling only rides as `affect_tag`) and `FirstVersionReplayCandidateSelector` (every item -> `forced_consolidation=True`, constant `priority_hint=0.9`).
2. `PersistedExperienceRecord` already supports `with_embedding` and the store already does bounded cosine `search_similar`; the `SemanticStoreBackedDirectedMemoryCandidateProvider` ranks every embedded record regardless of source. `_record_tier` maps by `continuity_kind`.
3. `RuntimeHandle.tick` already has `_persist_experience` (carry the `15` writeback result into the store, embed-at-write) and `_checkpoint_continuity`. There is no equivalent carry for `06` memory; `06` memory is never persisted.
4. The memory stage result (`MemoryAffectReplayStageResult`) publishes the owner `MemoryFormationState` (memory items + replay candidates), which is what the carry seam will read.

Gap: `06` formation is fabricated and `06` memory is non-durable. The substrate to fix both exists and is unused by `06`.

## 3. Target Architecture

### 3.1 Owner-owned affect-grounded formation (`helios_v2.memory`)

`06` stays the memory owner and never imports persistence/embedding. The formation path moves from composition into the owner:

```
@dataclass
class AffectGroundedMemoryFormationPath(MemoryFormationPath):
    def form_memory_items(self, feeling_state, binding_context, mismatch_evidence, config, tick_id):
        if binding_context is None:
            return ()
        # The affect_tag is the REAL 05 feeling vector (feeling_state.feeling), not a constant.
        family = "autobiographical" if <mismatch present / high-tension> else "episodic"  # owner mapping
        return (AffectTaggedMemoryItem(
            memory_id=f"memory:runtime:{tick_id}",
            family=family,
            source_feeling_state_id=feeling_state.state_id,
            affect_tag=feeling_state.feeling,
            content=binding_context.content,
            binding_context_id=binding_context.context_id,
            tick_id=tick_id,
        ),)
```

The owner-owned family mapping is deterministic and bounded; it reads only the real feeling vector and explicit evidence. (Item content still comes from the binding context; richer feeling-driven content shaping is future scope §8.)

### 3.2 Owner-owned salience gate (`helios_v2.memory`)

The replay selector becomes the consolidation salience gate, owned by `06`:

```
@dataclass
class SalienceGatedReplayCandidateSelector(ReplayCandidateSelector):
    consolidation_threshold: float = 0.5          # under consolidation_policy (P5-learnable)
    arousal_weight: float = 0.5                    # under replay_priority_policy
    tension_weight: float = 0.3
    pain_weight: float = 0.2
    mismatch_weight: float = 0.6

    def select_candidates(self, memory_items, feeling_state, mismatch_evidence, config):
        f = feeling_state.feeling
        affect_intensity = clamp(arousal_weight*f.arousal + tension_weight*f.tension + pain_weight*f.pain_like, 0, 1)
        mismatch = mismatch_evidence.mismatch_score if mismatch_evidence else 0.0
        salience = clamp(max(affect_intensity, mismatch_weight*mismatch), 0, 1)   # owner gate signal
        forced = salience >= consolidation_threshold
        reasons = (...derived from which term dominated, using the existing ReplayReason taxonomy...)
        return tuple(MemoryReplayCandidate(..., forced_consolidation=forced, priority_hint=round(salience,4), replay_reasons=reasons) for item in memory_items)
```

Key behavior: a flat low-affect tick with no mismatch yields `salience < threshold`, so `forced_consolidation=False` for every candidate, so the carry seam persists nothing that tick. A high-arousal/high-tension/high-pain tick or a high-mismatch tick clears the gate. Deterministic given inputs. `replay_reasons` must stay within the existing `ReplayReason` literal taxonomy (`high_affect_intensity`, `unresolved_tension_or_discomfort`, `prediction_mismatch_or_surprise`).

### 3.3 Additive durable-record discriminator (`helios_v2.persistence`)

`PersistedExperienceRecord` gains two additive fields, both default-preserving:

```
record_kind: str = "experience_writeback"     # 15 stream keeps this default => existing records byte-for-byte
metadata: Mapping[str, str] = <empty frozen>  # opaque owner-tagged provenance (e.g. family, affect summary)
```

- `record_kind` is an opaque stored string; the store never interprets it for meaning. Affect-memory records carry `record_kind="affect_memory"`.
- `metadata` is a frozen string->string map (like `linkage`), validated the same way; carries `06` provenance that does not fit the flat fields (e.g. `{"memory_family": "episodic", "source_feeling_state_id": "..."}`). Optional and defaulted so `15` records are unaffected.
- SQLite: add two nullable columns (`record_kind TEXT`, `metadata TEXT` JSON). On re-open of an older file the columns may be absent; `_row_to_record` must treat a missing/NULL `record_kind` as the default `"experience_writeback"` and missing `metadata` as empty. `initialize()` uses `CREATE TABLE IF NOT EXISTS` plus an additive `ALTER TABLE ADD COLUMN` guarded by a column-existence check (PRAGMA table_info), so an existing R33/R34 file upgrades in place without data loss.

### 3.4 Owner-neutral memory carry seam (`helios_v2.composition`)

A `MemoryRecordBridge` (mirrors `ExperienceRecordBridge`) projects the published `06` stage result into durable records:

```
@dataclass
class MemoryRecordBridge:
    def build_records(self, memory_stage_result, tick_id) -> tuple[PersistedExperienceRecord, ...]:
        state = memory_stage_result.state
        worthy = {c.memory_id for c in state.replay_candidates if c.forced_consolidation}
        records = []
        for item in state.memory_items:
            if item.memory_id not in worthy:
                continue                                   # persist ONLY consolidation-worthy items
        records.append(PersistedExperienceRecord(
                record_id=f"affect-memory:{item.memory_id}",
                tick_id=tick_id,
                continuity_kind=item.family,               # episodic/autobiographical -> tier mapping
                outcome_class="affect_memory",
                source_outcome_kind="memory_item",
                source_outcome_id=item.memory_id,
                writeback_status="formed",
                summary=<bounded content summary from item.content>,
                requested_effect_summary="",
                applied_effect_summary="",
                reason_trace=(...from the candidate's replay_reasons...),
                linkage={"source_feeling_state_id": item.source_feeling_state_id, ...},
                record_kind="affect_memory",
                metadata={"memory_family": item.family},
            ))
        return tuple(records)
```

It reads only published stage-result values and re-derives no decision (it does not recompute the gate; it filters by the `forced_consolidation` flag `06` already set). The `RuntimeHandle.tick` gains `_persist_memory(result)` mirroring `_persist_experience`: when a `memory_record_bridge` + store + `embed_record` are present, build records, embed each at write, append. Embedding/append failures propagate (hard stop). `15` persistence is untouched and runs in the same tick.

### 3.5 Recall (mostly free; tier mapping by family)

`SemanticStoreBackedDirectedMemoryCandidateProvider` already ranks every embedded record by cosine and emits candidates, so affect-memory records are recalled automatically once persisted with an embedding. The only change is `_record_tier`: today it keys on `continuity_kind` against an autobiographical set. For affect-memory records the stored `continuity_kind` is the `06` family (`episodic`/`autobiographical`), which already maps correctly (autobiographical -> autobiographical tier; episodic -> mid_term). No new branch is required if the family values are chosen to fall through the existing mapping; an explicit family-aware mapping is added for clarity and tested. No directed-retrieval contract changes; the candidate `source` distinguishes provenance for diagnostics.

### 3.6 Opt-in selection in assembly

`assemble_runtime` already selects semantic vs recency vs default. R45 reuses the same semantic-memory opt-in (store + embedding both present):

1. semantic-memory assembly -> `06` assembled with `AffectGroundedMemoryFormationPath` + `SalienceGatedReplayCandidateSelector`; `RuntimeHandle` wired with `MemoryRecordBridge` + the memory carry seam (embed-at-write reusing the existing `_embed_text`).
2. recency-only persistent or default assembly -> the existing `FirstVersion*` formation/selector and no memory carry seam (unchanged).
3. affect-memory requested without both store and embedding -> `CompositionError`, consistent with R34.

No new public assembly flag: the trigger is the existing `embedding_gateway` + `experience_store` opt-in, exactly like R35.

### 3.7 Default rollout

Default-off. Default and recency-only assemblies keep `FirstVersionMemoryFormationPath`/`FirstVersionReplayCandidateSelector` and persist no `06` memory. Only the semantic-memory assembly gains real formation, the salience gate, and durable affect-memory.

## 4. Data Structures

1. `AffectGroundedMemoryFormationPath` (in `helios_v2.memory`) - implements `MemoryFormationPath`; forms items from the real `05` feeling vector; owner-owned family mapping.
2. `SalienceGatedReplayCandidateSelector` (in `helios_v2.memory`) - implements `ReplayCandidateSelector`; owns the consolidation salience gate; sets `forced_consolidation`/`priority_hint` from the real feeling + mismatch.
3. `PersistedExperienceRecord` additive fields (in `helios_v2.persistence.contracts`): `record_kind: str = "experience_writeback"`, `metadata: Mapping[str, str] = {}` (frozen). `with_sequence`/`with_embedding` carry them through. No change to the existing required fields.
4. `MemoryRecordBridge` (in `helios_v2.composition.bridges`) - owner-neutral projection of consolidation-worthy memory items into durable records; imports the `PersistedExperienceRecord` type only; no embedding import (embedding via injected callable).
5. No new cross-owner contract in memory or directed-retrieval. `MemoryFormationState`, `Rapid... n/a`, `MemoryRetrievalCandidate`, `ThoughtWindowBundle` unchanged.

## 5. Module Changes

1. `helios_v2/src/helios_v2/memory/engine.py`: add `AffectGroundedMemoryFormationPath` and `SalienceGatedReplayCandidateSelector` (the salience gate and family mapping live here).
2. `helios_v2/src/helios_v2/memory/__init__.py`: export both.
3. `helios_v2/src/helios_v2/persistence/contracts.py`: add additive `record_kind` + `metadata` to `PersistedExperienceRecord` with default-preserving validation; thread through `with_sequence`/`with_embedding`.
4. `helios_v2/src/helios_v2/persistence/engine.py`: persist/read the two columns (additive ALTER guarded by PRAGMA; NULL -> defaults); make `_record_tier` family-aware (still a transport mapping by stored kind).
5. `helios_v2/src/helios_v2/composition/bridges.py`: add `MemoryRecordBridge`; in assembly bind the affect-grounded formation path and salience-gated selector under the semantic opt-in.
6. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: select the owner-owned formation/selector under the semantic opt-in; add `memory_record_bridge` to `RuntimeHandle` and a `_persist_memory` carry seam in `tick`; `CompositionError` if requested without store+embedding.

## 6. Migration Plan

1. All new code and record fields are additive. The default `FirstVersion*` formation/selector path is unchanged and remains the default.
2. `record_kind`/`metadata` default to the `15` values, so existing R33/R34 stores and records are byte-for-byte unchanged on read; an existing SQLite file gains the columns via guarded `ALTER TABLE` with no data loss.
3. No memory or directed-retrieval contract changes, so gating/thought/recall consume memory exactly as before; only the candidate set gains real persisted affect-memory when the opt-in is on.
4. No stage-order change; `06` is the same stage with different injected collaborators, and persistence is an after-tick carry like `15`.

## 7. Failure Modes and Constraints

1. No binding context this tick: formation returns `()` (defined outcome), nothing to gate or persist. Not a failure.
2. Low-salience tick (gate not cleared, no mismatch): items may form but none are `forced_consolidation`, so the carry seam persists nothing. Defined outcome, not a failure.
3. Embedding failure or store durability failure while affect-memory is enabled: propagate as a hard stop (`EmbeddingError`/`PersistenceError`). No non-persistent fallback, no fabricated memory.
4. Affect-memory requested without both store and embedding: `CompositionError` at assembly (consistent with R34).
5. The salience gate output is clamped to `[0,1]`; `priority_hint` stays within the `MemoryReplayCandidate` `[0,1]` contract; `replay_reasons` stay within the existing `ReplayReason` taxonomy.
6. The persistence owner gains no cognitive policy: `record_kind`/`metadata` are opaque; the tier mapping is by stored family/kind only.
7. No dedup/merge in this slice; growth is bounded by the salience gate only.
8. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. Memory facts travel through the `06` `MemoryFormationState`, the durable `PersistedExperienceRecord`, and the `10` `MemoryRetrievalCandidate`/`ThoughtWindowBundle`. The candidate `source` field (`experience_store_semantic`) and the record `record_kind`/`metadata` carry provenance for read-only diagnostics; no emission is added in `06`, persistence, or the carry seam.

## 9. Validation Strategy

Network-free, deterministic, using a deterministic fake embedding (hashed-bucket) and the in-memory + SQLite store backends.

1. `test_memory_engine.py` (extend):
   - `AffectGroundedMemoryFormationPath`: the formed item's `affect_tag` equals the real injected `05` feeling vector (not a constant); deterministic; no binding context -> `()`.
   - `SalienceGatedReplayCandidateSelector`: a high-arousal/high-tension feeling -> `forced_consolidation=True`, `priority_hint` reflecting the affect intensity; a flat low-affect feeling with no mismatch -> `forced_consolidation=False`; a high-mismatch evidence -> forced even with flat feeling; `replay_reasons` within taxonomy; `priority_hint` in `[0,1]`.
   - determinism: identical feeling + mismatch -> identical gate output.
2. `test_persistence_contracts.py` / `test_persistence_engine.py` (extend):
   - `PersistedExperienceRecord` with `record_kind="affect_memory"` + `metadata` round-trips through `with_sequence`/`with_embedding`.
   - SQLite append + re-open returns the same `record_kind`/`metadata`; an existing record without the columns (simulated NULL) reads back as `record_kind="experience_writeback"`, empty metadata.
   - `_record_tier` maps `episodic` family -> mid_term, `autobiographical` -> autobiographical.
3. `test_runtime_composition.py` (extend):
   - semantic-memory assembly: a high-salience tick persists an `affect_memory` record (assert store count rose and the record carries `record_kind="affect_memory"` + an embedding); the salient memory is then recalled through `10` (appears in the thought-window bundle with `source="experience_store_semantic"`).
   - restart: a second `assemble_runtime` against the same SQLite file recalls the prior session's affect-memory.
   - a low-salience-only sequence persists no affect-memory (store affect_memory count stays 0) while `15` continuity still persists in the same tick (assert both: `15` count rose, affect_memory count 0).
   - composition error when affect-memory wiring is requested without both store and embedding.
   - default assembly and recency-only persistent assembly: `06` keeps constant behavior, no affect-memory persisted; existing tests unmodified.
   - an embedding-failure provider makes an affect-memory-enabled tick hard-stop (no non-persistent fallback).
4. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_memory_engine.py helios_v2/tests/test_persistence_engine.py -q
```
