# Requirement P-TEMPORAL — P5 Mandatory Wiring + Wall-Clock Continuous State

## 1. Background and Problem

### 1.1 From R-PROTO-LEARN.Tier1-Tier4 to the missing wiring

The R-PROTO-LEARN program (Tier 1: R11-R15, Tier 2: R16-R17, Tier 3: R18-R20,
Tier 4: R21-R24, plus P5-A and P5-A.2) shipped 15 owner `Learner` sidecars in
`helios_v2/learning/` (memory / thought_gating / directed_retrieval /
internal_thought / autonomy / action_externalization / consciousness /
evaluation / experience_writeback / identity_governance / outward_expression /
outward_expression_externalization / planner_bridge / prompt_contract /
workspace). Each `Learner` conforms to one `LearnerABC` base and emits a
`_LearningSnapshot(residual, regime, commit)` per tick.

The 15 owner `Learner`s together expose **18 distinct
`LearnedParameterCategory` literals** (one per canonical owner: e.g.
`NeuromodulatorLearnedParameterCategory` covers `channel_gain_sensitivity` /
`cross_channel_coupling_strength` / `decay_speed_persistence` /
`gate_influence_strength` / `hormone_predict_coupling`). The `mandatory_learned_parameters`
contract on each canonical owner config declares the exact set of categories
that P5 must learn.

**However, none of the 15 canonical owners actually consumes the sidecar
learner output.** Search confirms it:

- `from helios_v2.learning import ...` returns **0 hits** in
  `src/helios_v2/{memory, autonomy, neuromodulation, feeling, identity_governance,
  consciousness, thought_gating, directed_retrieval, internal_thought,
  workspace, ...}/engine.py`.
- Only `scripts/r_proto_learn_*.py` (smoke + ablation studies) import the
  sidecars, and only as standalone evaluators.

So `mandatory_learned_parameters` is **declared but not wired** — the P5
contract is honored on paper but not at runtime.

### 1.2 From R-PROTO-LEARN.P5-A.2 to the missing time dimension

R-PROTO-LEARN.P5-A.2 (`f9d8896`, 2026-06-18 01:20+) hard-coupled the
4-channel `rpe_signal` (dopamine / norepinephrine / serotonin / cortisol) into
the `Learner.update` target-vector computation. The ablation study
(`scripts/r_proto_learn_p5a_ablation_study.py`) showed:

- regime switch H1 vs H0 p=0.015 (vs P5-A.1 p=1.0, decisive positive).
- commit count H1=6.45 vs H0=4.8 abs diff=1.65 (RealRPE = structured signal
  → closure better → commits MORE, scientifically inverted).
- R21 consciousness H0=0 commit → H1=7-8 commits.

The P5-A.2 study confirmed that **structured learning signals break the
attractor that P5-A.1 surfaced** (helios learning was getting trapped in a
`LLM appraisal × frozen weights × no clock` loop). The P5-A.2 root-cause was
that **the learning signal was LLM appraisal only**, missing real running
outcomes (RealRPE), and even with RealRPE the learner was still operating in
a tick-locked world.

### 1.3 From Turing System Eval 2026-06-18 to the four symptoms

The Turing System Eval (`research-turing-system-eval/`, 2026-06-18 03:09+)
ran 1129 real-LLM ticks across 10 scenario blocks (A 亲密 / B 压力 / C 长期记忆
/ D 惊喜 / E 威胁 / F 身份 / G 创造 / H 自我认知 / I 价值 / J 抗压) and scored
helios on 10 dimensions. The 6h / 1129-tick run surfaced **four symptoms that
share the same underlying pattern** (helios does not respond to accumulated
input):

