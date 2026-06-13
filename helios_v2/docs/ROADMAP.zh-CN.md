# Helios v2 开发路线图（活文档）

> 状态：活文档（前向开发规划）。最近同步：R90。
> 角色：记录"下一步做什么、大概是哪些 requirement、每个做什么"，避免反复重新推导。
> 配套：
> - `ARCHITECTURE_PHILOSOPHY.zh-CN.md` — 终局目标、锁定验收标准、P0→P7 阶段路线图（上位约束）。
> - `requirements/index.md` — 权威的逐 requirement `Maturity` 列。
> - `OWNER_GUIDE.zh-CN.md` / `PROGRESS_FLOW.zh-CN.md` — 逐 owner 完成度与着色进度图。
>
> 维护纪律：编号按**创建顺序**顺序分配（连续两位数起，不用子编号），落定于创建时——本文件中
> 未创建项的 Rxx 是**建议编号**，可能随实际创建顺序顺移。每完成一个 Rxx，把它从"队列"挪到
> "已完成"并更新一行。任何改变 owner 成熟度/阶段门的变更，须同步 `index.md` 与进度图。

## 1. 当前状态（截至最近同步）

- main 测试基线：996 passed / 4 skipped（离线）。
- **🎉 P0–P3 已达 100%**：地基期三门（G0 长跑稳定 / G1 owner 有界 / G2 记忆跨重启）此前已签收（R82/R83），唯一遗留的 B4「真实送达对账」由 **R87 收口**——`17` consequence corroboration 对本机 effector 动作已从"流程完成"升级为**真实送达可证伪**（network driver 仍属 P4）。
- **P0–P3 地基期工程门已全部签收**：
  - G2 持久化默认化（R82：`assemble_production_runtime()` 默认 SQLite store + R42 checkpoint + embedding 网关）。
  - G0 长跑稳定（R83：10万 tick legacy-constant 跑通，无崩溃，内存 peak 5.6MB 持平，零泄漏）。
  - G1 owner 有界性（R83 harness：04/05/09/18 逐 tick 有界、无 NaN、无发散，可证伪）。
  - G2 形成/检索/重启接续此前已成立（R45/R34/R42）。
  - B4 真实送达对账（R87：`tool_result` reafference 对账，`really_delivered`/`delivered_failed`/`delivery_unverified`）。
- **P4 进行中**：R84 交付首个 effector driver（沙箱化 OS 文件 driver）+ 工具结果 reafference 回流 `02`；**R85 收口 FG-4 自主工具使用闭环**；**R86 交付受治理的 OS 命令执行 effector + `13` 强制 risk-class 门 + `14` 两-tick fail-closed 授权握手**（`unrestricted` 命令直跑、`restricted` 硬拒、`governed` 经 `14` 授权后执行；解释器/写自身代码永久 restricted）。**P4 退出门剩余**：网络通道（QQ/飞书/语音）。
- **P5 评估框架已立起**：R88 行为漂移评估器（启动门）+ R89 长跑图灵式 harness（§13.4 六轴）+ R90 记忆保真探针（替换图灵 `memory_fidelity` stub 为真实 R10+R15 端到端探针）三件套交付完毕。下一步可转 P5 双轨记忆（R91 起）或 P4 网络通道。
- 真实信号驱动：`02–10` 默认语义链、`04` 七通道+双时标+R81 对账、`11` LLM、`18` autonomy。
- 仍 `baseline_real`：`12–16` 外化链（草稿非授权，但 R85/R86 起工具路径已可真实执行本机文件/命令副作用，R87 起其真实送达可证伪）；真实网络外化仍属 P4。

### 1.1 R83 长跑的关键实测结论（修正先前判断）
- 每 tick 成本**有界**，非随 store 发散：暖机后进入平台（legacy-constant ~9.5ms 持平 store 11→1991；语义 ~100ms 持平 store 290→1178）。
- 语义那 ~100ms 大头是**每 tick 固定的 hash-embedding 调用数 + checkpoint/SQLite I/O**，不是 O(store) 余弦扫描。
- 因此先前"O(n²)、ANN 是当前阻塞"的判断**作废**：ANN/bounded-window 降级为 **P5 真实规模问题**（真实高维 embedding + 大 store 时才显著），并入双轨记忆那一组。

## 2. 已完成（路线 A + 路线 B 地基）

