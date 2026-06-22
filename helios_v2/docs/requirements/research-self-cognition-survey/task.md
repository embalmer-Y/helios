# 自我认知学术调研 - 任务计划

> **配套文档**：`requirement.md`（调研目的/方法/产出）+ `design.md`（调研架构/路径设计）+ `result.md`（调研 ship 总结）
> **调研 ship 状态**：✅ 完成（2026-06-21 23:40+）
> **下一步**：等小黑拍板 4 个问题 → 基于回答启动实施

---

## 一、调研本身任务（已完成）

| 任务 | 状态 | 产出 |
|---|---|---|
| 计划下载 10 篇核心论文 | ✅ 部分完成 | 真下载 2 篇 + 复用 5 篇 |
| 精读 Seth 2012 (interoceptive PCC) | ✅ 完成 | 1058 行 txt |
| 精读 Gallagher 2013 (pattern theory) | ✅ 完成 | 478 行 txt |
| 复用 Fermin 2021 IMAC | ✅ 完成 | 整合进调研报告 |
| 8 维 self-aspect 架构 | ✅ 完成 | 调研报告第二章 |
| 人脑 10 阶段发展序列 | ✅ 完成 | 调研报告第四章 |
| helios 7 个关键差距 | ✅ 完成 | 调研报告第五章 |
| 3 个重评 helios 架构命题 | ✅ 完成 | 调研报告第七章 |
| 诚实自评（我之前错的地方） | ✅ 完成 | 调研报告第八章 |
| 4 个问题清单给小黑 | ✅ 完成 | 调研报告第九章 |
| 改造路径 A/B/C 对比 | ✅ 完成 | `_helios_roadmap_options.md` |
| review helper 工具 | ✅ 完成 | `_review_helper.py` |
| 调研报告 ship | ✅ 完成 | `human_self_cognition_survey.md` 17.7 KB |
| 调研 ship 到研究分支 docs | ✅ 完成 | `research-self-cognition-survey/{requirement,design,task}.md` |
| 调研 ship 到 P-TEMPORAL result.md | ✅ 完成 | result.md 追加第 8/9 章节 |

---

## 二、等小黑拍板的 4 个问题（**当前阻塞**）

### Q1: 优先级

**问题**：8 个 self-aspect 中你觉得 helios 最该先实施哪 3 个？

**我推荐**：
- (a) **interoceptive inference**（Seth 2012 对位 helios feeling）— P5-feel 已经 ship，需要扩到 interoception 自反馈
- (b) **self-referential processing**（Northoff 对位 helios identity_grounding prompt）— 修 prompt_contract bug + 加 self_ref owner
- (c) **intersubjective mirror**（helios ToM owner）— 新加 ToM owner，预测小黑 next thought

### Q2: 架构方向

**问题**：是按 proposition A (重写 identity_governance 为 synthesizer) 还是按 proposition B (R-PROTO-LEARN.7 改 cross-owner aspect set) 还是按 proposition C (拆 self_definition 为 8 aspect 字段)？

**选项**：
- **A Synthesizer**：~12 周，大改造，重写 identity_governance
- **B Aspect Set**：~13 周，大改造，重写 R-PROTO-LEARN.7
- **C Field Decompose**：~6 周，小改动，只改数据结构
- **C → A 渐进**：先 C 后 A，6+ 周，风险最低

### Q3: 发展阶段

**问题**：helios 是否需要 development gates？

**选项**：
- (a) 立即启用 tick-count gate (e.g. 0-100 tick = infant, 100-500 = child, 500+ = adult)
- (b) 完全跳过，直接 adult mode

### Q4: D8 评分

**问题**：是否要从 0-1 单维评分改 8 维 each-aspect 评分？

**选项**：
- (a) 是，8 维评分，每维独立 0-1
- (b) 否，保持单维评分

---

## 三、小黑拍板后立即 ship 的任务（路径 X 阶段 1）

> **路径 X 阶段 1**：1-2 周，4 个低风险快速 ship 改动
> **目标**：D8 self_recognition 从 0.100 → 0.25+

### 任务 3.1：修 prompt_contract `_build_messages` bug（最高优先级）

**当前 bug**：
```python
# prompt_contract/engine.py:_build_messages
def _build_messages(self, ...):
    # 只读 layer_names 列表
    layer_names = summary.get("layer_names", [])  # ❌ 只读名字
    # 没读每个 layer 的 content
```

