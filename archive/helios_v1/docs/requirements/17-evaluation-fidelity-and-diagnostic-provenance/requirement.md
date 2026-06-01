# Requirement 17 - Evaluation fidelity and diagnostic provenance

## 1. Background and Problem

当前 CLI 类脑评估已经能够跑通 5 分钟 live harness，并生成结构化报告，但评分仍存在明显失真。最近一次 5 分钟评估总分为 `0.59`，同时内部子系统维度仍给出了偏高分数；报告还显示 `sec_fallback_events=127`、`policy_rejection_events=22`、`outbound_success_events=11`，说明用户可见行为与内部健康分之间存在明显脱节。

现有评分实现仍偏向“字段存在”“范围正常”“链路被调用过”这类 presence-based 判断，缺少对真实因果链、失败来源、降级路径和证据出处的约束。这会掩盖主观性丢失、思考未外化、LLM SEC 回退过多、规划链空转等核心问题，使后续 requirement 的优先级判断失真。

## 2. Goal

将 CLI 类脑评估升级为以行为证据和链路溯源为中心的诊断系统，使每个维度分数都能映射到明确的运行证据、失败类型和责任模块，并在子系统行为弱化、回退频繁或链路断裂时自动压低对应分数。

## 3. Functional Requirements

### 3.1 评分证据模型

1. 评估器 must 为每个评分维度记录显式证据项，至少覆盖输入来源、思考触发、思考产物、规划决策、执行结果、外发结果、回退事件和拒绝事件。
2. 每个维度分数 must 由证据项驱动，而不能仅由状态字段存在性或摘要范围判断。
3. 评分结果 must 能区分“链路未触发”“链路触发但失败”“链路成功但质量低”“链路成功且稳定”四类状态。

### 3.2 诊断溯源与归因

1. 评估报告 must 输出维度级 provenance，明确每个分数依赖的事件计数、样本片段和责任模块。
2. 当存在 SEC fallback、policy rejection、empty thought、planner no-op、channel unavailable 或 outbound failure 时，报告 must 将其纳入负向归因，而不是只作为附录信息。
3. 评估器 should 生成维度级 gap summary，说明“当前分低的直接原因”和“下一跳应检查的 owner 模块”。
4. 评估报告 must 将 `thought produced -> action proposed -> planner accepted -> visible reply emitted / why not emitted` 作为 first-class diagnostic chain 输出，而不是只给出汇总计数。

### 3.3 SEC 契约稳定性与前段污染诊断

1. 评估器 must 将 `llm_sec_evaluator.py` 的 JSON parse failure、fallback 次数、fallback 比率、结构化输出成功率和失败来源纳入正式 evidence model。
2. 当 appraisal 前段主要依赖 fallback path 时，相关语言、情感理解、意识链路和外发链路维度 must 触发显式 penalty 或 warning。
3. 评估报告 must 能区分“prompt / behavior 本体问题”和“SEC appraisal 前段污染”两类主要失真来源。
4. 在 SEC 高频 fallback 场景下，报告 should 给出下一跳检查点，至少覆盖 SEC prompt contract、JSON-only 输出约束和 parser failure provenance。

### 3.4 行为门控与失真抑制

1. 当语言自然度、情感反应类人度、主动性或外发成功率低于阈值时，相关内部健康维度 must 被行为真实性门控压低。
2. 如果某维度主要依赖 fallback path、mock-like placeholder 或重复模板响应得到分数，该维度 must 触发 fidelity penalty。
3. 评估结果 must 对“高内部健康分但低用户可见表现”的失真场景输出显式 warning。
4. 当用户可见输出稀疏、承接弱或只剩低分辨率泛化表达时，评估结果 must 将其视为 thought-to-visible translation gap，而不是把它掩盖在内部健康分中。

### 3.5 长程连续性与 artifact 集成

