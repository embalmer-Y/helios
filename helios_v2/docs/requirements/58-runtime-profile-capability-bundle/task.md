# Requirement 58 - Runtime Profile Capability Bundle for the Composition Root

## 1. Task Breakdown

### T1 - Define `RuntimeProfile`
In `composition/runtime_assembly.py` add a frozen `RuntimeProfile` dataclass carrying the nine
capability seams plus the three dependency-surface overrides, with `__post_init__`
cross-capability validation (relocate the `embedding requires store` `CompositionError`
verbatim) and a `semantic_memory_enabled` property.

### T2 - Add the profile resolver
Add a private `_resolve_profile(profile, loose_kwargs)` helper: raise `CompositionError` if an
explicit profile is combined with any overlapping loose kwarg; otherwise return the supplied
profile or build `RuntimeProfile(**loose_kwargs)`.

### T3 - Consume the profile in `assemble_runtime`
Add the additive `profile: RuntimeProfile | None = None` parameter, resolve it at the top, and
mechanically repoint every capability read in the body from the loose name / `semantic_memory_enabled`
local to the profile attribute / property, preserving every branch and the dependency-spec
append semantics verbatim. Remove the inline `embedding requires store` check and the derived
local.

### T4 - Export `RuntimeProfile`
Add `RuntimeProfile` to `composition/__init__.py` exports.

### T5 - Tests
Add focused tests in `test_runtime_composition.py`: default-profile equals defaults;
embedding-without-store raises; `semantic_memory_enabled`; profile-vs-loose-kwargs assembly
equivalence; profile+overlapping-kwarg raises.

### T6 - Documentation
Update `index.md` (row 58), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`22` composition entry),
and `ARCHITECTURE_BOUNDARIES.md` (composition owner snapshot / migration note). The
progress-flow maps are unchanged (no owner maturity color, stage chain, or owner-boundary
change) and must not be edited for this requirement.

## 2. Dependencies

1. T1 → T2 → T3 (resolver and body need the type).
2. T4 after T1. T5 after T3+T4. T6 after T1–T5.
3. External requirement dependencies: 22 (composition root) and every capability requirement it
   already wires (25/30/31/33/34/42/50/55); no new owner.

## 3. Files and Modules

1. `src/helios_v2/composition/runtime_assembly.py` (T1, T2, T3)
2. `src/helios_v2/composition/__init__.py` (T4)
3. `tests/test_runtime_composition.py` (T5)
4. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/ARCHITECTURE_BOUNDARIES.md` (T6)

## 4. Implementation Order

T1 → T2 → T3 → T4 → T5 → T6. Type, resolver, consume, export, test, document.

## 5. Validation Plan

1. After T3 (focused slice):
   `pytest helios_v2/tests/test_runtime_composition.py -q` green (loose-kwarg path unchanged).
2. After T3 (back-compat regression):
   `pytest helios_v2/tests/test_continuity_checkpoint_resumption.py helios_v2/tests/test_channel_cli_driver.py helios_v2/tests/test_runtime_stage_chain.py -q` green.
3. After T5 (profile behavior):
   `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q` green.
4. Full suite:
   `pytest helios_v2/tests -q` green; count = prior baseline (716) + the added tests.

## 6. Completion Criteria

1. `RuntimeProfile` is defined, frozen, exported, validates embedding-without-store, and
   exposes `semantic_memory_enabled`; the inline check and derived local are gone from
   `assemble_runtime`.
2. `assemble_runtime` accepts an additive `profile=` and still accepts every existing keyword
   argument; profile-vs-loose-kwargs assemblies are byte-for-byte equivalent; profile +
   overlapping kwarg raises `CompositionError`.
3. Every existing call site works unchanged; the full network-free suite is green with only
   the added tests in the count; owner-boundary and ad-hoc-logging guards stay green.
4. `index.md`, `OWNER_GUIDE` (both), and `ARCHITECTURE_BOUNDARIES.md` record the capability
   bundle, with sync lines naming R58.
