# Requirement 99 — Emotion Validation Probe (tasks)

> Status: draft. Dependency: R91–R98 + R88/R89/R90 (tests-only, no runtime dependency).

## 1. Slice Dependency Graph

```
R96 real semantic embedding ✓
  ↓
R97 Chinese appraisal grounding ✓
  ↓
R98 post-LLM appraisal adjustment + hormone prompt coaching ✓
  ↓
R99 emotion validation probe (tests-only, W4 formalization)
  ↓
R100+ dual-track memory (P5, future)
```

## 2. Task Breakdown

### T1 — Probe core: data model + metrics computation

**Goal**: Implement `emotion_validation_probe.py` with `VisitorFixture`, `FixtureResult`, `EmotionValidationConfig`, `EmotionValidationReport`, `DEFAULT_VISITOR_FIXTURES`, and `run_emotion_validation_probe(handle_factory, config)`.

**Sub-tasks**:
1. **1.1** Define `VisitorFixture` (frozen dataclass) with `text`, `valence_category`, `valence_sign`.
2. **1.2** Define `FixtureResult` (frozen dataclass) with per-fixture outcome fields.
3. **1.3** Define `EmotionValidationConfig` (frozen dataclass) with config fields + `DEFAULT_VISITOR_FIXTURES`.
4. **1.4** Define `EmotionValidationReport` (dataclass) with 4 metric fields + `report_usable` property.
5. **1.5** Implement `run_emotion_validation_probe(handle_factory, config)`:
   - Build production assembly via `handle_factory` (SQLite + R42 checkpoint + semantic + R98 adjuster).
   - Inject `SequenceExternalSignalSource` with visitor fixtures as per-tick external stimuli.
   - Inject fake-LLM gateway (or real LLM via `llm_gateway_factory`).
   - Run N ticks, collect per-tick `04`/`11`/`10`/`13` stage results.
   - Compute `FixtureResult` per visitor fixture (match tick to fixture by timing).
   - Compute 4 aggregate metrics from fixture results.
6. **1.6** Implement `_compute_cortisol_valence_separation(fixture_results)`.
7. **1.7** Implement `_compute_thought_content_grounding(fixture_results)`.
8. **1.8** Implement `_compute_memory_recall_relevance(stage_results_by_tick)`.
9. **1.9** Implement `_compute_reply_loop_closure(fixture_results)`.
10. **1.10** Implement deterministic fake-LLM gateway `_FakeEmotionThoughtProvider`.

**Files**: `tests/r99_emotion_validation_probe/emotion_validation_probe.py` (NEW).

### T2 — Package init: exports + sys.path

**Goal**: Create `__init__.py` with exports mirroring R88/R89/R90 pattern.

**Sub-tasks**:
1. **2.1** Add `tests/` to `sys.path` (sibling import resolution).
2. **2.2** Export `VisitorFixture`, `FixtureResult`, `EmotionValidationConfig`, `EmotionValidationReport`, `DEFAULT_VISITOR_FIXTURES`, `run_emotion_validation_probe`.

**Files**: `tests/r99_emotion_validation_probe/__init__.py` (NEW).

### T3 — R89 additive integration

**Goal**: Add `emotion_validation_probe` parameter to `evaluate_turing` and additive field to `TuringVerdict`.

**Sub-tasks**:
1. **3.1** Add `emotion_validation_probe=None` parameter to `evaluate_turing()`.
2. **3.2** When emotion probe is usable, override `bio_responsiveness` with `clamp(separation * 10, 0, 1)` + R99 provenance.
3. **3.3** When emotion probe is `None`, keep original `_score_bio_responsiveness` path byte-for-byte unchanged.
4. **3.4** Add `emotion_validation_probe_usable: bool | None = None` to `TuringVerdict`.
5. **3.5** Set `emotion_validation_probe_usable` in `_finalize_verdict`.
6. **3.6** Update `__init__.py` exports.

**Files**: `tests/r89_turing_harness/turing_harness.py` (modify), `tests/r89_turing_harness/__init__.py` (modify).

### T4 — Regression tests

**Goal**: Create 15-20 network-free tests asserting probe correctness and R89 integration.

**Sub-tasks**:
1. **4.1** Config validation: fixture non-empty, valence signs valid, threshold positive.
2. **4.2** Probe run: 0 crash, all fixtures completed.
3. **4.3** `cortisol_valence_separation ≥ 0.05` (fake-LLM).
4. **4.4** `thought_content_grounding ≥ 0.5` (fake-LLM).
5. **4.5** `reply_loop_closure > 0` (fake-LLM).
6. **4.6** `memory_recall_relevance > 0` (fake-LLM).
7. **4.7** Honest absence: empty fixture set → all metrics `None`, `report_usable=False`.
8. **4.8** Honest absence: all-positive fixtures → `reply_loop_closure=None`.
9. **4.9** Honest absence: all-negative fixtures → separation still computed.
10. **4.10** R89 integration: `evaluate_turing(..., emotion_validation_probe=report)` upgrades `bio_responsiveness` to `available`/`reconstructed`.
11. **4.11** R89 baseline: `evaluate_turing(...)` without probe byte-for-byte unchanged.
12. **4.12** `FixtureResult` per-fixture data correctness.
13. **4.13** Robustness: single fixture → partial metrics (honest `None` for absent).
14. **4.14** Report `violations()` and `summary()` methods.

**Files**: `tests/r99_emotion_validation_probe/test_r99_emotion_validation_probe.py` (NEW).

### T5 — Real-LLM opt-in probe (deferred)

**Goal**: Script for running the emotion validation probe with a real LLM (requires `OPENAI_API_KEY`).

**Status**: Deferred. Framework supports it via `EmotionValidationConfig.llm_gateway_factory`. A standalone script will be created when API key is available.

### T6 — Documentation sync

**Goal**: Update `index.md`, `PROGRESS_FLOW.zh-CN.md`, `ROADMAP.zh-CN.md` with R99 status.

**Sub-tasks**:
1. **6.1** Add R99 row to `docs/requirements/index.md`.
2. **6.2** Update `docs/PROGRESS_FLOW.zh-CN.md` header (最近同步: R99).
3. **6.3** Update `docs/ROADMAP.zh-CN.md` W4 R99 status.

### T7 — Run full test suite

**Goal**: Verify 1176+ passed / 0 regression.

```bash
D:\Compiler\anaconda3\envs\helios\python.exe -m pytest helios_v2/tests/ -x --tb=short
```

### T8 — Git commit

**Goal**: Commit all R99 changes.

## 3. Execution Order

T1 → T2 → T3 → T4 → T7 → T6 → T8

(T5 deferred; T6 can overlap with T4 but must be done before T8.)

## 4. Time Estimate

| Phase | Estimate |
|---|---|
| T1 (probe core) | 2-3 hours |
| T2 (package init) | 15 min |
| T3 (R89 integration) | 1 hour |
| T4 (regression tests) | 1-2 hours |
| T6 (doc sync) | 30 min |
| T7 (test suite) | 10 min |
| T8 (commit) | 5 min |
| **Total** | **4-6 hours** |
