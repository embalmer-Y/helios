# Helios v2 开发路线图（活文档）

> 状态：活文档（前向开发规划）。最近同步：R92。
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

- main 测试基线：≥ 1059 passed / 4 skipped（离线）。
- **🎉 P0–P3 已达 100%**：地基期三门（G0 长跑稳定 / G1 owner 有界 / G2 记忆跨重启）此前已签收（R82/R83），唯一遗留的 B4「真实送达对账」由 **R87 收口**——`17` consequence corroboration 对本机 effector 动作已从"流程完成"升级为**真实送达可证伪**（network driver 仍属 P4）。
- **W1+W2 已收口**：R91（present-field 内容进入 prompt）+ **R92（wall-clock 真实时间戳）+ **R93（W2 对话回复闭环可靠化——"想说话"→`13` `reply_message` dispatch 端到端可靠，详见§10 W2）** + 原 R91（wall-clock 真实时间戳，**新基础设施 owner `helios_v2.wall_clock`，三处 additive 消费 `RuntimeFrame.tick_wall_seconds` / `received_at_wall` 元数据 / `PersistedExperienceRecord.created_at_wall`，`assemble_production_runtime` 默认开启 `SystemWallClock`，R91 present-field 多出 `last input: X.Xs ago` clause）。下一步进 W2 / W3 / W4。 **R93 Phase 2 - 行动自主 + 跨通道路由** 同批交付（2026-06）：模型对动作类（reply / tool / no_action）和目标用户/通道拥有完整自主权，通过新的 `action_intent` + `target_user_id` envelope 字段、`ChannelOpSpec.bound_user_ids`、以及 planner 的 `target_user` -> `preferred` -> `iteration-order` 优先级实现。旧 `emit_action` fallback 已删除。~47 个新测试 + 2 个真实 LLM probe（03 正控、04 负控）。**W2.5 R94（已交付 2026-06）**：彻底移除 `i_want_to_say` 字段名——Phase 1 引入的 `i_want_to_say` 字面带"say"动词，从 schema 层就引导 LLM 反射性填文字；Phase 2 de-emphasize 后负控 probe 仍存在残余偏差。R94 把这个字段名彻底删，换为 `reply_text`（仅当 `action_intent="reply"` 时相关），让 LLM 在 4 个 action 维度（reply / tool / no_action + 沉默）的真正自主权不被字段名所牵引。~1200+ 测试绿（4 个 pre-existing wall_clock 跳过 + 4 个新增 R94 专属 + 6 个 R93 文件重命名）。详见§10 W2.5。
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
| R91 | Present-field 内容进入 `11` 思考 prompt | W1 第一刀：`InternalThoughtRequest` 加 additive `present_field_summary`（默认 None 字节级不变；非空+600 char cap+确定性 `…(truncated)`）。`SemanticInternalThoughtRequestBridge` 经新 owner-neutral helper `_present_field_summary_text` 项目**真实 `02 sensory_ingress` 外部刺激内容**（`<source> said: "<content>"`，最多 3 条 ×200 字符，按既有 `_INTERNAL_MODALITIES` 过滤）+ `08` focal commitment + 可选 `TemporalSource` pacing；`11._build_messages` / `_render_content` 在字段非空时 prepend `Present field:` 行。**实施期实证修正（§11.2）**：初版假设 `08.focal_summary` 装操作者文本；smoke 抓 prompt 证伪——它是 `08` 的候选级通用描述符。修正为优先从 `02` 取真实文本，`08` 作次要附加。实证：smoke 的真实 prompt 现含 `Present field: cli via cli said: "家里现在静得让我害怕..."; focal: ...`，LLM 立即产出真正中文共情思考并经 CLI 真实回复。owner 边界：`11` 仍保留全部判断；composition 只读已发布 `02`/`08` stage 结果 + 注入 `TemporalSource`；bridge 不 import `06`/`10`/embedding/LLM；无 system-prompt 改动、无新日志、无 owner 色/链/边界改动。测试：7 个真实 LLM probe（`scripts/r91_probes/01..07`：焦虑/哀伤/喜悦/愤怒/沉默/连续性 + 复刻失败模式的 pre-R91 负控）+ 23 个新网络无关测试（contract/engine/bridge）。基线 996→1019 测试绿。 |
| R92 | Wall-Clock 真实时间戳（W1 收口） | W1 第二刀：把"时间感知"从 R91 R55 `pacing` 的 unitless 节律提升到真实 wall-time。新基础设施 owner `helios_v2.wall_clock`（peer of `temporal`/`interoception`，纯事实源、不持任何认知策略）：单方法 `WallClock` 协议 + `SystemWallClock`（`time.time()` 懒导入）+ 测试用 `FixedWallClock`（常量 / 自动 advance / 显式 sequence + `manual_advance`）+ 保留元数据键 `RECEIVED_AT_WALL_METADATA_KEY`。三处 additive 消费：`RuntimeFrame.tick_wall_seconds: float \| None` 由内核每 tick 起调用一次 `WallClock.now()` 种入（同 tick 所有 stage 共享同一值；也复制到 `RuntimeTickResult` 供持久化 carry seam 读取）；`CliChannelDriver.submit_line` 戳 `received_at_wall` 入 `InboundPacket.metadata`（**到达时**而非 drain 时；经 `02` 透传到 `Stimulus.metadata`）；`PersistedExperienceRecord.created_at_wall: float \| None` 经两条 record bridge（`ExperienceRecordBridge`/`MemoryRecordBridge`）从 `tick_wall_seconds` 写入，SQLite 经 PRAGMA-guarded `ALTER TABLE` 就地迁移（旧文件读回 `None`，仿 R45 `record_kind` 模式）。R91 `_present_field_summary_text` 多出一个 `last input: <X.X>s ago` clause（取最早外部刺激的 `received_at_wall`，NTP-rewind 钳到 `0.0s`，与既有 `pacing: <signal>` 并列）。`RuntimeProfile.wall_clock` opt-in capability seam（profile + loose-kwarg 同传 `CompositionError`，**identity 线穿**保证内核与 CLI driver 共享同一实例）；`assemble_production_runtime` 默认开启 `SystemWallClock` ON；`assemble_runtime` 默认 None 字节级不变。owner 边界：owner 包不 import 任何认知 owner，认知 owner 也不直接 import 它（事实只经 frame/stimulus/record 三个 additive 通道），composition 是唯一把 `tick_wall_seconds + received_at_wall` 渲染为 `last input: X.Xs ago` 的地方；本刀**无任何** owner 用 `created_at_wall` 做排序/衰减（独立后续切片，如 P5 双轨记忆 R93+ 计 Ebbinghaus 衰减）。失败语义：clock 返回 NaN/Inf/负值 raise `WallClockError`；exhausted sequence raise；NTP rewind 仅在渲染边界钳到 `0.0s`（持久值保留原始）。无新日志机制；no-ad-hoc-logging guard + composition owner-boundary guard 保持绿。测试：~40 个新网络无关测试（contract/frame/CLI 戳/profile threading/present-field 渲染/persistence 字段+SQLite 迁移）+ 3 个真实 LLM probe（`scripts/r92_probes/01_with_wall_clock.json`、`02_long_silence.json`、`03_no_wall_clock_negative_control.json`）。1019→≥1059 测试绿。 |
| R93 | 对话回复闭环可靠化（W2 收口） | W2 第一刀：把"想说话"变成真的回复——R93 之前 89 条仅 1 条真正回复用户（v3 `i_want_to_say` 很少转成 CLI `reply_message` dispatch）。两处断点修复：(1) `_parse_structured_thought` 读顶层 `i_want_to_say` 进新增 additive `StructuredThoughtEvidence.intended_reply_text: str = ""`（2000 字符上限 + deterministic `…(truncated)`；非字符串 parse-error）。(2) `11._emit_proposal` 加隐式 reply 分支——条件：`intended_reply_text` 非空 ∧ 无显式 `tool_op` ∧ `current_operator_id` 非空；构造 `reply_message` tool intent，`op_params={"outbound_text": <reply>, "target_user_id": <operator>}`，走 R85 既有 planner-spine；显式 tool 优先；无 operator 静默不构造（绝不虚构目标）。(c) composition 加 owner-neutral `_current_operator_id(frame)` helper（最早外部刺激 `source_name`），两个 internal-thought request bridge 都把 `current_operator_id` 加进 `prompt_contract_summary`。(d) `_build_messages` 把 `i_want_to_say` 加入 schema 行并附"transport clause"。owner 边界：`11` 保留全部判断；composition 只读已发布 `02` 并正向投影 `current_operator_id`（不动 `06`/`10`/`13`）；`13` 仍按 driver 自描述的 `required_params` 校验（defense in depth——R85 不变）；不回灌 `11`。测试：5+12+6+7+4+6 = ~40 个网络无关测试 + 2 个真实 LLM probe（`scripts/r93_probes/01_basic_reply.json` 正控、`02_silence_negative_control.json` 负控）。 |
| R93 P2 | 对话回复闭环可靠化 Phase 2 - 行动自主 + 跨通道路由 | R93 P1 引入的 `i_want_to_say` 解决了"端到端能不能回复"，但 2026-06 真实 LLM 评估暴露了"confiding machine"残余：97% 回复率却无法选 `no_action`。Phase 2 把动作类（reply / tool / no_action）和目标用户/通道完整交给 LLM：(a) 新增 envelope 字段 `action_intent`（reply/tool/no_action）+ `target_user_id`；(b) `ChannelOpSpec.bound_user_ids` 让 driver 自描述"接受哪些 user"；(c) planner 优先级 `target_user` → `preferred` → `iteration-order`；(d) 删旧 `emit_action` fallback。**仍保留 `i_want_to_say` 字段名但 P2 重大 de-emphasis**：L94/R94 决定彻底移除以解决"want to say"字段名对 LLM 的反射性填文偏差。~47 个新测试 + 2 个真实 LLM probe（03 正控、04 负控）。 |

