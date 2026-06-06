# Requirement 52 - Workspace multiplicity from recalled affect-memory replay (design)

## 1. Design Overview

R52 gives the `07` workspace a genuine multiplicity to arbitrate by having the `06` memory owner surface **recalled prior affect-memories** as additional replay candidates alongside the current-tick formed memory. "Replay-candidate surfacing" is already `06`'s stated responsibility; resurfacing a stored memory *is* replay. Today `06` surfaces only the one memory it just formed, so the workspace competes over a single candidate and R46/R47/R48 never exercise real competition/ignition/activation.

The change is three pieces, no contract change to any consumed/produced first-class contract:

1. A new `06`-owned recalled-replay path inside `MemoryAffectReplayEngine`: given raw recalled facts from an injected source, it re-forms each into an `AffectTaggedMemoryItem` (preserving the recalled `memory_id`, stored `family`, and original `affect_tag`, anchored to the current feeling state + binding context) plus a non-`forced_consolidation` `MemoryReplayCandidate` whose `priority_hint` comes from an owner-owned mapping over recall relevance and recalled affect intensity. These are appended to the published `MemoryFormationState`.
2. A narrow injected `RecalledMemoryProvider` protocol returning bounded `RecalledMemoryFact`s. The `06` owner imports no persistence/embedding owner.
3. A composition-owned `StoreBackedRecalledMemoryProvider` that semantically recalls `affect_memory`-kind records from the durable store (embedding the current binding-context content, reusing the R34 `search_similar`) and reconstructs each recalled affect vector from the affect-memory record's metadata. To make reconstruction possible, the R45 `MemoryRecordBridge` is extended to additionally write the affect vector into the record's opaque `metadata` (a string-encoded additive extension; no persistence contract change).

Once a prior consolidation-worthy affect-memory exists in the store, a later tick's `06` emits >1 replay candidate, so `07` competition (R46), `08` ignition (R47), and `09` activation (R48) all run over real multiplicity — fully exercised end to end, no change to those owners.

Scope boundary (honest): R52 sources multiplicity from *recalled past memory*, not from concurrent current-tick contents (multiple stimuli in one tick is R54 territory, gated on de-shimming the `02`/`03` projection). A cold store yields zero recalled candidates, so the single-candidate behavior is unchanged until a prior affect-memory exists.

## 2. Current State and Gap

Verified in code:

1. `MemoryAffectReplayEngine.record_state` calls `formation_path.form_memory_items(...)` (the R45 `AffectGroundedMemoryFormationPath` forms exactly one item from one binding context) then `replay_selector.select_candidates(...)` (the R45 `SalienceGatedReplayCandidateSelector` builds one candidate per item), so the state carries one replay candidate.
2. `WorkspaceCompetitionRuntimeStage` -> `SalienceWeightedWorkspaceCompetitionPath.build_candidate_set` iterates `replay_candidates`, so it competes over that single candidate; `BoundedAttentionRetentionPath` retains top-K of one; `IgnitionFocalSelectionPolicy` ignites the only candidate; `_workspace_activation` reports its score.
3. The durable store holds `affect_memory`-kind records (R45) with `metadata={"memory_family": family}` and a content summary, recalled semantically by R34 `search_similar` — but only into the `10` thought window, never into `07`. The affect vector is **not** persisted, so a recalled memory cannot retain its felt charge.
4. `MemoryFormationState`/`_validate_memory_items`/`_validate_replay_candidates` require: each item's `binding_context_id == current binding context id`; each candidate's `memory_id` is a published item and its `source_feeling_state_id == current feeling state id`.

Gap: `06` surfaces only the current memory; recalled memories never reach `07`; and even if surfaced, their affect is not persisted.

## 3. Target Architecture

### 3.1 New contracts (`helios_v2.memory.contracts`)

