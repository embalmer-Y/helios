# M1-T1: AspectState 向量实证(HOW)

> **任务**:M1-T1 详细设计
> **完成时间**:2026-06-28
> **配套**:`requirement.md`

## 0. 设计原则

1. **frozen dataclass**:AspectState 不可变(治理铁律 #8)
2. **字段独立**:10 字段各自有合法范围
3. **可序列化**:`to_dict()` / `from_dict()` round-trip
4. **可注入 LLM**:`to_llm_text()` < 200 字符
5. **不污染 v2**:独立模块 `helios_v2.research_v3_m1`

## 1. AspectState 10 字段

| 字段 | 范围 | 含义 |
|---|---|---|
| `activation` | [-1, 1] | 激活度 |
| `valence` | [-1, 1] | 效价 |
| `arousal` | [0, 1] | 唤醒度 |
| `certainty` | [0, 1] | 确定性 |
| `salience` | [0, 1] | 显著性 |
| `precision` | [0, 1] | 精度(FEP 核心) |
| `novelty` | [0, 1] | 新颖性 |
| `coherence` | [0, 1] | 跟其他维度相干 |
| `stability` | [0, 1] | 时间稳定性 |
| `resonance` | [0, 1] | 跟历史共振 |

## 2. v2 owner 投影规则

| AspectState 字段 | v2 数据源 | 投影 |
|---|---|---|
| `activation` | 04 DA + NE | (DA + NE) / 2 |
| `valence` | 05 valence | 直接 |
| `arousal` | 05 arousal | 直接 |
| `certainty` | 03 uncertainty | 1 - uncertainty |
| `salience` | 03 aggregate | 直接 |
| `precision` | certainty + stability | 0.5 × certainty + 0.5 × stability |
| `novelty` | 03 novelty | 直接 |
| `coherence` | 6 维基础字段 | 1 - std(...) |
| `stability` | R43 alpha_phasic | 1 - 1/(1 + alpha_phasic) |
| `resonance` | history_state | cosine 相似度 |

## 3. 3 个 fixture(可区分状态)

- **Fixture 1**:高激活低确定(activation=0.8, certainty=0.2)
- **Fixture 2**:正效价低唤醒(valence=0.7, arousal=0.2)
- **Fixture 3**:高激活高精度(activation=0.8, precision=0.95)

## 4. 关键论证

v1 标量形式下 3 fixture 区分度 < 0.1(信息有损),AspectState 形式下完美区分。

## 5. 真实 LLM probe

3 fixture × 3 问题 = 9 probe,测 LLM 能否引用 AspectState 字段、能否区分 3 fixture。