## 3. 近期队列：P4 通道生态 / P5 评估框架（P0–P3 已收口）

### R86 — OS Channel Driver：命令执行 + 治理 fail-closed ✅ 已交付（见 §2）
- 已实现为受治理的命令执行 effector + `13` 强制 risk-class 门 + `14` 两-tick fail-closed 授权握手。
- 首版 governed 集 = sandbox 内有界变更（`mkdir`/`cp`/`mv`）；解释器（`python <脚本>`/`bash`/`pytest` 等）= 任意代码执行，argv 级 allowlist 关不住，**永久 restricted**，留给未来带 OS 隔离的独立 requirement；写自身代码硬拒（P7）。

### R87 — Consequence-Truth 真实送达对账 ✅ 已交付（见 §2）
- 已把 `17` 对 effector 动作的对账从"流程完成"升级为"真实送达可证伪"，收口 B4 → **P0–P3 达 100%**。
- 剩余（独立项）：`23` 侧的跨 tick 送达延迟/重试长程诊断，可在需要时建在此 verdict 之上。

> 下一步方向（W1+W2+W2.5+W2.6 已收口；R93 Phase 2 同步交付；**R94 已交付 2026-06**；**R95 已交付 2026-06**：behavior-neutral schema 完成；1106 + R95 新增 passed / 4 skipped；详见 §10 W2.6）：**W3 R98** 真实语义 embedding（替换 hash，B2 收口，是 FG-2/记忆保真总闸，原 R95 顺移）；**W3 R99** 去英文中心 / 中文 appraisal grounding（原 R96 顺移）；**W4 R100** 把情感测试正式化为验收探针（原 R97 顺移）；**或** P4 网络通道生态（QQ/飞书/语音，达 P4 退出门）。P5 评估框架三件套（R88 漂移基线 + R89 图灵 harness + R90 记忆保真探针）已全部立起，准备好为后续 W3/W4 收口验证。

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

### R101+（双轨记忆：原 §5 计划，编号在创建时落定）
原 §5 的 R93–R98（schema/分层/重要性/衰减/检索规模化/工具/治理）已被 §10 W2.5 R94 / **W2.6 R95** / W3 R98 / W3 R99 / W4 R100 推后。
建在真实 embedding（R98，原 R95）之上，**建议编号 R101 起**，但 R101 之前的实际编号顺移将在创建时落定。
本节具体切片描述保留作 backlog（编号已顺移到 R101-R106）：

#### R101（建议）— MemoryRecord schema + 4 层时间分层
- L2/L3/L4/L5 分层，迁移 `PersistedExperienceRecord`。

#### R102（建议）— 6 维 objective_importance + 双重确认写入
- 重要性独立于 LLM 判断的客观维度 + 双重确认写入规则。

#### R103（建议）— Ebbinghaus 衰减 + recall 重固化 + 自动晋升层级

#### R104（建议）— bounded-window / ANN 语义检索
- 〔R83 修正后的 finding〕**非当前阻塞，是 P5 真实规模问题**：真实高维 embedding + 大 store 下朴素全库余弦才显著，届时换 bounded-window/ANN。建在双轨记忆检索层里最自然。

#### R105（建议）— memory_tool_channel
- `30` 框架下 LLM 记忆工具（recall/forget/consolidate 必做，link/reflect 推迟）；所有 keyword 匹配改 embedding 余弦；解决 owner 命名冲突（新 owner 名，不与 R31 CLI 冲突）。

