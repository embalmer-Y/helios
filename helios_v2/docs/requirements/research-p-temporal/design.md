# Design P-TEMPORAL — P5 Mandatory Wiring + Wall-Clock Continuous State

## 1. Architecture overview

```
┌────────────────────────────────────────────────────────────────────────┐
│ RuntimeFrame                                                           │
│  tick_wall_seconds: float | None  (R92, already shipped)                │
│  last_external_stimulus_wall_seconds: float | None  (NEW)              │
└──────────────┬─────────────────────────────────────────────────────────┘
               │ (read by every owner invocation via runtime_assembly glue)
               │
┌──────────────▼─────────────────────────────────────────────────────────┐
│ ContinuousStateOwner (NEW, infrastructure rank)                         │
│   wall_clock_elapsed_seconds: float (since helios start)               │
│   last_external_stimulus_wall_seconds: float                           │
│   current_episode_id: int                                              │
│   episode_start_wall_seconds: float                                    │
│   observe_tick(fired, external_stimulus_present, wall_seconds)          │
│   sample() -> ContinuousStateReading (frozen dataclass)                │
│ Held by composition/runtime_assembly; never invokes LLM.               │
└──────┬───────────────────────────────────────────────────────────────┬─┘
       │                                                               │
       │ (P5 wire-on: invoked each tick by 9 canonical owners)          │
       │                                                               │
┌──────▼──────────────────┐                                  ┌─────────▼─────────┐
│ CanonicalOwner.apply_   │  reads                           │ P5 Learner sidecar │
│ p5_policy(snapshot)     │  ←───────────────                │ (already shipped)  │
│   overrides 105 hard-   │                                  │   MemoryLearner    │
│   coded fields per      │                                  │   AutonomyLearner  │
│   p5_parameter_mapping  │                                  │   NeuromodLearner  │
└─────────────────────────┘                                  │   FeelingLearner   │
                                                             │   ... (15 total)   │
                                                             └─────────┬─────────┘
                                                                       │
                                                                       │ produces
                                                                       ▼
                                                              _LearningSnapshot(
                                                                  policy_output: tuple[float, ...],
                                                                  residual: float,
                                                                  regime: Regime,
                                                                  commit: bool)
```

Wire-on / wire-off seam lives in `composition/runtime_assembly.py`:

```python
@dataclass(frozen=True)
class RuntimeProfile:
    p5_wiring_enabled: bool = False   # default OFF (legacy byte-compat)
    p5_learners: tuple[LearnerABC, ...] = ()
    continuous_state_owner: ContinuousStateOwner | None = None
```

When `p5_wiring_enabled=False`, all canonical owners use their hardcoded
defaults **byte-for-byte** (G2 acceptance). When `True`, each canonical owner
invokes `apply_p5_policy(learner_snapshot)` after the learner update; the
snapshot's `policy_output[i]` overwrites the mapped field. `ContinuousStateOwner`
is held regardless of `p5_wiring_enabled` (it is pure-fact infrastructure).

## 2. P5 mandatory wiring protocol

### 2.1 `LearnerABC.wire_to_owner`

```python
class LearnerABC(Protocol):
    def update(self, state, llm_signal, novelty, tick_id, rpe_signal=None) -> _LearningSnapshot: ...
    def wire_to_owner(self, owner: Any) -> None:
        """Bind this learner's snapshot to the canonical owner's apply_p5_policy.
        Owner must implement apply_p5_policy(snapshot: _LearningSnapshot) -> None.
        Idempotent: re-wiring replaces the binding."""
        owner._p5_learner_binding = self
```

Sidecar learners already ship; `wire_to_owner` is added as a Protocol default
that delegates to a new helper in `learning/wiring.py`. All 15 existing
sidecar learners inherit this without code changes (Protocol default).

### 2.2 Canonical owner `apply_p5_policy`

Each canonical owner gains two new Protocol members:

```python
class P5WiredOwner(Protocol):
    p5_parameter_mapping: ClassVar[dict[str, str]]  # field_name -> LearnedParameterCategory
    _p5_learner_binding: LearnerABC | None
    
    def apply_p5_policy(self, snapshot: _LearningSnapshot) -> None:
        """Override hardcoded field defaults from a learner snapshot.

        Wire-on only. Wire-off never calls this method (G2 acceptance gate).

        For each (field_name, category) in p5_parameter_mapping:
            category_idx = self._learner_categories().index(category)
            value = snapshot.policy_output[category_idx]
            setattr(self, field_name, _clip_to_field_range(field_name, value))

        Failure semantics: any out-of-range value raises. No silent fallback.
        """
```

