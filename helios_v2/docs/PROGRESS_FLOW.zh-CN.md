# Helios v2 模块进度流程图（中文）

> 状态：活文档（进度地图）。任何实质改变 owner 成熟度、运行时阶段链或 owner 边界的 requirement，
> 必须在同一次变更里同步更新本文件。
> 最近同步：R82。R82 完成 17-dim BehaviorDriftDimension Literal + AggressiveRadicalDriftEvaluator P5 launch gate + R79-D CLI --with-drift-report + 25 R82 tests (23 unit + 2 integration). R81 之前已闭环：R81 完成 Internal Monologue cross-tick carry + `09` `self_continuation_signal` + `18` `DeferredContinuityRecord.source_kind="internal_monologue"` + 0.5x `proactive_drive_urgency` multiplier + `RuntimeContinuitySnapshot` v4 schema bump + `_migrate_v3_to_v4` load-time helper。R82 Acceptance 认可：(1) 17-dim BehaviorDriftDimension Literal in contracts.py 4-family (hormone/feeling/salience/behavior) PASS；(2) AggressiveRadicalDriftEvaluator reads R79-D JSONL, classifies 4-class (drift_positive / drift_negative / drift_neutral / dim_unavailable) per dim PASS；(3) DriftEvaluationReport 含 17 per-dim + 4 family aggregates + overall_drift_score + tick_count PASS；(4) is_p5_launch_gate_open(score, threshold=0.02) P5 launch gate predicate PASS；(5) 23 unit tests in test_r82_drift_evaluator.py + 2 integration tests in test_r82_drift_integration.py + R79-D CLI --with-drift-report 1 smoke test PASS；(6) full suite 947 passed (922 R81 + 25 R82 + 0 regression) PASS；(7) R21 ad-hoc logging guard 1/1 green PASS。R81 之前 Acceptance 认可：(1) carry seam 双写 `RuntimeHandle._carry_internal_monologue` + cell pattern + `PriorInternalMonologueCarryHolder` PASS；(2) `09` `_self_continuation_signal()` 公式 0.5+0.5 formula PASS；(3) `18` 引擎 source_kind="内部 monologue"` 的 deferred record + 0.5x urgency multiplier PASS；(4) `42` v3→v4 load-time migration (no reject) PASS；(5) full suite 922 passed (905 R80 + 17 R81 + 0 regression) PASS；(6) R21 ad-hoc logging guard 1/1 + composition guard 4/4 PASS。R82 已闭环（见上）。Defer to R83: 10 分钟长程预运行测试 (CLI 外部输入测试文本 + 多维评分 + AI 评定 + 图灵测试风格报告)。R81 需求包位于 `docs/requirements/81-r81-internal-monologue-self-continuation-and-cross-tick-carry/`；R82 需求包位于 `docs/requirements/82-r82-behavior-drift-dimension-and-evaluator/`。版本：R82。

### R80 模块索引 (Internal Monologue 等级)

- `02` sensory ingress → 新 second-order source `InternalMonologueSource`
- `03` rapid salience appraisal → 新 modality 分发器 `InternalMonologueAppraisalEstimator` (fixed 5-dim novelty 0.3 / uncertainty 0.7)
- `04` neuromodulation → 受益于 novelty+uncertainty pathway (NE 增量 贡献)
- `09` thought gating → ✓ R81 完成 (`self_continuation_signal` + `self_continuation_weight=0.3`)
- `18` autonomy → ✓ R81 完成 (`DeferredContinuityRecord.source_kind` + 0.5x `proactive_drive_urgency`)
- `22` composition → `assemble_runtime(internal_monologue_carry_provider=...)` opt-in, default bit-identical
- `42` continuity checkpoint → ✓ R81 完成 (snapshot v3 → v4 + `_migrate_v3_to_v4` + `internal_monologue` field)

### R81 模块索引 (Cross-Tick Carry 等级)

- `02` sensory ingress → ✓ closure provider 优先读 carry state, 再读 published LLM output (R80 priority rule)
- `09` thought gating → 新 `self_continuation_signal` 在 gate score (0.5*bool(iwttm) + 0.5*bool(tma nonempty)), weight=0.3
- `16` composition → 新 `RuntimeHandle._carry_internal_monologue` seam + `_r81_carry_cell` mutable cell + `PriorInternalMonologueCarryHolder`
- `18` autonomy → 新 `DeferredContinuityRecord.source_kind` field + `ProactiveDriveState.proactive_drive_urgency` post-multiplier + 0.5x multiplier when `source_kind="internal_monologue"`
- `42` continuity checkpoint → `SNAPSHOT_VERSION 3 → 4` + new `internal_monologue: InternalMonologueCarryState | None` field + `_migrate_v3_to_v4` one-shot helper (no reject, fill None)
- carry reset 规则: fire + `prior_self_continuation_signal > 0` → reset to None (rumination resolved); no-fire → persist (越想越气)

### R82 模块索引 (P5 Launch-Gate 等级)

- `17` evaluation → 新 17-dim `BehaviorDriftDimension` Literal in `contracts.py` (4 hormone + 4 feeling + 4 salience + 5 behavior); 新 `AggressiveRadicalDriftEvaluator` (frozen dataclass) consumes R79-D JSONL; 新 `DriftEvaluationReport` (per-dim + family aggregates + overall_drift_score + tick_count); 新 `is_p5_launch_gate_open(score, threshold=0.02)` P5 launch-gate predicate
- per-dim classification: 4-class (`drift_positive` / `drift_negative` / `drift_neutral` / `dim_unavailable`); per-family thresholds: hormone 0.10 / feeling 0.15 / salience 0.20 / behavior 0.10 / act_type_entropy 0.5
- behavior frequencies: derive from v3 LLM envelope (boolean → 0.0/1.0); missing key → `dim_unavailable`; `act_type_distribution` is Shannon entropy of `llm_output.act_type`
- recalibration recommendation per dim: |drift|>0.20 → `raise_weight`, |drift|<0.05 → `lower_weight`, else `hold`; `dim_unavailable` → `n/a`
- R79-D CLI → 新 `--with-drift-report` flag emits `*/*.drift_report.md` (family summaries + per-dim table + P5 gate verdict)
- 23 单元测试 in `tests/test_r82_drift_evaluator.py` (17 per-dim + 4 family-aggregate + 1 P5 launch-gate + 1 recalibration recommendation) + 2 integration tests in `tests/test_r82_drift_integration.py` (drift-positive + flat-data gate-closed)
- P5 launch gate = `is_p5_launch_gate_open(overall_drift_score) = score >= 0.02` (default conservative threshold); 0.5x `proactive_drive_urgency` multiplier (R81) 待 R82 数据驱动 recalibration

## R80 最终接入的 R-Number 方案 (T0)

✓ `helios_v2.sensory.internal_monologue` (`InternalMonologueSource`)
✓ `helios_v2.appraisal.r80_internal_monologue` (`InternalMonologueAppraisalEstimator`)
✓ `RapidSalienceAppraisalEngine._estimate_dimensions` per-modality dispatch
✓ `assemble_runtime(internal_monologue_carry_provider=...)` + `RuntimeProfile` field
✓ 5 单元测试 + 20-tick real-LLM probe acceptance PASS

