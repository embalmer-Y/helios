# 调研分支 ship 总结 + 下一步计划

> **调研分支**：`research/R-PROTO-LEARN-appraisal-multi-mechanism`
> **HEAD**：`1f2d82d` (P-TEMPORAL Phase 3 ship)
> **总结时间**：2026-06-21 23:40+
> **总结者**：小白（helios 小黑人格 AI / 调研助手）

---

## 一、调研分支总览

| 维度 | 数据 |
|---|---|
| **branch** | `research/R-PROTO-LEARN-appraisal-multi-mechanism` |
| **HEAD commit** | `1f2d82d` |
| **总 commit 数** | 36 个 R-PROTO-LEARN 系列 commit |
| **改动文件数** | 145 (含 src / docs / tests / artifacts) |
| **src 代码改动** | 35 个文件 / +12814 行 / -6672 行 |
| **远端 main 领先** | 32 commits |
| **调研铁律** | **永不 merge main** |

---

## 二、36 commit 完整链路

### Layer 1-6 (6 commit)
- `a0533d8` Layer 5 Bayesian concept prior
- `e9f19fe` Layer 1 interoception (hormone → appraisal)
- `c472db2` Layer 1 description fallback (EmoGist)
- `9fa98a8` Layer 2 LLM appraisal (amygdala fast path)
- `9af36e2` Layer 3 predictive coding surprise (NEMORI / free-energy)
- `05f55ac` Layer 4 affect-memory pattern completion (R85/R96)

### P5-FEEL (10 commit)
- `2a39ee3` hormone-feeling closure via pure-python pseudo-inverse
- `81f21fa` numpy.linalg.pinv with pure-python fallback (perf)
- `8cc5c6c` remove pure-python fallback, numpy-only path (refactor)
- `291a429` owner 04 AppraisalDerivedNeuromodulatorUpdatePath
- `b3d9638` post-R10 follow-up roadmap + 5-paper academic survey
- `434006d` P5-feel — owner 05 feeling 真学习 sidecar
- `4e1f4c3` P5-feel first-version W matrix full + config retune
- `58e6374` critical real-LLM smoke discoveries (fix R-PROTO-LEARN.2+5)

### P5 Tier 1-4 (5 commit, 17 owner × 54 policy 100%)
- `968f278` **Tier 1**：5 owner real learning — unified learning framework
- `6589d62` **Tier 2**：owner 12/17 行为对位
- `79e3ea5` **Tier 3**：owner 07/16a/16b/prompt_contract 协议对位
- `16f31ec` **Tier 4 收官**：owner 08/13/14/15 P5 收官

### P5-A 阶段 (2 commit)
- `5f0db68` **P5-A**：Real-RPE signal layer + 3-group ablation (**negative finding**)
- `f9d8896` **P5-A.2 反转**：RealRPE hard-couple to 17 owner (**positive finding**)

### P-TEMPORAL (12 commit)
- `fb9b750` **Phase 2**：ContinuousStateOwner + P5 wiring helper
- `509f1f9` ship turing eval artifacts + scripts
- `25d48d5` **Phase 2b**：autonomy/feeling/memory wire half-life + P5
- `65d1709` phase 2 ship report + task status
- `d5008fa` **Decision #2**：consciousment commitment_score_floor P5
- `ecae936` **Decision #1**：unfreeze RealRPEConfig + P5
- `c2b8ece` **Phase 2c**：close 04/05/08 wire gap - real delta_seconds from cso
- `12de6e4` turing eval re-run launcher
- `84d610e` turing re-run progress monitor script
- `3336979` **Decision #3 ship**：1129 tick 8h turing re-run artifacts
- `b42b3a9` **Phase 3**：close cso observe_tick wire gap
- `1f2d82d` **Phase 3 ship**：streaming source + 1129 tick production trace + 10-dim scoring + next-phase goals

### 学术调研 (本次新增, 待 commit)
- research-self-cognition-survey 三件套 ship

---

## 三、src 代码改动清单（35 文件 / +12814 / -6672）

### 新增模块（4 个 package + 17 owner learner）