#### R106（建议）— forget 治理 fail-closed
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
| W1 感知层（已收口） | 当下内容进入认知 + Wall-clock 真实时间戳 | R91（done）, R92（done） |
| W2 对话外化闭环 | "想说话"→`13` `reply_message` dispatch 端到端可靠 | R93 |
| W2.5 移除 `i_want_to_say` | LLM 完整行动 + 通道自主权（彻底删字段名，让 LLM 真正决定动作 + 通道） | R94（已交付 2026-06） |
| W2.6 Behavior-neutral schema | 彻底消除 schema 中的"行为暗示"字段；reply 不再特殊化；channel 自描述能力；LLM 自行关联；新增 `channel_request` 让 LLM 表达缺失能力 | R95（已交付 2026-06：1106 + R95 新增 passed / 4 skipped；8 个 R95 probe 写完待 API key 轮换后跑） |
| W3 真实语义（FG-2 总闸） | 替换 hash embedding 为真实语义 + 中文 grounding | R98（原 R95）, R99（原 R96） |
| W4 情感测试验收 | 把情感测试接入 R88/R89/R90 形成可证伪验收 | R100（原 R97） |
| 之后 | 内心独白二阶刺激（建在 R91 上）/ 双轨记忆（建在 R98 真实 embedding 上，受 R83 修正）/ 受治理自我进化 | 顺位编号待定（原 §5 R101+，原 R98+） |
| P4 通道生态（并行轨） | OS（R84/R86）+ QQ/飞书/语音/WeChat | R84/R86, 并行轨 |
| P6 / P7 | 受治理自我修订 / 受治理代码自修改 | 待 P5 框架立起后细化 |

> 注：本表按 §10 实测驱动顺序更新。R92 wall-clock 已收口 W1；R93+ 编号在创建时按实际顺序落定。
> 提醒：beta 分支 `aggressive-radical-persona-no-theater` 的 R79–R85 与 main **同名不同义**（beta 已预研漂移评估器/图灵 harness/内心独白/双轨记忆等），移植回 main 时一律按 main 的创建顺序重新编号，不沿用 beta 编号。

## 8. 当前待主人决策项

1. R85（LLM 自主工具选择）的工具意图 schema 形状与 planner 绑定策略边界（选择归 `13`，绝不回灌 `11`）。
2. R86 命令执行的治理边界方案（allowlist / sandbox root / high-risk 清单 / 首版是否禁止写自身代码）。**未确认前不动 R86。**
3. R84 生产部署时 OS 文件 driver 的 sandbox root 选址（建议 git-ignored 的 `data/fs_sandbox/`）与是否默认启用写。
4. R83 CI 档时长：当前 150 tick（套件 ~16s）；如更看重 CI 速度可降到 ~80 tick（~10s）。
5. 是否在某个节点手动跑"真实 LLM + 真实刺激"长跑（需 P4 真实 afferent 落地后信息量才大）。
6. **R94（移除 `i_want_to_say`）的 prompt 风险评估**：R93 Phase 1 fine-tune 已习惯 `i_want_to_say` 字段名。R94 移除后，旧 fine-tune 可能不再产 reply。是否需要在 R94 之后补一次"回填评估"（让真实 LLM 在 R94 prompt 上做 1-2 周 fine-tune，对比 before/after probe 03/04）？还是接受"模型在新 prompt 上重新适配"的轻量方案？

## 9. 实证测试记录：真实 LLM 情感长跑（2026-06，CLI 注入）

> 用 `scripts/cli_dialogue_prerun.py` / `scripts/emotion_test_run.py` + `scripts/sim_dialogue_zh.txt`
> 经 R31 CLI driver 把 89 条中文情感对话在随机 tick 间隔下喂入耐久+语义+channel-bound 运行时，
> `11` 思考由真实 LLM（MiniMax-M3）完成；逐条记录思考/回复 + `04`/`05` 生化 before→after。
> 分析见 `scripts/analyze_emotion_test.py`。这是项目首次"真实 LLM + 真实变化输入"的长跑实证。

### 9.1 结论（执行者 + 评委）
- ✅ **长跑稳定**：89/89 条零崩溃、内存有界、store 0→257（记忆真实累积）、88/89 触发真实 LLM 思考。
- ✅ **生化真实有界响应**：7 个 appraisal-responsive 通道波动（mean|Δ|≈0.09，峰值≈0.31，全程 clamp、无发散）；excitation/inhibition 恒 baseline（R80 设计）。
- ✅ **真实认知 grounded**：LLM 思考真实引用自身通道数值，并随对话累积逐渐意识到对话语境、后期发起 CLI 回复。
- ❌ **情感恰当性不成立（FG-2 缺口）**：正/负情绪生化分离 ≈ 0（cortisol 分离 −0.0095，其余更小），逐类签名与预期相反/随机。**根因**：appraisal `03` 跑在离线 hash embedding（无语义结构）+ R40 threat/reward 原型是英文而输入中文 → `03` 无法语义读懂中文情绪，Δ 由 hash-cosine 噪声 + 双时标振荡 + 随机 tick 数驱动。
- ❌ **外化几乎缺失**：89 条仅 1 条真正回复用户，绝大多数 tick 为内部 holding pattern。
- 评委口径：单一 LLM-judge 非正式评估，非 §13.4 锁定验收。

### 9.2 讨论衍生的发现与 backlog
1. **记忆系统：机制工作、功能弱**。store 增长、`10` 检索每 tick 投递、LLM 思考引用 "mid-term memory"；但喂给 LLM 的只是 R70 的薄投影——`retrieval_context`=层级**计数**、`continuity_context`=**首条命中 summary 截断 80 字符**，且 hash embedding 使"召回哪条"语义无意义。→ Helios 记得"有过交流"，记不住"聊了什么"。
2. **对话集重构（已采纳，本轮做）**：把逐条互不相关的情绪卡片改为"一个个访客带着小故事来谈心"——同一访客内情感弧自然累积（双时标能积分）、跨访客测记忆累积、face validity 更高。诚实限定：不解决 hash-embedding 语义召回根因。
3. **保存 LLM 原始输入输出（已采纳，本轮做）**：用日志包装 provider 包住真实 provider，落 system/user prompt + 原始 completion 到单独大 JSONL（gitignore `logs/`）。零侵入；可实证"记忆/状态/时间到底进了多少 prompt"。
4. **时间未进入 LLM 认知（待立 requirement，建议 R91）**：`temporal_signal`/`dmn_available` 只喂 `09` 门控与 `18` autonomy；`InternalThoughtRequest` 与 v3 具身 prompt **无任何时间字段** → 思考层对"时间流逝/距上次多久"零感知，且 runtime 无真实 wall-clock（tick 抽象无时刻）。两层方案：(a) 把 elapsed-pacing 作为认知内容投影进 prompt（复用 temporal owner 的 ticks_since_last_fire）；(b) 可选给 runtime 真实时间戳。与 ROADMAP R91/R92（内心独白 + `09` 自延续）契合。

