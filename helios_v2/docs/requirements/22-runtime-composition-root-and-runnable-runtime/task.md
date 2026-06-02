# Requirement 22 - Runtime composition root and runnable runtime task plan

## 1. Title

Requirement 22 - Runtime composition root and runnable runtime

## 2. Task Breakdown

1. Define the canonical nineteen-stage order constant and `CompositionError` in `composition/runtime_assembly.py`.
2. Implement the first-version owner-neutral cross-owner bridges and the first-version injected owner capabilities in `composition/bridges.py`, promoting the proven `Fixed*` behavior from the stage-chain test into shipped, provenance-preserving code.
3. Implement `CompositionConfig` and `default_composition_config()` in `composition/runtime_assembly.py`, mirroring the configs proven in the stage-chain test.
4. Implement the first-version dependency provider and default critical-dependency spec set in `composition/dependencies.py`.
5. Implement `assemble_runtime(...)` and the `RuntimeHandle` (`startup`, `tick`, `run_ticks`, `ingress`) in `composition/runtime_assembly.py`, including the post-registration canonical-order validation.
6. Export the composition public surface in `composition/__init__.py` and surface `assemble_runtime` and `RuntimeHandle` from the top-level package `__init__.py`.
7. Implement the thin driver `scripts/run_runtime_driver.py` that assembles a runtime with a JSON-line sink, supplies a bounded per-tick stimulus batch through ingress, runs a bounded number of ticks, and writes the event stream.
8. Add `tests/test_runtime_composition.py` covering assembly, ordering, fail-fast, single-tick provenance equivalence, multi-tick, and recorder-timeline reconstruction.
9. Add `tests/test_no_adhoc_logging_guard.py` enforcing the single-logging-mechanism rule across `helios_v2/src`.
10. Update `docs/requirements/index.md` and `docs/ARCHITECTURE_BOUNDARIES.md` to record the new composition owner and the single-logging-mechanism guard.

## 3. Dependencies

1. `01-runtime-kernel` provides the kernel lifecycle, stage dispatch, and dependency gate that the assembly wires.
2. `02-18` provide the owner engines, owner configs, and stage adapters being assembled.
3. `21-unified-runtime-observability-and-logging` provides the optional recorder, the JSON-line sink, and the logging-ownership rule this requirement enforces.

This requirement adds no new cognitive owner. It assembles existing owners and ships first-version glue only.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/composition/__init__.py`
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
3. `helios_v2/src/helios_v2/composition/bridges.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/src/helios_v2/__init__.py`
6. `helios_v2/scripts/run_runtime_driver.py`
7. `helios_v2/tests/test_runtime_composition.py`
8. `helios_v2/tests/test_no_adhoc_logging_guard.py`
9. `helios_v2/docs/requirements/index.md`
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`

## 5. Implementation Order

1. Land the canonical stage-order constant and `CompositionError` first; they have no internal dependency.
2. Land `composition/bridges.py` with the first-version bridges and injected owner capabilities, validating each against the existing owner contracts.
3. Land `CompositionConfig` and `default_composition_config()`.
4. Land `composition/dependencies.py`.
5. Land `assemble_runtime` and `RuntimeHandle`, then the canonical-order validation.
6. Land composition exports and top-level exports.
7. Add `tests/test_runtime_composition.py` and validate the assembled runtime in isolation.
8. Add the driver script and smoke-run it for a bounded tick count.
9. Add the logging-guard test.
10. Update `index.md` and `ARCHITECTURE_BOUNDARIES.md`.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
4. `python helios_v2/scripts/run_runtime_driver.py --ticks 3` to smoke-run the driver and confirm a parseable JSON-line event stream.
5. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. `assemble_runtime` returns a runnable handle with all nineteen stages registered exactly once in canonical order, and wrong order or count raises `CompositionError`.
2. Every cross-owner bridge protocol in `runtime/stages.py` has a shipped first-version implementation in `helios_v2/src/helios_v2/composition`, so no test-only doubles are required to run the chain.
3. A missing critical dependency makes `handle.startup()` raise `RuntimeStartupError` with no reduced-mode assembly.
4. One tick through the assembled runtime produces stage results whose provenance ids match the canonical chain expectations.
5. `run_ticks(n)` returns `n` ordered results with monotonic `tick_id`, and an attached recorder yields an event stream that reconstructs the per-tick stage timeline in canonical order with strictly monotonic sequence numbers.
6. A no-recorder assembled runtime emits nothing and matches bare-kernel behavior.
7. The driver runs a bounded number of ticks and writes a parseable JSON-line event stream.
8. The logging-guard test fails on any introduced `import logging`, logger, or `print(` under `helios_v2/src`, and the current tree passes it.
9. `pytest helios_v2/tests -q` is green.

## 8. Completion Snapshot

Status on 2026-06-02: implemented and validated as `baseline_implementation`.

Delivered files:

1. `helios_v2/src/helios_v2/composition/__init__.py`
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (`CANONICAL_STAGE_ORDER`, `CompositionConfig`, `default_composition_config`, `RuntimeHandle`, `assemble_runtime`, `CompositionError`)
3. `helios_v2/src/helios_v2/composition/bridges.py` (first-version owner-neutral cross-owner bridges and first-version injected owner capabilities, generalized across ticks)
4. `helios_v2/src/helios_v2/composition/dependencies.py` (`FirstVersionDependencyProvider`, `default_critical_dependency_specs`, `RUNTIME_COGNITION_BASELINE`)
5. `helios_v2/src/helios_v2/__init__.py` (surfaces `assemble_runtime` and `RuntimeHandle`)
6. `helios_v2/scripts/run_runtime_driver.py` (thin bounded-tick driver writing a JSON-line event stream)
7. `helios_v2/tests/test_runtime_composition.py`
8. `helios_v2/tests/test_no_adhoc_logging_guard.py`
9. `helios_v2/docs/requirements/index.md` (maturity updated to `baseline_implementation`)
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (section 4.5 composition owner snapshot)

Validated outcomes:

1. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q` -> `11 passed`
2. `pytest helios_v2/tests -q` -> `239 passed`
3. `python helios_v2/scripts/run_runtime_driver.py --ticks 2 --out logs/runtime_events.jsonl` -> 79 JSON-line events (1 startup + 2 x (19 stage_started + 19 stage_completed + 1 tick_completed)), each line a parseable JSON record.

Implementation notes:

1. The assembled runtime is default-off for observability: without an injected recorder it behaves exactly as the bare kernel and emits nothing.
2. The canonical stage-order constant uses the real `stage_name` values exposed by the stage adapters and is validated at assembly time; a mismatch raises `CompositionError`.
3. The first-version bridges and injected owner capabilities are baseline shims, deterministic and bounded, generalized to advance across arbitrary ticks. Later owner-deepening waves replace them through the owners without changing the `assemble_runtime` contract.
