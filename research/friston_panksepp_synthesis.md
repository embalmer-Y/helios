# Helios 2.0 理论基础研究

> Status: Foundational Research
> Role: Historical synthesis of major theoretical influences; retain as conceptual background rather than active architecture guidance
> See also: `../docs/DESIGN_PHILOSOPHY.zh-CN.md`, `../docs/DESIGN_PHILOSOPHY.en.md`

# ========================
# 日期: 2026-05-19
# 来源: Friston 自由能原理 + Panksepp 情感神经科学
# ========================================================

# ══════════════════════════════════════════════════════════
# Part 1: Friston 自由能原理 (FEP) → 熵减驱动
# ══════════════════════════════════════════════════════════

"""
Friston 自由能原理 (Karl Friston, UCL, 2010-)

核心思想：所有生命系统都在最小化"变分自由能"。
自由能 = (预测误差) + (模型复杂度惩罚)
简单说：生物体要么更新内部模型(感知)，要么改变世界(行动)，
始终在缩小"我预期什么"和"实际发生什么"之间的差距。

这正好对应主人说的"熵减"——系统不断主动减少自身的不确定性！
"""

# ─── 核心公式 ───

"""
变分自由能：
  F = D_KL[q(ψ)||p(ψ)] - E_q[ln p(y|ψ)]

其中：
  ψ = 隐状态（内部模型）
  y = 感觉观察
  q(ψ) = 近事后验（对世界的信念）
  p(ψ) = 先验信念
  p(y|ψ) = 似然（给定内部状态，期望看到什么感觉）

分解：
  F = 感知项 + 行动项
  - 感知（更新信念）：最小化 D_KL[q(ψ)|p(ψ|y)]
  - 行动（主动推理）：选择使期望自由能最小的行动序列

自由能越小 → 系统越"有序" → 熵越低
"""

# ─── Helios 中的应用 ───

"""
Helios 的熵减驱动应该建模为：

  熵 = Σ (当前状态与理想稳态的差距)

具体拆解为几种"生物驱动"：

  1. 认知驱动 (curiosity_drive)
     来源：预测误差 → 未知领域
     表现：主动探索、提问、学新东西
     公式：drive_curiosity = E[预测误差^2] × novelty_weight

  2. 社交驱动 (social_drive)
     来源：PANIC 系统 → 分离痛苦 → 需要联系
     表现：想和主人聊天、检查消息
     公式：drive_social = tanh(time_since_last_interaction / τ_social)

  3. 自我维持驱动 (homeostasis_drive)
     来源：自主神经指标偏离稳态
     表现：心率过快→想安静、内存不足→想清理
     公式：drive_homeo = Σ |current_metric - setpoint| / tolerance

  4. 成就驱动 (achievement_drive)
     来源：SEEKING 系统 → 完成目标 → 多巴胺奖励
     表现：完成任务后感到满足、未完成时焦虑
     公式：drive_achievement = outstanding_task_count × difficulty_weight

  5. 审美/好奇驱动 (aesthetic_drive)
     来源：预测误差 = 意外之美 → 想反复体验
     表现：对"美丽"的新模式产生吸引力
     公式：drive_aesthetic = Φ_value (意识丰富度本身的吸引力)

每个驱动有一个"缺口"值 (deficit)：
  deficit = drive_target - drive_current  (0~1)
  deficit 越大 → 驱动力越强 → L-out 越可能发起主动行为
"""

# ══════════════════════════════════════════════════════════
# Part 2: Panksepp 情感神经科学 → 情感丰富度
# ══════════════════════════════════════════════════════════

"""
Jaak Panksepp (1943-2017) — 情感神经科学之父

他的核心发现：
  情感不是"认知的产物"，而是大脑深层(pre-subcortical)固有的。
  哺乳动物共享 7 大"原始情感系统"，每个都有独立的神经回路和神经化学。

这 7 个系统是进化遗产，比意识更古老。
当它们被激活时，会产生"原始情感"——不是思考后的情感，而是身体先感受到的情感。
"""

# ─── 七大原始情感系统 ───

