# Requirement 20 - Brain architecture comparison and scientific grounding

## 1. Background and Problem

Helios 的整体目标是向“类脑、具身、意识优先”的系统演进，但目前文档中的脑科学映射仍偏概念性，缺少对模块与人脑功能系统的专业对照、引用依据和边界声明。这会导致两类问题：一是内部讨论中“像不像大脑”容易沦为口号；二是 requirement 优先级难以基于专业文献判断哪些是核心缺口、哪些只是表层体验问题。

用户已经要求形成一套更专业的 Helios-vs-human-brain 对比文档，并尽量基于专业论文或综述建立映射关系。当前缺的不是更多营销式表述，而是可审查、可引用、明确说明“相似点、缺口、不可比点”的科学 grounding 文档。

## 2. Goal

建立一套以中文为主、基于专业文献的脑架构比较文档，把 Helios 主要模块与人脑相关功能系统进行谨慎映射，明确系统当前已覆盖的能力、明显缺口、不可简单类比的边界以及对未来 requirement 优先级的启发。

## 3. Functional Requirements

### 3.1 模块到脑功能系统映射

1. 文档 must 对 Helios 的主要域与人脑相关功能系统建立映射，至少覆盖情绪/调节、记忆、价值与驱动、执行控制、感觉输入、行动输出和自我模型。
2. 每个映射 must 明确“近似对应的功能角色”，而不是宣称一一等价。
3. 对无法合理类比的实现部分 must 明确标记为工程替代物或当前空缺。

### 3.2 文献支撑

1. 主要比较结论 must 绑定具体论文、综述或教材级来源。
2. 文档 must 区分强证据、启发性类比和工程假设三类依据。
3. 引用 must 服务于架构判断，而不是堆砌参考文献。

### 3.3 差距分析与 requirement 反哺

1. 文档 must 输出 Helios 当前与目标类脑能力之间的主要差距清单。
2. 差距清单 must 指向现有或新增 requirement，而不是停留在抽象评论。
3. 文档 should 说明哪些脑功能特征在当前工程范围内不追求直接模拟。

## 4. Non-Functional Requirements

1. 文档应避免过度拟人化或伪科学表述，保持专业克制。
2. 映射和结论 must 能被架构设计直接消费，而不是仅供宣传阅读。
3. 中文为主，但关键英文术语和论文标题 should 保留，方便后续检索。
4. 若文献观点存在分歧，文档 must 标注范围和不确定性。

## 5. Code Behavior Constraints

1. 不得把工程模块直接写成人脑器官等价物。
2. 不得使用没有来源支撑的“脑区对应”断言作为 requirement 依据。
3. 不得让科学比较文档替代具体软件架构文档；它只能作为约束与启发来源。
4. 若某项类比仅为启发性，应显式标记，防止误导实现方向。

## 6. Impacted Modules

1. `docs/ARCHITECTURE_PHILOSOPHY.zh-CN.md`
2. `docs/HIGH_LEVEL_DESIGN.zh-CN.md`
3. `docs/index.md`
4. `docs/requirements/index.md`
5. `docs/requirements/20-brain-architecture-comparison-and-scientific-grounding/`

## 7. Acceptance Criteria

1. 至少形成一份可审阅的中文脑架构比较文档，包含模块映射、文献依据、差距清单和不可比边界。
2. 文档中每个主要映射段落都带有明确来源类别和引用条目。
3. 差距清单能回链到现有 requirement，至少覆盖 R17-R20 中的相关关注点。
4. 文档明确说明当前工程不直接模拟的脑功能范围，避免误导性目标膨胀。