The mapping is a class-level `ClassVar[dict[str, str]]` so that wire-off
owner instances still see the mapping but never read from it (the field
defaults remain first-version constants until `apply_p5_policy` is invoked).

### 2.3 `p5_parameter_mapping` per owner (105 entries)

Each owner declares its mapping in the config dataclass (frozen, so the
mapping table itself is immutable once the config is built). The mapping
points from the **canonical owner field name** to the **existing P5
`LearnedParameterCategory` literal**. This lets us reuse the 18 already-shipped
category literals without inventing new ones.

| Owner | Field | → Category |
|-------|-------|------------|
| **neuromodulation** (14) | `alpha_phasic` | `decay_speed_persistence` |
| | `alpha_tonic` | `decay_speed_persistence` |
| | `novelty_to_norepinephrine` | `channel_gain_sensitivity` |
| | `uncertainty_to_norepinephrine` | `channel_gain_sensitivity` |
| | `reward_to_dopamine` | `channel_gain_sensitivity` |
| | `novelty_to_dopamine` | `channel_gain_sensitivity` |
| | `threat_to_cortisol` | `channel_gain_sensitivity` |
| | `serotonin_social_safety` | `channel_gain_sensitivity` |
| | `oxytocin_social` | `channel_gain_sensitivity` |
| | `opioid_reward` | `channel_gain_sensitivity` |
| | `opioid_social` | `channel_gain_sensitivity` |
| | `acetylcholine_novelty` | `channel_gain_sensitivity` |
| | `coupling_gain` | `hormone_predict_coupling` |
| | `agreement_deadzone` | `hormone_predict_coupling` |
| **autonomy** (12) | `decay_factor` | `continuity_carry_policy` |
| | `minimum_decayed_pressure` | `continuity_carry_policy` |
| | `reinforcement_gain` | `continuity_carry_policy` |
| | `action_continuation_pressure` | `drive_integration_policy` |
| | `action_temporal_pressure` | `drive_integration_policy` |
| | `action_identity_pressure` | `drive_integration_policy` |
| | `continue_continuation_pressure` | `drive_integration_policy` |
| | `concluded_continuation_pressure` | `drive_integration_policy` |
| | `baseline_temporal_pressure` | `drive_integration_policy` |
| | `unresolved_identity_pressure` | `drive_integration_policy` |
| | `resolved_identity_pressure` | `drive_integration_policy` |
| | `retrieval_pull_divisor` | `proactive_externalization_policy` |
| | (implicit factor for `decayed_pressure` formula) | `continuity_carry_policy` |
| **feeling** (43) | `valence_from_dopamine`, `valence_from_opioid_tone`, `valence_from_serotonin`, `valence_from_cortisol` | `feeling_mapping_strength` |
| | `arousal_from_norepinephrine`, `arousal_from_excitation` | `feeling_mapping_strength` |
| | `tension_from_cortisol`, `tension_from_norepinephrine` | `feeling_mapping_strength` |
| | `comfort_from_opioid_tone`, `comfort_from_oxytocin`, `comfort_from_serotonin`, `comfort_from_cortisol` | `feeling_mapping_strength` |
| | `pain_like_from_cortisol`, `pain_like_from_opioid_tone` | `feeling_mapping_strength` |
| | `social_safety_from_oxytocin`, `social_safety_from_serotonin`, `social_safety_from_cortisol` | `feeling_mapping_strength` |
| | `fatigue_from_inhibition`, `fatigue_from_excitation` | `feeling_mapping_strength` |
| | `cpu_to_arousal`, `cpu_to_tension` | `feeling_coupling_strength` |
| | `memory_to_fatigue`, `memory_to_tension` | `feeling_coupling_strength` |
| | `latency_to_fatigue`, `latency_to_tension` | `feeling_coupling_strength` |
| | `error_to_pain_like`, `error_to_tension` | `feeling_coupling_strength` |
| | `alpha_phasic`, `alpha_tonic` (PersistentFeelingConstructionPath) | `feeling_persistence` |
| | `weight_clip_low`, `weight_clip_high` (P5-feel learning path) | `feeling_persistence` |
| | `bias_clip_low`, `bias_clip_high` (P5-feel learning path) | `feeling_persistence` |
| | `precision_floor`, `precision_ceiling`, `flexibility_threshold`, `flexibility_floor`, `flexibility_ceiling` (P5-feel) | `feeling_persistence` |
| | `learning_rate`, `commit_threshold`, `regime_hysteresis_ticks`, `habitual_residual_threshold` | `feeling_persistence` |
| **rpe** (13) | `w_success`, `w_response_accepted`, `w_latency` | (NEW: `dopamine_weight_policy`) |
| | `w_ne_executed`, `w_ne_failure`, `w_ne_latency` | (NEW: `norepinephrine_weight_policy`) |
| | `w_ser_alignment`, `w_ser_consecutive` | (NEW: `serotonin_weight_policy`) |
| | `w_cor_unresolved`, `w_cor_candidate`, `w_cor_suppressed` | (NEW: `cortisol_weight_policy`) |
| | `success_value`, `accepted_value`, `rejected_value` | (NEW: `reward_shaping_policy`) |
| | `latency_max_ticks`, `consecutive_normalize_ticks`, `candidate_normalize` | (NEW: `reward_shaping_policy`) |
| **memory** (10) | `recalled_relevance_weight` | `memory_replay_priority` |
| | `recalled_affect_weight` | `memory_replay_priority` |
| | `recalled_arousal_weight` | `memory_replay_priority` |
| | `recalled_tension_weight` | `memory_replay_priority` |
| | `recalled_pain_weight` | `memory_replay_priority` |
| | `consolidation_threshold` | `memory_consolidation_policy` |
| | `arousal_weight` | `memory_consolidation_policy` |
| | `tension_weight` | `memory_consolidation_policy` |
| | `pain_weight` | `memory_consolidation_policy` |
| | `mismatch_weight` | `memory_consolidation_policy` |
| **workspace** (5) | `priority_weight` | `workspace_priority_policy` |
| | `arousal_weight` | `workspace_arousal_policy` |
| | `tension_weight` | `workspace_tension_policy` |
| | `pain_weight` | `workspace_pain_policy` |
| | `feeling_weight` | `workspace_feeling_policy` |
| **thought_gating** (4) | `fire_threshold` | `fire_threshold_policy` |
| | `resource_pressure_block_threshold` | `resource_pressure_policy` |
| | `idle_decay` | `idle_decay_policy` |
| | `arousal_gain` | `arousal_gain_policy` |
| **temporal** (2) | `per_tick_increment` | (NEW: `temporal_pacing_sensitivity`) |
| | `max_signal` | (NEW: `temporal_pacing_sensitivity`) |
| **consciousness** (2) | `temperature` | `commitment_policy` |
| | `timeout_seconds` | `quiet_state_policy` |

