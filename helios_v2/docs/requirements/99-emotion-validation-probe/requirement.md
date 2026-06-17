# Requirement 99 — Emotion Validation Probe (W4 Formalization)

## 1. Background and Problem

R96 (real semantic embedding), R97 (Chinese appraisal grounding), and R98 (post-LLM appraisal adjustment + hormone prompt coaching) have delivered a correct emotional architecture:

- R96 B2 network-free closure: 10/10 novelty and prototype-cosine fixtures show directional shift vs hash baseline.
- R97 B3 network-free closure: 8/10 Chinese fixtures show threat+reward shift; recall-over-recency passes on R97 path.
- R98 architecture: `PostLLMHormoneAdjuster` + R98 scope extension (hormone prompt coaching) wired correctly; network-free closure tests pass (4/4 fake-LLM separation ≥ 0.05/0.10).

However, the **emotion validation is still ad-hoc**: the existing tools (`scripts/emotion_test_run.py` + `scripts/analyze_emotion_test.py` + `scripts/r96_b2_real_llm_probes/`) are standalone scripts, not part of the R88/R89/R90 tests-only evaluation framework. They:

1. Are not deterministic (require real LLM API calls and external dialogue files).
2. Are not consumable by the R89 Turing harness (`evaluate_turing` has no emotion-probe axis).
3. Are not repeatable in CI (network-dependent, ad-hoc JSON report format).
4. Do not validate the *full* emotional chain (cortisol separation is measured, but thought-content grounding, memory recall relevance, and reply-loop closure are not).

The honest real-cloud 85-utterance verdict shows the architecture is correct but the LLM behavior gap remains (5/85 parseable predictions, 1/85 cortisol). R99 formalizes the emotion validation as a tests-only probe (mirroring R88/R89/R90), making the emotional-chain improvement **falsifiable** and **repeatable** without requiring network access.

## 2. Goal

Create a tests-only, read-only, offline, deterministic emotion validation probe (`tests/r99_emotion_validation_probe/`) that:

1. Measures four bounded `[0,1]` emotional-chain metrics: `cortisol_valence_separation`, `thought_content_grounding`, `memory_recall_relevance`, `reply_loop_closure`.
2. Is consumable by the R89 Turing harness, upgrading `bio_responsiveness` from drift-only reconstruction to emotion-probe reconstruction.
3. Uses a deterministic fake-LLM gateway by default (CI-friendly), with an opt-in real-LLM interface (same pattern as R96 B2 probe).
4. Embeds visitor fixtures in the config (no external file dependency).

Target: `cortisol_valence_separation ≥ 0.05` under fake-LLM; `thought_content_grounding ≥ 0.5`; R89 `evaluate_turing` integration functional.

## 3. Functional Requirements

### 3.1 Emotion validation probe core
1. `EmotionValidationConfig` (frozen dataclass): `ticks`, `visitor_fixtures`, `cortisol_separation_threshold`, `fake_llm_factory`, optional `llm_gateway_factory`.
2. `VisitorFixture` (frozen dataclass): `text`, `valence_category`, `valence_sign` (positive: 1.0, negative: -1.0).
3. `EmotionValidationReport` (frozen dataclass): `ticks_completed`, `crash`, `fixture_results`, four metric fields (`float | None`, honest absence), `report_usable` boolean.
4. `run_emotion_validation_probe(handle_factory, config)` drives a production-shaped assembly with fake-LLM gateway, feeds visitor fixtures via `SequenceExternalSignalSource`, computes four metrics from per-tick `04`/`11`/`10`/`13` stage results.

### 3.2 Four bounded metrics
1. **`cortisol_valence_separation`**: positive-mean cortisol Δ minus negative-mean cortisol Δ, over ticks where a visitor fixture was the external stimulus. Honest `None` when no positive or negative fixtures produced a cortisol Δ.
2. **`thought_content_grounding`**: fraction of fired ticks where the `11` thought content references the current visitor fixture text (substring match, 20+ chars). Honest `None` when no ticks fired.
3. **`memory_recall_relevance`**: fraction of recall-possible ticks where the `10` bundle contains a store-sourced hit. Reuses R90 `_has_store_hit` logic. Honest `None` when no recall-possible ticks.
4. **`reply_loop_closure`**: fraction of negative-valence fixture ticks where the `13` planner accepted a reply-type proposal. Honest `None` when no negative-valence fixture ticks.

