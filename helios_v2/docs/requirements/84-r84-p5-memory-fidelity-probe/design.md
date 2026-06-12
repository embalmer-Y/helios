# R84: P5 Memory-Fidelity Probe — Design

**Status:** draft (sibling of R83 design)
**Owner:** 17 evaluation (MemoryProbe in `tests/r83/`)
**Last updated:** 2026-06-12

---

## 1. Architecture

R84 replaces the A3 stub in `src/helios_v2/tests/r83/memory_probe.py` with a real implementation that:

```
┌────────────────────────────────────────────────────────────────────┐
│                         R83 LongRunner                              │
│   (40 ticks, 8 state blocks × 5 variants)                          │
└────────────┬─────────────────────────────────────────┬──────────────┘
             │ emits records                            │ owns handle
             ▼                                          ▼
  ┌──────────────────────┐                  ┌──────────────────────┐
  │  r83_longrun.jsonl   │                  │ RuntimeHandle        │
  │  (40 ticks, llm_     │                  │   ├─ directed_       │
  │   output, hormones,  │                  │   │  retrieval_layer  │
  │   remember_this)     │                  │   │  (R10)            │
  └────────────┬─────────┘                  │   ├─ experience_     │
               │                            │   │  writeback_layer  │
               │ A3 phase: post-run         │   │  (R15)            │
               ▼                            │   └─ experience_     │
  ┌──────────────────────┐                  │     store (P5)       │
  │  MemoryProbe.score() │ ◄──── reads ─────┴──────────────────────┘
  │  (R84 NEW)           │
  │  - 5 retrieval       │
  │    probes (R10)      │ ◄─── issues probes via handle ───► directed_retrieval
  │  - read_recent()     │ ◄─── reads experience_store
  │  - per-state A3      │
  └────────────┬─────────┘
               │
               ▼
  ┌──────────────────────┐
  │ MemoryProbeResult    │
  │  score: 0.0-1.0      │
  │  retrieval_latency_ms│
  │  recall_hit_rate     │
  │  writeback_          │
  │   persistence_rate   │
  └──────────────────────┘
```

## 2. Component Design

### 2.1 `MemoryProbe.score(handle, jsonl_path)` — Real Implementation

**Inputs:**
- `handle`: `RuntimeHandle` from the R83 LongRunner
- `jsonl_path`: `Path` to the 40-tick JSONL trail

**Algorithm:**

```python
def score(self, handle, jsonl_path):
    # Step 1: Load 40 ticks
    records = load_ticks(jsonl_path)
    records_by_state = group_by_state(records)

    # Step 2: For each of 8 state blocks, issue 1 retrieval probe
    per_state_results = {}
    for state_id, state_records in records_by_state.items():
        # Use the FIRST tick's stimulus as the probe query
        first_record = state_records[0]
        probe_query = first_record['stimulus_text']

        # Step 2a: Retrieval probe
        t0 = time.time()
        retrieval_hit = self._issue_retrieval_probe(handle, probe_query)
        latency_ms = (time.time() - t0) * 1000.0

        # Step 2b: Recall hit rate (over the 5 ticks in this block)
        recall_hits = sum(
            1 for r in state_records
            if r['llm_output'].get('remember_this', False)
        )
        recall_hit_rate = recall_hits / len(state_records)

        # Step 2c: Writeback persistence (over all 40 records)
        writeback_persistence_rate = self._compute_writeback_persistence(
            handle, state_records
        )

        # Step 2d: Per-state A3 score
        latency_score = 1.0 - min(latency_ms / 1000.0, 1.0)
        per_state_a3 = (
            0.4 * recall_hit_rate +
            0.3 * writeback_persistence_rate +
            0.3 * latency_score
        )
        per_state_results[state_id] = {
            'a3': per_state_a3,
            'latency_ms': latency_ms,
            'recall_hit_rate': recall_hit_rate,
            'writeback_persistence_rate': writeback_persistence_rate,
        }

    # Step 3: Aggregate to single A3 axis score
    overall_a3 = mean(per_state_results[s]['a3'] for s in per_state_results)
    return MemoryProbeResult(
        score=overall_a3,
        per_state=per_state_results,
        retrieval_latency_ms=mean(...),
        recall_hit_rate=mean(...),
        writeback_persistence_rate=mean(...),
        reasoning="real-probe: 5 retrieval probes + experience_store scan"
    )
```

### 2.2 `_issue_retrieval_probe(handle, query_text)`

