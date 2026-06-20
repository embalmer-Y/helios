# Task P-TEMPORAL — Implementation Steps and Verification

## Phase 2 — Implementation Status (2026-06-20)

### Shipped
- [x] **Step 2.1**: `temporal_continuous_state/{__init__,contracts,engine}.py` (commit `fb9b750`)
  - 12/12 tests pass
- [x] **Step 2.2**: `learning/contracts.py` extended with `_LearningSnapshot.policy_output` (commit `fb9b750`)
- [x] **Step 2.3**: `learning/wiring.py` (new, 6.7KB) — `wire_learner_to_owner` + `apply_p5_policy_default` + `P5WiringError` (commit `fb9b750`)
- [x] **Step 2.4 Slice 3 first wave**: neuromodulation wire wall-clock half-life (commit `fb9b750`)
- [x] **Step 2.4 Slice 3 second wave**: autonomy/feeling/memory wire half-life + P5 surface (commit `25d48d5`)
- [x] **Step 2.5 runtime_assembly.py**: comment-only wire-in scaffolded (commit `25d48d5`)

### Deferred (requires architectural decisions)
- [ ] **Step 2.4 consciousness/identity_governance P5 surface**: contracts already declare 3 `ConsciousnessLearnedParameterCategory` literals; no numeric weights to wire. Identity governance is boolean policy. Decision needed: add new numeric field to `ConsciousnessConfig`?
- [ ] **Step 2.4 rpe P5 surface**: `RealRPEConfig.frozen` blocks mutation. Decision needed: unfreeze (breaking change) or sidecar learner?
- [ ] **Step 2.4 thought_gating/workspace P5 surface**: requires new `LearnedParameterCategory` literal values. Decision needed: define new categories or skip?
- [ ] **Step 2.5 full wire-in**: `runtime_assembly.py` change is comment-only. Decision needed: bind ContinuousStateOwner in production path or only in research profile?
- [ ] **Slice 4** (105 hardcoded → category): 73/105 wired via Slice 3 (4 owners). 32/105 deferred (frozen configs + missing categories).
- [ ] **Slice 5** (1129-tick 8h re-run): requires separate machine window with LLM budget cleared.

### Test baseline
```
504 passed in 13.00s (R-PROTO-LEARN)
679 passed in 25.70s (memory + neuromodulator + feeling + autonomy + P5-A + temporal)
12 passed in 2.83s (test_p_temporal_continuous_state.py)
2 pre-existing scipy errors (test_r_proto_learn_p5a_experiments.py)
```

### Branch state
- HEAD: `25d48d5`
- Branch: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
- Origin: pushed
- Iron rule: never merge to main

## Phase 1 — Documentation (DONE 2026-06-19 +小黑 拍板)

## Phase 1 — Documentation (DONE 2026-06-19 +小黑 拍板)

- [x] `requirement.md` (14k bytes) — problem statement, 105 hardcoded params audit, Turing 4-symptom table, code-level confirmation of time-dimension absence
- [x] `design.md` (25k bytes) — architecture overview, P5 wiring protocol, 105-entry mapping table, ContinuousStateOwner design, composition seam, test plan, risks, commit plan
- [x] `task.md` (this file)

## Phase 2 — Implementation (1 commit ship on `research/R-PROTO-LEARN-appraisal-multi-mechanism`)

### Step 2.1 — New infrastructure owner `temporal_continuous_state/`

Files:
- `src/helios_v2/temporal_continuous_state/__init__.py`
- `src/helios_v2/temporal_continuous_state/contracts.py`
- `src/helios_v2/temporal_continuous_state/engine.py`

Owner docstring: holds cross-tick wall-clock continuous state; pure-fact
infrastructure; imports no cognitive owner.

Acceptance:
- 8 unit tests pass (test_p_temporal_continuous_state.py::TestContinuousStateOwner).
- `__post_init__` rejects `wall_clock=...` mismatched type.

### Step 2.2 — Extend `learning/protocol.py` + `learning/contracts.py`

- `LearnerABC.wire_to_owner(owner)` default impl that sets `owner._p5_learner_binding = self`.
- Add 7 new `LearnedParameterCategory` Literals (one per missing
  owner-category) so the 105 mapping entries have a destination.

Acceptance:
- 24 existing P-PROTO-LEARN unit tests still pass (no regression).