```
@dataclass(frozen=True)
class RecalledMemoryFact:
    """Raw recalled prior-affect-memory fact supplied to the 06 owner by an injected source.
    Bounded; carries no priority (the 06 owner computes that)."""
    memory_id: str
    family: MemoryFamily
    summary: str
    recall_similarity: float          # [0,1], cosine relevance to the current context
    affect: InteroceptiveFeelingVector # the recalled memory's original felt affect
    def __post_init__(self):
        # non-empty memory_id/summary; family in taxonomy; recall_similarity in [0,1]

@runtime_checkable
class RecalledMemoryProvider(Protocol):
    def recall(
        self,
        binding_context: MemoryBindingContext,
        feeling_state: InteroceptiveFeelingState,
    ) -> tuple[RecalledMemoryFact, ...]:
        """Return bounded recalled prior-affect-memory facts relevant to the current context.
        Raw facts only; no priority, no item/candidate construction. Empty when none."""
```

### 3.2 Owner-owned recalled-replay surfacing (`helios_v2.memory.engine`)

`MemoryAffectReplayEngine` gains an optional `recalled_memory_provider: RecalledMemoryProvider | None = None`. In `record_state`, after the current-tick formation + selection (unchanged), when the provider is present and a binding context exists:

```
recalled_facts = self.recalled_memory_provider.recall(binding_context, feeling_state)
extra_items, extra_candidates = self._surface_recalled(recalled_facts, feeling_state, binding_context, current_memory_ids)
memory_items = current_items + extra_items
replay_candidates = current_candidates + extra_candidates
```

`_surface_recalled` is owner logic (the priority mapping lives here):

```
def _surface_recalled(self, facts, feeling_state, binding_context, taken_ids):
    items, candidates = [], []
    for fact in facts:
        if fact.memory_id in taken_ids:      # never shadow the current-tick item
            continue
        item = AffectTaggedMemoryItem(
            memory_id=fact.memory_id,         # preserve original id
            family=fact.family,               # preserve stored family
            source_feeling_state_id=feeling_state.state_id,   # anchor to current tick (invariant)
            affect_tag=fact.affect,           # preserve original felt affect
            content=MemoryContentPacket(content_kind="recalled_affect_memory",
                                        summary_ref=fact.summary, context_ref=None, salient_tokens=()),
            binding_context_id=binding_context.context_id,    # current surfacing context (invariant)
            tick_id=feeling_state.tick_id,
        )
        priority = self._recalled_priority(fact)
        candidates.append(MemoryReplayCandidate(
            candidate_id=f"recalled-candidate:{feeling_state.tick_id}:{fact.memory_id}",
            memory_id=fact.memory_id, family=fact.family,
            source_feeling_state_id=feeling_state.state_id,
            replay_reasons=self._recalled_reasons(fact),
            forced_consolidation=False,       # replayed, not newly consolidated
            priority_hint=priority,
        ))
        items.append(item); taken_ids.add(fact.memory_id)
    return tuple(items), tuple(candidates)

def _recalled_priority(self, fact):
    affect_intensity = clamp(0.5*fact.affect.arousal + 0.3*fact.affect.tension + 0.2*fact.affect.pain_like)
    return clamp(self.recalled_relevance_weight * fact.recall_similarity
                 + self.recalled_affect_weight * affect_intensity)   # weights 0.6 / 0.4 (sum 1)
```

