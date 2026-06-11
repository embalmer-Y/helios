# Helios v2 模块进度流程图（中文）

> 状态：活文档（进度地图）。任何实质改变 owner 成熟度、运行时阶段链或 owner 边界的 requirement，
> 必须在同一次变更里同步更新本文件。
> 最近同步：R83。R83 完成 10 分钟长程预运行 + 6-axis Turing-style 评估 + 8 情绪状态 × 5 变体 = 40 刺激目录 + 32 单元测试 (979 passed = 947 R82 baseline + 32 R83 new + 0 regression; R21 ad-hoc logging guard 1/1 green). R82 之前已闭环：R82 完成 17-dim BehaviorDriftDimension Literal + AggressiveRadicalDriftEvaluator P5 launch gate + R79-D CLI --with-drift-report + 25 R82 tests (23 unit + 2 integration). R81 之前已闭环：R81 完成 Internal Monologue cross-tick carry + `09` `self_continuation_signal` + `18` `DeferredContinuityRecord.source_kind="internal_monologue"` + 0.5x `proactive_drive_urgency` multiplier + `RuntimeContinuitySnapshot` v4 schema bump + `_migrate_v3_to_v4` load-time helper。R83 Acceptance 认可：(1) 8 state blocks × 5 variants = 40 stimuli catalog (手写中文，确定性) PASS；(2) `LongRunner` consumes R79-D ScriptedCliSource + RealLlmGateway + R82 AggressiveRadicalDriftEvaluator 三个原语 PASS；(3) `JudgeProbe` fail-soft (parse failure → 0.5/0.5/0.5) PASS；(4) `MemoryProbe` stub returns 0.5 with `not-implemented` reason PASS；(5) `Verdict.compute(scores)` returns `human-like` iff `mean>=0.6 AND min>=0.4`, else `needs-recalibration` PASS；(6) `R83ReportBuilder` writes `r83_report.md` with TL;DR + axis scores + per-block + bio-chemistry deltas + recalibration targets PASS；(7) CLI `python -m helios_v2.tests.r83 --duration 0.5 --no-judge --output-dir DIR` end-to-end real-LLM run PASS；(8) 32 unit tests in `tests/test_r83_smoke.py` (8 catalog / 4 StateBlock / 4 verdict / 3 A2 / 2 clamping / 2 R83Scores / 2 _delta / 4 LongRunner / 2 judge / 2 CLI / 1 memory / 1 report / 1 _io / 1 R21 self-guard) PASS；(9) full suite 979 passed (947 R82 + 32 R83 + 0 regression) PASS。R82 之前 Acceptance 认可：(1) 17-dim BehaviorDriftDimension Literal in contracts.py 4-family PASS；(2) AggressiveRadicalDriftEvaluator reads R79-D JSONL, 4-class per dim PASS；(3) DriftEvaluationReport per-dim + 4 family aggregates + overall_drift_score + tick_count PASS；(4) is_p5_launch_gate_open(score, threshold=0.02) PASS；(5) 23 unit + 2 integration tests PASS；(6) full suite 947 passed PASS；(7) R21 ad-hoc logging guard 1/1 green PASS。R81 之前 Acceptance 认可：(1) carry seam 双写 `RuntimeHandle._carry_internal_monologue` + cell pattern + `PriorInternalMonologueCarryHolder` PASS；(2) `09` `_self_continuation_signal()` 公式 PASS；(3) `18` 引擎 source_kind="internal_monologue" + 0.5x urgency multiplier PASS；(4) `42` v3→v4 load-time migration PASS；(5) full suite 922 passed PASS；(6) R21 + composition guard PASS。R83 已闭环（见上）。R83 复用 3 个原语（R79-D framework + R82 drift evaluator + R10 directed retrieval），不创建新 owner；R83 位于 `src/helios_v2/tests/r83/` 作为 sibling of `tests/r79d/`。R79 plan 全部 done (R79-A + R79-B + R79-C + R79-D + R80 + R81 + R82 + R83)。版本：R83。

### R83 模块索引 (Final Acceptance Gate 等级)

- `02` sensory ingress → 复用 R79-D `ScriptedCliSource` (`LongRunner` 直接 import)
- `11` LLM → 复用 R79-D `NoopLlmGateway` / `RealLlmGateway` (`LongRunner` 端到端 LLM I/O)
- `16` composition → 复用 `assemble_runtime(deterministic_thought=False, gateway=gateway)` 装配 runtime
- `17` evaluation → 复用 R82 `AggressiveRadicalDriftEvaluator` (`LongRunner._score_a5` 算出 A5 axis)
- R83 不创建新 owner；位于 `src/helios_v2/tests/r83/`（sibling of `tests/r79d/`）
- 6-axis Turing-style 评估: A1 `linguistic_naturalness` (LLM-judge) / A2 `bio_responsiveness` (algorithmic, 6 expected_response family rules) / A3 `memory_fidelity` (stub: P5 unblocker pending) / A4 `agency_locking` (LLM-judge) / A5 `cross_tick_continuity` (R82 drift) / A6 `stimulus_response_coherence` (LLM-judge)
- 40-stimulus catalog: 8 hand-written Chinese state blocks × 5 variants each (`praise` / `neglect` / `criticism` / `comfort` / `challenge` / `surprise` / `conflict` / `contrast`)
- `JudgeProbe` fail-soft: parse failure → 0.5/0.5/0.5 fallback; empty samples → `no-samples` reason
- `Verdict.compute(scores)`: `human-like` iff `mean >= 0.6 AND min >= 0.4`; `recalibration_targets` = axes with score < 0.6
- CLI: `python -m helios_v2.tests.r83 [--duration MINUTES=1.0] [--noop] [--no-judge] [--output-dir DIR] [--run-id ID]`
- 32 单元测试 in `tests/test_r83_smoke.py` (8 catalog / 4 StateBlock / 4 verdict / 3 A2 / 2 A2 clamping / 2 R83Scores.mean/.min / 2 _delta / 4 LongRunner / 2 judge / 2 CLI / 1 memory stub / 1 report builder / 1 _io / 1 R21 self-guard)

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

