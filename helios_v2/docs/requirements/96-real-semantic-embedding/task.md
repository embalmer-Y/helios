# Requirement 96 - Real Semantic Embedding as Default (tasks)

> **Companion to `requirement.md` and `design.md`**. Each task is independently completable and verifiable. Order reflects dependency and migration order. No task touches a cognitive owner.

## 1. Task Breakdown

### Task 1 - Embedding provider resolver (`composition.embedding_provider_resolution`)

**Goal**: the single composition-side function that reads three env vars and decides `openai_compatible` vs `deterministic_hash`.

**Subtasks**:

1. **1.1** Create `helios_v2/src/helios_v2/composition/embedding_provider_resolution.py` with:
   - `EmbeddingProviderKind = Literal["openai_compatible", "deterministic_hash"]`
   - `EMBEDDING_MODEL_DIMENSIONS: Mapping[str, int] = MappingProxyType({...})` (frozen, module-level)
   - `@dataclass(frozen=True) EmbeddingProviderResolution` with `kind`, `model`, `base_url`, `dimensions: int | None`, `api_key_env_var: str`; `__post_init__` validates non-empty `model` / `base_url` / `api_key_env_var` and `kind in the literal set`
   - `resolve_embedding_provider(env: Mapping[str, str]) -> EmbeddingProviderResolution`:
     - read `HELIOS_EMBEDDING_API_KEY`; `str.strip()`; if non-empty → `kind="openai_compatible"`
     - else → `kind="deterministic_hash"`, `model="deterministic-hash"`, `base_url="http://localhost"`, `dimensions=16`, `api_key_env_var="HELIOS_AUTO_EMBEDDING_KEY"`
     - for `openai_compatible`: read `HELIOS_EMBEDDING_MODEL` (default `"text-embedding-3-small"`); read `HELIOS_EMBEDDING_BASE_URL` (default `"https://api.openai.com/v1"`); look up dimensions in `EMBEDDING_MODEL_DIMENSIONS`; `api_key_env_var="HELIOS_EMBEDDING_API_KEY"`
   - Export from `composition/__init__.py` (additive).

**Touched modules**: `helios_v2/src/helios_v2/composition/embedding_provider_resolution.py` (new), `helios_v2/src/helios_v2/composition/__init__.py` (additive export).

**Completion definition**: module imports cleanly; the function is callable with any `Mapping[str, str]`; `__post_init__` rejects empty fields.

**Validation step**: `pytest helios_v2/tests/test_embedding_provider_resolution.py -q` (Task 5).

### Task 2 - RuntimeProfile extension + validation

**Goal**: extend `RuntimeProfile` with `embedding_provider_kind` / `embedding_provider_model` fields, with `__post_init__` validation; thread through `_resolve_profile`.

**Subtasks**:

1. **2.1** Add two new fields to `RuntimeProfile` (frozen dataclass in `composition.runtime_assembly`):
   - `embedding_provider_kind: EmbeddingProviderKind = "deterministic_hash"`
   - `embedding_provider_model: str = "deterministic-hash"`
2. **2.2** Extend `__post_init__` to validate the new fields: `kind in {"openai_compatible", "deterministic_hash"}`; `model` is non-empty.
3. **2.3** Extend `assemble_runtime`'s keyword-argument list to accept `embedding_provider_kind` and `embedding_provider_model` (with `_UNSET` sentinel) and thread them through `_resolve_profile`, mirroring the R69 `default_signal_mode` precedent.
4. **2.4** Extend the R58 `_resolve_profile` helper to honor the new fields when an explicit `profile=` is passed.

**Touched modules**: `helios_v2/src/helios_v2/composition/runtime_assembly.py` (additive).

**Completion definition**: the new fields are accepted, validated, and threaded through; existing callers that don't pass the new fields see the default hash kind; the `RuntimeProfile` is still frozen and immutable.

**Validation step**: `pytest helios_v2/tests/test_runtime_composition.py -q` (Task 5.2).

### Task 3 - R69 auto-provisioning block extension

