# Requirement 41 - Dimension-grounded aggregate salience judgment (design)

## 1. Design Overview

R41 replaces the constant aggregate-salience shim with an owner-owned deterministic convex combination of the five now-real `03` dimensions, under the existing semantic-memory opt-in. It is the smallest slice in the P3 `03` series: a pure function of the `RapidDimensionEstimate` already produced, with no new injected fact source, no embedding/store/transport access, and no contract change.

Two parts:

1. The `03` owner gains a `WeightedAggregateEstimator` implementing the existing `AggregateJudgmentEstimator` protocol, holding explicit first-version per-dimension weights that sum to `1.0`.
2. Composition selects that estimator (instead of `FirstVersionAggregateEstimator`) only under the semantic-memory opt-in.

## 2. Current State and Gap

`RapidSalienceAppraisalEngine.assess_batch` calls `aggregate = self.aggregate_estimator.estimate_aggregate(stimulus, dimensions)` and builds `RapidSalienceVector(..., aggregate=aggregate)`. Today `aggregate_estimator` is always `FirstVersionAggregateEstimator` (constant `0.4`, `del stimulus, dimensions`) — it is not switched by the opt-in the way the dimension estimator is. The `aggregate` field is range-validated (`[0,1]`) by `RapidSalienceVector.__post_init__`.

Gap: the aggregate ignores the five dimensions even when they are real. R41 makes it a function of them under the semantic assembly.

## 3. Target Architecture

### 3.1 Data flow (semantic-memory assembly)

```
GroundedDimensionEstimator.estimate_dimensions(stimulus)
   -> RapidDimensionEstimate(threat, reward, novelty, social, uncertainty)   [all real]
        |
        v
WeightedAggregateEstimator.estimate_aggregate(stimulus, dimensions)
   -> aggregate = clamp(sum(weight_k * dimension_k), 0, 1)                    [real]
        |
        v
RapidSalienceVector(threat, reward, novelty, social, uncertainty, aggregate)  [contract unchanged]
```

In the default/recency/offline assemblies, `FirstVersionAggregateEstimator` (constant `0.4`) runs unchanged over the still-constant dimensions.

### 3.2 Ownership

- the aggregate combination semantic (the weights and the convex combination): owned by the `03` engine module (`WeightedAggregateEstimator`).
- selecting the estimator under the opt-in: owned by composition assembly (a wiring choice, exactly like selecting `GroundedDimensionEstimator` for the dimensions).

The estimator needs no injected source — it is a pure function of the dimensions — so this is even simpler than R35-R40 (no composition fact source at all).

### 3.3 The combination (owner-private)

```
aggregate = clamp(
    w_threat * threat + w_reward * reward + w_novelty * novelty
    + w_uncertainty * uncertainty + w_social * social,
    0.0, 1.0,
)
```

First-version weights (explicit owner constants, sum = 1.0):

| dimension | weight |
| --- | --- |
| threat | 0.25 |
| reward | 0.25 |
| novelty | 0.20 |
| uncertainty | 0.15 |
| social | 0.15 |

Because the weights are non-negative and sum to 1.0 and each dimension is in `[0,1]`, the weighted sum is already in `[0,1]`; the `clamp` is a defensive guard (and keeps the contract invariant if weights are later tuned to not sum to exactly 1.0). Monotonic: non-negative weights make the aggregate non-decreasing in each dimension. Deterministic: pure arithmetic on the dimensions. Stateless: no prior-tick read.

The weights are a first-version PLACEHOLDER allocation (an engineering choice, not a calibrated importance prior); they are the P5-learnable surface. The aggregate inherits the grounding strength of its inputs: while threat/reward are the R40 `C_engineering_hypothesis` prototype anchor, the aggregate's threat/reward contribution is only as strong as that anchor — recorded, not over-claimed.

## 4. Data Structures

No contract change. `RapidSalienceVector`/`RapidDimensionEstimate` unchanged; the new behavior lives in a new `AggregateJudgmentEstimator` implementation.

### 4.1 `WeightedAggregateEstimator` (new owner-owned estimator)

```python
@dataclass
class WeightedAggregateEstimator(AggregateJudgmentEstimator):
    weight_threat: float = 0.25
    weight_reward: float = 0.25
    weight_novelty: float = 0.20
    weight_uncertainty: float = 0.15
    weight_social: float = 0.15
    def estimate_aggregate(self, stimulus, dimensions) -> float:
        del stimulus  # aggregate is a function of the dimensions only this slice
        return round(min(1.0, max(0.0,
            self.weight_threat * dimensions.threat
            + self.weight_reward * dimensions.reward
            + self.weight_novelty * dimensions.novelty
            + self.weight_uncertainty * dimensions.uncertainty
            + self.weight_social * dimensions.social
        )), 4)
```

## 5. Module Changes

1. `appraisal/engine.py`: add `WeightedAggregateEstimator`. The dimension estimators (`MemoryGroundedDimensionEstimator`, `GroundedDimensionEstimator`) and the `AggregateJudgmentEstimator` protocol are unchanged.
2. `appraisal/__init__.py`: export `WeightedAggregateEstimator`.
3. `composition/runtime_assembly.py`: when `semantic_memory_enabled`, build `RapidSalienceAppraisalEngine(dimension_estimator=GroundedDimensionEstimator(...), aggregate_estimator=WeightedAggregateEstimator())`; otherwise keep `FirstVersionAggregateEstimator()`. (The dimension estimator selection from R35-R40 is unchanged.)

## 6. Migration Plan

1. Add the owner estimator (inert until selected).
2. Switch the assembly's `aggregate_estimator` behind the existing `semantic_memory_enabled` flag (no new flag).
3. The default assembly keeps `FirstVersionAggregateEstimator`, unchanged, so default behavior and tests are unaffected.

No contract rewrite; only the injected aggregate estimator gains a real implementation under the opt-in.

## 7. Failure Modes and Constraints

1. Out-of-range aggregate: structurally prevented (convex combination of `[0,1]` values + defensive clamp).
2. Stateless: no prior-tick read.
3. No NN, no LLM, no hidden branch; deterministic.
4. No fallback: when enabled the aggregate is dimension-grounded every tick; when disabled the constant estimator runs.
5. The estimator ignores `stimulus` (signature compatibility) and combines only the dimensions; it produces no downstream semantics.

## 8. Observability and Logging

No new logging mechanism. The aggregate travels only through the existing `RapidSalienceVector.aggregate`. No `logging`/`print` under `src`; guard test stays green.

## 9. Validation Strategy

1. Engine tests (`test_rapid_salience_engine.py`):
   - aggregate equals the weighted sum for a known dimension vector; weights sum to 1.0;
   - monotonic: raising one dimension (others fixed) does not lower the aggregate;
   - a high-salience dimension vector yields a higher aggregate than a low-salience one;
   - range `[0,1]` for extreme dimensions; determinism;
   - through the engine: `RapidSalienceVector.aggregate` reflects the combination (not `0.4`).
2. Composition tests (`test_runtime_composition.py`):
   - the semantic assembly produces an aggregate that is dimension-driven (not the constant `0.4`) and differs across two ticks whose dimensions differ (read from the `03` stage result);
   - the default assembly keeps constant aggregate `0.4`.
3. Guard + full gate: `test_no_adhoc_logging_guard.py` plus `pytest helios_v2/tests -q` green and network-free.
