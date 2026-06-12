# Helios v2 模块进度流程图（中文）

> 状态：活文档（进度地图）。任何实质改变 owner 成熟度、运行时阶段链或 owner 边界的 requirement，
> 必须在同一次变更里同步更新本文件。
> 最近同步：R84。R84 完成 P5 memory-fidelity probe — 把 R83 A3 axis 从 stub 0.5 升级为 real 0.600 (8/8 states probed, latency=0.7ms, recall=0.00, persistence=1.00), end-to-end 验证 R10 + R15 + experience_store。R84 在 `src/helios_v2/tests/r83/memory_probe.py` 替换 stub（不改 owner），复用 R79-D `LongRunner` + `ScriptedCliSource` + 真实 LLM; `R83Scores` 新增 `a3_sub_metrics` + `a3_per_state` 字段; `R83ReportBuilder` 新增 "A3 memory-fidelity sub-metrics (R84)" 章节; `LongRunner.memory_probe_factory` 字段在 40-tick preflight 结束后注入 MemoryProbe 实例。R84 acceptance：(1) 8 单元测试 (no-records / no-handle / no-store / real-handle sub-metrics / 8-state breakdown / recall-zero / latency-formula / CLI smoke) PASS; (2) full suite 987 passed (979 R83 baseline + 8 R84 new + 0 regression) PASS; (3) R21 ad-hoc logging guard 1/1 green PASS; (4) noop-run A3 = 0.600 (real sub-metrics) instead of stub 0.500 PASS。R83 之前已闭环：R83 完成 10 分钟长程预运行 + 6-axis Turing-style 评估 + 8 情绪状态 × 5 变体 = 40 刺激目录 + 32 单元测试 (979 passed)。R82 之前已闭环：R82 完成 17-dim BehaviorDriftDimension Literal + AggressiveRadicalDriftEvaluator P5 launch gate + R79-D CLI --with-drift-report + 25 R82 tests。R81 之前已闭环：R81 完成 Internal Monologue cross-tick carry + `09` `self_continuation_signal` + `18` `DeferredContinuityRecord.source_kind="internal_monologue"` + 0.5x `proactive_drive_urgency` multiplier + `RuntimeContinuitySnapshot` v4 schema bump + `_migrate_v3_to_v4` load-time helper。R79 plan 全部 done (R79-A + R79-B + R79-C + R79-D + R80 + R81 + R82 + R83 + R84)。版本：R84。

### R83 模块索引 (Final Acceptance Gate 等级)

- `02` sensory ingress → 复用 R79-D `ScriptedCliSource` (`LongRunner` 直接 import)
- `11` LLM → 复用 R79-D `NoopLlmGateway` / `RealLlmGateway` (`LongRunner` 端到端 LLM I/O)
- `16` composition → 复用 `assemble_runtime(deterministic_thought=False, gateway=gateway)` 装配 runtime
- `17` evaluation → 复用 R82 `AggressiveRadicalDriftEvaluator` (`LongRunner._score_a5` 算出 A5 axis)
- R83 不创建新 owner；位于 `src/helios_v2/tests/r83/`（sibling of `tests/r79d/`）
- 6-axis Turing-style 评估: A1 `linguistic_naturalness` (LLM-judge) / A2 `bio_responsiveness` (algorithmic, 6 expected_response family rules) / A3 `memory_fidelity` (R84: real R10 + R15 + experience_store end-to-end probe; was a stub in R83) / A4 `agency_locking` (LLM-judge) / A5 `cross_tick_continuity` (R82 drift) / A6 `stimulus_response_coherence` (LLM-judge)
- 40-stimulus catalog: 8 hand-written Chinese state blocks × 5 variants each (`praise` / `neglect` / `criticism` / `comfort` / `challenge` / `surprise` / `conflict` / `contrast`)
- `JudgeProbe` fail-soft: parse failure → 0.5/0.5/0.5 fallback; empty samples → `no-samples` reason
- `Verdict.compute(scores)`: `human-like` iff `mean >= 0.6 AND min >= 0.4`; `recalibration_targets` = axes with score < 0.6
- CLI: `python -m helios_v2.tests.r83 [--duration MINUTES=1.0] [--noop] [--no-judge] [--output-dir DIR] [--run-id ID]`
- 32 单元测试 in `tests/test_r83_smoke.py` (8 catalog / 4 StateBlock / 4 verdict / 3 A2 / 2 A2 clamping / 2 R83Scores.mean/.min / 2 _delta / 4 LongRunner / 2 judge / 2 CLI / 1 memory stub / 1 report builder / 1 _io / 1 R21 self-guard)

### R84 模块索引 (P5 Memory-Fidelity Probe 等级)

- `10` directed retrieval → 复用 `FirstVersionDirectedRetrievalPath.plan_and_select` + `StoreBackedDirectedMemoryCandidateProvider` (MemoryProbe 走 R10 public path, 不走 per-tick gate-firing)
- `15` experience writeback → 复用 `experience_store.read_recent()` / `count()` 验证 writeback 持久化 (MemoryProbe 比对 persona 的 `remember_this=True` tick 与持久化记录的 `tick_id`)
- `17` evaluation → MemoryProbe 复用 `InMemoryExperienceStoreBackend` (auto-store from R78)
- R84 不创建新 owner; 修改 `src/helios_v2/tests/r83/{memory_probe,long_runner,__main__,report_builder}.py` 四个文件
- 3 sub-metrics per state (8 state blocks = 8 probes): `retrieval_latency_ms` (R10 probe wall-clock) / `recall_hit_rate` (proportion of `remember_this=True` ticks) / `writeback_persistence_rate` (`n_matched_persisted_records / n_remember_this_true_ticks`)
- Per-state A3 = `0.4 * recall_hit_rate + 0.3 * writeback_persistence_rate + 0.3 * latency_score`; Overall A3 = mean of 8 per-state scores
- Fail-soft: no-handle / no-store / all-probes-failed ⇒ A3=0.5 with discriminating reasoning (no more literal `not-implemented`)
- 8 单元测试 added in `tests/test_r83_smoke.py` (no-records / no-handle / no-store / real-handle sub-metrics / 8-state breakdown / recall-zero / latency-formula / CLI smoke)

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

