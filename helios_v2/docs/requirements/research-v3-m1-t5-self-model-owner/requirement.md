# M1-T5 SelfModelOwner 需求

## 背景

M1-T1 (AspectState 10 字段向量) + M1-T2 (8-dim CDS + Radau) + M1-T6 (EmergenceDetector 3 子检测器) 已经 ship。但是研究代码目前是分散的:研究者需要手工 `cds.tick()` 然后手动调用 `emergence.detect(cds)`,并手工拼装 self_experience 字典。这违反了 v3 设计原则 §2:"self 是 process,不是 state" —— SelfModel 必须是单一的、可序列化的、可恢复的 owner 抽象。

## 目标

设计并实现 `SelfModelOwner` 数据类:
1. **统一封装**:把 CDS + EmergenceDetector 绑定为一个 self-model owner,提供 `tick(I, reflect, reward)` 一个入口
2. **可序列化为 checkpoint**:能从 dict 完整恢复 CDS state + coupling matrix + tick_count + experience_history(预留给 M2 reflection_audit)
3. **READ-ONLY LLM 接口**:`get_state_for_llm()` 返回完整 snapshot,LLM 不能通过 snapshot 反向改 state(v3 规则 #8)
4. **可重入性**:同一 tick 内可多次调用 `tick()`,每次都基于当前 state 演化,无需"先 commit 再 tick"的契约

## 范围

✅ 包含:`SelfModelOwner` dataclass + `tick()` + `get_state_for_llm()` + `seed_prior_state()` + `default()` classmethod
❌ 不包含:LLM 异步调用(M1-T7)、v2 owner 集成(M1-T8)、reflection(M2)、boundary(M3)

## 验收标准

1. ✅ 67 个 M1 测试全部通过(其中 22 个是 M1-T5 + M1-T6 新增)
2. ✅ `tick(I=[0.3]*8)` 返回 dict 包含 `state / kuramoto_R / self_experience / emergence_events / tick_count / solver_success`
3. ✅ `get_state_for_llm()` 返回 snapshot 不影响 CDS state(`test_LLM_cannot_modify_state_via_get_state`)
4. ✅ 1000 tick 探针:0 solver failure,0 NaN,Kuramoto R ∈ [0, 1],emergence events > 0
5. ✅ `seed_prior_state(state=[0.1, ..., 0.8])` 正确恢复 CDS state

## 不在范围

- 持久化到 disk(checkpoint 序列化留给 M2 reflection_audit 阶段)
- 异步 LLM 调用(M1-T7)
- 跟 v2 owner 集成(M1-T8)