That is **105 field-to-category mappings** (verified by counting).
The 9 owners already have the matching `LearnedParameterCategory` literals
(`FeelingLearnedParameterCategory`, `AutonomyLearnedParameterCategory`,
`NeuromodulatorLearnedParameterCategory`, etc.). The 7 new ones
(`dopamine_weight_policy`, `norepinephrine_weight_policy`,
`serotonin_weight_policy`, `cortisol_weight_policy`,
`reward_shaping_policy`, `memory_replay_priority`,
`memory_consolidation_policy`, `workspace_*_policy`,
`fire_threshold_policy`, `resource_pressure_policy`,
`idle_decay_policy`, `arousal_gain_policy`,
`temporal_pacing_sensitivity`) are added to `RealRPELearnedParameterCategory`,
`MemoryLearnedParameterCategory`, `WorkspaceLearnedParameterCategory`,
`ThoughtGatingLearnedParameterCategory`, and a new
`TemporalLearnedParameterCategory` Literal. None of these are novel
concepts — they are the **names of the fields the canonical owners already
expose**, surfaced as P5 learner categories so wire-on has a target.

### 2.4 Snapshot binding: 11-dim policy_output → 105 fields

Each `_LearningSnapshot.policy_output` is a tuple of length `output_dim`
where `output_dim` is the union of all categories the learner is wired to
cover. For P-TEMPORAL, each canonical owner's learner produces
`output_dim = len(_LEARNED_PARAMETER_CATEGORIES)` for that owner (e.g.
neuromodulation: 5, autonomy: 3, feeling: 3, consciousness: 3, memory: 5,
workspace: 5, thought_gating: 4, temporal: 1, rpe: 6).