**Goal**: extend the R69 `if resolved_profile.default_signal_mode == "semantic":` block in `assemble_runtime` to call the resolver and pick the appropriate provider.

**Subtasks**:

1. **3.1** In the all-missing branch (no caller-injected `experience_store` or `embedding_gateway`): call `resolve_embedding_provider(env=os.environ)`; if `kind == "openai_compatible"`, build the cloud profile + cloud gateway; else build the R69 hash profile + R69 hash gateway (byte-for-byte preserved).
2. **3.2** In the embedding-only-missing branch: same resolver call; same provider-construction decision.
3. **3.3** In the store-only-missing branch: leave the existing R69 hash path untouched (the gateway is caller-supplied; the resolver is not consulted; the new fields on the rebuilt profile are derived from the injected gateway's provider class via `isinstance`).
4. **3.4** After rebuilding `resolved_profile` via `replace(...)`, set the new `embedding_provider_kind` and `embedding_provider_model` fields. The kind is derived from the *active* gateway's provider class (so the explicit-injection path also records the right kind).

**Touched modules**: `helios_v2/src/helios_v2/composition/runtime_assembly.py` (the R69 block, around L1207–L1245).

**Completion definition**: the R69 hash-fallback branch produces a resolved profile with `embedding_provider_kind == "deterministic_hash"`; the new cloud branch produces a resolved profile with `embedding_provider_kind == "openai_compatible"`; the explicit-injection branch records the right kind from the injected gateway.

**Validation step**: `pytest helios_v2/tests/test_runtime_composition.py -q` (Task 5.2); `pytest helios_v2/tests/r96_b2_closure.py -q` (Task 5.3).

### Task 4 - B2 closure focused tests (`tests/r96_b2_closure.py`)

**Goal**: prove the B2 root-cause closure by running the same fixture corpus under both providers and recording the per-provider `B2ClosureReport`.

**Subtasks**:

1. **4.1** Define a `FakeOpenAICompatibleEmbeddingProvider` in the test file: conforms to the `EmbeddingProvider` protocol; takes a frozen `dict[str, tuple[float, ...]]` of fixture_id → 1536-dim precomputed vector; for unknown text, returns a deterministic fallback (a fixed base vector + a per-text small offset).
2. **4.2** Define `B2FixtureShift` and `B2ClosureReport` frozen dataclasses (per `design.md` §5.6).
3. **4.3** Define the 10-emotion fixture corpus (the same 10 utterances from the ROADMAP §9.1 emotion test, but normalized to a small test corpus; not the full 89-utterance set — that lives in the real-LLM opt-in probe).
4. **4.4** Test 1 — `test_b2_novelty_signal_differs_across_providers`: drive the R35 novelty signal for each fixture under both providers; assert ≥ 8 of 10 fixtures show a sign-or-magnitude change > 0.05.
5. **4.5** Test 2 — `test_b2_threat_reward_prototype_cosine_differs_across_providers`: drive the R40 prototype-cosine for each fixture under both providers; assert ≥ 8 of 10 fixtures show a change in either dimension.
6. **4.6** Test 3 — `test_b2_recall_over_recency_holds_for_real_provider`: build a small `PersistedExperienceRecord` corpus with a known semantically-similar record (per the `FakeOpenAICompatibleEmbeddingProvider`'s precomputed vectors) and a less-similar more-recent record; run the R52 recalled-replay path under both providers; assert the real-cloud case ranks the semantically-similar record above the more-recent one; assert the hash case does not (recorded as the failing witness).
7. **4.7** Each test produces a `B2ClosureReport` and writes it to `logs/r96_b2_closure/{test_name}_{provider_kind}.json` (gitignored); the test asserts `b2_closed: bool == True` for the real-cloud case and `b2_closed: bool == False` for the hash case.

**Touched modules**: `helios_v2/src/helios_v2/tests/r96_b2_closure.py` (new).

**Completion definition**: all three B2 shift tests pass; the `b2_closed` verdicts are as required; the per-fixture shifts are recorded in the report.

**Validation step**: `pytest helios_v2/tests/r96_b2_closure.py -q`.

### Task 5 - Tests: composition wiring + no-regression

**Goal**: prove the composition-side switch works, the 1110 baseline is preserved, the R95 followup + R56/R57 guards keep passing.

**Subtasks**:

1. **5.1** `tests/test_embedding_provider_resolution.py` — 10 unit tests from `design.md` §5.3; fully deterministic; network-free.
2. **5.2** `tests/test_runtime_composition.py` extend — 6 tests from `design.md` §5.4; verify the resolved profile's new fields under each switch path; verify the explicit-injection path bypasses the resolver; verify the `legacy_constant` mode skips the resolver.
3. **5.3** `tests/r96_b2_closure.py` — Task 4 above.
4. **5.4** **No-regression sweep**: run the full `helios_v2/tests` suite (no test file modified) and verify all 1110 + R95-followup + R96-new tests pass; the R95 followup no-adhoc-logging guard passes; the R56 / R57 owner-boundary guards pass.

**Touched modules**: `helios_v2/src/helios_v2/tests/test_embedding_provider_resolution.py` (new), `helios_v2/src/helios_v2/tests/test_runtime_composition.py` (extend), `helios_v2/src/helios_v2/tests/r96_b2_closure.py` (new), `helios_v2/src/helios_v2/tests/test_no_adhoc_logging_guard.py` (no change, must pass), `helios_v2/src/helios_v2/tests/test_composition_owner_boundary_guard.py` (no change, must pass).

**Completion definition**: all new tests pass; all 1110 baseline tests pass unmodified; the no-adhoc-logging and owner-boundary guards pass.

**Validation step**: `pytest helios_v2/tests/ -q` (full suite); expect 1110 + R95-followup + R96-new green; the 4 skipped and 5 pre-existing wall-clock-profile + lt1 failures remain as documented.

### Task 6 - Real-LLM opt-in probe (`scripts/r96_b2_real_llm_probes/`)

**Goal**: opt-in real-cloud re-run of the 2026-06 emotion corpus; record the B2 closure under the real cloud.

**Subtasks**:

1. **6.1** Create `scripts/r96_b2_real_llm_probes/run.py`: re-uses the existing `scripts/emotion_test_run.py` infrastructure; reads `sim_dialogue_visitors_zh.txt`; uses the assembled runtime with `HELIOS_EMBEDDING_API_KEY` set; per-tick JSONL trace (using the existing `_LoggingProvider` pattern); records per-tick `04`/R36 levels.
2. **6.2** Create `scripts/r96_b2_real_llm_probes/analyze.py`: computes the `cortisol` positive-vs-negative emotion separation metric (mirroring `scripts/analyze_emotion_test.py`); writes a JSON report.
3. **6.3** Create `scripts/r96_b2_real_llm_probes/README.md`: documents the credential, the run command, the expected output, the directional acceptance criterion.
4. **6.4** Commit `docs/requirements/96-real-semantic-embedding/probe_results.md` (initially empty / placeholder); the real-LLM run results are recorded here after the first successful run.

**Touched modules**: `helios_v2/scripts/r96_b2_real_llm_probes/{run,analyze}.py` (new), `helios_v2/scripts/r96_b2_real_llm_probes/README.md` (new), `helios_v2/docs/requirements/96-real-semantic-embedding/probe_results.md` (new).

**Completion definition**: the probe scripts run end-to-end without errors when `HELIOS_EMBEDDING_API_KEY` is set; the README documents the credential and command; the `probe_results.md` is initially a placeholder (the real-LLM run is opt-in, post-merge, not in CI).

**Validation step**: `python helios_v2/scripts/r96_b2_real_llm_probes/run.py --help` (CLI surface present); manual run with credential produces the JSONL trace and the analysis JSON.

### Task 7 - Documentation sync (index, boundaries, comparison, progress flow, ROADMAP)

**Goal**: keep the four living-doc surfaces in sync with the R96 implementation.

**Subtasks**:

1. **7.1** `helios_v2/docs/requirements/index.md`: add the R96 row (depends on `34, 69, 82, 95`; maturity `baseline_implementation` initially, move to `relatively_complete` once the real-LLM probe is recorded).
2. **7.2** `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`: add a §4.X owner-snapshot note recording the composition-side change and that the `34` embedding owner is unchanged. The §4.5 composition-owner bullet list gains a sub-bullet for the new resolver.
3. **7.3** `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`: narrow `gap_persistence_and_learning` (recall is now *real-semantic* when credential present, hash-placeholder otherwise); add a new `gap_real_semantic_embedding` line for the no-credential default; link to the B2 closure report.
4. **7.4** `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` + `PROGRESS_FLOW.en.md`: add a sub-bullet to the `22` composition owner indicating the resolver-driven provider selection; update the test baseline count.
5. **7.5** `helios_v2/docs/ROADMAP.zh-CN.md` (and the English one if it exists): flip R96 from "next slice" to "delivered" once tests are green; keep R97 / R98 / R99+ as the next slices.

**Touched modules**: the four living-doc files; the `ROADMAP.zh-CN.md` file.

**Completion definition**: the four living docs reflect the same boundary truth as the code; the R96 row is in `index.md`; the §4.X owner-snapshot note is in `ARCHITECTURE_BOUNDARIES.md`; the `gap_*` entries are updated in `BRAIN_ARCHITECTURE_COMPARISON.md`; the progress-flow colors stay (composition is already `infra_done`); the ROADMAP flip is recorded.

**Validation step**: manual review of the four files; `git diff` review; no doc/code drift.

## 2. Dependencies

1. **R34** (semantic experience retrieval) — ships; provides the `EmbeddingProvider` protocol, the `OpenAICompatibleEmbeddingProvider`, the `DeterministicHashEmbeddingProvider`, the `EmbeddingGateway`, the readiness-report contract. **No R96 change touches the `34` owner.**
2. **R69** (semantic assembly as default runtime) — ships; provides the auto-provisioning block that R96 extends. The R69 hash-fallback branch is preserved byte-for-byte in the no-credential case.
3. **R82** (standard production assembly) — ships; the `assemble_production_runtime()` entry point delegates to `assemble_runtime(default_signal_mode="semantic")` and gets the new behavior automatically.
4. **R95** + **R95 followup C1-C6** — ships; the no-adhoc-logging guard and the engine/planner hardcode cleanup are preserved. R96 does not touch any of these.
5. **R91** (present-field) — ships; the operator's text reaches the LLM. R96's real-embedding path closes the B2 root cause that R91's evidence surfaced.
6. **R45** (affect-grounded memory formation), **R60** (binding context from real stimulus), **R52** (recalled-replay multiplicity) — all ships; the B2 closure test uses the real percept → binding context → affect memory path that R45 + R60 already provide, with the recalled-replay ranker that R52 already exercises.

## 3. Files and Modules

| File | Status | Owner |
| --- | --- | --- |
| `helios_v2/src/helios_v2/composition/embedding_provider_resolution.py` | **new** | composition |
| `helios_v2/src/helios_v2/composition/__init__.py` | extend (additive exports) | composition |
| `helios_v2/src/helios_v2/composition/runtime_assembly.py` | extend (`RuntimeProfile` fields + R69 block) | composition |
| `helios_v2/src/helios_v2/embedding/engine.py` | **no change** | embedding capability (R34) |
| `helios_v2/src/helios_v2/embedding/contracts.py` | **no change** | embedding capability (R34) |
| `helios_v2/src/helios_v2/persistence/contracts.py` | **no change** | persistence (R33 / R34) |
| `helios_v2/src/helios_v2/persistence/engine.py` | **no change** | persistence (R33 / R34) |
| `helios_v2/src/helios_v2/composition/dependencies.py` | **no change** | composition (R34 / R82) |
| `helios_v2/src/helios_v2/composition/bridges.py` | **no change** | composition (R34) |
| `helios_v2/src/helios_v2/tests/test_embedding_provider_resolution.py` | **new** | tests |
| `helios_v2/src/helios_v2/tests/test_runtime_composition.py` | extend (6 tests) | tests |
| `helios_v2/src/helios_v2/tests/r96_b2_closure.py` | **new** | tests |
| `helios_v2/src/helios_v2/tests/test_no_adhoc_logging_guard.py` | **no change** (must pass) | guard tests |
| `helios_v2/src/helios_v2/tests/test_composition_owner_boundary_guard.py` | **no change** (must pass) | guard tests |
| `helios_v2/scripts/r96_b2_real_llm_probes/run.py` | **new** | scripts (opt-in) |
| `helios_v2/scripts/r96_b2_real_llm_probes/analyze.py` | **new** | scripts (opt-in) |
| `helios_v2/scripts/r96_b2_real_llm_probes/README.md` | **new** | scripts (opt-in) |
| `helios_v2/docs/requirements/96-real-semantic-embedding/requirement.md` | **new** | docs |
| `helios_v2/docs/requirements/96-real-semantic-embedding/design.md` | **new** | docs |
| `helios_v2/docs/requirements/96-real-semantic-embedding/task.md` | **new** (this file) | docs |
| `helios_v2/docs/requirements/96-real-semantic-embedding/probe_results.md` | **new** (placeholder) | docs (post-merge probe results) |
| `helios_v2/docs/requirements/index.md` | extend (R96 row) | docs |
| `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` | extend (composition note) | docs |
| `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` | extend (gap updates) | docs |
| `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` + `PROGRESS_FLOW.en.md` | extend (composition sub-bullet) | docs |
| `helios_v2/docs/ROADMAP.zh-CN.md` | extend (R96 → delivered) | docs |

## 4. Implementation Order

The order is dependency-driven and migration-driven.

1. **Task 1** (resolver) — pure function, no dependencies on other code; can land first.
2. **Task 2** (RuntimeProfile extension) — depends on Task 1; additive field + validation; can land second.
3. **Task 5.1** (resolver tests) — depends on Task 1; runs in CI; can land in parallel with Task 1.
4. **Task 5.2** (composition tests extend) — depends on Task 2; can land in parallel with Task 2.
5. **Task 3** (R69 block extension) — depends on Tasks 1 and 2; the resolver + the new fields are the inputs; the auto-provisioning is the integration.
6. **Task 4** (B2 closure tests) — depends on Task 3 (the new fields are read by the B2 tests) and on R34 (the `FakeOpenAICompatibleEmbeddingProvider` is a `34`-protocol implementation).
7. **Task 5.3** (no-regression sweep) — runs after Tasks 1-4 land; verifies the 1110 baseline is preserved.
8. **Task 6** (real-LLM opt-in probe) — depends on Task 3 (the cloud path must work end-to-end) and on the existing R91 emotion-test tooling.
9. **Task 7** (documentation sync) — depends on Tasks 1-6 (the docs reflect the final state).

Phases:

- **Phase 1** (Tasks 1, 2, 3, 5.1, 5.2) — composition-side provider selection with the new fields. Network-free CI.
- **Phase 2** (Task 4, 5.3) — B2 closure focused tests. Network-free CI.
- **Phase 3** (Task 6) — real-LLM opt-in probe. Post-merge.
- **Phase 4** (Task 7) — documentation sync. Final.

## 5. Validation Plan

The validation is layered:

1. **Unit tests (CI, network-free)**:
   - `tests/test_embedding_provider_resolution.py` (10 tests) — `pytest -q` in CI.
   - `tests/test_runtime_composition.py` (6 new tests on top of existing) — `pytest -q` in CI.
2. **B2 closure focused tests (CI, network-free)**:
   - `tests/r96_b2_closure.py` (3 tests + `FakeOpenAICompatibleEmbeddingProvider` + per-fixture shift reporting) — `pytest -q` in CI.
3. **No-regression sweep (CI, network-free)**:
   - `tests/` full suite — `pytest -q` in CI; expect 1110 + R95-followup + R96-new green; the 4 skipped and 5 pre-existing wall-clock-profile + lt1 failures remain as documented.
4. **Guard tests (CI, network-free)**:
   - `tests/test_no_adhoc_logging_guard.py` — `pytest -q` in CI; must pass.
   - `tests/test_composition_owner_boundary_guard.py` — `pytest -q` in CI; must pass.
5. **Real-LLM opt-in probe (post-merge, opt-in)**:
   - `scripts/r96_b2_real_llm_probes/run.py` — run with `HELIOS_EMBEDDING_API_KEY` set; record the JSONL trace and the analysis JSON; commit `probe_results.md` with the result.
6. **First narrow CI command** (per task-authoring-standard §5.10):
   - `pytest helios_v2/tests/test_embedding_provider_resolution.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/r96_b2_closure.py -q` (the R96 surface).
7. **Full CI command** (per task-authoring-standard §5.10):
   - `pytest helios_v2/tests/ -q` (the whole suite).

## 6. Completion Criteria

The R96 slice is complete when **all** of the following are true:

1. **Composition-side switch works**:
   - `assemble_runtime()` with `HELIOS_EMBEDDING_API_KEY` set in the injected env produces a resolved `RuntimeProfile` with `embedding_provider_kind == "openai_compatible"` and the right `embedding_provider_model`.
   - `assemble_runtime()` with the key absent produces a resolved `RuntimeProfile` with `embedding_provider_kind == "deterministic_hash"` (R69-equivalent).
   - `assemble_runtime(embedding_gateway=...)` still wins (the resolver is not consulted on that path).
   - `assemble_runtime(default_signal_mode="legacy_constant")` does not consult the resolver.
2. **1110-test baseline is preserved**:
   - No existing test file is modified.
   - All 1110 + 4 skipped tests pass; the 5 pre-existing wall-clock-profile + lt1 failures are unchanged.
3. **Guards are preserved**:
   - The R95 followup no-adhoc-logging guard passes.
   - The R56 / R57 owner-boundary guards pass.
4. **B2 closure is verifiable**:
   - The three B2 shift tests in `tests/r96_b2_closure.py` pass.
   - The `b2_closed: bool` verdict is `True` for the real-cloud case and `False` for the hash case, with the `fallback_reason` recorded.
   - The per-fixture shifts are written to `logs/r96_b2_closure/` for human inspection.
5. **Real-LLM opt-in probe is documented and runnable**:
   - `scripts/r96_b2_real_llm_probes/{run,analyze}.py` exist and run end-to-end.
   - The README documents the credential and command.
   - The first real-LLM run (post-merge) records the `probe_results.md` and shows a directional shift over the pre-R96 -0.0095 baseline.
6. **Documentation is in sync**:
   - `index.md` has the R96 row.
   - `ARCHITECTURE_BOUNDARIES.md` has the §4.X composition-side note.
   - `BRAIN_ARCHITECTURE_COMPARISON.md` has the `gap_*` updates.
   - `PROGRESS_FLOW.zh-CN.md` + `PROGRESS_FLOW.en.md` have the composition sub-bullet.
   - `ROADMAP.zh-CN.md` has the R96 → delivered flip.
7. **Owner-confirmed decision is recorded**:
   - The §8 item 5 in `ROADMAP.zh-CN.md` records the `A — OpenAI-compatible cloud` decision.
   - The `requirement.md` §1 Background and §2 Goal both reference the owner-confirmed decision.
8. **No regressions in adjacent owners**:
   - R34 / R69 / R82 / R95 / R95 followup tests are unchanged.
   - The R95 followup no-adhoc-logging guard and the R56 / R57 owner-boundary guards pass.
   - The R82 `assemble_production_runtime` tests pass.

When all eight are true, R96 is delivered; the ROADMAP §10 W3 R96 row flips to "delivered"; the W3 R97 (Chinese-appraisal grounding) becomes the next slice.
