# Requirement 82 - Standard Production Assembly and Persistence-by-Default

## 1. Task Breakdown

### T1 - Production embedding gateway helper
In `composition/runtime_assembly.py`, add the `_EMBEDDING_*` env-name constants and
`_production_embedding_gateway(profile_name="experience-embedding", env=None)`: OpenAI-compatible
provider when `HELIOS_EMBEDDING_API_KEY` is present, deterministic-hash fallback otherwise; both
bound to the `experience-embedding` profile name and statically ready.

### T2 - Standard production entry point
In `composition/runtime_assembly.py`, add `DEFAULT_PRODUCTION_DATA_DIR = "data"` and
`assemble_production_runtime(*, data_dir=None, config=None, gateway=None, recorder=None,
embedding_gateway=None)`: build + initialize a SQLite experience store and a SQLite continuity
checkpoint under the data dir, resolve the embedding gateway, and delegate to `assemble_runtime(...)`
with `default_signal_mode="semantic"`.

### T3 - Export
In `composition/__init__.py`, export `assemble_production_runtime` (and
`DEFAULT_PRODUCTION_DATA_DIR`).

### T4 - Env documentation
In `helios_v2/.env.example`, add an optional `HELIOS_EMBEDDING_*` section (api key, base url, model)
documenting the production embedding credential and its offline-hash fallback.

### T5 - Tests
Add `tests/test_production_assembly.py`: (a) defaults-on wiring + critical deps + offline startup;
(b) cross-restart continuity (store count > 0 and prior checkpoint snapshot resumed across two
sessions on the same tmp data dir); (c) embedding selection (hash offline, OpenAI-compatible when a
credential env is passed), all network-free with an injected ready fake LLM gateway.

### T6 - Documentation sync
Update `index.md` (row 82) and `OWNER_GUIDE.*` (`22` composition root: standard production assembly
defaults persistence on). `PROGRESS_FLOW.*` only if a maturity color changes (it does not).

## 2. Dependencies

1. T1 -> T2 -> T3 -> T5; T4 parallel; T6 after T2.
2. External: R33 (`SqliteExperienceStoreBackend`), R34 (`EmbeddingGateway` + providers), R42
   (`SqliteCheckpointBackend`, checkpoint bridge + restore in `assemble_runtime`). No new owner, no
   contract change.

## 3. Files and Modules

1. `src/helios_v2/composition/runtime_assembly.py` (T1, T2)
2. `src/helios_v2/composition/__init__.py` (T3)
3. `helios_v2/.env.example` (T4)
4. `tests/test_production_assembly.py` (T5)
5. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`/`.zh-CN.md` (T6)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5 -> T6.

## 5. Validation Plan

1. After T1-T3: `pytest helios_v2/tests/test_production_assembly.py -q`.
2. Regression: `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_composition_owner_boundary_guard.py -q`.
3. Full: `pytest helios_v2/tests -q` green and network-free.

## 6. Completion Criteria

1. `assemble_production_runtime()` defaults SQLite experience store + SQLite R42 checkpoint +
   `experience-embedding` gateway on, registers the three `_ready` critical deps, and starts/runs
   offline with an injected ready LLM gateway.
2. Cross-restart: a second session on the same data dir reads back prior experience (count > 0) and
   resumes the prior continuity/affect checkpoint.
3. The embedding gateway is OpenAI-compatible when `HELIOS_EMBEDDING_API_KEY` is set and the
   deterministic-hash fallback otherwise (network-free).
4. `assemble_runtime()` defaults and the full network-free suite are unchanged; `index.md` row 82 and
   the `22` `OWNER_GUIDE` entry are updated.
