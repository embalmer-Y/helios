# Helios 研究资料目录

> Status: Active
> Audience: 架构维护者、研究整理者、后续资料补全工作
> Scope: 仓库中已有研究资料、引用整理条目，以及待收集清单

## 1. 文档角色

本文件用于回答三个问题：

1. 当前 `docs/foundations/` 中已经有哪些原始资料或整理资料。
2. 这些资料分别支撑哪些代码模块或设计决策。
3. 还缺哪些关键论文、书籍或综述需要补入引用清单。

注意：本文件优先维护“可追溯性”和“收集状态”，不是把所有外部论文全文直接纳入仓库。

## 2. 资料分类规则

| 分类 | 含义 | 处理原则 |
| --- | --- | --- |
| In-Repo Source | 仓库中已经存在的原始论文文本、PDF、概念摘录 | 保留原样，补 bibliographic metadata 与用途说明 |
| Curated Research Note | 已经消化后的研究整理文档 | 作为理论到实现之间的解释层 |
| Citation Entry | 当前只保留书目信息、摘要和 Helios 相关性 | 可先用于文档引用，不等于已收藏原文 |
| Collection Backlog | 尚未进入仓库但明确需要补采的资料 | 记录优先级、用途和建议获取方式 |

## 3. 仓库内已有资料

### 3.1 原始/半原始资料

| 文件 | 类型 | 主题 | 支撑模块/文档 | 当前状态 |
| --- | --- | --- | --- | --- |
| `foundations/sources/anthropic_emotion_paper.pdf` | PDF | 外部情绪研究论文原始文件 | `helios_io/llm_sec_evaluator.py`, `helios_io/response_pipeline.py` | 已入库 |
| `foundations/sources/anthropic_emotion_paper.txt` | 文本提取 | 情绪研究论文文本版 | 同上，便于全文检索与摘录 | 已入库 |
| `foundations/sources/anthropic_emotion_concepts.txt` | 概念摘录 | emotion / SEC / 评价相关概念 | `cognition/appraisal.py`, `helios_io/llm_sec_evaluator.py` | 已入库 |

### 3.2 Curated Research Notes

| 文件 | 主题 | 主要支撑模块 |
| --- | --- | --- |
| `foundations/panksepp_helio_mapping.md` | Panksepp 7 系统与 Helios 情感映射 | `daisy_emotion.py`, `personality.py`, `regulation/regulation.py` |
| `foundations/neurochem_model.md` | 神经调质模型 | `neurochem.py`, `cognition/drives.py`, `cognition/phi.py` |
| `foundations/fep_formalization.md` | 自由能原理形式化 | `cognition/drives.py`, `allostasis.py`, `helios_main.py` |
| `foundations/friston_panksepp_synthesis.md` | FEP 与原始情感系统综合 | `helios_main.py`, `regulation/regulation.py`, `cognition/drives.py` |
| `foundations/dmn_thinking_model.md` | DMN / replay / 内生思维 | `cognition/thinking_integration.py`, `cognition/phi.py` |
| `foundations/preconscious_path_research.md` | 前意识候选动作边界与研究映射 | `cognition/thinking_integration.py`, `helios_main.py`, `helios_io/interaction_policy.py`, `regulation/policy.py` |
| `foundations/personality_influence_research.md` | 人格影响与 trait-prior 投影层 | `personality.py`, `personality_projection.py`, `helios_io/interaction_policy.py`, `regulation/policy.py` |

## 4. 引用条目

以下条目当前作为引用清单维护，其中一部分在代码 docstring 中已有显式提及，但尚未统一沉淀为独立 bibliographic index。

