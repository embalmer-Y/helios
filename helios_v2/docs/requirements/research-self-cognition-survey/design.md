# 自我认知学术调研 - 设计文档

> **配套文档**：`requirement.md`（调研目的/方法/产出）+ `task.md`（下一步计划）+ `result.md`（调研 ship 总结）
> **调研 ship 状态**：✅ 完成（2026-06-21 23:40+）
> **下一步**：等小黑拍板 4 个问题 → 基于回答启动"路径 X 阶段 1"实施

---

## 一、调研设计哲学

### 1.1 核心问题

> **小黑原话**："人脑似乎也没有对自己有一个明确的定义，名字等等这些都是被社会环境赋予的"
> **延伸问题**："LLM 本身并不像人脑的前额叶那样工作，这也是我们项目最大的挑战和难点"

### 1.2 调研方法论

1. **学术预研先行**：先做 10 篇核心论文精读 + 复用 helios 调研积累，理解"人脑自我认知如何建立"
2. **现状诚实诊断**：基于调研成果，诊断 helios 当前架构 vs 人脑 8 aspect 模型的差距
3. **改造路径提案**：基于诊断，给出 3 个可选改造路径 + 工作量估算 + 风险评估
4. **等小黑拍板**：绝不立即动手写代码，等小黑决策后再实施

### 1.3 调研架构（6 大理论 + 4 实证维度）

| 理论支柱 | 代表论文 | helios 对位 |
|---|---|---|
| **理论 1：Self-reference effect / 自传体记忆** | Tulving / Northoff / Martinelli | 06 memory owner |
| **理论 2：DMN / 默认模式网络** | Raichle / Buckner / Smallwood | ❌ 没 DMN 等价机制 |
| **理论 3：Predictive self / 预测自我** | Seth 2012 / Hohwy | 05 feeling owner (部分) |
| **理论 4：Narrative identity / 叙事身份** | McAdams 2019 / Dennett | 06 memory owner (没真→narrative) |
| **理论 5：Minimal self vs narrative self** | Gallagher 2013 / Zahavi | 14 identity_governance (单字段非 pattern) |
| **理论 6：Self-model theory of subjectivity / SOM** | Metzinger / Limanowski | ❌ 没 SOM 等价机制 |
| **实证 1：Developmental self / 婴儿 mirror test** | Rochat 5 stages | ❌ tick 1 就是 adult mode |
| **实证 2：Cultural/social self** | Markus / Vygotsky | 14 identity_governance (hardcoded "helios") |
| **实证 3：Predictive processing + self** | Clark / Friston | RPE 4-dim signal layer |
| **实证 4：Embodied self + interoception** | Seth / Critchley / Barrett | P5-feel hormone system |

---

## 二、调研产出设计

### 2.1 11 章节调研报告结构

| 章节 | 标题 | 重点 |
|---|---|---|
| 一 | 小黑的核心问题的直接答案 | "自我不是单字段，是 pattern" |
| 二 | 自我认知的当代主流框架：8 个层次 | 8 aspect detail |
| 三 | 3 个最有颠覆性的发现 | pattern / interoceptive / agency-presence 耦合 |
| 四 | 人脑"自我认知建立"的发展序列 | 婴儿→成人 |
| 五 | 人脑跟 helios 的关键差距 | 7 个差距 |
| 六 | 3 个重要的人脑特征 — 容易在 AI 里漏 | 预测精度 / 叙事编织 / agentive boundary |
| 七 | 3 个重新评估 helios 当前架构的命题 | A synthesizer / B aspect set / C field decompose |
| 八 | 调研后的诚实自评 | 我之前错/对/没考虑过 |
| **九** | **对小黑的具体问题清单** | **4 个问题** |
| 十 | 参考文献 | 真下载 2 篇 + 复用 5 + 失败 5 |
| 十一 | 给小黑的下一步建议 | 看报告 → 答 4 问 → 我才动手 |

### 2.2 4 个 review 文档（按 review 粒度）