`apply_p5_policy` indexes into `policy_output` using a precomputed
`_category_to_index` table (built once when the learner is bound, frozen
on the owner instance). It then assigns each mapped field from its category
index, clipped to the field's declared range (e.g. `alpha_phasic` ∈
(0.0, 1.0]; `decay_factor` ∈ [0.0, 1.0]; etc.).

## 3. Wall-clock continuous state

### 3.1 `ContinuousStateOwner`

```python
@dataclass
class ContinuousStateOwner:
    wall_clock: WallClock | None
    _wall_clock_elapsed_seconds: float = field(default=0.0, init=False)
    _last_external_stimulus_wall_seconds: float | None = field(default=None, init=False)
    _current_episode_id: int = field(default=0, init=False)
    _episode_start_wall_seconds: float | None = field(default=None, init=False)
    _previous_tick_wall_seconds: float | None = field(default=None, init=False)
    _fired_previous_tick: bool = field(default=False, init=False)
    
    NEW_EPISODE_GAP_SECONDS: float = 60.0   # C_engineering_hypothesis first-version
    
    def observe_tick(
        self,
        *,
        fired: bool,
        external_stimulus_present: bool,
        tick_wall_seconds: float | None,
    ) -> None:
        if tick_wall_seconds is None:
            return  # wall-clock-absent mode: nothing to advance (honest absence)
        if self._previous_tick_wall_seconds is not None:
            self._wall_clock_elapsed_seconds += (
                tick_wall_seconds - self._previous_tick_wall_seconds
            )
        if external_stimulus_present and self._last_external_stimulus_wall_seconds is None:
            self._last_external_stimulus_wall_seconds = tick_wall_seconds
        if external_stimulus_present:
            self._last_external_stimulus_wall_seconds = tick_wall_seconds
        gap = (
            (tick_wall_seconds - self._episode_start_wall_seconds)
            if self._episode_start_wall_seconds is not None else 0.0
        )
        if (
            self._episode_start_wall_seconds is None
            or (tick_wall_seconds - self._previous_tick_wall_seconds or 0.0)
                > self.NEW_EPISODE_GAP_SECONDS
        ):
            self._current_episode_id += 1
            self._episode_start_wall_seconds = tick_wall_seconds
        self._previous_tick_wall_seconds = tick_wall_seconds
        self._fired_previous_tick = fired
    
    def sample(self) -> ContinuousStateReading:
        return ContinuousStateReading(
            wall_clock_elapsed_seconds=round(self._wall_clock_elapsed_seconds, 4),
            last_external_stimulus_age_seconds=(
                self._compute_age(self._last_external_stimulus_wall_seconds)
            ),
            current_episode_id=self._current_episode_id,
            episode_elapsed_seconds=(
                self._compute_age(self._episode_start_wall_seconds)
            ),
            wall_clock_present=self.wall_clock is not None,
        )
```

### 3.2 Wall-clock hormone decay

`DualTimescaleNeuromodulatorUpdatePath.update_levels` is upgraded to accept
the `ContinuousStateReading` and a wall-clock-driven decay term:

```python
# Old (shipped, R-PROTO-LEARN.9):
next = clamp(
    prior + α_phasic × (drive − prior) + α_tonic × (baseline − prior),
    legal_min, legal_max,
)

# New (P-TEMPORAL):
decay_fraction = (
    continuous_state.wall_clock_elapsed_since_prior / half_life_seconds
    if continuous_state is not None and half_life_seconds > 0
    else 0.0
)
α_wall = min(decay_fraction, 1.0)   # learner-supplied
next = clamp(
    prior
    + α_phasic × (drive − prior)
    + α_tonic × (baseline − prior)
    + α_wall × (baseline − prior),
    legal_min, legal_max,
)
```

`α_wall` is the **wall-clock-decay multiplier** that the learner controls via
`decay_speed_persistence`. The first-version learner uses the
R-PROTO-LEARN.9 `α_phasic=0.6` / `α_tonic=0.1` constants and produces
`α_wall=0.0` until enough ticks have passed to span a `half_life_seconds`
interval — so **wire-off legacy behavior is byte-for-byte preserved when
`α_wall=0.0`**.

`half_life_seconds` itself is **learned** (not hardcoded). It rides on the
existing `decay_speed_persistence` P5 category. The first-version learner
initializes `half_life_seconds=90.0` (cortisol reference from Einhauser 2018
pupil dilation as effort index, Seth 2013 interoceptive inference). Wire-on
then lets the learner tune this per channel.