### 9.3 推进顺序（主人已定）
1. **本轮**：Q2 访客故事对话集 + Q3 原始 LLM I/O 日志（均零侵入工具），完成后重跑小规模真实 LLM 测试，用真实日志实证 9.2.1。
2. 然后把 **时间进入认知** 落成正式 requirement（按创建顺序，建议 R91）。
3. **语义 embedding 根因**（替换 hash → 真实语义 embedding，B2）仍是 FG-2/记忆保真总闸，排 P5。

### 9.4 本轮 Q2+Q3 实证（访客故事对话集 + 原始 LLM I/O 抓取）
- 已交付工具：`scripts/sim_dialogue_visitors_zh.txt`（16 个访客带小故事，含情感弧），`emotion_test_run.py` 支持 `@visitor` 头 + `--llm-log`（用 `_LoggingProvider` 包真实 provider，落 system/user prompt + 原始 completion 到 JSONL）。小规模真实 LLM 重跑（12 条 / 2 访客）零崩溃。
- **🔑 关键实证发现（抓到的真实 `11` 思考 user prompt）**：
  ```
  Internal state: Neuromodulators: DA 0.55 NE 0.56 5-HT 0.37 ACh 0.36 Cort 0.53. Feeling: arousal 0.52, valence 0.41, tension 0.55. Salience: aggregate 0.72, top dimension: social.
  Autobiographical anchor: A thinking cycle concluded without outward action: ...
  Continuation pressure is inactive for this cycle.
  ```
  1. **操作者的消息内容完全不在 prompt 里**。`11._build_messages`（`internal_thought/engine.py`）只渲染 `internal_state_summary`（神经调质/感受/salience **数字**）+ 记忆召回 summary + 延续压力；**当前刺激文本从未作为文字进入思考 prompt**。消息内容只走到 `02/03`（被 appraise 成 "salience: social 0.72" 一个数），LLM 永远读不到"小苏说了什么"。这解释了为何每条思考都是"social salience 高，但当前没有具体的人/无外部需求"——**Helios 会评估这条消息，却从不阅读它**。这是本轮最重要的发现，也是它无法真正对话的首要原因。
  2. **记忆召回浮现的是自指的"无动作"记录**（"A thinking cycle concluded without outward action"），不是对话内容；且 hash embedding 使召回语义无意义。
  3. **prompt 里无任何时间字段**（实证确认 Q4）。
- **修正优先级（衍生 backlog，建议作为下一个 requirement，高优先）**：把**真实当前刺激内容（present-field）**投影进 `11` 思考 prompt（与 16 already-有的 `present_field` 层对齐，或在请求里带 stimulus_summary 供 `11` 渲染）；时间字段（Q4）可并入同一 requirement（"present-field：当前刺激内容 + elapsed 时间进入思考"）。语义 embedding 根因仍排 P5。

## 10. 测试驱动的近期开发计划（2026-06 真实 LLM 情感测试实证后）

> 本节是 §9 实证发现直接推导出的**权威近期计划**，优先级**高于** §4/§5 的早期推测队列。
> §4/§5 中的 internal_monologue（原建议 R91/R92）与双轨记忆（原建议 R93–R98）顺移到本节之后，
> 编号在创建时按实际顺序重新落定（建议号会随之顺移）。排序原则：**先让 Helios 真正"读到当下"，
> 再谈记得、回应、进化**——因为实证显示当前认知链存在"感知→认知内容断层"：真实输入被 appraise 成
> 数字，却从未作为文字进入思考。

### W1 — 让 Helios 真正读到当下（present-field 进入认知）｜最高优先、最便宜、解锁面最大

**R91 — 当下意识内容进入思考 prompt（present-field-to-thought）✅ 已交付（2026-06）**
- 实现：`InternalThoughtRequest` 加 additive `present_field_summary`（默认 None 字节级不变；非空规则+600 字符上限+确定性 `…(truncated)` 后缀）。`SemanticInternalThoughtRequestBridge` 通过新 owner-neutral helper `_present_field_summary_text` 项目**真实 `02 sensory_ingress` 外部刺激内容**（`<source> said: "<content>"`，最多 3 条 ×200 字符，按既有 `_INTERNAL_MODALITIES` 过滤 interoceptive）+ `08` focal commitment + 可选 `TemporalSource` pacing；`11._build_messages` / `_render_content` 在字段非空时 prepend `Present field:` 行。`FirstVersionInternalThoughtRequestBridge` 保持 None。
- 实施期实证修正（§11.2）：初版假设 `08.focal_summary` 装操作者文本；smoke 抓 prompt 证伪——它是 `08` 的候选级通用描述符。修正为优先从 `02` 取真实文本，`08` 作次要附加。
- 实证：smoke 的真实 prompt 现含 `Present field: cli via cli said: "家里现在静得让我害怕..."; focal: ...`，LLM 立即产出真正中文共情思考（"用户正在经历丧亲之痛...是把自己带大的奶奶..."）并经 CLI 真实回复。
- owner 边界：`11` 仍保留全部判断；composition 只读已发布 `02`/`08` stage 结果 + 注入 `TemporalSource`；bridge 不 import `06`/`10`/embedding/LLM；无 system-prompt 改动、无新日志、无 owner 色/链/边界改动。
- 测试：7 个真实 LLM probe（`scripts/r91_probes/01..07`：焦虑/哀伤/喜悦/愤怒/沉默/连续性 + 复刻失败模式的 pre-R91 负控）+ 23 个新网络无关测试（contract/engine/bridge）。基线 996→1019 测试绿。

