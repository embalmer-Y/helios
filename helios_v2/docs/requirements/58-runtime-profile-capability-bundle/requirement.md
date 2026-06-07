# Requirement 58 - Runtime Profile Capability Bundle for the Composition Root

## 1. Background and Problem

The composition root's `assemble_runtime` is the single assembly entry point. It has grown
to nine loosely-coupled capability seams passed as independent keyword arguments
(`recorder`, `gateway`, `deterministic_thought`, `channel_cli` + `cli_output_sink`,
`experience_store`, `embedding_gateway` + `embedding_profile_name`, `continuity_checkpoint`,
`interoceptive_sampler`, `temporal_source`) plus the dependency-surface overrides
(`dependency_specs`, `dependency_provider`, `config`).

This produces three concrete maintenance problems, observable in the current code:

1. Cross-capability rules are validated inline and scattered. "Semantic memory requires a
   durable experience store" is enforced by an ad-hoc `if embedding_gateway is not None and
   experience_store is None: raise CompositionError(...)` in the middle of the function, and
   the derived `semantic_memory_enabled = experience_store is not None and embedding_gateway
   is not None` is recomputed as a local and threaded through roughly ten ternaries.
2. The combinatorial surface is implicit. There is no single object that says "this is the
   set of capabilities this runtime was assembled with"; the truth is spread across nine
   parameters and a derived local. Each new capability (every P3/P4 slice adds one) means
   threading another loose flag through a ~600-line function and re-deriving combinations by
   hand, which is exactly the accretion pattern that produced the v1 technical debt.
3. The capability set is not introspectable. A caller (or a test, or a future default-on
   migration) cannot ask a runtime "which capabilities are you running" without re-deriving
   the booleans from the same scattered inputs.

This is structural debt in the composition root, not an owner-boundary violation: no
cognitive policy is involved. The fix is to give the capability set a first-class,
validated, introspectable representation without changing what any assembly computes.

## 2. Goal

Introduce a single frozen `RuntimeProfile` capability bundle that groups the composition
root's capability seams, validates the cross-capability rules in one place, and exposes the
derived capability flags (such as `semantic_memory_enabled`) as named properties, then have
`assemble_runtime` consume the profile internally, so the assembly's capability set is
first-class and introspectable while every existing call site and every assembly's runtime
behavior is byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Runtime profile contract

1. The composition package must define a frozen `RuntimeProfile` dataclass that carries the
   capability seams currently passed as loose kwargs: the observability recorder, the LLM
   gateway, the deterministic-thought flag, the channel-CLI flag and its output sink, the
   experience store, the embedding gateway and its profile name, the continuity checkpoint
   store, the interoceptive sampler, and the temporal source. It must also carry the
   dependency-surface overrides (`dependency_specs`, `dependency_provider`, `config`).
2. `RuntimeProfile` must validate cross-capability rules at construction with fail-fast
   `CompositionError`, including the existing rule that an embedding gateway requires an
   experience store. No cross-capability rule may remain validated inline in
   `assemble_runtime` once relocated.
3. `RuntimeProfile` must expose the derived capability flags as named read-only properties,
   at minimum `semantic_memory_enabled`, computed once in the profile rather than recomputed
   as a local in `assemble_runtime`.
4. `RuntimeProfile` must be constructible with all-default fields, producing exactly the
   current default assembly's capability set.

### 3.2 Assembly consumption

1. `assemble_runtime` must consume a `RuntimeProfile` internally for all capability decisions
   (capability presence, the derived flags, and the dependency surface), rather than reading
   the loose kwargs and recomputing the derived local.
2. `assemble_runtime` must continue to accept the existing keyword arguments as a backward-
   compatible convenience: when no explicit `profile` is given, it must build a
   `RuntimeProfile` from those kwargs and use it. Passing an explicit `profile` and the
   overlapping loose kwargs together must fail fast with `CompositionError` rather than
   silently preferring one.
3. Every existing call site (tests, scripts, entry points) must keep working unchanged.

### 3.3 Behavioral invariance

1. For every assembly combination (default, deterministic-thought, channel-CLI, persistence,
   semantic memory, continuity checkpoint, interoceptive, temporal, and any combination of
   them), the assembled `RuntimeHandle` — its stage order, its registered dependency specs,
   its wired bridges/paths, and its per-tick output — must be byte-for-byte identical to the
   pre-change assembly.
2. The cross-capability failure (embedding without store) must still raise `CompositionError`
   with equivalent semantics.

### 3.4 Boundary and recurrence

1. `RuntimeProfile` must hold no cognitive policy: it is a capability/configuration bundle and
   carries no salience mapping, no pressure constant, no decision threshold. The existing
   owner-boundary guard must stay green.

## 4. Non-Functional Requirements

1. Performance: no runtime performance change; this is an assembly-time refactor.
2. Reliability: validation moves to one fail-fast location; no degraded path is introduced.
3. Observability and logging: no new logging mechanism; the ad-hoc-logging guard stays green.
4. Compatibility and migration: the public `assemble_runtime` keyword signature is preserved
   (additive `profile` parameter only). Default rollout is immediate and unconditional;
   behavior is unchanged for every assembly and every existing caller.

## 5. Code Behavior Constraints

1. Forbidden: changing any assembly's wiring, stage order, dependency specs, or per-tick
   output during this refactor. The change must be behavior-preserving.
2. Forbidden: removing or renaming an existing `assemble_runtime` keyword argument (callers
   depend on them); the profile is additive.
3. Boundary rule: `RuntimeProfile` is a composition-owned capability bundle; it must not carry
   any owner cognitive policy.
4. Failure mode: cross-capability validation is fail-fast `CompositionError` at profile
   construction; supplying both an explicit profile and overlapping loose kwargs is a
   fail-fast `CompositionError`.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — define `RuntimeProfile`,
   relocate the cross-capability validation and the derived `semantic_memory_enabled` into it,
   and have `assemble_runtime` consume it.
2. `helios_v2/src/helios_v2/composition/__init__.py` — export `RuntimeProfile` if the package
   exports the assembly surface.
3. `helios_v2/tests/test_runtime_composition.py` — add focused profile tests (construction,
   validation, derived flags, profile-vs-kwargs equivalence).
4. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/ARCHITECTURE_BOUNDARIES.md`. (The progress-flow maps do
   not change: no owner maturity color, stage chain, or owner boundary changes.)

## 7. Acceptance Criteria

1. `RuntimeProfile` is importable from the composition package, is frozen, constructs with
   all defaults to the current default capability set, validates `embedding-without-store` as
   a `CompositionError`, and exposes `semantic_memory_enabled` as a property.
2. `assemble_runtime(profile=RuntimeProfile(...))` and the equivalent loose-kwarg call produce
   an assembly that is byte-for-byte equivalent (same stage order, same dependency spec names,
   same per-tick result), verified by a focused equivalence test.
3. Passing both an explicit `profile` and an overlapping loose kwarg raises `CompositionError`.
4. The inline `embedding requires store` check and the derived `semantic_memory_enabled` local
   no longer exist in `assemble_runtime`; both are owned by `RuntimeProfile`.
5. Every existing call site compiles and the full network-free suite is green
   (`pytest helios_v2/tests -q`), count growing only by the added focused tests; the
   owner-boundary and ad-hoc-logging guards stay green.
6. `index.md` has a row 58; `OWNER_GUIDE` (`22` composition entry) and
   `ARCHITECTURE_BOUNDARIES.md` record the capability-bundle structure, with sync lines naming
   R58.