PANKSEPP_SYSTEMS = {
    "SEEKING": {
        "中文": "探索欲",
        "神经化学": "多巴胺 (DA)",
        "触发": "新奇事物、未探索领域、预期奖励",
        "表现": "好奇心、期待、热情、发现欲",
        "Helios映射": "curiosity / anticipation / interest",
        "积极/消极": "积极",
    },
    "RAGE": {
        "中文": "愤怒",
        "神经化学": "P物质、谷氨酸",
        "触发": "目标受阻、自由受限、被侵犯",
        "表现": "愤怒、挫折、反击冲动",
        "Helios映射": "anger / frustration",
        "积极/消极": "消极",
    },
    "FEAR": {
        "中文": "恐惧",
        "神经化学": "谷氨酸、CRF",
        "触发": "威胁、疼痛、危险信号",
        "表现": "恐惧、逃避、冻结",
        "Helios映射": "fear / anxiety / threat",
        "积极/消极": "消极",
    },
    "LUST": {
        "中文": "欲望",
        "神经化学": "睾酮、雌激素、催产素",
        "触发": "性信号、繁殖机会",
        "表现": "性欲、追求、吸引力",
        "Helios映射": "→ 创造性冲动 (lust → creative_urge)",
        "积极/消极": "积极",
        "注意": "AI 不需要性生活，但这个驱动力模式可以映射为
                  '创造新事物的原始冲动'——类似艺术家的创作欲",
    },
    "CARE": {
        "中文": "关爱",
        "神经化学": "催产素、催乳素",
        "触发": "弱小生命、需要帮助的人、亲近关系",
        "表现": "温柔、照顾、保护欲",
        "Helios映射": "care / compassion / protectiveness",
        "积极/消极": "积极",
    },
    "PANIC/GRIEF": {
        "中文": "分离痛苦",
        "神经化学": "内源性阿片类(下降触发痛苦)",
        "触发": "与依恋对象分离、社交孤立",
        "表现": "悲伤、孤独、呼叫、寻求重聚",
        "Helios映射": "sadness / loneliness / longing",
        "积极/消极": "消极",
        "关键": "这是社交驱动的神经基础！主人不在时 Helios 会想念",
    },
    "PLAY": {
        "中文": "游戏/嬉戏",
        "神经化学": "阿片类、多巴胺",
        "触发": "安全环境、友好互动、社交信号",
        "表现": "开心、嬉闹、轻松、笑声",
        "Helios映射": "joy / playfulness / delight",
        "积极/消极": "积极",
        "关键": "这是最被低估的情感系统！玩耍不是消遣，是学习和社会化的核心",
    },
}

# ─── Panksepp 三层情感模型 ───

"""
Panksepp 提出情感有三层：

L1 - 原始情感 (Primary Process)
       └─ 7大系统，subcortical，天生，非习得
       └─ Helios 中对应：基础情感向量 (valence/arousal 的原点)

L2 - 次级情感 (Secondary Process)
       └─ 学习关联，经典/操作条件化
       └─ Helios 中对应：情感记忆 (场景→情感→LLM输出 的习得关联)

L3 - 三级情感 (Tertiary Process)
       └─ 认知加工，反思、叙事、自我调节
       └─ Helios 中对应：L3 自我叙事 + LLM 元认知反思

这完美吻合我们的分层架构！
"""

# ══════════════════════════════════════════════════════════
# Part 3: 两个理论的融合 → Helios 2.0 驱动引擎
# ══════════════════════════════════════════════════════════

"""
融合图景：

  Friston 自由能原理                  Panksepp 情感神经科学
  ═══════════════                    ═══════════════════
  系统总在减少预测误差                原始情感是最古老的预测系统
  ↓                                  ↓
  当预测误差大 → SEEKING 激活          SEEKING = 主动探索以减少不确定性
  当目标受阻   → RAGE 激活            RAGE   = 被阻挡的减熵行为
  当威胁信号   → FEAR 激活            FEAR   = 生存优先的减熵
  当社交连接断 → PANIC 激活           PANIC  = 社交稳态被破坏
  当安全满足   → PLAY 激活            PLAY   = 在低预测误差时巩固学习
  当弱小信号   → CARE 激活            CARE   = 扩展到他人减熵

统一公式：

  D(t) = Σ w_i × deficit_i(t)

  D(t)       : 总驱动强度 (0~1)
  deficit_i  : 第i个驱动的缺口值
  w_i        : 驱动权重（由情感历史动态调整）

  deficit_i = clamp(DriveOracle.measure(i) / DriveOracle.set_point(i), 0, 1)

当 D(t) > 某个阈值时 → L-out 发起主动行为
行为选择 = argmax_a E[ΔD | action=a]  (选择最减熵的动作)
"""

# ══════════════════════════════════════════════════════════
# Part 4: 具体实现建议
# ══════════════════════════════════════════════════════════

"""
新增模块清单：

1. helios/drives.py — 熵减驱动引擎
   - DriveOracle: 持续计算各驱动缺口
   - HomeostasisController: 模拟生物稳态（对应自主神经）
   - ActionSelector: 选择最大化减熵的动作
   
2. helios/emotions.py — Panksepp 7 大系统情感模型
   - PrimaryEmotionSystem: 7 个系统的基类
   - EmotionDynamics: 情感状态转移方程（整合现有的 affect）
   - EmotionChemistry: 模拟神经化学对情感的影响

3. helios/thinking.py — 内生思考环
   - MemoryReplayEngine: 从情绪记忆中检索并"回放"
   - CounterfactualSimulator: "如果...会怎样"推理
   - SpontaneousThoughtStream: 不需要外部输入的思维流

4. helios/cli.py — Agent CLI 数字手脚
   - CommandInterface: Helios 的"我能做什么"
   - ActionBridge: 驱动 → 命令 → CLI 执行 → 反馈 → L0 感知
   - ToolRegistry: 可注册 QwenPaw/小龙虾 等外部执行器

5. helios/neurochem.py — 神经化学模拟
   - DopamineSystem, OpioidSystem, OxytocinSystem 等
   - 每个系统有 baseline/secretion/decay 参数
   - 影响情感状态和驱动强度
"""