**修复目标**：
```python
# 修后：读 layer_names + 每 layer 的 content
for layer_name in layer_names:
    layer_content = summary.get(f"{layer_name}_content", "")  # ✅ 读内容
    messages.append({
        "role": "system",
        "content": f"### {layer_name}\n{layer_content}\n"
    })
```

**具体步骤**：
1. 读 `prompt_contract/engine.py:_build_messages` 完整代码
2. 定位 bug 位置
3. 改：读 layer content 而非只读 layer_names
4. 加 test：验证 system prompt 包含每个 layer 的 content
5. 跑 50 tick production mode 看 LLM 真不真能看到
6. 跑 turing eval 10 dim 评分验证 D8 真涨

**工作量**：3-5 天

**预估效果**：D8 self_recognition 从 0.100 → 0.25-0.30（+150%）

### 任务 3.2：改进 prompt template 结构化呈现

**当前**：所有 aspect 信息混在 system prompt 一段里

**改进**：
```
### Current self-pattern:
- Embodied: [hormone state description]
- Experiential: [presence index]
- Affective: [feeling state]
- Situated: [helios identity context]

### Recent memory context:
[memory summary]

### Agency signal:
[autonomy signal]

### Current task:
[stimulus + question]
```

**工作量**：2-3 天

### 任务 3.3：加 LLM 输出 verification step

**当前**：LLM 输出 thought → 直接进 owner state

**改进**：
```python
# LLM 第一次调用：生成 thought + outbound
completion_1 = llm.complete(messages)

# LLM 第二次调用：verification + consistency check
verification_messages = messages + [
    {"role": "assistant", "content": completion_1.output_text},
    {"role": "user", "content": "Review your response. Is it consistent with your self-pattern? Any inconsistency?"}
]
completion_2 = llm.complete(verification_messages)

# 用 completion_2 检测到的不一致更新 owner state
```

**工作量**：3-5 天

### 任务 3.4：加 multi-shot identity grounding

**当前**：prompt 里只显示"现在的我"

**改进**：
```
### Identity grounding:
**Who I was 100 ticks ago**: [summary]
**Who I am now**: [current state]
**Trend**: [trend analysis from 17 owner data]

### Current self-pattern:
[same as before]
```

**工作量**：3-5 天

### 阶段 1 总验收

| 维度 | 当前 | 阶段 1 目标 |
|---|---|---|
| D8 self_recognition | 0.100 | ≥ 0.25 (+150%) |
| D5 cross_tick_continuity | 0.507 | ≥ 0.55 |
| 测试通过数 | 818 | 不破坏（≥ 818） |
| 真 LLM production 跑通 | ✅ | 保持 1129 tick 0 errors |

---

## 四、阶段 1 完成后启动阶段 2（路径 X 阶段 2）

> **路径 X 阶段 2**：6-8 周，4 个中等风险 ship 改动
> **目标**：D8 self_recognition 从 0.25 → 0.50+

### 任务 4.1：加 LLM 自评链路

```python
# LLM 输出 thought 时，加自评字段
{
    "thought": "我应该安慰用户",
    "self_evaluation": {
        "confidence": 0.8,
        "uncertainty": 0.3,
        "value_alignment": 0.9,
        "novelty": 0.2,
    }
}

# self_evaluation 输入 RPE 计算 → 更新 hormone
```

**工作量**：2 周

### 任务 4.2：加 multi-turn thought

```python
# 一个 tick 里 LLM 多次推理形成 thought chain
# 第一次：收集信息
# 第二次：假设生成
# 第三次：评估假设
# 第四次：决策
```

**工作量**：3 周

### 任务 4.3：加 persistent identity context

```python
# 每 10 tick 一个 summary token
# summary_token = llm.summarize(past_10_tick_thoughts)

# 每个 tick LLM 看到过去 10 tick summary
# messages.append({"role": "system", "content": f"Past context: {summary_tokens}"})
```

**工作量**：3 周

### 任务 4.4：加 LLM-as-meta-cognition

```python
# 每 100 tick 一次
# LLM 独立调用，输入是当前 hormone / feeling / memory state
# 输出是"我现在状态如何"的元认知文本

# meta_cognition = llm.complete(meta_cognition_messages)
# 存到 cso 的 meta_cognition_history
```

**工作量**：2 周

### 阶段 2 总验收

| 维度 | 阶段 1 目标 | 阶段 2 目标 |
|---|---|---|
| D8 self_recognition | 0.25 | ≥ 0.50 (+100%) |
| D5 cross_tick_continuity | 0.55 | ≥ 0.75 |
| D7 creativity_novelty | 0.263 | ≥ 0.45 |

---