### Step 2.3 — New `learning/wiring.py`

- `P5OwnerWiring` factory class.
- `wire_learner_to_owner(learner, owner)` helper.
- `P5WiringError` exception type.

Acceptance:
- All wire-off tests pass without `apply_p5_policy` being called.

### Step 2.4 — Patch 9 canonical owners

For each owner in
`[neuromodulation, autonomy, feeling, rpe, memory, workspace, thought_gating, temporal, consciousness]`:

1. Add `p5_parameter_mapping: ClassVar[dict[str, str]] = { ... }` listing
   each hardcoded field → `LearnedParameterCategory` literal.
2. Add `_p5_learner_binding: LearnerABC | None = field(default=None, init=False, repr=False)`.
3. Add `apply_p5_policy(self, snapshot: _LearningSnapshot) -> None` method
   that validates the snapshot's `policy_output` length, looks up category
   indices, clips to field range, and `setattr`s.
4. Patch the `DualTimescaleNeuromodulatorUpdatePath.update_levels` (in
   `neuromodulation/engine.py`) to accept an optional
   `continuous_state: ContinuousStateReading | None = None` and
   `half_life_seconds: float | None = None`, adding the wall-clock decay
   term gated by learner-supplied `α_wall`.
5. Patch `RestStateTemporalSource.sample` (in `temporal/engine.py`) to
   accept an optional `continuous_state: ContinuousStateReading | None`.

Acceptance:
- 27 unit tests (3 × 9 owners) pass.
- 18 integration tests (2 × 9 owners) pass: wire-off byte-compat.
- 506 existing R-PROTO-LEARN tests still pass.

### Step 2.5 — Composition wiring `composition/runtime_assembly.py`

- Add `p5_wiring_enabled: bool = False`, `p5_learners: tuple[LearnerABC, ...] = ()`,
  `continuous_state_owner: ContinuousStateOwner | None = None` to
  `RuntimeProfile`.
- `__post_init__` validates wire-on requires both `p5_learners` and
  `continuous_state_owner`.
- Add `wire_p5(self) -> None` method on `SemanticRuntimeAssembly` (or
  equivalent): for each canonical owner, call `learner.wire_to_owner(owner)`
  and `owner._p5_learner_binding = learner`.
- Add `run_tick_with_p5(self, frame) -> None` that, after the standard
  stage pipeline, iterates `(owner, learner)` pairs and calls
  `owner.apply_p5_policy(learner.update(...))`. Production assembly uses
  this; tests use the legacy path.

Acceptance:
- 4 integration tests pass (ContinuousStateOwner wired correctly).
- 18 wire-off byte-compat tests pass (no P5 side-effect in test assembly).

### Step 2.6 — Test files

- `tests/test_p_temporal_wiring.py` (45 tests).
- `tests/test_p_temporal_continuous_state.py` (12 tests).
- `tests/test_p_temporal_smoke_1129.py` (3 tests, real-LLM gated).
- `tests/test_p_temporal_architecture_guard.py` (3 tests).

Total new tests: **63** (84 with legacy).

### Step 2.7 — Commit + push

```
git -C /root/project/helios add \
  helios_v2/src/helios_v2/temporal_continuous_state/ \
  helios_v2/src/helios_v2/learning/{protocol,contracts,wiring}.py \
  helios_v2/src/helios_v2/{neuromodulation,autonomy,feeling,rpe,memory,workspace,thought_gating,temporal,consciousness}/engine.py \
  helios_v2/src/helios_v2/composition/runtime_assembly.py \
  helios_v2/tests/test_p_temporal_*.py \
  helios_v2/docs/requirements/research-p-temporal/

git -C /root/project/helios commit -m "feat(R-PROTO-LEARN.P-TEMPORAL): ..."

git -C /root/project/helios push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
```

Iron rule: never merge to `main`.

## Phase 3 — Long-running real-LLM validation (background, 6h budget)

### Step 3.1 — Reuse Turing eval scripts

The 2026-06-18 Turing eval scripts live at
`/root/project/helios/helios_v2/scripts/helios_turing_*.py` and are
preserved on the research branch. Re-run them with P-TEMPORAL wire-on
enabled in `runtime_assembly.py`:

```bash
cd /root/project/helios/helios_v2
PYTHONPATH=src setsid python scripts/helios_turing_system_runner.py \
    --profile production --p5-wiring-on \
    --output /tmp/p_temporal_trace_1129.jsonl \
    > /tmp/p_temporal_run.log 2>&1 < /dev/null &
```

Estimated wall-clock: ~6h (188 ticks/h baseline).

### Step 3.2 — Background detach pattern

```bash
_start_turing.sh  # the same pattern as _start_turing.sh 2026-06-18 03:33
```

Use `setsid` + redirect stdin from /dev/null + close stdout/stderr to log;
PID is recorded to `/tmp/p_temporal.pid`.

### Step 3.3 — Poll progress every 30 min

```bash
tail -f /tmp/p_temporal_run.log
ls -la /proc/$(cat /tmp/p_temporal.pid)/fd/1   # log inode (handles logrotate)
```

### Step 3.4 — Score after completion

```bash
PYTHONPATH=src python scripts/helios_turing_scorer.py \
    --trace /tmp/p_temporal_trace_1129.jsonl \
    --output /tmp/p_temporal_scores.json
```

Expect:
- D2 bio_responsiveness: **≥ 0.5** (vs baseline 0.008)
- D5 cross_tick_continuity: **≥ 0.6** (vs baseline 0.521)
- D8 self_recognition: **≥ 0.4** (vs baseline 0.184)
- D10 stress_recovery: **≥ 0.5** (vs baseline 0.000)

### Step 3.5 — Spot-check 8 scenarios (小黑扮演评审)

Use `scripts/helios_turing_scorer.py --spotcheck` to extract 8 representative
scenarios (one per block A-I; skip J which is stress-recovery mechanical).
Store at `/tmp/p_temporal_spotcheck.json`. 小黑 reviews these as 10%
sample of total scenarios.

### Step 3.6 — Permanent archive

Copy all artifacts to:
- `helios_v2/docs/requirements/research-p-temporal/artifacts/`
  - `p_temporal_trace_1129.jsonl`
  - `p_temporal_scores.json`
  - `p_temporal_run.log`
  - `p_temporal_spotcheck.json`
  - `p_temporal_analysis.md` (deep-dive parallel to `analysis-deep-dive.md`)

## Phase 4 — 小黑拍板 / commit / report

- [ ] 1129-tick real-LLM run completes successfully
- [ ] D2 / D5 / D8 / D10 baseline lift confirmed
- [ ] 小黑 spot-check 8 scenarios approved
- [ ] Final commit on research branch (no merge to main)
- [ ] `result.md` written with score deltas
- [ ] `analysis-deep-dive.md` written with root-cause mapping (P-TEMPORAL
      mapping table → each Turing dim)
- [ ] Daily memory note: `memory/2026-06-20-p-temporal-ship.md`

## Phase 5 — Follow-up decisions (deferred until Phase 4 lands)

- 是否 ship Phase 5 「Deep Dive 测试」：
  - 1000+ tick 多 block 对比 (with vs without P-TEMPORAL)
  - 24h 长程 stress 测试（验证 half-life 真有累积效应）
  - 跨 session 重启连续性测试（验证 continuity_checkpoint 持久化）
- 是否 ship 「P-TEMPORAL.Slice 2: Long-form Consolidation」：
  - L4 autobiographical 真正的 wall-clock decay
  - experience_writeback 真正的 replay_priority 学习
- 是否 ship 「P-TEMPORAL.Slice 3: Self-Model Reinforcement」：
  - identity_governance 真正的 boundary_check_policy 学习
  - D8 self_recognition 真实提升路径

## Acceptance Summary

| Gate | Status | Diagnostic |
|------|--------|------------|
| G1 unit tests (63) | pending | `pytest tests/test_p_temporal_*.py -q` |
| G2 wire-off byte-compat (18) | pending | 200-tick deterministic replay |
| G3 wire-on coverage (105/105) | pending | snapshot inspection |
| G4 wall-clock decay active (200 tick) | pending | cortisol std > 0.05 |
| G5 1129-tick real-LLM D2/D5/D8/D10 | pending | scorer output |
| G6 R-PROTO-LEARN regression (506) | pending | `pytest tests/test_r_proto_learn_*.py -q` |
| G7 whole-tree regression (1640) | pending | split-run |
| G8 architecture guard | pending | scripts/architecture_guard.py |