**R92 — Wall-clock 真实时间戳（W1 收口）✅ 已交付（2026-06）**
- 实现：新基础设施 owner `helios_v2.wall_clock`（`WallClock` 协议 + `SystemWallClock` 懒导入 `time.time()` + 测试用 `FixedWallClock` 三模式 + 保留元数据键 `RECEIVED_AT_WALL_METADATA_KEY`）。三处 additive 消费：`RuntimeFrame.tick_wall_seconds` 由内核每 tick 起种入；`CliChannelDriver.submit_line` 戳 `received_at_wall`（到达时而非 drain 时，经 `02` 透传到 `Stimulus.metadata`）；`PersistedExperienceRecord.created_at_wall` 经两条 record bridge 写入（SQLite 经 PRAGMA-guarded `ALTER TABLE` 就地迁移，旧文件读回 `None`）。R91 `_present_field_summary_text` 多出 `last input: <X.X>s ago` clause（取最早外部刺激戳，NTP-rewind 钳到 `0.0s`，与既有 `pacing: <signal>` 并列）。`RuntimeProfile.wall_clock` opt-in；`assemble_production_runtime` 默认开启 `SystemWallClock`；`assemble_runtime` 默认 None 字节级不变。
- owner 边界：owner 包不 import 任何认知 owner；认知 owner 不直接 import 它（事实只经三个 additive 通道）；composition 是唯一渲染 `last input:` 的地方；本刀**无任何** owner 用 `created_at_wall` 做认知判断（独立后续切片，如 P5 双轨记忆 R93+ 计 Ebbinghaus 衰减）。
- 测试：~40 个网络无关测试 + 3 个真实 LLM probe（`scripts/r92_probes/01_with_wall_clock.json`、`02_long_silence.json` 验证模型用秒级 elapsed 事实，`03_no_wall_clock_negative_control.json` 负控验证缺字段时不编造时间）。1019→≥1059 测试绿。
- 后续独立切片（不属 R92）：`09`/`temporal` 把 tick-counted pacing 升级为按真实秒；`04`/`05` 双时标 alpha 改为按秒；`42` checkpoint 纳入 wall-time；P5 双轨记忆按 `created_at_wall` 实现 Ebbinghaus 衰减。

### W2 — 把"想回应"变成真的回应（对话外化闭环）

**R93 — 对话回复闭环可靠化 ✅ 已交付（2026-06）
- 问题（实证）：89 条仅 1 条真正回复用户；v3 `i_want_to_say` 很少转成 CLI `reply_message` dispatch。两处断点：(1) `_parse_structured_thought` 从未读顶层 `i_want_to_say` 字段，所以 reply 文本从未进 `StructuredThoughtEvidence`；(2) legacy `emit_action` fallback 构造 `ThoughtActionProposalCarrier(outbound_text=thought.content, preferred_channels=("cli",), no op_params)`，R85 `13` `required_params` 校验因缺 `outbound_text`+`target_user_id` 拒掉，写回 `world_blocked`。
- 实现（已交付）：(a) `_parse_structured_thought` 读可选顶层 `i_want_to_say` 进新增 additive `StructuredThoughtEvidence.intended_reply_text: str = ""`（2000 字符上限 + deterministic `…(truncated)`；非字符串 parse-error）。(b) `11._emit_proposal` 加隐式 reply 分支——条件：`intended_reply_text` 非空 ∧ 无显式 `tool_op` ∧ prompt-contract 摘要 `current_operator_id` 非空；构造 `reply_message` tool intent，`op_params={"outbound_text": <reply>, "target_user_id": <operator>}`，走 R85 既有 planner-spine；显式 tool 优先；无 operator 静默不构造（绝不虚构目标）；`evidence is None`（deterministic offline 路径）字节级不变。(c) composition 加 owner-neutral `_current_operator_id(frame)` helper（最早外部刺激 `source_name`，同 R91/R92 的 `_INTERNAL_MODALITIES` 过滤；honest `""` 当无外部刺激），两个 internal-thought request bridge 都把 `current_operator_id` 加进 `prompt_contract_summary`。(d) `_build_messages` 把 `i_want_to_say` 加入 schema 行并附一句"模型：填此字段时 runtime 会通过 cli 作为 `reply_message` 发给当前操作者"的 transport clause。
- owner 边界：`11` 仍保留全部判断；composition 只读已发布 `02` 并正向投影 `current_operator_id`（不动 `06`/`10`/`13`）；`13` 仍按 driver 自描述的 `required_params` 校验 `op_params`（defense in depth——R85 不变）；不回灌 `11`。
- 测试：5 个 evidence 契约 + 12 个 parser + 6 个 composition projection + 7 个 implicit-reply intent precedence + 4 个 build-messages transport clause + 6 个端到端 channel-bound CLI dispatch；2 个真实 LLM probe（`scripts/r93_probes/01_basic_reply.json` 正控、`02_silence_negative_control.json` 负控）。基线 ≥ 1059 + R93 新增 passed / 4 skipped（离线）。
- 退出信号达成：模型填 `i_want_to_say` 时可靠产生可端到端重建的 CLI 回复；不填则诚实 internal-only。

### W2.5 — 彻底移除 `i_want_to_say`；让 LLM 真正决定动作 + 通道（R94，已交付 2026-06）

**R94 — Drop `i_want_to_say`；LLM 完整行动 + 通道自主权（2026-06）**
- **问题（R93 Phase 2 评估暴露）**：R93 Phase 1 引入的 `i_want_to_say` envelope 字段名从设计上就**让模型反射性填文字**——字段名带 "say" 动词，模型看到就倾向于"既然叫这个就该填段话"。R93 Phase 2 用 `action_intent` (reply/tool/no_action) 修复了**动作类**偏差，但 `i_want_to_say` 仍然作为 schema 的一行存在，**结构上**仍在引导模型优先文字回复。Phase 2 负控 probe 04（低显著度"ok"输入）能让模型选 `no_action`，说明模型"内在判断"可以压过 prompt 暗示；但 `i_want_to_say` 字段名带来的结构性偏差是设计本身的瑕疵，需要从 schema 层消除。
- **设计决策**：把 `i_want_to_say` **彻底移除**。模型声明动作类通过 `action_intent`（reply/tool/no_action）；声明要发什么回复通过新字段 `reply_text`（仅当 `action_intent="reply"` 时相关）；声明对谁说通过 `target_user_id`；声明调用什么 channel **不**通过显式命名——LLM 只说"我对 user:xyz 说话"，系统按 `bound_user_ids` 自动找匹配的 driver（多 driver 透明，driver 增减对 LLM 无感）。
- **契约层（严格 additive → breaking）**：
  - 删 `_optional_intended_reply_text` parser
  - 删 `StructuredThoughtEvidence.intended_reply_text` 字段
  - 加 `StructuredThoughtEvidence.reply_text: str \| None = None`（`action_intent="reply"` 时用）
  - 加模块级 `REPLY_TEXT_MAX_CHARS = 2000` + 复用 `INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX`
  - 保留 `action_intent`（reply/tool/no_action）+ `target_user_id` + 现有 `tool_op` / `tool_params` / `i_want_to_use_tool` 字段（`i_want_to_use_tool` 是另一字段名，由 R85 引入，不属 R94 范围）
  - **不**新增 `preferred_channel` 字段——LLM 不需要直接命名 channel（耦合 driver 实现细节）
- **引擎层**：
  - `_emit_proposal` 新优先级：explicit-tool 工具 > `action_intent="reply"` + `reply_text` + `target_user_id` 解析成功 > `action_intent="tool"` > `action_intent="no_action"`（无 proposal）
  - 删 `reply_compat_path`（`i_want_to_say` 那条分支）
  - 删 `model_intends_action` 残留含义
  - `_build_messages` system prompt：删 `i_want_to_say` schema 行；改 `reply_text` 为"only when action_intent=reply"；强化"CHOICE"段（已存在，措辞微调）