| Req | 名称 | 作用 |
| --- | --- | --- |
| R81 | Hormone-Predict Corroboration | P3 情感链收口；项目首条"模型断言 + owner 对账"路径，P5 学习雏形。 |
| R82 | 标准生产装配 + 持久化默认化 | `assemble_production_runtime()` 默认 SQLite + R42 checkpoint + embedding；收口 G2。 |
| R83 | 长跑稳定 + owner 有界性 harness | 可复现长跑 + 逐 owner 有界性 + JSONL 轨迹；CI 档 + opt-in 10万/真实 LLM 档；收口 G0/G1。 |
| R84 | OS 文件 channel driver（沙箱化 effector） | P4 开篇 + 首个 effector driver（FG-4）。`fs_read/fs_write/fs_list/fs_modify` 限定 sandbox root（`resolve()`+relative 校验，绝对外/`..`/软链逃逸拒绝），异步注入式 executor（测试 inline 确定性 / 生产 ThreadPool 真异步），结果作为 `tool_result` 带 correlation provenance 回流 `02`（efference→reafference 闭环）。失败写回（绝不冒充成功）；写操作受 `allow_write` 门控；readiness=sandbox 存在。channel-bound 装配泛化为 `RuntimeProfile.channel_drivers`（CLI+effector 共存）。纯传输/effector，无认知策略；stdlib-only，无进程/网络。888→912 测试绿。 |
| R85 | LLM 驱动自主工具选择 | 收口 FG-4 自主工具闭环：`11` 真实认知选工具 op+params → `12` 结构性归一化（D2a，op_params 贯通）→ `13` 按 op 绑定 driver + 通用 `required_params` 校验 + 能力门由 channel-state 派生 → 执行 → 结果回流 `02` 再思考。driver 自描述每个 op（`ChannelOpSpec`：required_params/user_visible 启用，effect_class/risk_class 声明留 R86/R87）。取消 `tool` scope（D1）；op 感知校验从 `12` 上移 `13`（D2a）。新增 planner-rejection tick 的 `world_blocked` 写回闭环（FG-4.4）。无 function-calling（`25` 不变）。912→921 测试绿。 |
| R86 | 受治理的 OS 命令执行 | 新 effector `helios_v2.channel.drivers.os_command`（`run_command`，op 级 `risk_class="governed"`）：argv-前缀 default-deny allowlist（`unrestricted` 只读/诊断 + `governed` `mkdir`/`cp`/`mv`），no-shell、sandbox cwd、超时、注入式 `CommandExecutor`+`CommandRunner`（CI 用 `FakeCommandRunner` 无子进程）、`tool_result` 回流。`13` 把 R85 的 `risk_class` read-through 升级为**强制 fail-closed 门**：`unrestricted` 直跑（pre-R86 op 字节级不变）、`restricted`/未知 → `risk_class_restricted` 硬拒、`governed` → 查 carried `14` 授权 → 执行 / `governance_denied` / `governance_required`。`14` additive 扩展为 `governed` 动作授权权威（`GovernedActionAuthorization` + `GovernedActionGovernancePath` + 两-tick carry，自我修订路径不变）。解释器/写自身代码永久 restricted（argv 级关不住 in-script 效应，留 OS 隔离的未来需求）。921→957 测试绿。 |
| R87 | Consequence-Truth 真实送达对账（B4 收口） | 把 `17` consequence corroboration 从"流程完成"（R32 阶段完成检查）升级为对 effector 动作的**真实送达可证伪** verdict，消费 R84/R85/R86 的 `tool_result` reafference。严格 additive、只读：R32 verdict/taxonomy/打分字节级不变。`ConsequenceClaim` 加 `decision_id`/`selected_op`/`op_effect_class`/`op_user_visible`（从 `ActionDecision` 取）；bundle 加 `delivered_tool_result_evidence`（composition 从 `channel_inbound_drain` 投影本 tick 回流的 correlation decision_id+ok）；无新 carry holder（N 决策的回流在 N+1 drain，与重评 N claim 同帧）。新 `_corroborate_delivery` 发 `really_delivered`/`delivered_failed`(+告警)/`delivery_unverified`(诚实缺席,绝不乐观)/`delivery_not_applicable`。`effect_class` 成为真实消费者（收口 R85 前置声明）。**B4 收口**（本机 effector 路径；网络 driver 仍 P4）→ **P0–P3 达 100%**。957→968 测试绿。 |
| R88 | 行为漂移评估器（P5 启动门） | tests-only 只读/离线/确定性漂移评估器（`tests/r88_drift_evaluator/`），消费 R83 逐 tick JSONL。按 early-vs-late 窗口均值差 + 死区（`neutral_band` 默认 0.02，归一化到维度合法量程，`<=` 边界判 neutral 带 float epsilon）把每个 owner 维分类为 `drift_positive`/`drift_negative`/`drift_neutral`/`dim_unavailable`，并对朝合法边界饱和的方向漂移加 `divergent_high`/`divergent_low`。方向类只表征跨窗变化的**符号**，非好坏判断；样本不足（`< min_samples_for_trend`，默认 4）判 `dim_unavailable`，绝不冒充 neutral。维度按 `NN.field` 机械发现，合法量程/期望维集默认取 R83 `TRACKED_FIELD_BOUNDS`（真实 substrate 19 维：`04`×9+`05`×7+`09`×2+`18`×1，**无 `03` salience**，修正 ROADMAP 旧"17 维"beta 口径）。`analysis_ok` 为可证伪 verdict（解析够样本、期望维全可分类、无 divergence）。对 committed `logs/r83/semantic_600.jsonl` 验证（50 样本、19 维全在、settled→全 neutral、无 divergence、ok）+ 合成 rising/falling/flat/sparse/divergent + empty/malformed 鲁棒性。无 runtime/owner 改动。968→981 测试绿。 |
| R89 | 长跑图灵式评估 harness | §13.4 长跑图灵式验收的 harness 骨架。tests-only `tests/r89_turing_harness/`：只读/离线/确定性 `evaluate_turing(long_run_report, drift_report, config, injected_scores)`，消费 R83 `LongRunReport` + R88 `DriftReport`，把 6 锁定 rubric 轴打成 `TuringVerdict`。编码 §13.4 纪律：双相似维（behavior=linguistic_naturalness/stimulus_response_coherence；internal causal-chain=其余四轴）、证据锚定（available 轴空 provenance→0）、人类/LLM-judge 注入轨（`InjectedAxisScore`）、保守聚合（逐维 nearest-rank 下分位 + 两维取 min 且都必需 + 任一 available 轴 <0.50 塌方 fail + ≥0.80 通过线）。内部轴由真实 provenance 重建（bio_responsiveness=affect 健康+移动；cross_tick_continuity=完成+continuation 有界+affect carry；agency_locking=owner 维 present/non-divergent 比例，部分代理）。memory_fidelity=stub（待 R90）；behavior 轴离线 unavailable。**反表演基线**：真实短跑 verdict 恒 incomplete 不通过。**非目标**：只交付 harness + 可重建内部轴；§13.4 完整验收（≥300 刺激/真人+LLM judge/拟人度/R90 探针）延后需 P4。真实 R83→R88→R89 集成 + 合成 pass/collapse/missing-provenance/both-dimension/empty 鲁棒性验证。无 runtime/owner 改动。981→990 测试绿。 |
| R90 | 记忆保真探针 | 替换 R89 图灵 `memory_fidelity` stub 为真实 R10+R15 端到端探针。tests-only `tests/r90_memory_fidelity_probe/`：只读/离线/确定性 `run_memory_fidelity_probe(handle_factory, config)`，驱动真实耐久生产装配（`assemble_production_runtime`，SQLite+R42 checkpoint+语义链，确定性离线 gateway）+ 一次重启，测三个有界 `[0,1]` 指标：recall_hit_rate（R10——fire 且 store 非空 tick 中 `directed_retrieval_into_thought_window` bundle 含 `experience_store` 前缀 hit 比例）、writeback_persistence_rate（R15→R33——本轮 appended 跨重启存活比例）、latency_score（R34/R33 `search_similar` 中位延迟 vs 100ms + self-recall 正确性计数）。诚实缺席 `None`，`fidelity_score`=可用指标均值，`usable` 要求无崩溃+全完成+writeback+recall/latency 之一。R89 `evaluate_turing` 加 additive 可选 `memory_fidelity_probe`：usable→`memory_fidelity` 轴真实 available/reconstructed 计 fidelity_score；缺省/不可用保持 stub 字节级不变（R89 全绿）。离线实测 recall=1.0(59/59)/persistence=1.0(120 全存活)/latency=1.0(~2ms)→fidelity=1.0。behavior 轴仍 P4 unavailable，整体 verdict 仍 incomplete。无 runtime/owner 改动（一处 additive 测试侧参数）。990→996 测试绿。 |

