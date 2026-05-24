# Requirement 08 - Stimulus Weighting and Thought Gating

## 1. Background and Problem

当前系统虽然存在事件 trigger、novelty factor、SEC 特征和 cognitive impact，但这些信号分散在不同模块中，没有统一的 stimulus contract。结果是：

1. 输入来源语义不统一。
2. 刺激强度没有成为统一 0-1 一等变量。
3. 不是所有输入都需要触发思考这一原则尚未被正式实现。
4. 习惯化、敏感化、drive、temporal state 和 phi/ICRI 对 thought gate 的作用没有统一 owner。

## 2. Goal

建立统一 stimulus contract 和 thought gating 机制，使所有输入都带有来源、触发条件和归一化强度，并由统一门控决定当前 tick 是否进入思考以及思考强度如何变化。

## 3. Functional Requirements

### 3.1 Unified Stimulus

1. 所有输入必须被标准化为统一 stimulus 对象。
2. stimulus 对象必须至少包含：
   - source channel
   - source kind
   - trigger condition
   - stimulus intensity in `[0, 1]`
   - payload
   - timestamp
3. stimulus intensity 必须是正式语义字段，而不是临时推导值。

### 3.2 Thought Gating

1. thought gate 必须统一消费以下因素：
   - stimulus intensity
   - novelty / habituation
   - sensitization
   - drive urgency
   - temporal dynamics
   - ICRI / phi
   - resource pressure
   - continuation pressure
2. 系统必须允许某些 stimulus 被识别为不足以触发思考。
3. 系统必须允许在 absence of external input 时仅因 continuation pressure 或 internal drive 进入思考。

### 3.3 Gate Result

1. thought gate 的结果不得是简单 bool。
2. gate result 必须至少包含：
   - should_think
   - gate score
   - dominant reasons
   - blocked reasons
   - contributing signals
3. gate result 必须能够被 observability 和测试读取。

### 3.4 Habituation and Sensitization

1. 习惯化与敏感化不得只作为情感 trigger 前处理。
2. habituation/sensitization 必须显式影响 thought gate。
3. 长时间无暴露的恢复必须能影响 stimulus 再次进入思考的概率。

## 4. Non-Functional Requirements

1. stimulus normalization 和 gate 计算必须保持轻量，适合每 tick 执行。
2. gate result 必须可解释，便于调试和 prompt 指标说明。
3. 新 contract 不要求兼容旧 message-only 输入边界。
4. channel 新增时必须能自然接入 unified stimulus。

## 5. Code Behavior Constraints

1. 不得继续让 channel 输入只以裸 `text` 或松散 metadata 进入主循环。
2. 不得把 stimulus intensity 放在 prompt 文本中而不进入结构化状态。
3. 不得把 habituation 仅作为 DAISY trigger 缩放器而不进入 thought gating。
4. 不得保留无意义旧输入 wrapper 作为长期边界。

## 6. Impacted Modules

1. `helios_io/channel.py`
2. `helios_io/channel_gateway.py`
3. `core/helios_state.py`
4. `core/trigger_merge.py`
5. `habituation.py`
6. `cognition/cognitive_impact.py`
7. `cognition/appraisal.py`
8. `cognition/phi.py`
9. `helios_main.py`

## 7. Acceptance Criteria

1. 任一输入在进入主循环前都可被表示为统一 stimulus 对象。
2. thought gate 返回结构化 gate result，而不是仅返回 bool。
3. `habituation.py` 的结果显式参与 thought gate，而不仅参与情感 trigger 缩放。
4. 低强度 stimulus 可被 gate 拒绝，并可观察到拒绝原因。
5. continuation pressure 或 internal drive 可在无外部输入时独立触发 thought gate。
