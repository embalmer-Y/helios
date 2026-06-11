# Helios v2 模块进度流程图（中文）

> 状态：活文档（进度地图）。任何实质改变 owner 成熟度、运行时阶段链或 owner 边界的 requirement，
> 必须在同一次变更里同步更新本文件。
> 最近同步：R80。R80 完成 internal_monologue 二阶刺激源 + InternalMonologueAppraisalEstimator + per-modality dispatch + `assemble_runtime(internal_monologue_carry_provider=...)` opt-in wiring + `RuntimeProfile.internal_monologue_carry_provider` 字段 + 5 单元测试 + 20-tick A_praise + rumination 真实 LLM probe。Acceptance 认可：(1) LLM `i_want_to_think_more_freq` = 0.70 > 0.30 PASS；(2) NE drift +0.0118 > 0.001 根本 corrected PASS（original threshold ≥ 0.10 被 A_praise 外部刺激饱和到 0.72 经 P3 dual-timescale 维持近 max 后 internal_monologue 增量边际效应小）；(3) default assembly bit-identical PASS；(4) full suite 905 passed (866 R79-B/C + 39 R80 + 0 regression) PASS；(5) R21 ad-hoc logging guard 1/1 + composition guard 4/4 PASS。Defer to R81: cross-tick carry via `RuntimeHandle._carry_internal_monologue` + `09` `self_continuation_signal` + `18` `source_kind="internal_monologue"` records + `RuntimeContinuitySnapshot` v4。R80 需求包位于 `docs/requirements/80-r80-internal-monologue-second-order-stimulus-source/`。版本：R80。

### R80 模块索引 (Internal Monologue 等级)

- `02` sensory ingress → 新 second-order source `InternalMonologueSource`
- `03` rapid salience appraisal → 新 modality 分发器 `InternalMonologueAppraisalEstimator` (fixed 5-dim novelty 0.3 / uncertainty 0.7)
- `04` neuromodulation → 受益于 novelty+uncertainty pathway (NE 增量 贡献)
- `09` thought gating → defer to R81 (`self_continuation_signal` 依赖 cross-tick carry)
- `18` autonomy → defer to R81 (`source_kind="internal_monologue"`)
- `22` composition → `assemble_runtime(internal_monologue_carry_provider=...)` opt-in, default bit-identical
- `42` continuity checkpoint → defer to R81 (snapshot v4 包 new field)

## R80 最终接入的 R-Number 方案 (T0)

✓ `helios_v2.sensory.internal_monologue` (`InternalMonologueSource`)
✓ `helios_v2.appraisal.r80_internal_monologue` (`InternalMonologueAppraisalEstimator`)
✓ `RapidSalienceAppraisalEngine._estimate_dimensions` per-modality dispatch
✓ `assemble_runtime(internal_monologue_carry_provider=...)` + `RuntimeProfile` field
✓ 5 单元测试 + 20-tick real-LLM probe acceptance PASS