### 3.3 R89 integration
1. `evaluate_turing` gains an additive `emotion_validation_probe: EmotionValidationReport | None = None` parameter.
2. When a usable emotion validation probe is supplied, the `bio_responsiveness` axis is scored from `cortisol_valence_separation` (mapped: `clamp(separation * 10, 0, 1)`) with provenance `"R99 emotion validation probe: cortisol_valence_separation=X"`.
3. The original drift-reconstruction path remains as fallback when `emotion_validation_probe is None` (byte-for-byte unchanged).
4. `TuringVerdict` gains an additive `emotion_validation_probe_usable: bool | None = None` field. Existing aggregation logic unchanged.

### 3.4 Real-LLM opt-in interface
1. `EmotionValidationConfig.llm_gateway_factory: Callable | None` allows a real LLM gateway to be injected (same pattern as R96 B2 probe). Default `None` uses the deterministic fake.
2. The fake-LLM gateway produces: negative-valence → `hormone_response_i_predict` containing `{"cortisol": "elevated"}`; positive-valence → `{"dopamine": "elevated", "oxytocin": "elevated"}`; neutral → null/omit.
3. Real-LLM validation requires `OPENAI_API_KEY` (out of scope for network-free tests; CI remains offline).

### 3.5 Visitor fixture set
1. The default `DEFAULT_VISITOR_FIXTURES` contains 10 Chinese-language emotion inputs: 5 negative-valence (anxiety, grief, anger, loneliness, fear) + 5 positive-valence (joy, gratitude, love, hope, calm).
2. Each fixture carries a `valence_category` matching the R96/R97 analyzer `_POSITIVE` / `_NEGATIVE` sets for cross-compatibility.
3. The fixture set is embedded in the probe module; no external file dependency.

## 4. Non-Functional Requirements

1. **Tests-only**: No runtime/owner code changes. The probe lives under `tests/` and consumes only the public `tick()` API + stage result fields. Mirrors R88/R89/R90 constraint.
2. **Read-only / offline / deterministic**: No mutation, no network, no model call (default fake-LLM). The probe is reproducible in CI.
3. **R89 additive**: `evaluate_turing` gains one optional parameter; `TuringVerdict` gains one additive field. All existing R89 tests pass byte-for-byte unchanged.
4. **Honest absence**: Any metric with insufficient data is `None`, never a fabricated number. `report_usable` is `True` only when 0 crash + all fixtures completed + all 4 metrics non-None.
5. **Compatibility**: All 1176 existing network-free tests pass unchanged. R88/R90 reports unchanged.

## 5. Code Behavior Constraints

1. **Forbidden**: modifying any runtime/owner code (R88/R89/R90 discipline — tests-only).
2. **Forbidden**: importing owner internals from `helios_v2.src` (only public API + stage result public fields).
3. **Forbidden**: fabricating metric values — honest `None` for insufficient data.
4. **Boundary**: R99 probe owns the visitor fixture set and metric definitions; R89 owns the Turing aggregation. The `evaluate_turing` interface is additive (one optional parameter), not a redesign.

## 6. Impacted Modules

1. `helios_v2/tests/r99_emotion_validation_probe/emotion_validation_probe.py` (NEW) — probe core
2. `helios_v2/tests/r99_emotion_validation_probe/__init__.py` (NEW) — exports
3. `helios_v2/tests/r99_emotion_validation_probe/test_r99_emotion_validation_probe.py` (NEW) — regression tests
4. `helios_v2/tests/r89_turing_harness/turing_harness.py` — additive `emotion_validation_probe` parameter
5. `helios_v2/tests/r89_turing_harness/__init__.py` — export `emotion_validation_probe_usable`
6. `docs/requirements/99-emotion-validation-probe/` — R99 docs (requirement, design, task)
7. `docs/requirements/index.md` — R99 row
8. `docs/PROGRESS_FLOW.zh-CN.md` — sync header
9. `docs/ROADMAP.zh-CN.md` — W4 R99 status

## 7. Acceptance Criteria

1. `cortisol_valence_separation ≥ 0.05` under fake-LLM (negative-valence fixtures produce cortisol elevation).
2. `thought_content_grounding ≥ 0.5` (fake-LLM thought references visitor text).
3. `reply_loop_closure > 0` (negative-valence fixtures produce reply proposals).
4. R89 `evaluate_turing(..., emotion_validation_probe=report)` makes `bio_responsiveness` axis `available`/`reconstructed` with R99 provenance.
5. R89 `evaluate_turing(...)` without emotion probe byte-for-byte unchanged.
6. Complete test suite 1176+ passed / 0 regression.
7. R99 docs three-piece set complete (requirement.md, design.md, task.md).
8. `index.md` / `PROGRESS_FLOW.zh-CN.md` / `ROADMAP.zh-CN.md` synced.
