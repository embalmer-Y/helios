# M1-T8 OwnerFieldBridge 需求

## 背景

v3 设计的 self-model 由 8-dim CDS state 表达(对应 PTS_DIMENSION_NAMES:bodily / minimal_experiential / affective / intersubjective / psychological / narrative / ecological / normative)。但 v2 owner 的实际数据是 21 字段:
- 04 Hormone9D (9 fields)
- 05 Feeling7D (7 fields)
- 03 Salience5D (5 fields + aggregate = 6 fields)

M1-T1 提供了 `project_v2_to_aspect_state()` —— 把 v2 数据投影到 AspectState(用于 LLM 提示)。但**没有**提供"v2 数据 → CDS 8-dim 输入向量 I"的桥接器。

没有这个桥,M2-M8 接入 v2 owner 时,CDS tick 的 I 输入只能手工构造或全零,导致 v3 self-model 跟 v2 数据完全脱节。

## 目标

设计并实现 `OwnerFieldBridge`:
1. **bridge_input(hormone, feeling, salience) → 8-dim I**:把 21 个 v2 字段加权组合成 CDS 输入向量
2. **bridge_reflect(aspect_state, history?) → 8-dim reflect**:AspectState → CDS reflect 调制向量(M2 预留接口)
3. **可配置权重**:`OwnerFieldMapping` dataclass 允许自定义每个 CDS 维度的权重
4. **fixture 测试**:`fixture_neutral / high_positive / high_threat / low_energy` 4 个语义化测试 fixture

## 验收标准

1. ✅ 110 个 M1 测试全过(90 旧 + 20 新 M1-T8)
2. ✅ 1000-tick 探针:0 solver failure, 0 NaN, R ∈ [0, 1]
3. ✅ Fixture |I| 均值:neutral=0, high_positive=0.76, high_threat=0.52, low_energy=0.22(语义排序正确)
4. ✅ 8 个 default mappings 互不相同(每个 CDS 维度有专属权重)
5. ✅ `bridge_input` 输出 ∈ [-1, 1]

## 映射策略

每个 CDS 维度 = v2 字段加权和:

| CDS 维度 | 主要 v2 来源 |
|----------|-------------|
| 0 bodily_processes | cortisol, opioid_tone, pain_like, fatigue(-) |
| 1 minimal_experiential | serotonin, acetylcholine, comfort, uncertainty(-) |
| 2 affective | dopamine, NE, valence, arousal, tension, reward |
| 3 intersubjective | oxytocin, social_safety, comfort, social |
| 4 psychological_cognitive | dopamine, ACh, tension, novelty, uncertainty |
| 5 narrative | excitation, dopamine, valence, reward, novelty |
| 6 ecological_extended | NE, arousal, threat, novelty |
| 7 normative | inhibition, serotonin, comfort, uncertainty(-) |

## 范围

✅ 包含:`OwnerFieldBridge` + `OwnerFieldMapping` + `DEFAULT_MAPPINGS` + 4 个 fixture + 20 测试 + 1000-tick 探针
❌ 不包含:
- 权重学习(目前是 hand-tuned,留到 M5/M8 探索 learning)
- 跟 v2 owner 真实模块的 import 集成(目前 v2 owner 是 mock dataclass,真实集成等 M8)
- v2 → v3 schema validation(目前 fixture 输入是手填,validation 留到 M5)

## 不在范围

- 多 owner 多桥接(本期 1 个 bridge → 1 个 CDS,M2 可能扩展)
- 跨 session 的权重持久化(留到 M8)