| Dim | Symptom | Baseline | Diagnostic finding |
|-----|---------|----------|---------------------|
| D2 bio_responsiveness | 🧊 Hormone freeze | 0.008 | After 8 tick warmup, 1121 ticks of cortisol / dopamine / serotonin stay locked at (0.7607, 0.6928, 0.3000). |
| D10 stress_recovery | 😰 No recovery | 0.000 | Block J (12 抗压 scenarios) cortisol 0.6928 ticks 0-100; no half-life decay. |
| D5 cross_tick_continuity | 🎭 No narrative | 0.521 | Across-tick Jaccard 0.34 on internal thought; narrative thread breaks every few ticks. |
| D8 self_recognition | 💬 No "I" | 0.184 | Block A (亲密) self_ref 9.8% vs Block J (抗压) 37.3%; overall 18.4%. |

On 2026-06-19 16:55+ 小黑 articulated the unified root cause: **"底层架构设计的这颗仿生人脑架构，从底层上就缺失了时间维度，各个模块现在的enhance就像是在 by 模块去单独解决这个问题，而没有解决根本问题"** (translation: the brain-inspired architecture is missing the time dimension at its foundation; per-module enhancements don't fix the root cause).

### 1.4 Code-level confirmation of the time-dimension absence

`grep -rnE "(wall_clock|elapsed|decay|half_life|temporal)" src/helios_v2/{consciousness,memory,neuromodulation,identity_governance,feeling,internal_thought,workspace,...}/engine.py` returns **0 hits** outside `autonomy` (which uses a per-tick `decay_factor=0.82` constant, not wall-clock). `wall_clock/` is wired into 5 non-cognitive files (`runtime/kernel.py`, `runtime/contracts.py`, `composition/bridges.py`, `composition/runtime_assembly.py`, `channel/drivers/cli.py`) — the value is **produced and carried but never consumed**.

The existing `temporal` owner (`helios_v2/temporal/engine.py`,
`RestStateTemporalSource`) only feeds the `09` thought-gate. It uses
`ticks_since_last_fire` (tick-counted pacing, unitless `[0,1]`) — **not
wall-clock**. So even the temporal-aware owner is not time-aware.

### 1.5 From 105 hardcoded defaults to P5 surfaces

A scan across 14 cognitive owner directories (`neuromodulation`, `autonomy`,
`temporal`, `feeling`, `consciousness`, `rpe`, `memory`, `thought_gating`,
`workspace`, `outward_expression`, `directed_retrieval`, `internal_thought`,
`identity_governance`, `evaluation`) finds **105 numeric defaults** in
`dataclass` field initializers:

| Owner | Hardcoded count | Notes |
|-------|-----------------|-------|
| feeling | 43 | `valence_from_dopamine = 0.30` × 43 mapping weights |
| neuromodulation | 14 | `alpha_phasic = 0.6` + 11 drive-mapping gains + 2 corroborator params |
| rpe | 13 | 16 RPE channel weights (some grouped as sums) |
| autonomy | 12 | `decay_factor = 0.82` + 11 pressure / carry params |
| memory | 10 | `recalled_relevance_weight = 0.6` × 10 replay/consolidation weights |
| workspace | 5 | `priority_weight = 0.6` × 5 weights |
| thought_gating | 4 | `fire_threshold = 0.55` + 3 |
| temporal | 2 | `per_tick_increment = 0.2`, `max_signal = 1.0` |
| consciousness | 2 | `temperature = 0.1`, `timeout_seconds = 30.0` |

These 105 constants are the **first-version surface area** that R-PROTO-LEARN
explicitly designated for P5 learner replacement: the contracts already name
the categories (`channel_gain_sensitivity`, `feeling_mapping_strength`,
`continuity_carry_policy`, `boundary_check_policy`, etc.). The gap is **not a
missing category list — it is the missing wiring**.

## 2. Goal

Ship **P-TEMPORAL** in one commit: a single research slice that wires the
existing 15 P5 sidecar learners into their canonical owners **and** introduces
a wall-clock-driven continuous-state substrate so that the four Turing-eval
symptoms (D2 / D5 / D8 / D10) are no longer addressed per-module but are
solved at the architectural foundation.

Two coupled outcomes:

1. **P5 mandatory wiring**: the 105 hardcoded constants become **declared
   P5 learner surfaces** (each owner config gains a `p5_parameter_mapping:
   dict[str, LearnedParameterCategory]` table; each owner gains a
   `apply_p5_policy(snapshot)` method that overrides its hardcoded defaults
   from a learner snapshot). Wire-on / wire-off seam: **wire-off preserves
   byte-for-byte legacy behavior** (R-PROTO-LEARN.6 no-fallback philosophy,
   R100/R101 capability-seam pattern). Wire-on production default in
   `runtime_assembly.py`.
2. **Wall-clock continuous-state substrate**: a new infrastructure owner
   `temporal_continuous_state/` (ranked alongside `wall_clock` /
   `observability` / `persistence`) holds `wall_clock_elapsed_seconds` /
   `last_external_stimulus_wall_seconds` / `current_episode_id` /
   `episode_start_wall_seconds`. `DualTimescaleNeuromodulatorUpdatePath`
   gains a wall-clock-driven decay term whose strength is **the existing P5
   `decay_speed_persistence` learned-parameter category**. `TemporalSource`
   is upgraded from `ticks_since_last_fire` (tick-counted) to wall-clock
   pacing. All cognitive owner invocations in `composition/runtime_assembly.py`
   receive the continuous-state handle.

## 3. Scope and Non-Scope

### 3.1 In scope (one commit)

- **`learning/protocol.py`** — extend `LearnerABC` with `wire_to_owner(owner)` + canonical owner-side `apply_p5_policy(snapshot)` Protocol.
- **`learning/wiring.py` (NEW)** — `P5OwnerWiring` factory, wire-on / wire-off seam, per-owner parameter-to-snapshot binding.
- **`temporal_continuous_state/` (NEW owner, infrastructure rank)** — `ContinuousStateOwner` with wall-clock fields and `observe_tick` cross-tick state machine.
- **9 canonical owners** gain `apply_p5_policy(snapshot)` + `p5_parameter_mapping` config table:
  `neuromodulation` (14 params), `autonomy` (12), `feeling` (43), `rpe` (13), `memory` (10), `workspace` (5), `thought_gating` (4), `temporal` (2), `consciousness` (2). Total: **105 mapping entries** into the existing 18 `LearnedParameterCategory` literals.
- **`DualTimescaleNeuromodulatorUpdatePath.update_levels`**: add wall-clock decay term gated by `decay_speed_persistence` learner category.
- **`RestStateTemporalSource`**: upgrade pacing from `ticks_since_last_fire` to `wall_clock_elapsed_since_last_fire`.
- **`composition/runtime_assembly.py`**: wire `ContinuousStateOwner` + 9 `apply_p5_policy` invocations per tick, behind a single `p5_wiring_enabled: bool` seam.
- **Tests**: 24 + 8 + 27 + 18 + 4 + 3 = 84 tests across unit / integration / smoke / legacy-byte-compat / wall-clock-decay / 1129-tick real-LLM regression.

### 3.2 Out of scope (explicit non-goals)

- ❌ No episode detection via LLM-judge (Nemori Structure Prior full version). Episode split = pure wall-clock gap > 60s, runtime-only arithmetic.
- ❌ No new "phase transition" / "rupture-re-attunement" concepts (Geometric Hyperscanning of Affect 2025); those belong to a future P6 slice.
- ❌ No new owner called `temporal_continuity` (the architectural fix is wire-all-owners, not add-one-owner).
- ❌ No hardcoded half-life constants: half_life is learned via existing `decay_speed_persistence` category.
- ❌ No DualNet / MIRAGE-style fast-slow explicit split: helios already has R85 4L memory + R-PROTO-LEARN.3 predictive coding; this slice does not re-architect.
- ❌ No re-implementation of R100/R101 (4-layer memory stratification + 6-dim objective importance) — those ship on `main` and we do not merge.
- ❌ No re-implementation of R85 4L memory decay formulas — `memory` owner's `apply_p5_policy` learns `consolidation_threshold` (existing learned category), not new decay math.

## 4. Acceptance Gates

| Gate | Acceptance | Diagnostic |
|------|------------|------------|
| **G1 unit tests** | 24 + 8 + 27 + 18 = 77 tests passed | `pytest tests/test_p_temporal_*.py -q` |
| **G2 wire-off byte-compat** | 9/9 owners byte-for-byte identical to pre-P-TEMPORAL behavior | compare owner output JSON via golden file |
| **G3 wire-on parameter coverage** | 105/105 hardcoded params overridden by learner snapshot | snapshot inspection, `apply_p5_policy` must set each field |
| **G4 wall-clock decay active** | 200-tick smoke shows cortisol varies across ticks under stress | `assert np.std(cortisol_history) > 0.05` |
| **G5 1129-tick real-LLM Turing** | D2 ≥ 0.5, D5 ≥ 0.6, D8 ≥ 0.4, D10 ≥ 0.5 | re-run `scripts/helios_turing_system_runner.py` and `helios_turing_scorer.py` |
| **G6 R-PROTO-LEARN regression** | 506 + 77 = 583 tests passed | `pytest tests/test_r_proto_learn_*.py -q` |
| **G7 whole-tree regression** | 1640 + 84 = 1724 tests passed (perf 7 known fail excluded) | split-run per minute-shell-timeout rule |
| **G8 architecture guard** | R21 print/log guard + R79-A naming guard + R-PROTO-LEARN.6 no-fallback guard all green | `python scripts/architecture_guard.py` |

G5 is the binding gate: **if D2 / D5 / D8 / D10 do not improve over the
2026-06-18 09:42 baseline (0.008 / 0.521 / 0.184 / 0.000), the slice fails
regardless of G1-G4**.

## 5. Constraints (preserved from prior R-PROTO-LEARN / P5 / Turing slices)

- **Research branch only**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`. Never merged to `main`.
- **No fallback / no degradation** (R-PROTO-LEARN.6): wire-on failure must hard-stop, not silently fall back to wire-off.
- **Fail-fast truth-first**: missing numpy / missing LLM key / missing wall-clock all raise, never paper over.
- **CRLF preservation**: any patch into an existing file must first detect `b'\r\n'` line endings via `Path.read_bytes().count(b'\r\n')`.
- **Shell heredoc / pipe failures**: use `write_file` for multi-line content; use `python -c` for shell snippets.
- **commit message format**: conventional-commits style with `feat(R-PROTO-LEARN.P-TEMPORAL): ...` prefix.

## 6. References

- `docs/requirements/research-r-proto-learn/requirement.md` — R-PROTO-LEARN charter.
- `docs/requirements/research-p5-feel-9/` — P5-feel 6-layer emotion architecture.
- `docs/requirements/research-p5a-real-rpe-coupled/result.md` — P5-A.2 ablation results (R21 H0=0 commit → H1=7-8 commits).
- `docs/requirements/research-turing-system-eval/analysis-deep-dive.md` — Turing 4-symptom diagnostic.
- `helios_v2/learning/contracts.py` — `LearnerConfig` 13 hyperparameters + `LearnerABC`.
- `helios_v2/wall_clock/contracts.py` — `WallClockReading` (pure-fact capability boundary).
- `helios_v2/continuity_checkpoint/` — `decayed_pressure` checkpoint pattern (same wall-clock decay idea, currently only at checkpoint, not at runtime).

## 7. Open questions deferred to design.md / task.md

- Q1: How exactly does `apply_p5_policy` route the 11-dim `_LearningSnapshot.policy_output` vector into 105 specific field overrides (binding table format)?
- Q2: How does wall-clock decay coexist with `DualTimescaleNeuromodulatorUpdatePath`'s existing `α_phasic`/`α_tonic` leaky integrator (no double-counting)?
- Q3: Episode split heuristic — wall-clock gap > 60s only, or include scenario_id change / topic-shift keyword match?
- Q4: 1129-tick smoke cost: ~6h wall-clock — budget check vs 8h.
- Q5: When wire-off, how do we guarantee the `p5_parameter_mapping` table does not accidentally activate? (Hard test that asserts every owner has `apply_p5_policy` callable but never invoked.)