`recalled_relevance_weight`/`recalled_affect_weight` are engine fields (first-version constants under the owner config's `replay_priority_policy` category, P5-learnable). `_recalled_reasons` reuses the fixed `ReplayReason` taxonomy (`high_affect_intensity`, plus `unresolved_tension_or_discomfort` when tension/pain dominates). The existing `_validate_memory_items`/`_validate_replay_candidates` run over the combined set and all hold (recalled items carry the current binding-context id and feeling-state id; recalled candidates reference published recalled items).

### 3.3 Composition-owned store-backed provider (`helios_v2.composition.bridges`)

```
@dataclass
class StoreBackedRecalledMemoryProvider(RecalledMemoryProvider):
    embed_text: Callable[[str], tuple[float, ...]]
    store: ExperienceStore
    limit: int = 3
    max_scan: int = 256
    def recall(self, binding_context, feeling_state):
        query_text = _memory_content_summary_from_packet(binding_context.content)  # bounded projection
        if not query_text.strip():
            return ()
        query_vector = self.embed_text(query_text)
        result = self.store.search_similar(query_vector, limit=self.limit, max_scan=self.max_scan)
        facts = []
        for hit in result.hits:
            record = hit.record
            if record.record_kind != "affect_memory":
                continue
            affect = _decode_affect_vector(record.metadata.get("affect_vector"))
            if affect is None:        # legacy record without persisted affect -> not faithfully recallable
                continue
            facts.append(RecalledMemoryFact(
                memory_id=record.source_outcome_id,    # the original memory_id
                family=_family_from_record(record),    # stored family (metadata/continuity_kind)
                summary=record.summary,
                recall_similarity=clamp(hit.similarity),
                affect=affect,
            ))
        return tuple(facts)
```

It reaches the embedding owner only through the injected `embed_text` callable and the persistence owner only through the `ExperienceStore` public API (mirroring `MemoryGroundedSimilaritySource`). An embedding/store failure propagates (hard stop). A cold store / empty content / no `affect_memory` hit yields `()`.

### 3.4 Persisting the affect vector (extend the R45 carry)

`MemoryRecordBridge.build_records` adds the affect vector to the affect-memory record metadata (string-encoded, since metadata is `Mapping[str, str]`):

```
metadata = {"memory_family": item.family,
            "affect_vector": _encode_affect_vector(item.affect_tag)}   # "v,a,t,c,f,p,s" rounded
```

`_encode_affect_vector`/`_decode_affect_vector` are composition helpers (7 rounded floats joined by `,` / parsed back, returning `None` on a malformed or absent value). This is additive: existing R33/R34/R45 records without the key are simply not recall-eligible for workspace replay (they read back fine; `_decode_affect_vector(None) -> None`, the provider skips them). No persistence contract change; the SQLite `metadata` column already exists (R45).

### 3.5 Assembly wiring (`runtime_assembly.py`)

Under the semantic-memory assembly (store + embedding present), construct the provider and inject it into the `06` engine:

```
recalled_provider = (
    StoreBackedRecalledMemoryProvider(embed_text=embed_record, store=experience_store)
    if semantic_memory_enabled else None
)
memory = MemoryAffectReplayEngine(
    config=resolved_config.memory,
    formation_path=AffectGroundedMemoryFormationPath() if semantic_memory_enabled else FirstVersionMemoryFormationPath(),
    replay_selector=SalienceGatedReplayCandidateSelector() if semantic_memory_enabled else FirstVersionReplayCandidateSelector(),
    recalled_memory_provider=recalled_provider,
)
```

`embed_record` is the same embedding callable composition already builds for R34/R35. Default-off: when not semantic, `recalled_memory_provider=None` and `record_state` behaves exactly as today.

### 3.6 Default rollout

Default-off. Recalled surfacing requires the semantic assembly AND a non-cold store with at least one R52-persisted affect-memory carrying the affect vector. The default, recency-only, channel-bound-without-semantic, and offline assemblies register no provider and are byte-for-byte unchanged.

## 4. Data Structures

1. New `RecalledMemoryFact` (frozen, validated) + `RecalledMemoryProvider` protocol — `helios_v2.memory.contracts`.
2. New engine fields + `_surface_recalled`/`_recalled_priority`/`_recalled_reasons` — `helios_v2.memory.engine`.
3. New `StoreBackedRecalledMemoryProvider` + affect-vector encode/decode helpers + extended `MemoryRecordBridge.build_records` — `helios_v2.composition.bridges`.
No change to `MemoryReplayCandidate`, `AffectTaggedMemoryItem`, `MemoryFormationState`, `MemoryContentPacket`, `PersistedExperienceRecord`, `WorkspaceCandidate`, or any downstream contract.

## 5. Module Changes

1. `helios_v2/src/helios_v2/memory/contracts.py`: add `RecalledMemoryFact` + `RecalledMemoryProvider`.
2. `helios_v2/src/helios_v2/memory/engine.py`: add the optional provider field and the owner-owned recalled-replay surfacing + priority mapping.
3. `helios_v2/src/helios_v2/memory/__init__.py`: export the new contract + protocol.
4. `helios_v2/src/helios_v2/composition/bridges.py`: extend `MemoryRecordBridge` to persist the affect vector; add `StoreBackedRecalledMemoryProvider` + encode/decode helpers.
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: inject the provider into the `06` engine under the semantic assembly.

## 6. Migration Plan

1. All new code is additive; the `06` engine's provider field defaults to `None` (current behavior).
2. The affect-vector metadata is an additive key; existing store files read back unchanged and are simply not workspace-recall-eligible.
3. No stage-order change; recalled surfacing happens inside the existing `06` stage.
4. The only assembly whose behavior changes is the semantic assembly once a prior affect-memory with a persisted affect vector exists; every other assembly is byte-for-byte unchanged.

## 7. Failure Modes and Constraints

1. Cold store / empty binding context / no `affect_memory` hit / no hit carrying a decodable affect vector -> zero recalled candidates (single-candidate behavior unchanged), never a fabricated recall.
2. An embedding or store failure during recall propagates as a hard stop (consistent with the R35 novelty source); there is no silent single-candidate fallback masking a recall failure.
3. Recalled candidates are non-`forced_consolidation` and additive; the current-tick formed memory, its salience gate, and the R45 persistence carry are unchanged.
4. All existing `06` owner invariants (`_validate_memory_items`, `_validate_replay_candidates`, `MemoryFormationState.__post_init__`) run over the combined set and still fail fast.
5. The `06` owner imports no persistence/embedding owner; the mapping lives in `06`; composition owns store/embedding access and affect reconstruction.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. The recalled candidates appear as additional `MemoryReplayCandidate`s in the published `MemoryFormationState`, additional `WorkspaceCandidate`s in the `07` result, and (when a recalled memory wins) as the ignited focal content in `08` — all through existing contracts.

## 9. Validation Strategy

Network-free, deterministic, with a fake recalled provider (owner tests) and the fake embedding gateway + in-memory store (composition tests).

1. `test_memory_engine.py` (extend):
   - A fake `RecalledMemoryProvider` returning two facts -> `record_state` publishes 1 current + 2 recalled candidates; recalled items preserve original `memory_id`/`family`/`affect_tag`, are anchored to the current feeling state + binding context, and pass all `MemoryFormationState` invariants.
   - Recalled candidates are `forced_consolidation=False`; the current-tick candidate is unchanged.
   - The recalled priority mapping is monotonic in recall similarity and in affect intensity, bounded, deterministic; a high-similarity high-affect fact outranks a low one.
   - A fact whose `memory_id` equals the current item's is skipped (no shadowing).
   - No provider / empty facts / no binding context -> exactly the pre-R52 single-candidate state.
2. `test_runtime_composition.py` (extend):
   - Persist a prior affect-memory (run a high-affect tick that consolidates), then on a later tick assert the `07` `WorkspaceCompetitionStageResult` carries >1 candidate, the `08` state ignites a single focal candidate with the rest demoted to supporting context, and `09` `global_activation_level` equals the max retained score.
   - A constructed strong recalled memory (high persisted affect + high relevance) becomes the ignited focal winner over a weaker current-tick candidate.
   - Affect-vector round trip: a persisted affect-memory's metadata carries `affect_vector`, and the provider reconstructs an `InteroceptiveFeelingVector` equal (within rounding) to the originally formed affect.
   - Default assembly: still one candidate; `07`/`08`/`09` byte-for-byte as before.
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_memory_engine.py -q
```
