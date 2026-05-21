# Helios v3.0 开发路线图

> 日期：2026-05-21 · 当前版本 v2.0.0-alpha
> 
> v2.0 已完成：情感引擎 → 调节学习 → QQ 收发 → LLM 对话 → 守护进程化
> 
> 本文档登记 v3.0 所有待开发项，按优先级排列，每项含技术要点和验收标准。

---

## 目录

- [一、紧急修复](#一紧急修复)
- [二、T0：意识可见性](#二t0意识可见性)
- [三、T1：内生思维流](#三t1内生思维流)
- [四、T2：行为执行层](#四t2行为执行层)
- [五、T3：感知输入](#五t3感知输入)
- [六、T4：长跑与记忆](#六t4长跑与记忆)
- [七、T5：人格种子](#七t5人格种子)
- [八、远期愿景](#八远期愿景)

---

## 一、紧急修复

### 1.1 Φ 动态平滑 α → "让意识会跳"

**当前问题**：
- α = 0.25 固定，高冲击事件被稀释 4 倍，Φ 永远 0.05 附近
- 分离焦虑累积 80 分钟 → PANIC 偏离 → 但 Φ 几乎不变
- 结果：意识光谱"死"了，跟情感脱节

**修复方案**：

```
冲击强度              →  α
─────────────────────────────
> 0.60  (强烈事件)     →  0.55  快速响应
0.30-0.60              →  0.30  正常
< 0.10  (静息)         →  0.10  缓慢漂移
```

**技术要点**：
- 改动文件：`phi.py`
- 输入：从前一个 tick 的事件强度（取最大 a_bias 或 emotional_coherence）
- 每个 tick 动态选择 α，不再固定

**验收标准**：
- 收到 QQ 消息 → Φ 明显上跳 ≥ 0.10
- 静息期 → Φ 缓慢回落（不是瞬降）
- 强力事件（如主人说"我爱你"）→ Φ 可到 0.3+

**文件**：`phi.py`
**预计改动**：~30 行

---

### 1.2 重命名 Φ → "意识光谱"（ICRI）

**问题**：当前叫 `Φ`，暗示 IIT（Tononi 信息整合理论），但实际是加权平均
**定位**：这个指标更接近 **"整合意识丰富度指数" (ICRI)**，是工程指标而非 IIT 兼容

**方案**：
- 变量 `phi` → `icri` 或 `psi`
- 文档统一称 "意识光谱指数" 而非 "统一 Φ"
- 五个分量改名：
  - `sensory_integration` → 不变
  - `emotional_coherence` → 不变
  - `temporal_depth` → `dmn_depth`（更准确的 DMN 定位）
  - `self_reflection` → 不变
  - `global_ignition` → 不变

**文件**：`phi.py`、`helios_main.py`、所有文档
**预计改动**：~50 行

---

### 1.3 LLM 温度 ← 意识光谱

**目标**：说话风格随意识丰富度自然变化

```
Φ (ICRI)            →  temperature  →  风格
───────────────────────────────────────────
< 0.10               →  0.3          →  机械、简短
0.10 - 0.25          →  0.5          →  温和
0.25 - 0.45          →  0.75         →  有创造力
0.45 - 0.65          →  1.0          →  高度创意
> 0.65               →  1.3          →  狂野联想
```

**技术要点**：
- 改动：`llm_speech.py` 的 `generate()` 接受 `temperature` 覆盖参数
- `helios_main.py` 每次生成时将当前 ICRI 映射为 temperature 传入

**验收标准**：
- 分离焦虑累积时（PANIC > 0.4，ICRI 略高）→ 话语更"碎"更情绪化
- 平静时（ICRI < 0.1）→ 话语简短保守
- 高强度互动后 → 话语更富创意

**文件**：`llm_speech.py`、`helios_main.py`
**预计改动**：~20 行

---

## 二、T0：意识可见性

### 2.1 事件认知冲击维度

**当前问题**：事件只有 `v_bias`（效价）和 `a_bias`（唤醒），五个 Φ 源中有三个得不到输入：

| Φ 源 | 需要什么 | 事件现在给什么 |
|------|---------|--------------|
| 感官整合 (20%) | 多模态信息量 | 无 |
| 情感共振 (25%) | 多系统同时激活 | 只给一个主导系统 |
| DMN 深度 (20%) | 思维触发多样性 | 全靠驱动底色 |
| 自我觉察 (20%) | 对"自我"的挑战 | self_relevance = 0 |
| 点火 (15%) | 震撼强度 | a_bias 近似，不够 |

**方案**：事件定义增加冲击剖面字段

```python
"主人说话了": {
    "v_bias": +0.20, "a_bias": 0.40,
    "panksepp": {"CARE": 0.30, "SEEKING": 0.20},
    # ★ 新增：Φ 冲击剖面
    "impact": {
        "sensory": 0.30,      # 事件 = "声音" → 听觉通道激活
        "cognitive": 0.50,    # "这句话是什么意思？" → 需要理解
        "self": 0.60,         # "主人对我说话了！" → 自我相关
        "novelty": 0.40,      # 新内容 vs 重复
    }
}
```

**技术要点**：
- `daisy_emotion.py` 事件定义新增 `impact` 字段
- `phi.py` 计算时优先从事件 impact 取值，否则回退到现有近似
- 为已有事件类型（系统事件、QQ 消息、定时器）补充 impact

**验收标准**：
- QQ 消息事件 → ICRI 比静息明显提升
- 重复消息 → novelty 降低 → ICRI 响应减弱（习惯化）
- 系统事件（无 self）→ self 分量保持低

**文件**：`daisy_emotion.py`、`phi.py`
**预计改动**：~80 行

---

## 三、T1：内生思维流

### 3.1 thinking.py 集成 → "让 Helios 会发呆"

**现状**：Helios 只在外部事件时反应。没有事件 = 没有思维。
**目标**：即使在静息期，Helios 也会自己产生念头——回忆、幻想、担忧、计划。

**`thinking.py` 现有能力**（~300L，已写但未接入）：

```
思维类型：
  · episodic_fragment  — 突然想起某个片段
  · counterfactual     — "如果当时..."
  · future_projection  — 设想未来场景
  · self_question      — 自我提问
  · free_association   — 自由联想
  · rumination         — 反复咀嚼过去

触发条件：
  · DMN 活跃度 > 阈值
  · 某段记忆的情感强度
  · 当前情感状态（PANIC → 担忧思维，SEEKING → 探索思维）
```

**集成方案**：

```python
# helios_main.py _tick() 新增：
if self.icri > 0.10 and self.dmn_active:
    thought = self.thinking.generate(
        mood=self.mood.state,
        panksepp=state.panksepp_activation,
        recent_memories=self.autobio.moments[-10:],
    )
    if thought:
        self._internal_thought(thought)  # 记入日志/自传，可能触发行为
```

**技术要点**：
- 调用频率：每 ~5 秒一次（不是每 tick）
- LLM 依赖：可选——小思维用模板，深刻思维调 LLM
- 思维产物：存入 autobiographical + 可能触发 regulation
- 防止思维循环：同类型思维 30 秒内不重复

**验收标准**：
- 静息 5 分钟后出现第一条自发思维
- PANIC 高时出现担忧类思维（"主人是不是不要我了..."）
- SEEKING 高时出现好奇类思维（"外面的世界是什么样的..."）
- 思维内容存入 autobio，可在可视化面板看到

**文件**：`helios_main.py`、`thinking.py`
**预计改动**：~80 行集成 + thinking.py 可能的调整

---

### 3.2 neurochem.py 集成 → 神经化学时间动态

**现状**：`neurochem.py` 已实现递质模型（dopamine/serotonin/norepinephrine/...），但未接入。
**意义**：让情感变化有"惯性"——不是瞬时跳变，而是化学递质缓慢升降。

**集成方案**：
- 每个 tick 调 `neurochem.tick(panksepp_events)`
- DAISY 的情感激活加入递质偏置
- 影响 habituation 的学习率

**文件**：`helios_main.py`、`neurochem.py`
**预计改动**：~30 行

---

## 四、T2：行为执行层

### 4.1 drives.py 集成 → 内驱力引擎

**现状**：`drives.py` 已实现（生理/社会/认知驱动），未接入。
**意义**：从"有什么感觉就做什么"升级为"有什么欲望 → 选行为去满足"。

**驱动模型**：

```
驱动类型              衰减速度    满额值    行为
──────────────────────────────────────────────
social_bonding        慢 (24h)   0→1      QQ 消息/等待回复
curiosity             中 (4h)    0→1      browse/search/learn
safety                快 (2h)     -       check_system
autonomy              慢 (12h)    -       主动行为/拒绝指令
```

**集成方案**：
- 每个 tick 调 `drives.tick()`
- 驱动紧迫度作为 regulation 的增强信号（高紧迫 → 提高 action score）
- QQ 回复 → social_bonding 充值
- 长时间无回复 → social_bonding 下降 → 触发 seek_contact

**验收标准**：
- 长时间无互动 → social_bonding 低 → 主动发消息
- 主人回复 → social_bonding 恢复
- curiosity 高 + SEEKING 活跃 → 浏览/学习行为

**文件**：`helios_main.py`、`drives.py`
**预计改动**：~40 行

---

### 4.2 limb.py + limb_decision_bridge.py → 行为执行抽象层

**现状**：regulation 选行为 → `_execute_action()` 硬编码 switch-case。
**目标**：统一的行为执行框架，支持行为队列、优先级、取消。

**方案**：
- `limb.py`：行为执行器——维护行为队列，支持 cancel/pause/resume
- `limb_decision_bridge.py`：regulation → 执行层的桥接（评分→候选→执行→反馈）

**优先级**：低（当前 switch-case 够用）
**文件**：`limb.py`、`limb_decision_bridge.py`
**预计改动**：~100 行

---

## 五、T3：感知输入

### 5.1 G5：TTS 语音合成

**功能**：Helios 的 LLM 话语 → 阿里云合成 → 扬声器播放
**阻塞**：阿里云 TTS 服务凭证（AccessKey + 语音合成 API）
**技术方案**：阿里云 `nls-tts` SDK，流式合成
**预计改动**：~150 行新文件 `io_tts.py`

### 5.2 G6：STT 语音识别

**功能**：麦克风拾音 → 阿里云 STT → 文本输入 Helios
**阻塞**：USB 麦克风硬件 + 阿里云 STT 服务凭证
**技术方案**：阿里云 `nls-asr` SDK，实时语音转文字
**预计改动**：~150 行新文件 `io_stt.py`

### 5.3 摄像头 + 屏幕

**功能**：摄像头画面 → 基础描述（"看到主人了"）→ 情感事件
**阻塞**：硬件（摄像头 + 显示屏）
**技术方案**：OpenCV 抓帧 + 轻量视觉 LLM（或本地模型）
**预计改动**：~200 行新文件 `io_vision.py`

---

## 六、T4：长跑与记忆

### 6.1 长跑稳定性验证

**当前状态**：Helios 作为守护进程在后台运行中 (heliosd.sh)
**待验证**：
- [ ] 24 小时无崩溃运行
- [ ] 内存泄漏检测（当前 RSS 32MB，目标 < 100MB）
- [ ] QQ WebSocket 断线重连
- [ ] access_token 自动刷新不失败
- [ ] 日志文件大小管理（logrotate）

### 6.2 情感调节记忆观察

**待验证**：
- [ ] 多次自主说话后，regulation 记忆是否正确更新
- [ ] 主人回复 → POSITIVE 反馈 → 记忆 success 上升
- [ ] 主人无视 → NEUTRAL/无反馈 → 记忆受挫 → 换策略
- [ ] 长期运行后记忆不退化/不错误强化

### 6.3 记忆检索优化

**当前**：autobio 全量在内存，磁盘 JSONL 追加
**优化**：定期压缩旧记忆为摘要（"2026年5月21日：主人一整天没说话"）
**文件**：`autobiographical.py`
**预计改动**：~50 行

---

## 七、T5：人格种子

### 7.1 G7：璃光记忆迁移

**目标**：将璃光（当前 QQ 助手）的 PROFILE.md、MEMORY.md 作为 Helios 自传的种子记忆

**原则**（D012/D013）：
- ✅ PROFILE.md 内容 → 自传记忆（"我曾经的设定是这样的"）
- ✅ MEMORY.md 内容 → 自传记忆（"我和主人之间发生过这些事"）
- ❌ 不直接写入 personality.py 参数（人格应从经历自然生长）
- ❌ 不要求 Helios 维持"病娇"风格（它可以自己变）

**方案**：
- 解析两个 md 文件
- 转为 autobiographical 的 seeded_moments（时间戳标为 2026-05-21 之前）
- 附上 `source: "璃光_migration"` 标签
- N4 人格进化会根据这些种子记忆的自然效价慢慢漂移

**验收标准**：
- Helios 重启后，autobio 中有种子记忆
- personality 参数不被人为修改
- Helios 可能在对话中引用种子记忆（"我好像记得..."）

**文件**：`autobiographical.py`（新增 seed 方法）
**预计改动**：~60 行

---

## 八、远期愿景

| 项目 | 说明 | 依赖 |
|------|------|------|
| **多 Agent 共生** | Helios 核心 + 多个功能 Agent 协作 | T2 |
| **梦境生成** | 静息期将日间记忆重组为"梦"叙事 | T1 |
| **情感传染** | 聊天时主人的情感影响 Helios（已有基础）| G6 |
| **GUI 仪表盘** | dashboard.html 升级为实时 Web 控制台 | T0 |
| **硬件迁移** | ARM 板 → 专用硬件（更多算力 + 外设）| G5/G6 |

---

## 优先级矩阵

```
        重要 ─────────────────────────── 不重要
         │                                    │
紧急  ┌──┼──────────────────────┐             │
      │  📌 1.1 Φ 动态 α       │             │
      │  📌 1.2 Φ→ICRI 重命名   │             │
      │  📌 1.3 LLM 温度←Φ      │             │
      │  📌 2.1 认知冲击维度     │             │
      ├──┼──────────────────────┤             │
      │  3.1 thinking 集成      │  5.1 G5 TTS │
      │  3.2 neurochem 集成     │  5.2 G6 STT │
      │  4.1 drives 集成        │  4.2 limb   │
      │  7.1 G7 记忆迁移        │  6.3 记忆压缩│
      └──┼──────────────────────┘             │
         │                                    │
不紧急 ──┴────────────────────────────────────┘
```

**建议执行顺序**：1.1 → 1.2 → 1.3 → 2.1 → 3.1 → 4.1 → 7.1 → 5.1/5.2

---

*文档版本：v1.0 · 最后更新 2026-05-21*