## 3. 近期队列：P4 通道生态 / P5 评估框架（P0–P3 已收口）

### R86 — OS Channel Driver：命令执行 + 治理 fail-closed ✅ 已交付（见 §2）
- 已实现为受治理的命令执行 effector + `13` 强制 risk-class 门 + `14` 两-tick fail-closed 授权握手。
- 首版 governed 集 = sandbox 内有界变更（`mkdir`/`cp`/`mv`）；解释器（`python <脚本>`/`bash`/`pytest` 等）= 任意代码执行，argv 级 allowlist 关不住，**永久 restricted**，留给未来带 OS 隔离的独立 requirement；写自身代码硬拒（P7）。

### R87 — Consequence-Truth 真实送达对账 ✅ 已交付（见 §2）
- 已把 `17` 对 effector 动作的对账从"流程完成"升级为"真实送达可证伪"，收口 B4 → **P0–P3 达 100%**。
- 剩余（独立项）：`23` 侧的跨 tick 送达延迟/重试长程诊断，可在需要时建在此 verdict 之上。

> 下一步方向（择一推进）：**P4 网络通道生态**（QQ/飞书/语音，达 P4 退出门）或 **P5 双轨记忆**（R91 起，建在真实长跑反馈 + R88/R89/R90 评估框架上）。P5 评估框架三件套（R88 漂移基线 + R89 图灵 harness + R90 记忆保真探针）已全部立起。

