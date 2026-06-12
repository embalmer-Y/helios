# R84: P5 Memory-Fidelity Probe — Task Plan

**Status:** draft → in_progress (T0 done 2026-06-12)
**Owner:** 17 evaluation
**Target commit hash:** (TBD after T9)

---

## Task Breakdown

### T0. Requirements tri-pack [x] — 2026-06-12 00:55 UTC
- `requirement.md` (8.6 KB) — §1-§8 (Background / Goal / FR / NFR / Code Constraints / Impacted / Acceptance / Out-of-scope)
- `design.md` (10.1 KB) — §1-§6 (Architecture / Component / Failure Modes / Test / Migration / Risks)
- `task.md` (this file)

### T1. Read & document R10/R15 current state
- T1.1 ✓ Verified: `assemble_runtime` wires `directed_retrieval` (R10) + `experience_writeback` (R15) + `experience_store` (persistence) — see `runtime_assembly.py:1629-1677` and `:1756`
- T1.2 ✓ Verified: `_persist_experience` (runtime_assembly.py:870-891) calls `experience_store.append_records` after each tick
- T1.3 ✓ Verified: `FirstVersionExperienceWritebackRequestBridge` (bridges.py:2556) builds ExperienceWritebackRequest per tick
- T1.4 ✓ Verified: handle has `directed_retrieval_layer` + `directed_retrieval_config` + `experience_store` (need to confirm by probe)

### T2. Probe `RuntimeHandle` API for what R84 needs
- T2.1: Check `handle.directed_retrieval_layer.plan_and_select` signature
- T2.2: Check `handle.experience_store.read_recent(count)` signature
- T2.3: Check `handle.experience_store.count()` signature
- T2.4: Check what fields are in `PersistedExperienceRecord` (for source_provenance matching)

### T3. Implement real `MemoryProbe.score()`
- T3.1: Add `score(handle, jsonl_path) -> MemoryProbeResult` method
- T3.2: Implement `_issue_retrieval_probe(handle, query_text) -> bool` (using R10)
- T3.3: Implement `_compute_writeback_persistence(handle, state_records) -> float` (using experience_store)
- T3.4: Compute per-state A3 + overall A3 + sub-metrics
- T3.5: Fail-soft wrappers (no engine, no store, exception in probe)

### T4. Update R83 CLI / LongRunner to pass `handle` to MemoryProbe
- T4.1: `LongRunner.run()` returns `handle` (or accepts a probe hook)
- T4.2: `r83/__main__.py` constructs `MemoryProbe(handle=handle)` and calls `score(handle, jsonl_path)`
- T4.3: `report_builder.py` shows A3 sub-metrics in r83_report.md

### T5. Write ≥5 unit tests
- T5.1: `test_memory_probe_returns_real_submetrics`
- T5.2: `test_memory_probe_per_state_breakdown`
- T5.3: `test_memory_probe_failsoft_no_engine`
- T5.4: `test_memory_probe_recall_hit_rate_zero`
- T5.5: `test_memory_probe_latency_score_inverse`
- T5.6: `test_memory_probe_in_r83_smoke` (smoke test with noop + no-judge)

### T6. Smoke test: A3 != 0.5 in r83_report.md
- T6.1: `python -m helios_v2.tests.r83 --duration 0.5 --no-judge --output-dir /tmp/r84_smoke`
- T6.2: Verify r83_report.md A3 row shows real sub-metrics
- T6.3: Verify reasoning is not "not-implemented"

### T7. Doc sync (4 files)
- T7.1: `docs/requirements/index.md` — append R84 row
- T7.2: `docs/OWNER_GUIDE.md` — §3.8.5 new section + status header
- T7.3: `docs/ARCHITECTURE_BOUNDARIES.md` — §10.f new section + status header
- T7.4: `docs/PROGRESS_FLOW.zh-CN.md` — R84 索引块 + status

### T8. Real LLM 10-min run
- T8.1: `python -m helios_v2.tests.r83 --duration 10 --output-dir /tmp/r84_10min`
- T8.2: Verify A3 != 0.5 with real sub-metrics
- T8.3: Verify verdict >= `human-like` (R83 baseline) or better

### T9. Regression + commit
- T9.1: `pytest tests/` — must be ≥ 985 passed, 0 regressions
- T9.2: `git commit -m "R84: ..."` + `git push -f origin aggressive-radical-persona-no-theater`
- T9.3: Update HEARTBEAT.md + MEMORY.md + memory/2026-06-12.md

---

## Status

| Task | Status | Date | Notes |
|---|---|---|---|
| T0 | done | 2026-06-12 00:55 | Tri-pack created |
| T1 | done | 2026-06-12 00:50 | R10/R15 already wired |
| T2-T9 | pending | — | — |

---

## Exit Criteria

- T9.1: `pytest tests/` returns ≥ 985 passed, 0 regressions
- T8.2: A3 in r83_report.md has real sub-metric numbers
- T8.3: Verdict is `human-like` (R83 baseline maintained or improved)
- T7: 4 doc files synced
- T9.2: Commit pushed to origin