1. live harness must 将新增证据、维度归因和 warning 纳入 JSON 与 Markdown report。
2. harness must 支持在 5 分钟和 10 分钟运行中稳定产出同构 artifact，不因缺少某个可选 channel 而失败。
3. 评估 artifact may 输出适合 requirement 回顾的摘要块，但不得替代原始计数与原始证据。
4. 评估 artifact must 暴露 late-session degradation、visible-output sparsity、specific recall persistence、continuity carry 和 user-visible anchoring drift 等长程诊断字段。
5. 同一 scenario 下的“SEC 正常结构化输出条件”与“SEC fallback 高频条件” should 能产出可并排比较的 artifact。
6. 在 forced fallback 对照条件下，artifact must 优先使用 runtime provenance 计数（如 `sec_evaluator.fallback_count`、`llm_successes`、`total_evaluations`），不得仅依赖日志文本匹配推断 SEC 退化程度。
7. 同一 scenario 下的 forced fallback 对照条件 must 在总分层和至少一个对外行为相关维度上产生稳定负向差异，不得出现 `sec_fallback_delta` 已显著拉开但总分仍与正常结构化 SEC 条件打平的结果。

## 4. Non-Functional Requirements

1. 评估增强不得要求改动主运行时 owner 边界；新增采样与统计应优先复用现有 state、log 和 harness 输出。
2. 缺失证据时系统 must 降级为“unknown / not observed”，而不是推断成功。
3. JSON report 与 Markdown report 的关键计数、维度分和 warning must 保持一致。
4. 新增诊断逻辑 should 能被窄范围单测覆盖，并支持离线 fixture 回放。
5. 评估增强 must 支持对照运行条件的可重复比较，避免单次 live run 被 SEC fallback confounder 完全污染后仍无法定位根因。
6. forced fallback、normal SEC、以及 mixed/occasional fallback 三类条件的语义边界 must 明确可复现；显式传入 `api_key=""` 的对照运行不得隐式回退复用环境变量里的凭证。

## 5. Code Behavior Constraints

1. 禁止继续以“字段非空”“模块对象存在”“数值落在 0 到 1”作为高分的充分条件。
2. 禁止在 report 渲染阶段二次推断责任归因；归因 owner 必须属于评估核心数据模型。
3. 不得绕过 `helios.get_state()`、evaluation harness 或正式日志路径手工拼接临时评分来源。
4. 失败事件不得只写入文本总结而不进入结构化 artifact。
5. 不得把 `SEC fallback` 只当作环境噪声忽略；若它已影响刺激理解和情绪细化，必须进入正式扣分与归因。
6. 不得让 forced fallback 对照条件在 runtime owner、评估 provenance owner 和 artifact renderer 三处出现不一致语义；若对照侧被显式强制为 fallback，相关计数与 warning 必须在结构化 report 中保持一致。

## 6. Impacted Modules

1. `helios_evaluation/cli_brain_like_evaluation.py`
2. `tests/test_cli_brain_like_evaluation.py`
3. `tests/manual/run_10min_cli_eval.py`
4. `helios_main.py`
5. `core/helios_state.py`
6. `helios_io/llm_debug.py`
7. `helios_io/response_pipeline.py`
8. `helios_io/planning.py`

## 7. Acceptance Criteria

1. 使用固定 evaluation fixture 时，至少一个“内部指标存在但行为失败”的场景会将相关维度压低，并在 report 中输出 fidelity warning。
2. live harness 生成的 JSON report 包含每个维度的 evidence、negative factors、owner hints 和 gap summary。
3. 在 SEC fallback 高频场景下，相关语言/意识/路由维度分数会被可重复地压低，而不是维持近似健康分。
4. Markdown report 与 JSON report 对总分、维度分、warning 计数和关键负向事件计数保持一致。
5. report 中能直接看到 `thought produced -> action proposed -> planner accepted -> visible reply emitted / why not emitted` 的诊断链条。
6. 至少存在一组同 scenario 的对照 artifact，能并排比较 SEC 正常结构化输出条件与 fallback 高频条件对总分和各维度的影响。
7. 上述对照 artifact 中，forced fallback 一侧必须在总分层与至少一个对外行为维度上稳定低于 normal SEC 一侧；若两侧 `sec_fallback_delta` 已显著拉开而总分仍打平，则 requirement 视为未满足。