## 4. 中期队列：P5 评估框架 + 内心独白

### R88 — 行为漂移评估器（P5 启动门）✅ 已交付（见 §2）
- 已交付为 tests-only 的只读、离线、确定性漂移评估器（`tests/r88_drift_evaluator/`），消费 R83 逐 tick JSONL，按 early-vs-late 窗口均值差 + 死区把每个 owner 维度分类为 `drift_positive`/`drift_negative`/`drift_neutral`/`dim_unavailable`，并对朝合法边界饱和的漂移加 `divergent_high`/`divergent_low` 标记；`analysis_ok` 为可证伪 verdict。
- **ROADMAP 口径修正**：原 §4 草案的"4 hormone + 4 feeling + 4 salience + 5 behavior = 17 维"是 beta 分支衍生口径，与 main 不符。main 的 R83 轨迹实际承载 **19 个 owner 维**（`04`×9 + `05`×7 + `09`×2 + `18`×1），**无 `03` salience**。R88 按 main 真实 substrate 落地；把 `03` salience 加入轨迹是未来的 R83-轨迹扩展，明确不在 R88 范围。

### R89 — 长跑图灵式评估 harness ✅ 已交付（见 §2）
- 已交付为 tests-only 只读/离线/确定性 harness（`tests/r89_turing_harness/`），消费 R83 `LongRunReport` + R88 `DriftReport`，按 §13.4 锁定 rubric 把 6 轴打分成 `TuringVerdict`：双相似维（behavior / internal causal-chain）、证据锚定（无 provenance→0）、人类/LLM-judge 注入轨、保守聚合（逐维下分位 + 两维取 min 且都必需 + 任一可用轴塌方<0.50 fail + ≥0.80 通过线）。
- 内部轴由真实 provenance 重建：`bio_responsiveness`（R88 affect 健康 + R83 affect 移动幅度）、`cross_tick_continuity`（完成 + `09.continuation_level` 有界 + 跨 tick affect carry）、`agency_locking`（期望 owner 维 present/可分类/non-divergent 比例，**部分代理**，完整 owner-decision provenance 待 `21`/`17`）。`memory_fidelity` = stub（待 R90 替换）；behavior 轴离线 `unavailable_needs_real_afferent`。
- **反表演基线**：离线真实短跑 verdict 恒为 `incomplete` 且不通过——内部轴单独不能过、behavior-only 不能过、stub/unavailable 轴不能贡献乐观分。
- **诚实非目标**：只交付 harness + 可重建内部轴；§13.4 完整验收（≥300 真实刺激、真人/LLM judge、真实拟人度、R90 记忆探针）延后，需 P4 真实 afferent。

### R90 — 记忆保真探针 ✅ 已交付（见 §2）
- 已交付为 tests-only 只读/离线/确定性探针（`tests/r90_memory_fidelity_probe/`），驱动真实耐久生产装配 + 一次重启，从真实 provenance 测三个有界指标替换 R89 图灵 `memory_fidelity` stub：`recall_hit_rate`（R10 端到端——fire 且 store 非空 tick 中，`10` bundle 含 store-sourced hit 的比例）、`writeback_persistence_rate`（R15→R33——本轮 appended 记录跨重启存活比例）、`latency_score`（R34/R33 `search_similar` 中位延迟 vs 100ms 阈值）。诚实缺席为 `None`，绝不编造；`fidelity_score` = 可用指标均值。
- R89 `evaluate_turing` 加 additive 可选 `memory_fidelity_probe` 参数：usable report 使 `memory_fidelity` 轴变真实 `available`/`reconstructed`；缺省/不可用保持 stub 字节级不变（R89 测试全绿）。离线实测 recall=1.0(59/59)、persistence=1.0(120 全存活)、latency=1.0(~2ms) → fidelity=1.0。behavior 轴仍 unavailable（P4），整体 verdict 仍 incomplete——R90 只移除记忆 stub。

