# Helios v2 模块进度流程图（中文）

> 状态：活文档（进度地图）。任何实质改变 owner 成熟度、运行时阶段链或 owner 边界的 requirement，
> 必须在同一次变更里同步更新本文件。
> 最近同步：R81。R81 完成 Internal Monologue cross-tick carry + `09` `self_continuation_signal` + `18` `DeferredContinuityRecord.source_kind="internal_monologue"` + 0.5x `proactive_drive_urgency` multiplier + `RuntimeContinuitySnapshot` v4 schema bump + `_migrate_v3_to_v4` load-time helper。Acceptance 认可：(1) carry seam 双写 `RuntimeHandle._carry_internal_monologue` + cell pattern + `PriorInternalMonologueCarryHolder` PASS；(2) `09` `_self_continuation_signal()` 公式 0.5+0.5 formula PASS；(3) `18` 引擎 source_kind="内部 monologue"` 的 deferred record + 0.5x urgency multiplier PASS；(4) `42` v3→v4 load-time migration (no reject) PASS；(5) full suite 922 passed (905 R80 + 17 R81 + 0 regression) PASS；(6) R21 ad-hoc logging guard 1/1 + composition guard 4/4 PASS。Defer to R82: 17-dim `BehaviorDriftDimension` + `AggressiveRadicalDriftEvaluator` P5 launch gate + recalibrate `self_continuation_weight=0.3` 与 0.5x urgency multiplier。R81 需求包位于 `docs/requirements/81-r81-internal-monologue-self-continuation-and-cross-tick-carry/`。版本：R81。

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
## R80 最终接入的 R-Number 方案 (T0)

✓ `helios_v2.sensory.internal_monologue` (`InternalMonologueSource`)
✓ `helios_v2.appraisal.r80_internal_monologue` (`InternalMonologueAppraisalEstimator`)
✓ `RapidSalienceAppraisalEngine._estimate_dimensions` per-modality dispatch
✓ `assemble_runtime(internal_monologue_carry_provider=...)` + `RuntimeProfile` field
✓ 5 单元测试 + 20-tick real-LLM probe acceptance PASS

