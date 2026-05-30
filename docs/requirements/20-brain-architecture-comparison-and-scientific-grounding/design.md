# Requirement 20 - Brain architecture comparison and scientific grounding

## 1. Design Overview

本设计以文档产物为核心，目标是在不夸大类比的前提下，把 Helios 的工程架构与认知神经科学、情绪神经科学和记忆系统相关研究做谨慎映射。设计会产出一份主比较文档，并与现有哲学/HLD/requirements 索引建立链接。该文档不负责定义软件 owner，但负责说明哪些 requirement 受何种科学启发支持。

## 2. Current State and Gap

当前缺口包括：

1. 现有文档对情绪、调节、记忆、自我和行动只有哲学性描述，缺少论文级 grounding。
2. 模块与脑功能系统的对应关系未系统化，导致讨论容易混淆“工程 owner”和“生物功能角色”。
3. requirement 优先级尚未显式引用科学差距，例如为什么主动性、记忆分层、评估真实性比表层口吻更关键。

## 3. Target Architecture

目标文档结构建议如下：

1. 比较方法说明
   - 说明何为功能类比、何为工程替代、何为当前空缺。
2. 域级映射表
   - Helios 域 -> 人脑相关功能系统 -> 依据来源 -> 当前完成度 -> 主要缺口。
3. 专题章节
   - 情绪与异稳态
   - 记忆分层与自传连续性
   - 执行控制、规划与外化
   - 主动性、内驱和主观连续性
   - 自我模型与身份治理
4. 差距到 requirement 映射
   - 将主要差距对应到 R07-R20。

## 4. Data Structures

本 requirement 以文档表格为主，建议统一以下表结构：

1. `HeliosDomain`
2. `BrainFunctionRole`
3. `EvidenceLevel`
4. `CurrentCoverage`
5. `GapToRequirement`

这些表结构只存在于文档中，用于保持比较逻辑一致。

## 5. Module Changes

1. 新增脑架构比较主文档。
2. `docs/index.md`
   - 将比较文档纳入总入口。
3. `docs/requirements/index.md`
   - 补充 R20 与其他 requirement 的科学支撑关系。
4. 如有必要，在哲学或 HLD 文档中增加对比文档链接。

## 6. Migration Plan

1. 第一阶段先完成文献框架、比较方法和域级映射表。
2. 第二阶段补差距分析和 requirement 映射。
3. 第三阶段只在后续 requirement 明显变化时增量维护。
4. 默认 rollout 为文档发布即生效，不要求代码同步修改。

## 7. Failure Modes and Constraints

1. 若某项映射证据不足，必须标注为启发性类比或空缺，而不是强行对应。
2. 若发现不同文献结论冲突，应保留分歧并说明采用理由。
3. 文档不能把“当前实现中的统计字段”误写成“脑机制已实现”。
4. 本 requirement 不负责新增神经模拟或数值脑模型。

## 8. Observability and Logging

1. 文档应指出哪些现有运行指标可作为功能角色的工程 proxy。
2. 对无法观测的能力缺口，应明确标记缺少什么指标或实验。
3. 对 R17 的诊断指标和 R18 的主动性指标，应给出科学比较中的解释位置。

## 9. Validation Strategy

1. 检查文档是否为每个主要映射提供来源和证据级别。
2. 检查差距清单是否能回链到 requirement。
3. 交叉审阅文档，确认没有把工程 owner 和脑功能角色混淆。
4. 验证 docs 总入口和 requirements index 已纳入该文档。