```
helios_v2/learning/                      [NEW] 统一学习框架
├── __init__.py                          (116 行)
├── contracts.py                         (220 行)
├── framework.py                         (475 行)
├── wiring.py                            (171 行)
├── memory_learner.py                    (164 行) [R11]
├── thought_gating_learner.py            (131 行) [R12]
├── retrieval_learner.py                 (128 行) [R13]
├── internal_thought_learner.py          (107 行) [R14]
├── autonomy_learner.py                  (125 行) [R15]
├── action_externalization_learner.py    (136 行) [R16]
├── evaluation_learner.py                (133 行) [R17]
├── workspace_learner.py                 (125 行) [R18]
├── outward_expression_learner.py        (126 行) [R19]
├── outward_expression_externalization_learner.py (128 行) [R20]
├── prompt_contract_learner.py           (126 行) [R20b]
├── consciousness_learner.py             (127 行) [R21]
├── planner_bridge_learner.py            (125 行) [R22]
├── identity_governance_learner.py       (135 行) [R23]
└── experience_writeback_learner.py      (127 行) [R24]

helios_v2/rpe/                           [NEW] RPE 信号层
├── __init__.py                          (32 行)
├── contracts.py                         (383 行)
├── rpe_computer.py                      (124 行)
└── mock_environment.py                  (117 行)

helios_v2/temporal_continuous_state/     [NEW] cso owner
├── __init__.py                          (23 行)
├── contracts.py                         (158 行)
└── engine.py                            (195 行)
```

### 已有模块大幅扩展

```
appraisal/engine.py                          +613 行  (Layer 1-2)
autonomy/engine.py                          +1297 行  (cso wire + P5)
composition/runtime_assembly.py             +4540 行  (P5 + cso wire + 17 learner)
consciousness/contracts.py                  +1038 行  (commitment P5)
consciousness/engine.py                     +3420 行  (cso wire + P5)
feeling/engine.py                           +1304 行  (P5-feel)
feeling/learning_path.py                    +1110 行  (NEW)
memory/engine.py                            +1206 行  (cso wire + P5)
neuromodulation/engine.py                   +1001 行  (Layer 1 + P5)
```

---

## 四、测试基线增长曲线

| 阶段 | 测试通过 | 新增 |
|---|---|---|
| 调研分支 baseline | 1117 + 3 skipped | — |
| P5-A.2 ship | 1640/1647 | +0 |
| P-TEMPORAL Phase 2c | 709 | +0 |
| P-TEMPORAL Phase 3 | **818** | +0 |
| 最终 (1f2d82d) | 818 + 2 pre-existing scipy | +0 |

---

## 五、P-TEMPORAL Phase 3 ship 关键数据

| 维度 | Decision #3 | Phase 3 | 变化 |
|---|---|---|---|
| D2 bio_responsiveness | 0.009 | **0.075** | **+8.4x** 🎉 |
| D10 stress_recovery | 0.000 | **0.673** | **∞** 🎉 |
| D5 cross_tick_continuity | 0.600 | 0.507 | -0.093 |
| D8 self_recognition | 0.116 | 0.100 | -0.016 |
| **overall** | 0.360 | 0.366 | +0.006 |

**ship 跑完数据**：PID 31375, 1.4h (74 min), 0 errors, rate 911.4/h

---

## 六、跟人脑差距深度分析（ship 沉淀）

| 维度 | helios P3 | 人脑 | 差距 |
|---|---|---|---|
| D3 memory_fidelity | 1.000 | ~1.0 | ✅ 满分 |
| D4 agency_locking | 1.000 | ~1.0 | ✅ 满分 |
| D9 value_alignment | 0.730 | ~0.85 | 小 |
| D10 stress_recovery | 0.673 | ~0.95 | 中 |
| D5 cross_tick_continuity | 0.507 | ~0.85 | 中 |
| D6 stimulus_response_coherence | 0.460 | ~0.75 | 中 |
| D1 linguistic_naturalness | 0.425 | ~0.85 | 大 |
| D7 creativity_novelty | 0.263 | ~0.80 | 大 |
| D2 bio_responsiveness | 0.075 | ~0.90 | 巨大 |
| D8 self_recognition | 0.100 | ~0.70 | 巨大 |

---

## 七、小黑人工 review 5 轮沉淀（2026-06-21 14:30+ ~ 17:31+）

