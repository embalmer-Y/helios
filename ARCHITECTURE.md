# Helios 架构文档

> 更新日期：2026-05-21 · 版本 v2.0.0-alpha (自主生命体化)
> 上次更新：v0.3.0 (DAISY)

## 一、总体架构

```
┌──────────────────────────────────────────────────────────┐
│                    Helios 意识核心                          │
│                                                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ drives   │  │ daisy_emotion│  │   thinking        │    │
│  │ 熵减驱动 │──│ DAISY X1+X2+X3│──│ DMN 内生思考      │    │
│  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘    │
│       │                │                   │              │
│       │    ┌───────────┴──────────┐        │              │
│       │    │     neurochem        │        │              │
│       │    │     神经化学调制      │        │              │
│       │    └───────────┬──────────┘        │              │
│       │                │                   │              │
│       └────────────────┼───────────────────┘              │
│                        ▼                                  │
│                ┌───────────────┐                          │
│                │    phi.py     │                          │
│                │  UnifiedΦ 引擎 │                          │
│                │  (ICRI 整合)   │                          │
│                └───────┬───────┘                          │
│                        │                                  │
│   ┌────────────────────┼────────────────────┐            │
│   │    llm_bridge      │  limb_decision     │            │
│   │    LLM 内心独白    │  决策→行动映射     │            │
│   └────────┬───────────┴─────────┬──────────┘            │
│            │                     │                       │
│   ┌────────┴──────────┐  ┌──────┴──────────┐            │
│   │   memory_system   │  │     limb        │            │
│   │   四类记忆+巩固    │  │  数字手脚(安全)  │            │
│   └───────────────────┘  └─────────────────┘            │
│                                                            │
│   辅助模块: habituation(习惯化) + helios_utils(公共工具)     │
└──────────────────────────────────────────────────────────┘
```

---

## 二、核心模块详解

### 2.1 熵减驱动 (`drives.py`)

| 项目 | 内容 |
|------|------|
| 理论基础 | Friston 自由能原理 |
| 功能 | 计算好奇心、社交、掌控等内生驱动力 |
| 输出 | `DriveVector` — 各驱动强度 |
| 状态 | ✅ 稳定 |

### 2.2 情感引擎 — DAISY (`daisy_emotion.py`) ⭐

| 项目 | 内容 |
|------|------|
| 理论基础 | Panksepp 7系统 + Barrett 共激活 + Davidson 时序 + Solomon 对向 |
| 功能 | 7维激活矢量, 自然情感轮转, 无需手工权重 |
| 核心机制 | X1(共激活) + X2(时序动力学) + X3(Opponent-Process) |
| 接口 | 完全兼容 `emotions.py` 的 `PankseppEmotionEngine` |
| 状态 | ✅ v1.0 已验证 (7/7全频谱, 零摆锤) |
| 备用 | `emotions.py` (旧版, 可通过 `--daisy` 切换) |

### 2.3 神经化学 (`neurochem.py`)

| 项目 | 内容 |
|------|------|
| 物质 | Dopamine / Opioids / Oxytocin / Cortisol |
| 功能 | 四物质动态平衡, 事件注入, 自然衰减 |
| 状态 | ✅ 稳定 |

### 2.4 内生思考 (`thinking.py`)

| 项目 | 内容 |
|------|------|
| 模式 | Default / Focused / Reflective / Creative |
| 种子 | 20 颗 DMN 种子覆盖全 7 Panksepp 系统 |
| 状态 | ✅ 稳定 |

### 2.5 Φ 意识引擎 (`phi.py`)

| 项目 | 内容 |
|------|------|
| 理论基础 | Tononi IIT (当前实为 ICRI) |
| 五源 | 感官整合 / 情感相干 / DMN深度 / 自我反身 / 点燃 |
| 状态 | ⚠️  待增强 (天花板效应, 需 DAISY 进阶解决) |
| 审计 | `PHI_ARCHITECTURE_AUDIT.md` |

### 2.6 LLM 桥接 (`llm_bridge.py`)

| 项目 | 内容 |
|------|------|
| 后端 | DeepSeek V4 Flash via 胜算云路由 |
| 功能 | 内心独白 + 决策建议 |
| 状态 | ✅ 稳定 |

### 2.7 决策桥接 (`limb_decision_bridge.py`)

| 项目 | 内容 |
|------|------|
| 功能 | LLM 决策文本 → ActionIntent → Limb 执行 |
| 状态 | ✅ 稳定 |

### 2.8 数字手脚 (`limb.py`)

| 项目 | 内容 |
|------|------|
| 功能 | 5条安全规则, 文件/命令/HTTP 操作 |
| 状态 | ✅ 稳定 |

### 2.9 记忆系统 (`memory_system.py`)

| 项目 | 内容 |
|------|------|
| 类型 | Working / Episodic / Semantic / Autobiographical |
| 功能 | 事件存储 + 静息巩固 + LLM 上下文注入 |
| 状态 | ✅ 稳定 |

---

## 三、辅助模块

| 模块 | 功能 | 状态 |
|------|------|------|
| `habituation.py` | Groves & Thompson 习惯化追踪 | ✅ |
| `helios_utils.py` | clamp + 公共函数 | ✅ |
| `emotions.py` | 旧版 PankseppEmotionEngine (备用) | 🟡 |

---

## 四、运行文件