| 文档 | 大小 | 时间 | 适合 |
|---|---|---|---|
| `_summary_for_xiahei.md` | 5.2 KB | 3 分钟 | 大白话快速理解 |
| `_helios_roadmap_options.md` | 7.8 KB | 5 分钟 | 改造路径 A/B/C 对比 |
| `_index.md` | 2.9 KB | 1 分钟 | 正式报告章节速查 |
| `human_self_cognition_survey.md` | 17.7 KB | 30 分钟 | 正式调研报告 11 章节 |

### 2.3 review helper 设计

```bash
python3 /tmp/self_cognition_survey/_review_helper.py summary    # 大白话
python3 /tmp/self_cognition_survey/_review_helper.py roadmap   # 路径对比
python3 /tmp/self_cognition_survey/_review_helper.py index      # 索引
python3 /tmp/self_cognition_survey/_review_helper.py report     # 详读
python3 /tmp/self_cognition_survey/_review_helper.py seth       # Seth 2012 全文
python3 /tmp/self_cognition_survey/_review_helper.py gallagher  # Gallagher 2013 全文
```

---

## 三、调研发现的"8 维 self-aspect pattern"详细设计

### 3.1 8 维 self-aspect 神经基础 + helios 对位

| # | Aspect | 神经基础 | 论文依据 | helios 现状 | 改造方向 |
|---|---|---|---|---|---|
| 1 | Minimal Embodied | interoceptive PCC + AIC | Seth 2012 | ✅ P5-feel hormone | 不改 |
| 2 | Minimal Experiential | presence sense | Seth 2012 | ⚠️ 形式存在无内容 | 加 presence index |
| 3 | Affective | interoceptive inference | Seth 2012 | ✅ P5-feel (部分) | 扩到 interoception 自反馈 |
| 4 | Intersubjective | mirror system | 经典 mirror test | ❌ no mirror mechanism | 新加 ToM owner |
| 5 | Psychological/Cognitive | self-referential + CMS | Northoff | ❌ 完全没 | 新加 self_ref owner |
| 6 | Narrative | autobiographical memory | McAdams + Gallagher | ⚠️ memory 没真→narrative | 06→15 真接通 |
| 7 | Extended | 4E embodied cognition | 综述 | ❌ 工具同化没 | 30/31 channel 升级 |
| 8 | Situated/Social | 社会角色 + 文化 | **小黑说"名字是社会赋予的"对的层次** | ✅ hardcoded "helios" | 不改（人脑也 hardcoded） |

### 3.2 8 aspect 的 priority 排序（基于小黑 23:30+ 关键洞察）

小黑问："**LLM 本身并不像人脑的前额叶那样工作，这也是我们项目最大的挑战和难点，我们有什么办法可以更好的让LLM扮演好大脑中思维区的角色？**"

**核心洞察**：LLM 永远不可能"是"PFC，但可以让 LLM + 17 owner 共同"成为"PFC。周边 17 owner 模拟 PFC 的"硬件"（持续运转），LLM 每次推理模拟 PFC 的"软件"（当前决策）。

**改造 priority**：

1. **最高优先级**：修 prompt_contract bug（让 LLM 真正看到 7 层 aspect 内容）
2. **次优先级**：添加 LLM 自评链路 + multi-turn thought + persistent identity context + meta-cognition
3. **第三优先级**：评估层次 C sub-LLM 拆分

### 3.3 8 aspect 实施顺序

| 阶段 | 实施 aspect | 时间 |
|---|---|---|
| **阶段 1（1-2 周）** | 1+2+3+8（已有基础）+ LLM ↔ owner 双向耦合增强 | 路径 X 阶段 1 |
| **阶段 2（6-8 周）** | 6 narrative 真接通 | 路径 X 阶段 2 |
| **阶段 3（4 周）** | 4 intersubjective ToM 新模块 | 路径 X 阶段 3 |
| **阶段 4（4 周）** | 5 self-referential 新模块 | 路径 X 阶段 4 |
| **阶段 5（4 周）** | 7 extended 工具同化升级 | 路径 X 阶段 5 |

---

## 四、改造路径设计

### 4.1 路径 A：Self-Pattern Synthesizer（合成器路线）