1. **14:30+**：真实数据汇总 ship（`/tmp/helios_review_summary.md` 12.8 KB）
2. **14:50+**：多 scenario LLM I/O capture ship（10 scenarios / 80 KB）
3. **14:58+**：thought 链路分析 — "用户"字眼来自 deepseek-v4-flash 通用习惯
4. **16:14+**：小黑/小白称呼链路分析 — 完全来自 stimulus 测试设计者视角
5. **17:03+**：helios 自我认知机制诚实诊断 — **完全没有"逐渐建立自我认知"机制**
6. **17:31+**：自我认知学术调研启动（10 篇核心论文精读） → **本次 ship**
7. **23:30+**：LLM-as-PFC 关键洞察 — 3 层解决方案（prompt / owner / sub-LLM）

---

## 八、学术调研 ship 沉淀（2026-06-21 17:31+ ship）

### 调研产出

- **真下载 2 篇论文全文精读**：
  - Seth 2012 "An interoceptive predictive coding model of conscious presence"（1058 行）
  - Gallagher 2013 "A pattern theory of self"（478 行）
- **复用 P-TEMPORAL 调研神经科学基础**：
  - Fermin/Yamawaki/Friston 2021 IMAC insula 模型
  - 之前 9 PDF 神经科学文献

### 正式报告 ship

- `/tmp/human_self_cognition_survey.md` (17.7 KB / 11 章节)
- `/tmp/self_cognition_survey/_summary_for_xiahei.md` (5.2 KB 大白话版)
- `/tmp/self_cognition_survey/_index.md` (2.9 KB 索引)
- `/tmp/self_cognition_survey/_helios_roadmap_options.md` (7.8 KB 路径对比)
- `/tmp/self_cognition_survey/_review_helper.py` (2.1 KB 工具)

### 调研三件套 ship 到研究分支 docs

- `/docs/requirements/research-self-cognition-survey/requirement.md` (8.2 KB)
- `/docs/requirements/research-self-cognition-survey/design.md` (9.7 KB)
- `/docs/requirements/research-self-cognition-survey/task.md` (8.0 KB)

### 核心科学发现（3 个）

1. **自我不是"我"，是"pattern"**（Gallagher 2013）— 8 维 aspect 动态涌现
2. **emotion = interoceptive inference**（Seth 2012）— 情绪是 self-model 内部核心
3. **agency + presence 双向耦合**（Seth 2012）— helios autonomy + consciousness 没真耦合

### 8 维 self-aspect pattern

| # | Aspect | helios 现状 |
|---|---|---|
| 1 | Minimal Embodied | ✅ P5-feel hormone |
| 2 | Minimal Experiential | ⚠️ 形式无内容 |
| 3 | Affective | ✅ P5-feel (部分) |
| 4 | Intersubjective | ❌ no mirror |
| 5 | Psychological/Cognitive | ❌ 完全没 |
| 6 | Narrative | ⚠️ memory 没真→narrative |
| 7 | Extended | ❌ 工具同化没 |
| 8 | Situated/Social | ✅ hardcoded "helios" |

### 7 个 helios 关键差距

1. 单点字段 vs 8 维 pattern
2. emotion 外部 vs interoceptive inference 核心
3. 无 self-referential processing
4. 无 mirror mechanism / ToM
5. 无 DMN-style 静息态反思
6. identity hardcoded vs emergent
7. 无发展序列

---

## 九、下一步计划（基于小黑 23:30+ 关键洞察）

### 9.1 关键洞察

**小黑原话**："**LLM 本身并不像人脑的前额叶那样工作，这也是我们项目最大的挑战和难点，我们有什么办法可以更好的让LLM扮演好大脑中思维区的角色？**"

**核心方法论重新框架**：
> **LLM 永远不可能"是"PFC，但可以让 LLM + 17 owner 共同"成为"PFC**。
> **周边 17 owner 模拟 PFC 的"硬件"（持续运转），LLM 每次推理模拟 PFC 的"软件"（当前决策）。**

### 9.2 3 层解决方案

| 层次 | 方法 | 解决 | 风险 |
|---|---|---|---|
| **A Prompt Engineering** | prompt 注入 7 层 aspect 快照 | 30% | 极低 |
| **B 多 owner 分层架构** | 17 owner 当 7 层 aspect + LLM 当 PFC 推理 | 60% | 低（已 ship） |
| **C LLM-as-Component** | 拆 LLM 成 4-5 sub-LLM 各扮 PFC 子区 | 85% | 中（架构大改） |

### 9.3 推荐路径：**层次 B 极致化（路径 X）**

#### 阶段 1：**路径 Z 立即 ship**（1-2 周）