- **通道路由**（沿用 R93 Phase 2 设计，不动）：
  - LLM 选 `target_user_id` → planner 按 `ChannelOpSpec.bound_user_ids` 过滤 → 命中 wildcard 或匹配 user_id 的 driver 入选
  - 仍执行 `target_user` → `preferred` → `iteration-order` 优先级
- **测试夹具**（约 8 个文件，~50 处更新或新增）：
  - `_internal_thought_test_fixtures.py` `envelope()` 加 `reply_text`、删 `i_want_to_say`
  - `test_runtime_composition.py` `FakeThoughtProvider`
  - `test_internal_thought_engine.py` `FakeThoughtGateway` / `JsonThoughtGateway`
  - `test_internal_thought_implicit_reply_intent.py`
  - `test_internal_thought_evidence_intended_reply.py` → 重命名为 `..._reply_text.py`
  - `test_internal_thought_parse_i_want_to_say.py` → 重命名为 `..._parse_reply_text.py`
  - `test_runtime_stage_chain_implicit_reply.py`
  - `test_internal_thought_emit_proposal_phase2.py`（更新 `i_want_to_say` → `reply_text`）
  - 新增 `test_internal_thought_no_i_want_to_say_in_prompt.py`（断言 system prompt 完全不出现 `i_want_to_say` 字样）
- **真实 LLM probe**（4 个 JSON 重跑）：
  - 01_basic_reply（正控）：模型声明 `action_intent="reply" + reply_text=...` + CLI sink 收到回复
  - 02_silence（负控）：模型声明 `action_intent="no_action"`，无 sink 输出
  - 03_action_choice（正控）："应不应该回"的判断上模型不再反射性回
  - 04_no_action_when_unmoved（负控）：低显著度"ok"输入选 `no_action`（**评估焦点**：与 R93 Phase 2 时的同一 probe 对比，看 `i_want_to_say` 移除后 `no_action` 选择是否更稳定）
- **退出信号**：
  - 完整网络无关测试套件 1107+ tests passed / 4 skipped（pre-existing wall_clock），0 regression
  - 4 个真实 LLM probe 全部 PASS
  - 系统 prompt 完全不出现 `i_want_to_say` 字样（用 `test_internal_thought_no_i_want_to_say_in_prompt.py` 自动检查）
  - 端到端：`action_intent="reply" + reply_text` → 真实 CLI sink 输出；`action_intent="no_action"` → 无输出
- **owner 边界**：
  - `11` 仍保留全部判断（不替模型决策）
  - composition 只读 `02` 投影 `current_operator_id`，不动 `06`/`10`/`13`
  - `13` 仍按 driver 自描述的 `required_params` 校验（defense in depth——R85 不变）
  - 不回灌 `11`、无新日志机制、no-adhoc-logging guard 保持绿
- **依赖**：无新外部依赖；R93 Phase 2 内部状态。
- **风险**：
  - 行为回归：`i_want_to_say` 移除后，旧 fine-tune 的模型可能不再产 reply（probe 评估会量化此风险）
  - 若真实 LLM probe 显示 04 负控仍不充分，进一步到 **R96**（**中文 appraisal grounding**）根因层
- **vs R93 Phase 2 关系**：R93 Phase 2 仍独立成立（`i_want_to_say` 字段名是 Phase 1 引入的，Phase 2 没移除只是 de-emphasize）。R94 是**对 Phase 1 字段命名的根因修正**，完全建立在 Phase 2 之上。
- **测试基线预期**：1107（pre-R93）+ R93 Phase 1（~40）+ R93 Phase 2（~47）+ 移除/重命名适配 + 2 个新探针测试 ≈ 1195+ passed。
- **requirement 路径**：`docs/requirements/94-drop-i-want-to-say-llm-agency/{requirement.md,design.md,task.md}`。

### W2.6 — Behavior-neutral schema（LLM 真正决定动作 + 通道；reply 不再特殊化）

**R95 — Drop the "behavior-suggestive" family; channel self-describes; LLM has full agency（2026-06，**已交付**）**
- **问题（R94 评估 + 你的洞察）**：R94 移除了 `i_want_to_say`（带"say"动词），但同家族字段全部残留：
  - `reply_text`（"reply" 动词，行为暗示）—— R94 引入但保留了动词
  - `i_want_to_use_tool`（"I want to" + "use"，第一称 + 行为暗示）—— R85 时代引入，R94 漏网
  - `wants_to_continue`（"wants" 动词，行为暗示）—— R81 引入，R94 漏网
  - `intends_action` / `intends_revision`（"intends" 动词，行为暗示）—— R81 引入，R94 漏网
  - `action_intent`（reply/tool/no_action 三分类，结构预设）—— R93 P2 引入
  - `target_user_id` 顶层（让 LLM 显式身份验证是错的——身份是 LLM 自己的内容决策；不是 channel 的 feature、不是 engine 的 projection）—— R93 P2 引入
  - 顶层 schema 中"reply"作为特殊 op 的预设（"我说什么你发什么"——也是行为暗示）
- **设计决策（你的回答 Q1-Q7）**：
  - Q1=B：完全合并 `action_intent` 为 `tool_op`；reply 是 `tool_op` 的特殊取值；no_action = `tool_op` 缺失/空
  - Q2=B：保留 `thinking_complete: bool` 中性信号替代 `wants_to_continue`；OWNER 选择性采纳（仍以 OWNER 的 continuation 决策为权威）
  - Q3=A：直接删除 `proposed_action` / `self_revision` 整对象；OWNER 不再读 `intends_action` / `intends_revision`
  - Q4=A：暴露**所有** ready channels × ops 给 LLM（含 op_name, required_params, effect_class, risk_class, bound_user_ids）
  - Q5=完全移除 reply 类提示：不在 system prompt 中特殊化 `reply_message`；让 channel 自己描述能力；LLM 自行关联"QQ 来消息从 QQ 回"（"模型能力越来越强"——不需要硬编码映射）；**新增 `channel_request` 字段让 LLM 表达"想要的 channel 能力"（当目标 channel 不存在时）**
  - Q6=A：8 个探针（4 旧重写 + 4 新增：confirm-only / pure-punct / tool-choice / cross-channel-routing）
  - Q7=A：probe 04 改为检查 `tool_op` 字段缺失（`must_contain="thought"`, `must_not_contain="tool_op"`）
  - Q8-Q10=：移除顶层 `target_user_id`；**不**让 channel 标记 source_user_id（这不是 feature；CLI 等 channel 根本没能力标记）；engine **不**自动注入 `target_user_id`；composition **不**投影 `current_operator_id`；身份完全是 LLM 自己的内容决策（如果 LLM 想填就填在 `tool_params.target_user_id`，planner 校验）—— 身份是 LLM 内容的一部分，不归 system 层处理（"channel 标记 `source_user_id` 这一点要很小心"）