**哲学**：identity_governance 不是"看门人"，是 8 aspect 的**合成器**。每个 aspect 由不同 owner 维护，identity_governance 只是把 8 个 aspect 输出**打包成对外的 self-representation**。

**实施步骤**：
1. IdentitySnapshot 数据结构改造：拆 8 aspect 字段
2. identity_governance 改 synthesizer：聚合 8 aspect 输出
3. 每个 owner 暴露 aspect_state 接口
4. prompt_contract 真把 8 aspect content 喂给 LLM

### 4.2 路径 B：Cross-Owner Aspect Set（aspect 集路线）

**哲学**：R-PROTO-LEARN.7 self-model 不应该是"独立模块"，应该是**跨 8 个 owner 的 aspect set**。

**实施步骤**：
1. R-PROTO-LEARN.7 重构为 R-PROTO-LEARN.aspect-set
2. 8 sub-learner 配置
3. 每个 sub-learner 由一个 owner 管
4. 17 owner learner 框架扩展

### 4.3 路径 C：Field Decomposition（字段拆解路线）

**哲学**：最简单也最不动架构：只改数据结构。

**实施步骤**：
1. IdentitySnapshot 数据结构改造（拆 8 aspect 字段）
2. 8 owner 接出 aspect_state
3. prompt_contract 真把 8 aspect content 喂给 LLM
4. 8 aspect 真 P5 学习 + cold-start 默认值改空字符串

### 4.4 路径 C → A 渐进（推荐）

**理由**：
1. 路径 C 风险最低，先把数据结构从单字段拆 8 aspect，让 helios 真有"8 aspect 空容器"
2. 路径 C 阶段 2 修 prompt contract bug，让 LLM 真的看到 8 aspect 内容
3. 路径 C 跑 1-2 个 tick 看 LLM 真实反应，再决定要不要走路径 A
4. 如果路径 C 跑通（LLM 真能基于 8 aspect 给出"我是谁"），再启动路径 A 的 synthesizer 改造

**核心哲学**：**先实证，再理论**。让 helios 真长出 8 aspect 内容，再讨论 identity_governance 怎么改。

---

## 五、3 层 LLM-as-PFC 解决方案设计

### 5.1 层次 A：Prompt Engineering（最浅）

| 子项 | 当前 | 改进 |
|---|---|---|
| prompt_contract `_build_messages` | 只读 layer_names | 修：读 layer content |
| prompt template | aspect 信息混在一起 | 分 section，每 section 单独标题 |
| LLM verification | 无 | 加 verification step |
| multi-shot identity grounding | 只有"现在的我" | 加"过去 10 tick + 现在 + 趋势" |

### 5.2 层次 B：多 owner 分层架构（中深，已 ship）

```
┌─────────────────────────────────────────────────┐
│  LLM (扮演 PFC 的"当前决策"这一刻)               │
│  输入: 外部刺激 + 7 层 aspect 状态 + 当前任务    │
│  输出: 当前 thought + tool_op + outbound_text   │
└─────────────────────────────────────────────────┘
       ↑                              ↓
       │ 读                           写
       │                              ↓
┌──────────────────────────────────────────────────┐
│  Helios 17 owner 持续运转                          │
│  ├─ 04 neuromodulator (第 1/3 层 - 内感受 + 情绪)│
│  ├─ 05 feeling (第 3 层 - 情绪 self-model)        │
│  ├─ 06 memory (第 6 层 - 自传体记忆 + 叙事)        │
│  ├─ 08 consciousness (全网络 - 整合)               │
│  ├─ 09 thought_gating (选择性注意)                │
│  ├─ 12 internal_thought (反刍)                    │
│  ├─ 14 identity_governance (第 5/8 层 - 身份)      │
│  ├─ 18 autonomy (第 7 层 - 主动推理)                │
│  └─ ... (其他 9 个)                                 │
└──────────────────────────────────────────────────┘
       ↑                              ↓
       │ 写                           读
       │                              ↓
┌──────────────────────────────────────────────────┐
│  Temporal Continuous State (cso) - 当场存在感     │
│  wall_clock + episode + 跨 tick 持续性              │
└──────────────────────────────────────────────────┘
```