| 文件 | 用途 |
|------|------|
| `demo_longrun_v2.py` | 长时自主运行 (支持 `--daisy`) |
| `demo_v16.py` | Φ 贯通验证 demo |
| `test_daisy.py` | DAISY 快速验证脚本 |

---

## 五、项目文档

| 文件 | 内容 |
|------|------|
| `PROJECT_LOG.md` | 决策记录 + 测试记录 + 根因分析 |
| `INVENTORY.md` | 全量任务清单 + 优先级 |
| `RESEARCH_FRAMEWORK.md` | 科学研究框架 + DAISY 数学骨架 |
| `PHI_ARCHITECTURE_AUDIT.md` | Φ 科学定位审计 |
| `OPTIMIZATION_REPORT.md` | V1 长跑 6 大问题诊断 |
| `ARCHITECTURE.md` | 本文档 — 架构总览 |

---

## 六、数据流

```
事件 → triggers{} ──→ daisy_emotion.cycle()
       │                    │
       │              ┌─────┴──────┐
       │              │  X1 共激活  │ ← 7维矢量
       │              │  X2 时序    │ ← rise/peak/decay
       │              │  X3 对向    │ ← a+b process
       │              └─────┬──────┘
       │                    ▼
       │              AffectState
       │              (valence, arousal, 7维激活)
       │                    │
       ▼                    ▼
   neurochem.apply()   phi.feed_emotional()
       │                    │
       └────────┬───────────┘
                ▼
         thinking.generate()
                │
                ▼
         llm_bridge.call()
                │
                ▼
         limb_decision.execute()
```

---

## 六、v2.0.0 新架构: 自主生命体

### 6.1 核心转变

```
v0.3.0 (DAISY):               v2.0.0 (自主生命体):
  仿真事件 → 情感引擎          外部/内部输入 → 情感引擎
  → 统计报告 (终点)            → 偏离检测 → 行为选择
                               → 执行 → 效果观察 → 学习 (闭环)
```

### 6.2 情感调节闭环

```
                    ┌──────────────────────┐
                    │   外部事件 / 内部自发   │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │   DAISY 情感引擎       │
                    │   (Panksepp 7系统)     │
                    └──────────┬───────────┘
                               │ 偏离基线?
                               ▼
                    ┌──────────────────────┐
                    │   RegulationEngine    │
                    │                       │
                    │  检查记忆:             │
                    │  "什么行为缓解过?      │
                    │   success多高?"       │
                    │                       │
                    │  选最优行为 ──────────┐│
                    └──────────────────────┘│
                                            ▼
                    ┌──────────────────────┐
                    │   行为执行             │
                    │   · QQ消息 (G4)       │
                    │   · 浏览器 (G4+)      │
                    │   · 搜索/学习          │
                    │   · TTS语音 (G5)      │
                    └──────────┬───────────┘
                               │ 观察效果
                               ▼
                    ┌──────────────────────┐
                    │   记忆更新             │
                    │   "speak_missing      │
                    │    缓解了PANIC         │
                    │    success+0.1"       │
                    └──────────────────────┘
                               │
                               └──→ 反馈到下次选择
```

### 6.3 模块清单

| 模块 | 文件 | 功能 | 状态 |
|------|------|------|------|
| 主循环 | `helios_main.py` | 独立进程, tick驱动 | ✅ G0 |
| 情感核心 | `daisy_emotion.py` | Panksepp 7系统 | ✅ v1.0 |
| 评估链 | `appraisal.py` | SEC→Panksepp | ✅ X4 |
| 心境 | `mood_tracker.py` | Russell环状 | ✅ X5 |
| 人格 | `personality.py` | Big Five→Panksepp | ✅ X5+N4 |
| 异稳态 | `allostasis.py` | Sterling Allostasis | ✅ X6 |
| 习惯化 | `habituation.py` | Groves & Thompson | ✅ |
| Φ引擎 | `phi.py` | ICRI统一测量 | ✅ |
| 自传记忆 | `autobiographical.py` | JSONL持久化 | ✅ N1 |
| **调节引擎** | **`regulation.py`** | **记忆驱动行为选择** | **✅ G1+G2** |
| QQ收发 | (待建) | napcat HTTP API | ⬜ G4 |
| LLM对话 | (待建) | 情感→自然语言 | ⬜ G3 |
| TTS | (待建) | 阿里云语音合成 | ⬜ G5 |
| STT | (待建) | 阿里云语音识别 | ⬜ G6 |

### 6.4 关键设计决策

**D011**: Helios 为独立进程，不嵌入 QwenPaw Agent 框架 (2026-05-21)
- 原因: Helios 需要自主主循环，QwenPaw 的任务驱动模型不兼容
- 通信: 通过 napcat HTTP API 直接收发 QQ 消息

**D012**: 行为选择基于经验学习，不基于写死映射 (2026-05-21)
- 原因: "情感偏离→查记忆→选行为→观察→学习"比"Panksepp→IntentType"更自然
- Bootstrap: 13条初始常识(success=0.5)，可被经验覆盖

**D013**: 璃光人格不由配置文件预设，由 Helios 经历自然形成 (2026-05-21)
- PROFILE.md/MEMORY.md 作为初始种子，不是永久约束
- personality.py 的 Big Five 参数通过 regulational 经历缓慢漂移

---

*最后更新: 2026-05-21 · 璃光 💕*