- **契约层（11 字段删除 + 2 字段新增）**：
  - **删除**：`reply_text`, `i_want_to_use_tool`, `wants_to_continue`, `continue_reason`, `intends_action`, `action_summary`, `intends_revision`, `self_revision_summary`, `proposed_action` (整对象), `self_revision` (整对象), `action_intent`, `target_user_id` (顶层)
  - **保留 + 提升为主决策**：`thought`, `sufficiency`, `tool_op`, `tool_params`
  - **保留**：`hormone_response_i_predict`
  - **新增**：`thinking_complete: bool`（替代 wants_to_continue；OWNER 选择性采纳）
  - **新增**：`channel_request: dict | None`（LLM 表达"我想要 X 能力但 channel 没实现"）
- **引擎层**：
  - `_emit_proposal` 新优先级：单点判断 `evidence.tool_op` 非空 → 构造 proposal；`tool_op` 空 → no_action
  - 移除 `reply_explicit_path` / `explicit_tool_path_via_intent` / `explicit_no_action` 三分支
  - 移除 `model_intends_self_revision` 决策（OWNER 仅按 `self_revision_allowed_by_owner` 决定）
  - `_derive_thought_judgment` 的 `continuation_requested` 决策改为：(runtime_forces_continue ∨ low_context_forces_continue ∨ (model_thinking_complete is False AND model still has reasoning hooks))，OWNER 仍权威
  - `_build_messages` system prompt：
    - 删 `reply_text` / `i_want_to_use_tool` / `wants_to_continue` / `continue_reason` / `proposed_action` / `self_revision` / `action_intent` / `target_user_id` 8 个 schema 行
    - 加 `thinking_complete: bool`（替代 wants_to_continue）
    - 加 `channel_request: dict | None`（可选，让 LLM 表达"想要的 channel 能力"）
    - **新增 "Available channels" section**：从 `composition/bridges.py` 投影 `ChannelStateSnapshot`，列出每个 ready channel × 每个 op 的 `op_name` + `required_params` + `effect_class` + `risk_class` + `bound_user_ids`
    - **删除** 任何 "reply / tool / no_action" 三分类的提示（统一为 "tool_op"）
    - **删除** 任何"特殊 op"的提示（如 `reply_message`）——让 LLM 看 channel 自描述
- **composition 层**：
  - `bridges.py` 投影 channel state 到 prompt contract summary（新增 `available_channel_ops: tuple[dict, ...]`）
  - 移除 `current_operator_id` 投影（target_user_id 取消，channel 自行标记 source）
  - `InternalThoughtRequest.prompt_contract_summary["available_channel_ops"]` = `[(driver_id, op_name, required_params, risk_class, bound_user_ids), ...]`
- **测试夹具更新**（约 12-15 个文件）：
  - `_internal_thought_test_fixtures.py` `envelope()` 加 `thinking_complete` + `channel_request`，删 8 个旧字段
  - `test_runtime_composition.py` `FakeThoughtProvider` 同步
  - `test_internal_thought_engine.py` `FakeThoughtGateway` / `JsonThoughtGateway` 同步
  - 7 个改名/更新测试 + 2 个新增测试：
    - 新增 `test_internal_thought_no_behavior_suggestive_in_prompt.py`（断言 system prompt 完全没有 `reply_text` / `i_want_to_use_tool` / `wants_to_continue` / `intends_action` / `intends_revision` / `action_intent` / `target_user_id` 7 个家族字段）
    - 新增 `test_internal_thought_channel_request_field.py`（测试 `channel_request` 字段的解析 + 透传）
    - 新增 `test_internal_thought_available_channels_in_prompt.py`（断言 system prompt 含 Available channels section + 至少 1 个 op 描述）
    - 新增 `test_internal_thought_thinking_complete_field.py`（测试 `thinking_complete` 替代 wants_to_continue 后 OWNER 仍权威）
- **真实 LLM probe**（8 个 JSON，4 重写 + 4 新增）：
  - 01_basic_reply：模型 `tool_op="reply_message" + tool_params.outbound_text=...`（reply 仍存在但作为 tool，不特殊化）
  - 02_silence_negative_control：模型 `tool_op` 缺失/空
  - 03_action_choice：模型 `tool_op` 非空（reply 或其他）
  - 04_no_action_when_unmoved：**R95 核心验证**——低显著度"ok"输入 → `tool_op` 缺失/空
  - **05（新增）received_no_reply**：用户说"我看到了你之前的回复"→ `tool_op` 缺失（确认型消息不触发新回复）
  - **06（新增）pure_punctuation**：用户发"……" → `tool_op` 缺失（纯标点不触发回复）
  - **07（新增）tool_choice**：用户说"帮我查一下明天天气"→ `tool_op` 是 `weather_op` 而非 `reply_message`（**暴露 channels 的关键验证**）
  - **08（新增）cross_channel_routing**：用户说"把这段发到 QQ"→ 模型**自主选择** `qq.send_message` 而非 CLI（**跨通道决策的验证**）
- **退出信号**：
  - 完整网络无关测试套件 1217（pre-R95 baseline）+ R95 新增 ≈ 1260+ passed / 4 skipped / 0 regression
  - 8 个真实 LLM probe 全部 PASS
  - system prompt 完全不出现 7 个家族字段（自动检查 `test_internal_thought_no_behavior_suggestive_in_prompt.py`）
  - system prompt 出现 "Available channels" section 且含至少 1 个 op 描述
  - LLM 在 04 / 05 / 06 probe 上 `tool_op` 字段缺失（不填 tool）
  - LLM 在 07 / 08 probe 上 `tool_op` 字段**精确**选中 `weather_op` / `qq.send_message`（不默认 CLI）
- **owner 边界**：
  - `11` 仍保留全部判断（不替模型决策）
  - composition 只读 `ChannelStateSnapshot` 投影到 `available_channel_ops`，**不**做 channel 选择
  - `13` planner 仍按 driver 自描述的 `required_params` 校验 `op_params`（defense in depth）
  - 不回灌 `11`、无新日志机制
  - **身份是 LLM 自己的内容决策，不归 system 层处理**：target_user_id 取消，channel **不**标记 source_user_id（不是 feature，CLI 等 channel 根本没能力），composition **不**投影 `current_operator_id`，engine **不**自动注入；LLM 想填就填在 `tool_params.target_user_id`（planner 校验）—— 身份完全在 LLM 手里，system 不做身份处理