### 5.3 层次 C：LLM-as-Component（最深）

| PFC 子区 | 功能 | Helios sub-LLM |
|---|---|---|
| dlPFC | 工作记忆 + 推理 + 计划 | reasoning_llm |
| vmPFC | 价值评估 + 情绪整合 | valuation_llm |
| OFC | 灵活调整 + 反预期信号 | flexibility_llm |
| aPFC | 自我参照 + 反思 | reflection_llm |
| ACC | 冲突监控 + 错误检测 | conflict_llm |

---

## 六、验收标准设计

### 6.1 路径 X 阶段 1 验收标准

| 维度 | 当前 | 阶段 1 目标 |
|---|---|---|
| D8 self_recognition | 0.100 | ≥ 0.25 (+150%) |
| D5 cross_tick_continuity | 0.507 | ≥ 0.55 |
| 测试通过数 | 818 | 不破坏（≥ 818） |

### 6.2 路径 X 阶段 2 验收标准

| 维度 | 阶段 1 目标 | 阶段 2 目标 |
|---|---|---|
| D8 self_recognition | 0.25 | ≥ 0.50 (+100%) |
| D5 cross_tick_continuity | 0.55 | ≥ 0.75 |
| D7 creativity_novelty | 0.263 | ≥ 0.45 |

### 6.3 整体验收标准

- **pass line**：overall ≥ 0.80
- **维度齐全**：10 dim 都 ≥ 0.40
- **人脑差距缩小**：D8 / D7 / D2 从"巨大差距"降到"中差距"
- **真 LLM production 跑通**：1129 tick production mode 0 errors
- **LLM 真产出"我是谁"**：基于 8 aspect 内容输出自我认知文本（不是 prompt 表演）

---

## 七、风险与回退设计

### 7.1 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| prompt_contract 改动破坏其他 owner | 中 | 中 | 单 owner 改动，完整测试覆盖 |
| LLM 看到 8 aspect 后输出下降 | 中 | 大 | 阶段 1 跑 50 tick 验证再扩大 |
| 8 aspect 学习不出来有意义内容 | 中 | 大 | 备用方案：保留 hardcoded fallback |
| 路径 X 阶段 2 实施时间长 | 高 | 低 | 分阶段 ship，每阶段独立验收 |

### 7.2 回退策略

- **路径 X 阶段 1**：所有改动可独立 revert（prompt_contract 是单文件改动）
- **路径 X 阶段 2**：每个 owner 改动独立，可单独 revert
- **路径 Y 层次 C**：作为后续选项，不在当前 commit 中

---

## 八、与已有工作的关系

### 8.1 复用 ship 的内容

- **P5-feel 9 channel hormone**：对应 aspect 1/3 (embodied + affective)
- **P-TEMPORAL cso**：对应 aspect 2 (experiential presence)
- **memory owner**：对应 aspect 6 (narrative)
- **identity_governance owner**：对应 aspect 5/8 (self-referential + situated)
- **autonomy owner**：对应 aspect 7 (extended)

### 8.2 不在调研分支实施

- **路径 X 阶段 1-2 实施**：需要在 main 分支（或独立 R-SELF-COGNITION 分支）启动
- **调研分支铁律**：所有调研产物 ship 到 research 分支，**永不 merge main**

### 8.3 调研分支归档

`research/R-PROTO-LEARN-appraisal-multi-mechanism` 分支已 ship：
- Layer 1-6 (R-PROTO-LEARN.1-6)
- P5-feel 完整 (R-PROTO-LEARN.7-10)
- P5 17 owner × 54 policy 100% ship (Tier 1-4)
- P5-A 负面发现 + P5-A.2 反转 ship
- P-TEMPORAL Phase 2/2c/Decision#1/#2/#3/Phase3 ship
- 图灵评估永久保存
- 真实数据汇总 + 多 scenario LLM I/O capture + 链路分析
- **学术调研 ship**（本次新增 research-self-cognition-survey 三件套）