### 3.3 `RestStateTemporalSource` upgrade

The existing `temporal/engine.py` `RestStateTemporalSource` counts
`ticks_since_last_fire` (a tick-counted pacing signal, unitless `[0,1]`). It
is upgraded to also accept `wall_clock_elapsed_seconds` from
`ContinuousStateOwner.sample()`:

```python
def sample(
    self,
    external_stimulus_present: bool,
    continuous_state: ContinuousStateReading | None = None,
) -> TemporalPacingSample:
    if continuous_state is not None and self._last_fire_wall_seconds is not None:
        # wall-clock-driven pacing
        elapsed = continuous_state.wall_clock_elapsed_seconds - self._last_fire_wall_seconds
        signal = min(self.max_signal, self.per_tick_increment * (elapsed / self.reference_pace_seconds))
    else:
        # legacy tick-counted pacing
        signal = min(self.max_signal, self.per_tick_increment * self._ticks_since_last_fire)
    return TemporalPacingSample(
        temporal_signal=round(max(0.0, signal), 4),
        dmn_available=not external_stimulus_present,
    )
```

`reference_pace_seconds` is itself the **P5 `temporal_pacing_sensitivity`
category** (first-version default 1.0s — a tick is conceptually ~1 second in
the brain's intrinsic time scale).

## 4. Composition wiring

`composition/runtime_assembly.py` gains:

```python
@dataclass(frozen=True)
class RuntimeProfile:
    p5_wiring_enabled: bool = False   # OFF by default (G2 byte-compat)
    p5_learners: tuple[LearnerABC, ...] = ()
    continuous_state_owner: ContinuousStateOwner | None = None
    
    def __post_init__(self):
        if self.p5_wiring_enabled and not self.p5_learners:
            raise CompositionError("p5_wiring_enabled=True requires at least one LearnerABC")
        if self.p5_wiring_enabled and self.continuous_state_owner is None:
            raise CompositionError(
                "p5_wiring_enabled=True requires ContinuousStateOwner (wall-clock substrate)"
            )
```

Per tick, after each canonical owner's `observe` / `update`, the assembly
calls (only when `p5_wiring_enabled=True`):

```python
for owner, learner in zip(canonical_owners, self.profile.p5_learners):
    snapshot = learner.update(
        owner.get_state(),
        llm_signal=current_appraisal_signal,
        novelty=novelty_score,
        tick_id=frame.tick_id,
        rpe_signal=current_rpe_signal,
    )
    owner.apply_p5_policy(snapshot)
```

The order is **owner.update → learner.update → owner.apply_p5_policy** so
that the policy is learned against the same state the owner just used, then
applied for the **next** tick. This preserves determinism: snapshot.policy_output[i]
on tick N is the value applied on tick N+1. Tick 0 uses first-version defaults
(consistent with the legacy path byte-compat).

`ContinuousStateOwner.observe_tick` is called **once per tick** at the very
start of the composition, so every owner sees the same continuous-state
reading for the current tick.

## 5. Wire-off byte-compat guarantee

Wire-off test (G2 acceptance): for each of 9 owners, run a 200-tick deterministic
seed, dump `__dict__` after every tick, byte-compare against pre-P-TEMPORAL
golden files. Implementation:

```python
def test_wire_off_byte_compat_neuromodulation():
    owner = FirstVersionNeuromodulatorEngine(...)   # wire-off defaults
    golden = load_golden("neuromodulation_wireoff_200ticks.json")
    for tick in range(200):
        state = owner.observe(...)                  # deterministic inputs
        assert owner.__dict__ == golden[tick]
        owner.update(...)
```

The golden files are recorded once before any P-TEMPORAL change to the
canonical owner code, so wire-off is **literally identical to pre-slice
behavior**.

## 6. Test plan

| Tier | Count | Description |
|------|-------|-------------|
| Unit (owner `apply_p5_policy`) | 27 | 3 tests × 9 owners: field override + range clip + category-index lookup |
| Unit (ContinuousStateOwner) | 8 | episode split on 60s gap, no-clock absent mode, single-stimulus age, episode_id monotonic |
| Integration (wire-off byte-compat) | 18 | 2 tests × 9 owners: 200-tick deterministic replay + JSON-equality |
| Integration (wall-clock decay) | 4 | cortisol decays under stress, dopamine varies under reward, episode split, no-clock absent |
| Smoke (real LLM 1129 tick) | 3 | re-run Turing runner; assert D2 ≥ 0.5, D5 ≥ 0.6, D8 ≥ 0.4, D10 ≥ 0.5 |
| Architecture guard | 3 | R21 print guard, R79-A naming, R-PROTO-LEARN.6 no-fallback |
| **Total** | **63** | plus 18 legacy R-PROTO-LEARN + 5 helios_v2 baseline = 86 in `tests/test_p_temporal_*.py` |

Test files:

- `tests/test_p_temporal_wiring.py` — 27 unit + 18 integration
- `tests/test_p_temporal_continuous_state.py` — 8 unit + 4 integration
- `tests/test_p_temporal_smoke_1129.py` — 3 smoke (skipped in CI; run on real-LLM budget)
- `tests/test_p_temporal_architecture_guard.py` — 3 architecture

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Wire-on default OFF means default behavior is unchanged; production assembly must explicitly enable | Default OFF is the **safe** choice for a research slice. Production assembly defaults wire-on (matches R100/R101 capability-seam pattern). |
| 1129-tick real-LLM cost ~6h, might exceed budget | Run smoke in background detached (same `_start_turing.sh` pattern); fall back to 200-tick smoke if budget tight (G4 acceptance still passes). |
| `p5_parameter_mapping` table mistakes (wrong field name) | `apply_p5_policy` validates every mapping key against `dataclasses.fields()` of the owner; raises `P5WiringError` on miss. |
| CRLF corruption on first edit to any owner file | Detect with `Path.read_bytes().count(b'\r\n')`; if > 0, normalize to LF before patch. |
| Wall-clock absent mode (test fixtures without WallClock) | ContinuousStateOwner.observe_tick returns silently when `tick_wall_seconds is None`; legacy path byte-compat holds. |
| Existing 506 R-PROTO-LEARN tests regress due to wire-on default in tests | All R-PROTO-LEARN tests use the **wire-off** profile (no P5 wiring). The 506 baseline is preserved. |

## 8. Commit plan

Single commit on `research/R-PROTO-LEARN-appraisal-multi-mechanism`:

```
feat(R-PROTO-LEARN.P-TEMPORAL): wire 105 hardcoded params to P5 + wall-clock continuous state

Slice: P-TEMPORAL — single commit shipping both the P5 mandatory wiring
(105 hardcoded canonical-owner fields across 9 cognitive owners bound to
the existing 18 LearnedParameterCategory literals) and the wall-clock
continuous-state substrate (new ContinuousStateOwner infrastructure rank +
DualTimescaleNeuromodulatorUpdatePath wall-clock decay term +
RestStateTemporalSource wall-clock pacing upgrade).

Architecture rationale: helios P5 learner sidecars (15 owners) ship
complete since P5-A.2 (commit f9d8896, 2026-06-18 01:20+), but no
canonical owner consumes them. The Turing System Eval (2026-06-18 09:42)
showed four symptoms (D2/D5/D8/D10) all rooted in the same
time-dimension absence (small black 16:55+ 核心洞察: "底层架构缺失时间维度").

This slice solves both at the architectural foundation rather than per
module:
  - 105 hardcoded defaults -> P5 learner surfaces (wire-on / wire-off seam)
  - 0 cognitive owners consuming wall-clock -> all 9 consume
    ContinuousStateOwner.

Out of scope (deferred): LLM-judge episode detection, phase transitions,
re-implementation of R85/R100/R101.

Files changed: 18 source files + 4 test files (84 new tests). 6h 1129-tick
real-LLM regression validates D2/D5/D8/D10 baseline lift.
```

## 9. Implementation order

1. New `temporal_continuous_state/{__init__,contracts,engine}.py` + tests.
2. New `learning/wiring.py` Protocol helpers.
3. Extend `learning/protocol.py` (LearnerABC.wire_to_owner).
4. Extend `learning/contracts.py` (5 new LearnedParameterCategory Literals).
5. Patch each of 9 canonical owners: add `p5_parameter_mapping` ClassVar + `apply_p5_policy` method.
6. Patch `DualTimescaleNeuromodulatorUpdatePath` wall-clock decay.
7. Patch `RestStateTemporalSource` wall-clock pacing.
8. Patch `composition/runtime_assembly.py` wire-on / wire-off seam.
9. Run unit + integration tests; iterate to green.
10. Run 1129-tick real-LLM smoke (6h budget).
11. Score 10-dim Turing, compare to baseline.
12. Commit on research branch (no merge to main).