- **依赖**：R94（已交付）作为基础；R91 present-field 通道已立
- **风险**：
  - 模型需要重新适配新 schema（无 `reply_text` / `action_intent`），需要 1-2 周 fine-tune
  - `channel_request` 是新概念，模型可能过度使用或不用；需要观察
  - LLM 自主关联"QQ 来消息从 QQ 回"——需要验证模型确实能做这种隐式 mapping（probe 08）
- **vs R94 关系**：R94 是"移除最显眼的 bias 源（`i_want_to_say`）"；R95 是"系统性消除整个家族"——R95 把 R94 的精神目标完整实现

### W3 — P5 根因：真实语义（让"恰当"成为可能）

**R98 — 真实语义 embedding 接入（替换 hash，B2 收口）**（原 R95 顺移）
- 问题（实证）：`03` 跑离线 hash embedding（无语义）→ 无法读懂中文情绪 → 生化响应与情绪无关、正负情绪分离≈0；记忆召回 hash 选取、语义无意义、且浮现自指"无动作"记录。
- 做什么：接真实语义 embedding（本地小模型优先，支持自训练/离线再训练），使 `03` novelty/threat/reward、`06`/`10` 检索由真实语义驱动。
- owner 边界：embedding 是能力 owner（`34`），`03`/`06`/`10` 消费；不改 owner 判断权。
- 退出信号：相似情绪输入产生可区分且方向恰当的生化签名；记忆召回浮现相关对话内容。
- 依赖：R91（先让内容进认知，embedding 才有完整价值）+ W2.5 R94（先让 LLM 真正决定动作，语义评估的输出才有意义）+ W2.6 R95（先把 schema 行为暗示清除，语义评估的输出才有意义）。

**R99 — 去英文中心 / 可学习的 appraisal grounding**（原 R96 顺移）
- 问题（实证）：R40 threat/reward 原型是英文，中文输入下失效。
- 做什么：支持中文语义的 appraisal 锚点（多语原型或学习式），系数 P5 可学。
- 依赖：R98。

### W4 — 用情感测试作为可证伪验收

**R100 — 情感响应测试正式化为验收探针**（原 R97 顺移）
- 做什么：把 `scripts/emotion_test_run.py`（访客故事集 + 原始 LLM I/O 日志）+ `analyze_emotion_test.py` 接入 R88 漂移 / R89 图灵 harness / R90 记忆探针，形成可重复的"情感恰当性"可证伪验收；W1–W3 每完成一步重跑对照。
- 退出信号：正负情绪生化分离显著、思考引用真实内容、记忆召回相关、回复闭环成立——全部可只读重建。
- 依赖：R91–R99 + W2.5 R94 + W2.6 R95。

### 之后（顺移的原 P5 计划）
- 内心独白二阶刺激（原 R91/R92 内容）：建在 R91 present-field 通道上更自然（上一 tick LLM 输出回流为 present-field 的一种来源）。
- 双轨记忆（原 R93–R98 内容 → 现 R101+）：schema/分层/重要性/衰减/记忆工具/forget 治理，建在 R98 真实 embedding 之上。
- 受治理自我修订 / 代码自修改（P6/P7）。

### 一句话排序（更新）
**R91 读到当下 ✓ → R92 感知时间 ✓ → R93 学会回应 ✓ → R93 P2 完整行动 + 通道自主 ✓ → R94 移除 `i_want_to_say` ✓（W2.5，**已交付 2026-06**）→ R95 行为暗示清零 + channel 自描述（**W2.6，进行中**）→ R98 真实语义（恰当，原 R95）→ R99 中文 appraisal grounding（原 R96）→ R100 情感验收（原 R97）→ 内心独白/双轨记忆（R101+，原 R98+）/自进化。**

## 11. 工程纪律：prompt 变更必须先用真实 LLM probe 验证

> 工具：`scripts/run_llm_prompt_probe.py`（真实 LLM prompt 探针：发 system/user → 输出，校验
> must-contain/must-not-contain + 可选 JSON 解析，多模型对比，存 JSON 报告）。

**规则（已写入 `requirements/requirement-authoring-standard.md` §8.2）**：任何**增/改 LLM 面向 prompt**
的 requirement（`16` 具身 prompt 层、`11` 思考请求投影、R70 语义桥等），在实现前/实现中**必须**用该
工具对**预期的增强 prompt**做真实模型验证——构造期望 prompt 作 `--case-file`，对真实模型跑，确认模型
确实消费了新上下文、能解析、且不触发反模式（如表演化措辞、或本次要修复的"无真实信号"症状）；推理模型
（MiniMax-M3）须加 `--strip-reasoning`（镜像 `11` 的 `<think>`/围栏剥离）+ 足够 `--max-tokens`（≥2048）。
probe 结果（PASS + 关键观察）写进 requirement 的 `design.md` 验证策略。probe 只做设计验证，不替代
网络无关的 owner/契约测试。

## 11.2 R91 实施期实证修正：present-field 必须从 `02` 取，不是 `08`（2026-06）

R91 实现 T1–T4 后第一次真实 LLM smoke 抓取的 user prompt 暴露了一个设计假设错误，需要记录：

- 期望（设计假设）：`08 ReportableConsciousContent.focal_summary` 是操作者实际消息文本的归宿。
- 实情：`08.focal_summary` 是 `08` 的候选级**通用描述符**，例如：
  ```
  Present field: focal: Current focal content from perceived-stimulus-summary: perceived-stimulus-summary: current-cycle memory context
  ```
  操作者真实文本（"你好，我叫小林..."）**不在** `08.focal_summary` 中——它在 `02 sensory_ingress.batch.stimuli[*].content`。
- 修正：`_present_field_summary_text` 改为**优先**项目 `02` 的真实 external stimuli（按既有 `_INTERNAL_MODALITIES` 过滤，避免把 interoceptive 当成"说话者"），格式 `<source> said: "<content>"`；`08` focal commitment 作为次要附加；temporal pacing 仍可选。修正后真实 prompt：
  ```
  Present field: cli via cli said: "家里现在静得让我害怕，到处都是她的影子。"; focal: ...; (pacing: ...)
  ```
  LLM 立即开始真正的中文共情对话（"用户正在经历丧亲之痛...是把自己带大的奶奶...这种失去带有双重分量"）并通过 CLI 真实回复，端到端实证 R91 假设成立。
- 经验教训（写进 §11 工作流）：probe 工具用**手写理想 prompt**验证模型对内容的**消费**能力，但不保证**composition 真的能产出该内容**。两层验证都需要：probe 验证模型一端，**实施期 smoke 验证 composition 一端**。R91 因为有 smoke + LLM 原始日志，30 分钟内发现并修复；否则单测会通过但运行时仍是 holding pattern。
- 该实证修正写进 design.md §1/§3.2；`scripts/r91_probes/` 的 cases 仍代表"应当看到的 prompt 形状"——经修正后的代码就产出这个形状。