The R10 path is operational inside the runtime, but `RuntimeHandle` does NOT expose `directed_retrieval_layer` as a public field (it's held by the kernel via the `DirectedRetrievalRuntimeStage`). The cleanest path for R84 is to **construct a fresh R10 query using the public R10 path API + a `StoreBackedDirectedMemoryCandidateProvider` over the same experience_store**. This tests the full R10 + persistence stack end-to-end without coupling to the per-tick stage firing logic.

**Implementation (with correct field names verified from contracts.py):**
```python
def _issue_retrieval_probe(self, handle, query_text):
    from helios_v2.directed_retrieval import (
        FirstVersionDirectedRetrievalPath,
        RetrievalRequest,
        DirectedRetrievalConfig,
    )
    from helios_v2.thought_gating.contracts import SelectedStimulusSummary
    from helios_v2.persistence import StoreBackedDirectedMemoryCandidateProvider

    # Build a minimal RetrievalRequest (bypasses gate, but exercises R10 path)
    request = RetrievalRequest(
        request_id=f"r84-probe-{query_text[:20].replace(' ', '_')}",
        source_gate_result_id="r84-memory-probe",  # synthetic gate-id
        source_continuation_active=False,
        compact_stimuli=(
            SelectedStimulusSummary(
                stimulus_id=query_text[:40],
                source_kind="r84_memory_probe",
                source_channel_id="r84-memory-probe",
                stimulus_intensity=0.5,
            ),
        ),
        recall_intent=query_text,
        selected_memory_refs=(),
        target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
        limit=10,
        tick_id=None,
    )
    # Use R10 path directly with store-backed provider
    path = FirstVersionDirectedRetrievalPath()
    provider = StoreBackedDirectedMemoryCandidateProvider(
        store=handle.experience_store,
    )
    config = DirectedRetrievalConfig(
        max_hits_per_tier=10,
        max_short_term_context=10,
        retrieval_bootstrap_id="r84-memory-probe",
        mandatory_learned_parameters=(
            "retrieval_planning_policy",
            "tier_selection_policy",
            "thought_window_shaping_policy",
        ),
    )
    plan, bundle = path.plan_and_select(request, provider, config)
    return _bundle_contains_text(bundle, query_text)
```

**Key insight**: The R10 path's `plan_and_select` is **decoupled from the gate-firing logic**; it only requires a `RetrievalRequest` and a `DirectedMemoryCandidateProvider`. By providing a `StoreBackedDirectedMemoryCandidateProvider(handle.experience_store)`, we get back a `ThoughtWindowBundle` with the real persisted experience records as candidates. We then check whether the probe query text appears in any candidate's `summary` (a simple substring match is enough for a stub-grade probe — if any of the 4 tier buckets' `*_hits` contains a candidate whose `summary` contains the probe text, it's a hit).

### 2.3 `_compute_writeback_persistence(handle, state_records)`

Use the runtime's `experience_store` to count how many records correspond to `remember_this=True` ticks.

```python
def _compute_writeback_persistence(self, handle, state_records):
    remember_count = sum(
        1 for r in state_records
        if r['llm_output'].get('remember_this', False)
    )
    if remember_count == 0:
        return 0.0  # No claims to verify

    # Count records in experience_store whose source_outcome_id
    # corresponds to a remember_this=True tick
    persisted_records = handle.experience_store.read_recent(limit=200)
    # Each record has source_provenance with source_request_id
    # matching a tick; we count overlaps

    # Simple proxy: ratio of stored records to total ticks
    # (more sophisticated matching is R85)
    stored_for_state = sum(
        1 for record in persisted_records
        if any(
            str(r['tick_id']) in record.source_provenance.get('source_request_id', '')
            for r in state_records
        )
    )
    return min(stored_for_state / max(remember_count, 1), 1.0)
```

### 2.4 R83 CLI Integration

Modify `r83/__main__.py`:
```python
# Was: a3 = 0.5  (stub)
# Now:
memory_probe = MemoryProbe(handle=handle)
probe_result = memory_probe.score(
    handle=handle,
    jsonl_path=output_dir / "r83_longrun.jsonl",
)
a3 = probe_result.score
```

The `report_builder.py` updates the A3 row to show sub-metrics.

---

## 3. Failure Modes

| Failure | Detection | Response |
|---|---|---|
| `handle.directed_retrieval_layer` is None | hasattr check | return partial result, A3 = 0.5, reasoning "no-r10-engine" |
| `handle.experience_store` is None | hasattr check | partial result, omit writeback sub-metric |
| Retrieval probe raises exception | try/except | that state's A3 = 0.5, reasoning "probe-failed: {exc}" |
| experience_store.append_records failed (rare) | log to report | partial result with sub-metric=None |
| All 8 probes fail | result.reasoning | A3 = 0.5 fallback (same as stub), but reasoning is different |

---

## 4. Test Plan

| Test | What it verifies |
|---|---|
| `test_memory_probe_returns_real_submetrics` | score() returns MemoryProbeResult with non-None sub-metrics on a real handle |
| `test_memory_probe_per_state_breakdown` | 8 per-state A3 scores, not just one |
| `test_memory_probe_failsoft_no_engine` | handle without directed_retrieval → 0.5 with "no-r10-engine" reason |
| `test_memory_probe_recall_hit_rate_zero` | block where persona never said remember_this → recall_hit_rate=0.0, A3 still computed |
| `test_memory_probe_latency_score_inverse` | latency > 1s → latency_score=0.0 |
| `test_memory_probe_in_r83_smoke` | R83 smoke test (real LLM, 0.5 min) produces A3 != 0.5 in r83_report.md |

---

## 5. Migration Path

R84 is **additive + replacement**:

1. **R84 ships**: stub `MemoryProbe.score()` replaced with real impl
2. **A3 row in r83_report.md**: now shows real sub-metric numbers
3. **No data migration**: R83's `--no-judge --noop` smoke test still works (uses noop gateway, no experience_store)
4. **Real LLM run**: now produces real A3 numbers
5. **R85+** can now consume A3 numbers to update `mandatory_learned_parameters`

---

## 6. Risks

1. **R10 retrieval engine's internal `RetrievalRequest` API is complex** — 8+ required fields. We may need a minimal helper to synthesize a valid `RetrievalRequest` from just a query string.
2. **experience_store may be empty for first 5 ticks** — writeback is per-tick, so it takes ~5 ticks to populate. R84 reads after the 40-tick run completes, so this is safe.
3. **Per-tick `source_provenance` may not contain the stimulus text** — we may need to use `request_id` matching instead. R85 can improve the source_provenance schema.
4. **Latency measurement may include 5-30s for first call** — first call often includes import overhead. We'll use the SECOND call's latency for the score.
5. **The 8 state probes may not all hit the same experience_store** — if the experience_store is per-handle, all 8 probes hit the same store. If it's per-runtime-profile, we need to be careful. R84 assumes per-handle (R78 default).
