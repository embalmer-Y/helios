# Requirement 58 - Runtime Profile Capability Bundle for the Composition Root

## 1. Design Overview

Introduce a frozen `RuntimeProfile` dataclass in `composition/runtime_assembly.py` that
bundles the composition root's capability seams and dependency-surface overrides, validates
the cross-capability rules in `__post_init__`, and exposes the derived capability flags as
properties. `assemble_runtime` gains an additive `profile: RuntimeProfile | None = None`
parameter: when omitted it builds the profile from the existing loose kwargs (preserving the
public signature and every call site); when supplied it must not be combined with overlapping
loose kwargs. The body then reads the profile for all capability decisions. No assembly's
wiring, stage order, dependency specs, or per-tick output changes.

## 2. Current State and Gap

`assemble_runtime` today:

1. Validates `embedding requires store` inline (`if embedding_gateway is not None and
   experience_store is None: raise CompositionError(...)`).
2. Computes `semantic_memory_enabled = experience_store is not None and embedding_gateway is
   not None` as a local, then branches on it ~10 times (appraisal estimators, neuromodulator
   path, feeling path, memory formation/selector/recall, workspace, consciousness, gate path,
   recall holder, memory record bridge).
3. Reads nine loose capability kwargs plus three dependency-surface kwargs directly.

Gap: the capability set has no single representation, the cross-capability rule is inline, and
the derived flag is a local. Adding a capability means threading another kwarg and re-deriving
combinations by hand.

## 3. Target Architecture

```
composition/runtime_assembly.py
  @dataclass(frozen=True)
  class RuntimeProfile:
      # capability seams
      recorder: RuntimeObservabilityRecorder | None = None
      gateway: LlmGatewayAPI | None = None
      deterministic_thought: bool = False
      channel_cli: bool = False
      cli_output_sink: Callable[[str], None] | None = None
      experience_store: ExperienceStore | None = None
      embedding_gateway: EmbeddingGatewayAPI | None = None
      embedding_profile_name: str = "experience-embedding"
      continuity_checkpoint: ContinuityCheckpointStore | None = None
      interoceptive_sampler: RuntimePressureSampler | None = None
      temporal_source: TemporalSource | None = None
      # dependency-surface overrides
      dependency_specs: tuple[RuntimeDependencySpec, ...] | None = None
      dependency_provider: RuntimeDependencyProvider | None = None
      config: CompositionConfig | None = None

      def __post_init__(self): ...          # cross-capability validation (fail-fast)

      @property
      def semantic_memory_enabled(self) -> bool:
          return self.experience_store is not None and self.embedding_gateway is not None

  def assemble_runtime(*, profile: RuntimeProfile | None = None, **loose) -> RuntimeHandle:
      profile = _resolve_profile(profile, loose)   # build-from-kwargs or reject-both
      # body reads profile.* everywhere it previously read the loose kwargs/local
```

The body's existing logic is preserved verbatim; only the source of each value changes from a
loose name / local to a `profile.` attribute / property.

## 4. Data Structures

`RuntimeProfile` (frozen). Note `dependency_specs` becomes a `tuple` on the profile (immutable
field) while `assemble_runtime` still accepts a `list` loose kwarg for back-compat and converts
it when building the profile; internally the existing code that does
`list(resolved_specs) + [...]` continues to work by materializing a list from the tuple at use
sites (or the profile stores the list defensively copied). The chosen representation must keep
the existing "append a spec when a capability is on and `dependency_specs is None`" semantics
exactly: the profile records whether the caller supplied explicit specs (the override case) so
the append-only-on-default behavior is preserved.

`__post_init__` validation rules (relocated, not new):

1. `embedding_gateway is not None and experience_store is None` -> `CompositionError`
   (verbatim message preserved).

No other new validation is introduced (the goal is behavior invariance). Additional rules may
be added later; this slice only relocates the existing one.

## 5. Module Changes

1. `runtime_assembly.py`
   - Add `RuntimeProfile` with the fields above, `__post_init__` cross-capability validation,
     and the `semantic_memory_enabled` property.
   - Add a private `_resolve_profile(profile, loose_kwargs)` helper: if `profile is not None`
     and any overlapping loose kwarg was explicitly supplied, raise `CompositionError`;
     otherwise return the supplied profile or a `RuntimeProfile(**loose_kwargs)`.
   - Change `assemble_runtime` to accept `profile: RuntimeProfile | None = None` plus the
     existing keyword arguments, resolve the profile, and read `profile.*` throughout (replace
     the inline `embedding requires store` check and the `semantic_memory_enabled` local with
     the profile's validation and property).
2. `composition/__init__.py`
   - Export `RuntimeProfile` alongside `assemble_runtime` / `RuntimeHandle`.
3. `tests/test_runtime_composition.py`
   - Add focused tests: default profile = default assembly; embedding-without-store raises;
     `semantic_memory_enabled` property; explicit-profile-vs-loose-kwargs equivalence; both
     supplied -> `CompositionError`.

## 6. Migration Plan

1. Add `RuntimeProfile` and `_resolve_profile`.
2. Add `profile` parameter to `assemble_runtime`; build the profile from loose kwargs when
   absent.
3. Mechanically repoint each capability read in the body from the loose name/local to the
   profile attribute/property, preserving every branch verbatim. The dependency-surface
   append logic keys on "did the caller supply explicit specs" exactly as today.
4. Export `RuntimeProfile`.
5. Add the focused tests; run the full suite and assert behavior invariance (count grows only
   by the added tests).
6. Update documentation truth.

This is an internal refactor: the public keyword signature is preserved (additive `profile`),
no call site changes, and the assembly logic is transcribed rather than rewritten.

## 7. Failure Modes and Constraints

1. `embedding_gateway` without `experience_store` -> `CompositionError` at profile
   construction (same as today, relocated).
2. Explicit `profile` plus an overlapping loose kwarg -> `CompositionError` (new guard against
   ambiguous configuration; it prevents a silent precedence bug, it does not change any valid
   call).
3. The profile is frozen; capability decisions are pure reads. No degraded path.
4. Default-on and unconditional: the refactor changes code structure, not computed output.

## 8. Rollout (Default-On vs Default-Off)

Unconditional and behavior-invariant. There is no opt-in: the profile is an internal
representation. Every assembly and every existing caller is byte-for-byte unchanged. The only
new externally-visible surface is the additive `RuntimeProfile` type and the additive
`profile=` parameter, both optional.

## 9. Observability and Logging

No new logging. The `21` observability owner remains the single logging mechanism. The profile
and the resolve helper use neither `logging` nor `print`; the ad-hoc-logging guard stays green.

## 10. Validation Strategy

1. Profile unit tests: all-default profile fields equal the current defaults;
   `embedding_gateway` without `experience_store` raises `CompositionError`;
   `semantic_memory_enabled` is True only when both are present.
2. Equivalence test: assemble two handles for the same capabilities — one via `profile=`, one
   via loose kwargs — and assert equal stage order, equal dependency-spec name sets, and equal
   per-tick result for a fixed deterministic/offline configuration.
3. Ambiguity guard test: `assemble_runtime(profile=..., gateway=...)` raises `CompositionError`.
4. Regression: the existing composition, checkpoint-resumption, channel, and stage-chain tests
   stay green unchanged (they exercise the loose-kwarg path), proving back-compat.
5. The owner-boundary guard and ad-hoc-logging guard stay green. Full network-free suite green;
   count = prior + added tests.