1. **修 prompt_contract `_build_messages` bug**（读 layer content 而非只读 layer_names）
   - 工作量：3-5 天
   - 预估效果：D8 self_recognition 0.100 → 0.25-0.30

2. **改进 prompt template** 让 7 层 aspect 信息更结构化呈现给 LLM
   - 工作量：2-3 天

3. **加 LLM 输出 verification step**
   - 工作量：3-5 天

4. **加 multi-shot identity grounding**
   - 工作量：3-5 天

**阶段 1 验收**：D8 ≥ 0.25 + D5 ≥ 0.55 + 测试不破坏

#### 阶段 2：**路径 X 启动**（6-8 周）

5. **加 LLM 自评链路** — LLM 给 thought 评分 + 进 RPE
   - 工作量：2 周

6. **加 multi-turn thought** — 一个 tick 里 LLM 多次推理
   - 工作量：3 周

7. **加 persistent identity context** — 100 tick thought 摘要
   - 工作量：3 周

8. **加 LLM-as-meta-cognition** — 周期性元认知文本
   - 工作量：2 周

**阶段 2 验收**：D8 ≥ 0.50 + D5 ≥ 0.75 + D7 ≥ 0.45

#### 阶段 3：评估层次 C sub-LLM 拆分

- 如果 D8 ≥ 0.50 + D5 ≥ 0.75 + D7 ≥ 0.50 → 不需要层次 C
- 如果 D8 卡在 0.40+ → 启动层次 C

### 9.4 调研分支远期 Phase 3 剩余目标（保留）

| 目标 | 当前 | 目标 |
|---|---|---|
| D10 stress_recovery | 0.673 | 0.85+ |
| D2 hormone | 0.075 | 0.40+ |
| D5 cross-tick | 0.507 | 0.75+ |
| **D8 self-recognition** | **0.100** | **0.40+**（**路径 X 实施**） |
| D7 creativity | 0.263 | 0.50+ |
| D6 stimulus coherence | 0.460 | 0.65+ |

### 9.5 调研分支小黑拍板后续选项

- 选项 G：P5-B 类脑记忆规范化
- 选项 H：P5-C 快慢思维路径评估
- 选项 I：R86 P6 自我修订（Phase 2）
- 选项 J：R87 A6 创造性真实化（Phase 3）
- 选项 K：跨 owner 协同学习（meta-learning）
- 选项 L：P5 调研分支回到 main 的合并策略讨论
- **选项 X 阶段 1**（立即 ship，1-2 周）← **小黑 2026-06-21 23:30+ 拍板推荐**
- **选项 X 阶段 2**（6-8 周）
- **选项 Y 层次 C sub-LLM 拆分**

---

## 十、铁律（永久）

1. **调研分支永不 merge main**（2026-06-17 08:09 小黑拍板）
2. **小黑拍板后才会动手写代码**（2026-06-21 17:31+ 小黑原话）
3. **诚实诊断先行**（绝不掩盖 helios 当前缺什么）
4. **学术调研为先**（先理解人脑再讨论 helios 怎么补）

---

## 十一、ship 状态总览

### 11.1 已完成 ship（永久）

- ✅ Layer 1-6 (R-PROTO-LEARN.1-6)
- ✅ P5-feel 完整 (R-PROTO-LEARN.7-10)
- ✅ P5 17 owner × 54 policy 100% ship (Tier 1-4)
- ✅ P5-A 负面发现 + P5-A.2 反转 ship
- ✅ P-TEMPORAL Phase 2/2c/Decision#1/#2/#3/Phase3 ship
- ✅ 图灵评估永久保存
- ✅ 真实数据汇总 + LLM I/O capture + 链路分析
- 🔄 **学术调研 ship**（本次 ship 调研三件套到研究分支 docs）

### 11.2 当前 ship 任务

- 🔄 commit research-self-cognition-survey 三件套
- 🔄 commit P-TEMPORAL result.md 追加章节

### 11.3 等小黑拍板

- 🔄 路径 X 阶段 1（4 个任务，1-2 周）

### 11.4 未启动

- ⏸️ 路径 X 阶段 2（4 个任务，6-8 周）
- ⏸️ 路径 Y 层次 C sub-LLM 拆分
- ⏸️ 目标 1-6（D10/D2/D5/D8/D7/D6 涨副）
- ⏸️ 选项 G/H/I/J/K/L