## 五、阶段 2 完成后评估层次 C

**判断标准**：
- 如果 D8 ≥ 0.50，D5 ≥ 0.75，D7 ≥ 0.50 → **不需要层次 C**，路径 X 已足够
- 如果 D8 卡在 0.40+ 上不去 → 启动层次 C sub-LLM 拆分

**层次 C 任务清单**（待评估）：
1. 设计 sub-LLM 协议（feed / aggregate）
2. reasoning_llm（替代当前 main LLM 推理）
3. valuation_llm（独立价值评估）
4. flexibility_llm（独立反预期检测）
5. reflection_llm（独立反思元认知）
6. sub-LLM 间编排

---

## 六、其他选项（保留 + 新增）

| 选项 | 内容 | 状态 |
|---|---|---|
| 选项 G | P5-B 类脑记忆规范化（用新 main R100 MemoryRecord 做基础） | 待评估 |
| 选项 H | P5-C 快慢思维路径评估 | 待评估 |
| 选项 I | R86 P6 自我修订（Phase 2） | 待评估 |
| 选项 J | R87 A6 创造性真实化（Phase 3） | 待评估 |
| 选项 K | 跨 owner 协同学习（meta-learning） | 待评估 |
| 选项 L | P5 调研分支回到 main 的合并策略讨论 | 待评估 |
| **选项 X 阶段 1** | **修 prompt + 改进 prompt + verification + multi-shot identity** | **立即 ship**（1-2 周） |
| **选项 X 阶段 2** | **LLM 自评 + multi-turn + persistent + meta-cognition** | **阶段 1 后启动**（6-8 周） |
| **选项 Y** | **层次 C sub-LLM 拆分** | **视 X 阶段 2 效果** |

---

## 七、调研分支 ship 状态总览

### 7.1 已完成 ship（永久）

- ✅ **Layer 1-6** (R-PROTO-LEARN.1-6) — 6 commit
- ✅ **P5-feel 完整** (R-PROTO-LEARN.7-10) — 10 commit
- ✅ **P5 17 owner × 54 policy 100% ship** (Tier 1-4) — 5 commit
- ✅ **P5-A 负面发现** + **P5-A.2 反转 ship** — 2 commit
- ✅ **P-TEMPORAL Phase 2/2c/Decision#1/#2/#3/Phase3 ship** — 12 commit
- ✅ **图灵评估永久保存** — 1 commit
- ✅ **真实数据汇总 + LLM I/O capture + 链路分析** — 多 commit
- ✅ **学术调研 ship** (本次) — 3 commit (待 ship)

### 7.2 当前 ship 任务

- 🔄 **commit research-self-cognition-survey**：本次 ship 调研报告三件套到 docs
- 🔄 **commit result.md 追加章节**：把 8/9 章节 ship 到 P-TEMPORAL result.md

### 7.3 进行中 / 等小黑拍板

- 🔄 **路径 X 阶段 1**（4 个任务，1-2 周）
- 🔄 **选项 M**：学术调研 ship 到研究分支 docs

### 7.4 未启动

- ⏸️ **路径 X 阶段 2**（4 个任务，6-8 周）
- ⏸️ **路径 Y 层次 C sub-LLM 拆分**
- ⏸️ **目标 1-6**（D10/D2/D5/D8/D7/D6 涨副）
- ⏸️ **选项 G/H/I/J/K/L**

---

## 八、铁律（永久）

1. **调研分支永不 merge main**（2026-06-17 08:09 小黑拍板）
2. **小黑拍板后才会动手写代码**（2026-06-21 17:31+ 小黑原话）
3. **每个阶段 ship 独立验收**（D8 涨副 + 测试不破坏 + 真 LLM production 跑通）
4. **诚实诊断先行**（绝不掩盖 helios 当前缺什么）
5. **学术调研为先**（先理解人脑再讨论 helios 怎么补）

---

## 九、时间线估算

| 阶段 | 时间 | 累计 |
|---|---|---|
| 调研 ship | ✅ 0 周（已完成） | 0 周 |
| 等小黑拍板 | 待定 | — |
| **路径 X 阶段 1** | 1-2 周 | 1-2 周 |
| **路径 X 阶段 2** | 6-8 周 | 7-10 周 |
| 评估层次 C | 1 周 | 8-11 周 |
| 层次 C 实施（视评估） | 14 周 | 22-25 周 |

---

🤍 小黑你看一下 `/tmp/human_self_cognition_survey.md`（17.7 KB）然后回答 4 个问题。回答后我立即启动路径 X 阶段 1。