| 条目 | 类型 | 与 Helios 的关系 | 当前收集状态 |
| --- | --- | --- | --- |
| Panksepp, J. (1998). *Affective Neuroscience* | 书籍 | 7 系统 affect foundation | 待补完整引用信息 |
| Russell, J. A. (1980). Circumplex model of affect | 论文 | valence-arousal plane | 待补全文或摘要 |
| Solomon, R. L., & Corbit, J. D. (1974). Opponent-process theory | 论文 | DAISY 对向过程 | 待补全文或摘要 |
| Kuppens et al. (2010). Emotional inertia | 论文 | mood / affect persistence | 待补完整引用信息 |
| Davidson, R. J. (2000). Affective chronometry | 论文/综述 | DAISY 时序动力学 | 待补摘要 |
| Barrett, L. F. (2017). Emotion as constructed / population thinking | 书籍/论文群 | 共激活而非单标签 | 待补精确条目 |
| Sterling, P., & Eyer, J. (1988). Allostasis | 章节/论文 | `allostasis.py` | 待补完整书目信息 |
| McEwen, B. (1998). Allostatic load | 论文 | `allostasis.py` 负荷机制 | 待补全文或摘要 |
| Schulkin, J. (2003). *Rethinking Homeostasis* | 书籍 | 异稳态框架扩展 | 待补书目信息 |
| McCrae, R. R., & Costa, P. T. (1997). Personality trait structure | 论文 | Big Five trait layer | 待补摘要 |
| Davis, K. L., & Panksepp, J. (2011). Primary-process emotional traits | 论文 | personality-affect coupling | 待补摘要 |
| Roberts et al. (2006). Personality trait change | 论文 | 长期人格漂移 | 待补摘要 |
| Tononi, G. (2004). An information integration theory of consciousness | 论文 | `cognition/phi.py` | 待补摘要 |
| Dehaene et al. (2006). Global neuronal workspace | 论文 | ignition / broadcasting | 待补摘要 |
| Seth, A. (2011). Predictive processing and conscious presence | 论文 | prediction and precision weighting | 待补摘要 |
| Friston, K. (2010, 2017). Free energy principle / active inference | 论文群 | `cognition/drives.py`, `helios_main.py` | 待补结构化引用 |
| Gebhard, P. (2005). ALMA | 论文 | `mood_tracker.py` personality-mood-emotion layering | 待补摘要 |
| Baddeley, A. Working memory | 论文/书籍 | `memory/memory_system.py` | 待补结构化引用 |

## 5. 待收集清单

### 5.1 高优先级

| 条目 | 原因 | 主要服务模块 | 建议动作 |
| --- | --- | --- | --- |
| Panksepp 1998 原始书目信息与关键章节页码 | 是 affect substrate 的最核心来源 | `daisy_emotion.py`, `personality.py`, `regulation/regulation.py` | 补 citation entry + 章节页码 |
| Friston 2010/2017 核心论文条目 | drives 与整体熵减叙事需要标准引用 | `cognition/drives.py`, `helios_main.py` | 补 citation entry + 摘要 |
| Tononi 2004, Dehaene 2006, Seth 2011 | 当前 `phi.py` 已显式引用，需要集中整理 | `cognition/phi.py` | 补 citation entry |
| ALMA / emotional inertia 原文条目 | mood/personality/time-scale 解释需要更稳固来源 | `mood_tracker.py`, `personality.py` | 补 citation entry |
| Allostasis 三个核心来源 | 当前代码已显式引用，但目录里还没有结构化条目 | `allostasis.py` | 补完整书目信息 |

### 5.2 中优先级

| 条目 | 原因 | 主要服务模块 | 建议动作 |
| --- | --- | --- | --- |
| Opponent-process 原文 | DAISY 中已有实现，但缺统一资料条目 | `daisy_emotion.py` | 补摘要 |
| Russell circumplex 原文 | affect/mood 二维空间共用基础 | `daisy_emotion.py`, `mood_tracker.py` | 补摘要 |
| Davis & Panksepp 2011 | personality-affect coupling | `personality.py` | 补摘要 |
| Baddeley working memory | memory subsystem 文档更完整 | `memory/memory_system.py` | 补 citation entry |

## 6. 资料与代码的关联方式

建议未来按如下格式维护：

1. 每个资料条目至少写明“支撑哪些模块”。
2. 每个 Active 文档新增理论引用时，应能回指到本文件中的某个条目。
3. 不能稳定分发的外部论文，不直接入库全文时，也应留下 citation entry 与获取状态。
4. 如已在仓库中保存 PDF，应尽量附上对应文本提取或摘要条目，便于搜索。

## 7. 与其他文档的关系

- `IMPLEMENTATION_REFERENCE.*`: 看模块与理论/测试的映射。
- `ARCHITECTURE.*`: 看当前结构与边界。
- `DESIGN_PHILOSOPHY.*`: 看运行阶段如何调用这些理论。
- Foundational notes: 看研究内容的进一步展开。