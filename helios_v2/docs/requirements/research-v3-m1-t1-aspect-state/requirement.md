# M1-T1: AspectState 向量实证(WHAT + WHY)

> **任务**:helios_v3 M1-T1 —— AspectState 10+ 字段向量取代 v1 标量 s_i
> **完成时间**:2026-06-28 ship
> **作者**:helios 调研分支(综合 v3 plan §05 + Self-Model v2 redesign)
> **配套**:`design.md` + `task.md` + `result.md`

## 0. 一句话总览

**把 v2 9-dim hormone + 7-dim feeling + 5-dim salience 投影到 AspectState 10+ 字段向量,实证证明向量形式能表达 v1 标量丢掉的"高激活低确定""正效价低唤醒""高激活高精度"等关键心理状态,为 M1 后续 Radau ODE / Kuramoto R / Reward-Hebbian 提供数据底座。**

## 1. 研究问题

v1 Self-Model 设计用 8 个标量 `s_i ∈ R` 表示 8 个 PTS 维度,丢失"高激活低确定"等关键心理状态(certainty 维度被折叠)。v2 redesign 要求 10+ 字段向量,本调研 ship 实证 v2 owner 数据能填满这个 10+ 字段向量。

## 2. 成功标准(可证伪)

1. **10 字段完整**:`AspectState` dataclass 至少包含 10 字段,每个字段都有合法范围
2. **3 个新状态可区分**:"高激活低确定" / "正效价低唤醒" / "高激活高精度" 在 AspectState 形式下唯一识别
3. **v2 投影完整**:能从 v2 `04` 9-dim hormone + `05` 7-dim feeling + `03` 5-dim salience 投影到 AspectState 10 字段
4. **数值合法**:所有字段都 clip 到合法范围,无 NaN/Inf
5. **测试 100% passed**:单元测试 + 投影测试
6. **token 预算**:`AspectState.to_llm_text()` 输出 < 200 字符
7. **可序列化**:`to_dict()` / `from_dict()` round-trip 一致
8. **可冻结**:`AspectState` 是 frozen dataclass(治理铁律 #8 "LLM 只能看不能改")

## 3. ship 7 件套

- [x] `requirement.md`(本文件)
- [x] `design.md`(HOW)
- [x] `task.md`(TASK + 验收)
- [x] `result.md`(ship 总结)
- [x] `helios_v2/src/helios_v2/research_v3_m1/aspect_state.py`(实现)
- [x] `helios_v2/src/helios_v2/research_v3_m1/projections.py`(v2 owner 投影)
- [x] `helios_v2/tests/research_v3_m1/test_aspect_state.py`(单元测试)
- [x] `helios_v2/tests/research_v3_m1/test_projections.py`(投影测试)
- [x] `helios_v2/scripts/r_v3_m1_t1_probe.py`(真实 LLM probe)

## 4. 依赖

- 无外部依赖(纯 Python dataclass + numpy 基础运算)
- v2 owner 04 / 05 / 03 已有实现(可直接 import)

## 5. 4 个拍板问题(主人 2026-06-21 红线)

1. ✅ 下一步研究问题对齐 v3 plan(M1-T1 直接实证 v3 plan §05_self_model_design_v2 §1)
2. ⚠️ 投影规则 `activation = (DA + NE) / 2` 是新决策,需主人拍板
3. ⚠️ "10 字段语义重叠"风险已识别,建议 mutual information 验证
4. ✅ 1 个真实 LLM probe(deepseek-v4-pro via shengsuanyun),`.env` 已有凭证

**待主人拍板后开始 M1-T2(Radau stiff solver 收敛性)。**