### R91 — internal_monologue 二阶刺激源
- `02` 新 sensory source + `03` appraisal estimator；上一 tick LLM 输出回流为 `internal_monologue` 刺激。依赖：R79。

### R92 — 内心独白跨 tick carry + 09 自延续 + 18 source_kind + 42 v4
- `RuntimeHandle._carry_internal_monologue` carry seam；`09` 加 `self_continuation_signal`；`18` `DeferredContinuityRecord.source_kind` 加 `"internal_monologue"`；`42` checkpoint v3→v4（带一次性迁移）。依赖：R91。

## 5. P5 重头：双轨记忆（建在真实长跑反馈上）

### R93 — MemoryRecord schema + 4 层时间分层
- L2/L3/L4/L5 分层，迁移 `PersistedExperienceRecord`。

### R94 — 6 维 objective_importance + 双重确认写入
- 重要性独立于 LLM 判断的客观维度 + 双重确认写入规则。

### R95 — Ebbinghaus 衰减 + recall 重固化 + 自动晋升层级

### R96 — bounded-window / ANN 语义检索
- 〔R83 修正后的 finding〕**非当前阻塞，是 P5 真实规模问题**：真实高维 embedding + 大 store 下朴素全库余弦才显著，届时换 bounded-window/ANN。建在双轨记忆检索层里最自然。

### R97 — memory_tool_channel
- `30` 框架下 LLM 记忆工具（recall/forget/consolidate 必做，link/reflect 推迟）；所有 keyword 匹配改 embedding 余弦；解决 owner 命名冲突（新 owner 名，不与 R31 CLI 冲突）。

### R98 — forget 治理 fail-closed
- `14` 在 forget 上的 fail-closed 门 + 永久审计轨迹 + soft-delete + GC。

## 6. 并行轨：P4 其余 channel driver（与 A/B/C 解耦，任意插入）

- QQ / 飞书 双向收发驱动（`.env` 已有 `HELIOS_QQ_*` 凭证位）。
- 实时语音：DashScope ASR/TTS 流式（`ALIBABA_CLOUD_*` 凭证）。
- WeChat（加分项，不阻塞退出门）。
- → OS + QQ + 飞书 + 语音 = **P4 退出门**。

## 7. 阶段映射

| 阶段 | 内容 | 对应 Req |
| --- | --- | --- |
| P4 工具入口 | OS 文件 effector（已交付）+ LLM 自主工具选择 + OS 命令执行 | R84（done）, R85, R86 |
| P0–P3 收尾 | B4 真实送达对账 + 退出再评估 | R87 |
| P5 评估框架 | 漂移评估 + 图灵 harness + 记忆探针 | R88–R90 |
| P5 内心独白 | 二阶刺激回流 + 跨 tick carry | R91–R92 |
| P5 双轨记忆 | schema/分层/重要性/衰减/ANN/记忆工具/forget 治理 | R93–R98 |
| P4 通道生态 | OS（R84/R86）+ QQ/飞书/语音/WeChat | R84/R86, 并行轨 |
| P6 / P7 | 受治理自我修订 / 受治理代码自修改 | 待 P5 框架立起后细化 |

> 注：本表为当前建议编号，与 §3–§5 一致（按实际创建顺序落定）。§4/§5 此前存在 R87 重号 + 整体 off-by-one，已对齐为：P0–P3 收尾 R86/R87、P5 评估框架 R88–R90、内心独白 R91–R92、双轨记忆 R93–R98。
> 提醒：beta 分支 `aggressive-radical-persona-no-theater` 的 R79–R85 与 main **同名不同义**（beta 已预研漂移评估器/图灵 harness/内心独白/双轨记忆等），移植回 main 时一律按 main 的创建顺序重新编号，不沿用 beta 编号。

## 8. 当前待主人决策项

1. R85（LLM 自主工具选择）的工具意图 schema 形状与 planner 绑定策略边界（选择归 `13`，绝不回灌 `11`）。
2. R86 命令执行的治理边界方案（allowlist / sandbox root / high-risk 清单 / 首版是否禁止写自身代码）。**未确认前不动 R86。**
3. R84 生产部署时 OS 文件 driver 的 sandbox root 选址（建议 git-ignored 的 `data/fs_sandbox/`）与是否默认启用写。
4. R83 CI 档时长：当前 150 tick（套件 ~16s）；如更看重 CI 速度可降到 ~80 tick（~10s）。
5. 是否在某个节点手动跑"真实 LLM + 真实刺激"长跑（需 P4 真实 afferent 落地后信息量才大）。
