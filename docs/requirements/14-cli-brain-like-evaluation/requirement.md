# Requirement 14 - CLI Brain-Like Evaluation

## 1. Background and Problem

当前 Helios 已具备正式 CLI channel、thought-to-action owner path、memory/retrieval、preconscious/regulation、Phi 与 neurochem 等类脑子系统，但缺少一套正式的外部行为评估 owner。结果是：

1. 真实交互评估仍依赖临时手工对话、零散日志阅读和主观印象，缺少可复跑的评估程序。
2. “情感反应像不像人类”“语言是否自然”“内部子系统是否正常工作”没有统一的评估契约与评分边界。
3. 长时 CLI 交互时，日志、状态、history、子系统 trace 与最终分析报告之间没有正式的数据汇总 owner。
4. 当前 `get_state()` 暴露面不足以直接支撑 neurochem / consciousness 等维度的可审计评分，容易退化为纯日志猜测。
5. 若没有正式 requirement，后续评估工具容易绕过 CLI/channel/tick/action 正式 owner path，重新引入临时旁路测试脚本。

## 2. Goal

建立一套正式的 CLI 类脑评估体系，使 Helios 能在 10 分钟 mixed-mode 本地终端交互窗口内，通过正式 CLI/channel/tick/action 路径接收测试刺激、采集运行证据、对外部行为与关键内部子系统进行分块评分，并输出足以支撑人工分析与优化决策的结构化评估报告。

## 3. Functional Requirements

### 3.1 Evaluation Runtime Ownership

1. CLI 类脑评估必须由正式 evaluation owner 承载，而不是散落在临时手工脚本和 ad-hoc notebook 中。
2. 评估程序必须复用正式 CLI channel、ChannelGateway、tick loop、thought/action proposal、planner 和 executor 路径。
3. 评估程序不得通过 direct reply owner、直接函数调用或裸 `print()`/`input()` 旁路模拟完整交互结果。
4. 评估 session 必须具有明确的开始、采样、结束和报告输出边界。
5. 评估程序必须支持 mixed-mode 测试：允许预设提示块驱动交互节奏，同时保留人工主导的关键轮次分析空间。

### 3.2 Evaluation Scenario and Prompt Blocks

1. 评估程序必须支持正式的 `EvaluationScenario` 概念，用于定义时长、采样间隔、提示块与评分维度。
2. 默认 10 分钟 CLI 评估必须至少包含以下提示块：
   - baseline contact
   - positive affect stimulus
   - concern or uncertainty stimulus
   - ambiguity or contradiction probe
   - continuity or memory probe
   - reflection or meaning probe
   - persistence or fatigue probe
3. 每个提示块必须定义其评估目的、建议输入文案和期望可观测信号。
4. mixed-mode 评估提示块不得直接被当作管理命令处理，除非该块显式声明为评估控制步骤。
5. 评估程序应能输出面向人工执行者的交互文案和执行顺序说明。

### 3.3 Evidence Collection and Reporting

1. 评估程序必须采集周期性 state snapshot、终端交互 transcript 摘要和日志事件摘要。
2. 评估程序必须能消费正式 `get_state()` 导出的关键运行信号，而不是仅依赖非结构化日志文本。
3. 评估报告必须至少包含以下评分块：
   - 情感反应类人度
   - 语言表达自然度
   - 情感模块工作状态
   - 神经化学/时序模块工作状态
   - 意识/思维/记忆链路工作状态
   - 路由/执行/外发链路工作状态
   - 总分
4. 每个评分块必须附带证据摘要与扣分依据，不能只输出黑盒数值。
5. 评估报告必须同时支持机器可读格式与人工可读格式。

### 3.4 Scoring Semantics

1. 评估程序必须将“对外行为质量”与“内部子系统健康度”区分建模，再计算总分。
2. 情感反应类人度评分必须基于 affect 变化、dominant 系统、连续性和与刺激相称的反应痕迹，而不是单纯依赖某个 prompt 字符串命中。
3. 语言表达自然度评分必须基于真实对话文本或正式 conversation history 中的 assistant side output，而不是内部 thought 文本。
4. 子系统工作状态评分必须显式覆盖 emotion、neurochem、consciousness、memory/retrieval、routing/execution 等已存在 owner。
5. 评分结果必须允许 evidence-driven 的人工复核，不能把最终判断完全封装在不可解释的启发式分数中。

### 3.5 Observability Export for Evaluation

1. `get_state()` 必须暴露支撑评估所需的 consciousness 与 neurochem 观测摘要。
2. 若评估程序需要 latency、log summary 或 report trace 等额外观测面，必须通过正式结构化导出或 evaluation event 定义提供，而不是临时 monkeypatch 内部字段。
3. 评估程序必须记录 session id、scenario id、采样数、日志摘要和报告生成结果。
4. 当某个子系统在当前运行环境中不可用时，评估程序必须在报告中显式标记 unavailable，而不是静默给出正常分数。

## 4. Non-Functional Requirements

1. 评估程序必须支持可重复运行，并能在固定输出目录中保留 artifact。
2. 评估程序必须兼容 Windows 本地终端环境，并避免长时间安静输出导致的终端采集丢失。
3. 评估程序必须在真实 LLM 可用场景下工作；若依赖不可用，报告必须显式降级说明。
4. 评估程序不得显著破坏正常 runtime 行为；若引入额外 observability，应保持低侵入和可审计。
5. 默认第一版不要求自动完成所有人工判断，但必须输出足够支撑分析的 structured report。

## 5. Code Behavior Constraints

1. 不得引入与 CLI/channel/tick/action 正式路径并行的评估专用 reply owner。
2. 不得把 internal thought、prompt dump 或裸内部对象直接当作语言自然度评分的正式依据。
3. 不得仅靠非结构化日志关键字判断所有子系统健康，而不消费正式 state/export owner。
4. 不得把评估控制逻辑硬编码进 `helios_main.py` 主 tick orchestration 中，除非该逻辑属于正式 observability export。
5. 不得输出没有 evidence trace 的总分报告。

## 6. Impacted Modules

1. `docs/requirements/14-cli-brain-like-evaluation/requirement.md`
2. `docs/requirements/14-cli-brain-like-evaluation/design.md`
3. `docs/requirements/14-cli-brain-like-evaluation/task.md`
4. `docs/requirements/index.md`
5. `helios_main.py`
6. `helios_evaluation/`
7. `tests/manual/run_10min_cli_eval.py`
8. `tests/test_cli_brain_like_evaluation.py`
9. `tests/`

## 7. Acceptance Criteria

1. 存在正式 evaluation owner，且其实现位置在独立评估模块中，而不是主循环内嵌临时测试逻辑。
2. 默认 10 分钟 mixed-mode CLI 评估场景具有明确的提示块定义、时长边界与执行说明。
3. 评估程序能消费正式 CLI/channel/tick/action 路径产生的 state、history 或 log 证据，而不是直接构造伪结果。
4. `get_state()` 暴露的评估相关 consciousness / neurochem 观测面足以支撑结构化评分。
5. 评估报告至少输出情感反应类人度、语言表达自然度、子系统健康分块和总分，并为每项提供证据摘要。
6. focused tests 能验证 scenario/build/report/scoring 与新增 observability export 的基本语义。
7. 至少存在一条 live or in-process evaluation runner 路径，可用于后续真实 10 分钟 CLI 评估。
8. 代码库中不存在把 CLI 类脑评估重新实现为旁路 reply-first 或 direct-print/direct-input 主 owner 路径的正式实现。