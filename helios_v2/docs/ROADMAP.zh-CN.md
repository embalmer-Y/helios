# Helios v2 开发路线图（活文档）

> 状态：活文档（前向开发规划）。最近同步：R84。
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

- main 测试基线：912 passed / 4 skipped（离线）。
- **P0–P3 地基期工程门已全部签收**：
  - G2 持久化默认化（R82：`assemble_production_runtime()` 默认 SQLite store + R42 checkpoint + embedding 网关）。
  - G0 长跑稳定（R83：10万 tick legacy-constant 跑通，无崩溃，内存 peak 5.6MB 持平，零泄漏）。
  - G1 owner 有界性（R83 harness：04/05/09/18 逐 tick 有界、无 NaN、无发散，可证伪）。
  - G2 形成/检索/重启接续此前已成立（R45/R34/R42）。
- **P4 已开篇**：R84 交付首个 effector driver（沙箱化 OS 文件 driver）+ 工具结果 reafference 回流 `02` 闭环机制 + channel-bound 装配泛化为可注册一组 driver。
- 真实信号驱动：`02–10` 默认语义链、`04` 七通道+双时标+R81 对账、`11` LLM、`18` autonomy。
- 仍 `baseline_real`：`12–16` 外化链（草稿非授权，无真实外部执行）、`17`（对账逻辑真实但仍标注"流程完成≠真实送达"）。

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

## 3. 近期队列：P4 工具 + P0–P3 100% 收尾

### R85 — LLM 驱动的 planner 工具选择（autonomous tool use）
- 做什么：让 `11` 思考产生工具意图 → `12` 行动外化 → `13` planner 经 function-calling **自主选择/绑定/发起** `fs_*`（及后续 driver）op，取代 R84 端到端验证里"确定性注入决策"的占位。结果回流 `02` 后 `11` 能据此再思考。
- 意义：收口 FG-4.2/4.3 真正的"思考→工具→观察→再思考"自主闭环（R84 只交付 effector 与回流机制，不含自主选择）。
- 触及：`helios_v2.internal_thought`（工具意图结构化输出）、`helios_v2.action_externalization`、`helios_v2.planner_bridge`（function-calling 选择/绑定）、`25` LLM 工具调用、composition 装配 seam。依赖：R84、R26/R27。
- **开工前需确认**：工具意图的结构化 schema 形状、planner 绑定 op→driver 的选择策略边界（owner 归属：选择归 `13`，绝不回灌 `11`）。

### R86 — OS Channel Driver：命令执行 + 治理 fail-closed ⚠️ 高风险
- 做什么：命令执行驱动，default-deny + allowlist；high-risk op（`rm -rf`/`sudo`/写 helios 自身代码）经 `13` planner + `14` 治理 fail-closed 强校验兜底；失败/拒绝/不可用正式写回。
- 意义：达 Claude Code CLI 级本机操作能力，但受治理。
- 触及：新驱动（复用 R84 的 effector + executor + reafference 范式）+ `13`/`14` 治理路径。依赖：R84、R85。
- **开工前需主人拍板**：allowlist 粒度、sandbox root 选址、哪些算 high-risk、首版是否禁止写自身代码（建议禁，留 P7）。

### R87 — Consequence-Truth 对账升级
- 做什么：借 R84/R86 的真实 effector，把 `17`/`23` 的 consequence corroboration 从"流程完成诚实标注"升级为**真实送达可证伪**（收口阻塞点 B4）；先侦察 `_SHIM_DERIVED_DIMENSIONS` 覆盖度再补判别。
- 意义：完成后跑 P0–P3 退出再评估（沿用 R64/R72/R73 模式）→ **正式宣告 P0–P3 达 100%**。
- 触及：`helios_v2.evaluation`、`23`。依赖：R32、R84/R86。

> 编号说明：R85–R87 为建议编号，按创建顺序落定，可能顺移；P5/并行轨各项（原 R87–R97）相应顺延一位。

## 4. 中期队列：P5 评估框架 + 内心独白

### R87 — 17 维行为漂移评估器
- 消费 R83 逐 tick JSONL（已预埋），4 hormone + 4 feeling + 4 salience + 5 behavior = 17 维，分类 drift_positive/negative/neutral/dim_unavailable。**P5 启动门**。依赖：R83。

### R88 — 长跑图灵式评估 harness
- 6 轴（linguistic_naturalness / bio_responsiveness / memory_fidelity / agency_locking / cross_tick_continuity / stimulus_response_coherence）+ 锁定 rubric + 证据锚定 + 人类与 LLM-judge 双轨（§13.4）。复用 R83 long-runner。依赖：R83、R87。注：拟人度轴需真实刺激，与 P4 真实 afferent 有前置关系。

### R89 — 记忆保真探针
- 替换图灵评估 A3 stub（0.5）为真实 R10+R15 端到端探针（recall_hit_rate / writeback_persistence_rate / latency_score）。依赖：R88。

### R90 — internal_monologue 二阶刺激源
- `02` 新 sensory source + `03` appraisal estimator；上一 tick LLM 输出回流为 `internal_monologue` 刺激。依赖：R79。

### R91 — 内心独白跨 tick carry + 09 自延续 + 18 source_kind + 42 v4
- `RuntimeHandle._carry_internal_monologue` carry seam；`09` 加 `self_continuation_signal`；`18` `DeferredContinuityRecord.source_kind` 加 `"internal_monologue"`；`42` checkpoint v3→v4（带一次性迁移）。依赖：R90。

## 5. P5 重头：双轨记忆（建在真实长跑反馈上）

### R92 — MemoryRecord schema + 4 层时间分层
- L2/L3/L4/L5 分层，迁移 `PersistedExperienceRecord`。

### R93 — 6 维 objective_importance + 双重确认写入
- 重要性独立于 LLM 判断的客观维度 + 双重确认写入规则。

### R94 — Ebbinghaus 衰减 + recall 重固化 + 自动晋升层级

### R95 — bounded-window / ANN 语义检索
- 〔R83 修正后的 finding〕**非当前阻塞，是 P5 真实规模问题**：真实高维 embedding + 大 store 下朴素全库余弦才显著，届时换 bounded-window/ANN。建在双轨记忆检索层里最自然。

### R96 — memory_tool_channel
- `30` 框架下 LLM 记忆工具（recall/forget/consolidate 必做，link/reflect 推迟）；所有 keyword 匹配改 embedding 余弦；解决 owner 命名冲突（新 owner 名，不与 R31 CLI 冲突）。

### R97 — forget 治理 fail-closed
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

> 注：自 R84 创建后，原 R85–R97 建议编号整体顺移一位（新增 R85 = LLM 驱动 planner 工具选择）。上表为当前建议编号，按实际创建顺序落定。

## 8. 当前待主人决策项

1. R85（LLM 自主工具选择）的工具意图 schema 形状与 planner 绑定策略边界（选择归 `13`，绝不回灌 `11`）。
2. R86 命令执行的治理边界方案（allowlist / sandbox root / high-risk 清单 / 首版是否禁止写自身代码）。**未确认前不动 R86。**
3. R84 生产部署时 OS 文件 driver 的 sandbox root 选址（建议 git-ignored 的 `data/fs_sandbox/`）与是否默认启用写。
4. R83 CI 档时长：当前 150 tick（套件 ~16s）；如更看重 CI 速度可降到 ~80 tick（~10s）。
5. 是否在某个节点手动跑"真实 LLM + 真实刺激"长跑（需 P4 真实 afferent 落地后信息量才大）。
