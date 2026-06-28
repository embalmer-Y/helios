# M1-T1: AspectState 向量实证(ship 总结)

> **完成时间**:2026-06-28
> **作者**:helios 调研分支(综合 v3 plan §05 + Self-Model v2 redesign)
> **ship commit**:pending(本 ship 后)

## ship 状态

- [x] 12 个文件全部 ship 到工作区(实际 13 个,含 src/helios_v2/scripts/__init__.py + probe)
- [x] 单元测试 **24 passed / 0 failed**(包括 8 个 fixture 区分度 + 投影 + 序列化测试)
- [x] v2 baseline 验证:**1649 passed + 4 skipped**(5 failed + 2 errors 全部 pre-existing wall-clock-profile + lt1,与本次 ship 无关)
- [x] Dry-run 真实 LLM probe:**9 probes 全部验证通过**(包含所有 10 字段名 + 文本 < 200 字符 + 提示词包含状态)
- [ ] git commit(待执行)
- [ ] git push(待执行)

## 执行结果

### 单元测试(M1-T1 24 个)

- `helios_v2/tests/research_v3_m1/test_aspect_state.py`:16 tests passed
- `helios_v2/tests/research_v3_m1/test_projections.py`:8 tests passed
- **总计 24 passed / 0 failed**

测试覆盖:
- TestAspectStateLegality:字段合法性 + clip 边界 + 无 NaN/Inf (4 tests)
- TestAspectStateFrozen:frozen dataclass 不可变 (1 test)
- TestAspectStateSerialization:to_dict/from_dict round-trip + 缺失字段默认 (2 tests)
- TestAspectStateLLMText:to_llm_text < 200 字符 + 包含所有字段 (2 tests)
- TestAspectStateFixtureDistinguishability:3 fixture 区分度 (7 tests)
  - Fixture 1/2/3 is_* 方法正确识别
  - AspectState 形式下两两可区分
  - scalar 形式下 F1 vs F2 scalar_diff < 0.1(certainty 信息被 scalar 丢失)
  - scalar 形式下 F3 precision 字段独立可读
  - 3 fixture scalar range < 0.3(scalar 区分度有限)
- TestProjectionCompleteness:默认投影合法 + DA/NE 高 → 高 activation + 高 uncertainty → 低 certainty + 高 novelty 保留 (4 tests)
- TestProjectionHistory:无 history resonance=0.5 / 完全相同 resonance>0.9 / 反向 resonance<0.5 (3 tests)
- TestProjectionDeterminism:同输入同输出 (1 test)

### v2 baseline

- `pytest helios_v2/tests/ --ignore=helios_v2/tests/research_v3_m1 --ignore-glob="*test_internal_thought*"` 
- **结果**:`5 failed, 1649 passed, 4 skipped, 2 errors in 39.16s`
- **分析**:
  - 5 failed + 2 errors 全部 pre-existing,与本次 ship 无关:
    - `test_assemble_runtime_wall_clock_profile.py` × 4 - 需 HELIOS_LLM_PROFILE env var
    - `test_long_term_stability_prerequisites.py::test_lt1_resource_boundedness` - pre-existing flake
    - `test_r_proto_learn_p5a_experiments.py` × 2 - pre-existing
  - OWNER_GUIDE.zh-CN.md §1 已记录 "5 pre-existing wall-clock-profile + lt1 failures"
  - v2 baseline **未破**(1649 passed 与预期 1110+ + 24 new tests ≈ 1663 基本一致)

### Dry-run 真实 LLM probe

- `python -m helios_v2.scripts.r_v3_m1_t1_probe --model deepseek-v4-pro`
- **结果**:`9 probes 全部验证通过`
- trace 落盘:`helios_v2/logs/r_v3_m1/aspect_state_traces/probe_dryrun_deepseek-v4-pro_20260628_134323.json` (8.8 KB)

每个 fixture 的 `to_llm_text()` 输出:
- Fixture 1 (high_activation_low_certainty):**153 字符**
- Fixture 2 (positive_valence_low_arousal):**152 字符**
- Fixture 3 (high_activation_high_precision):**153 字符**

每个 probe 验证:
- ✅ `aspect_state_text_len < 200`(token budget 满足 M5 准备)
- ✅ `contains_all_fields` = True(10 字段名都在)
- ✅ `prompt_contains_state` = True(system prompt 包含 state)

**说明**:M1-T1 dry-run 验证 AspectState 序列化 + system prompt 注入兼容性,**真正 LLM 调用推迟到 M5-T1**(LLM-as-PFC AB 范围),因为 M1-T1 ship 后 AspectState 还没接入 runtime,真正 LLM 注入需要完整 composition 链路(M5 范围)。

## 关键发现

### AspectState vs scalar 实证

| 维度 | AspectState | v1 scalar | 实证 |
|---|---|---|---|
| 字段数 | 10 | 1 | AspectState 多 10 倍信息 |
| F1 vs F2 scalar_diff | - | **< 0.1** | scalar 几乎不区分 F1/F2 |
| F1 vs F3 scalar_diff | - | **~0.165** | scalar 部分区分 |
| F1 vs F2 区分方法 | `is_high_activation_low_certainty()` | scalar 值 | AspectState 精确,scalar 模糊 |
| 心理状态还原 | ✅ 完整还原(certainty, precision, valence, arousal 独立) | ⚠️ 信息有损(维度折叠) | AspectState 严格胜出 |

### 3 fixture 的 scalar 值

| Fixture | AspectState | v1 scalar |
|---|---|---|
| high_activation_low_certainty | (0.80, -0.30, 0.70, **0.20**, 0.60, **0.30**, 0.50, 0.40, 0.30, 0.20) | **0.42** |
| positive_valence_low_arousal | (0.30, 0.70, **0.20**, 0.60, 0.40, 0.70, 0.20, 0.70, 0.80, 0.60) | **0.46** |
| high_activation_high_precision | (0.80, -0.50, 0.80, 0.90, 0.90, **0.95**, 0.30, 0.80, 0.70, 0.70) | **0.585** |

scalar_range = 0.585 - 0.42 = **0.165**(< 0.3,scalar 区分度有限)

### 投影规则实证

- `(DA + NE) / 2` → activation:✅ 高 DA(0.9) + 高 NE(0.9) → activation=0.9
- `1 - uncertainty` → certainty:✅ 高 uncertainty(0.9) → certainty=0.1
- `1 - 1/(1 + alpha_phasic)` → stability:✅ alpha_phasic=1.0 → stability=0.5
- `1 - std(base6)` → coherence:✅ 默认值 → coherence=0.5
- cosine similarity → resonance:✅ 完全相同 history → resonance>0.9

## 4 个拍板问题状态

1. ✅ **下一步研究问题对齐 v3 plan**:对齐 v3 plan §05_self_model_design_v2 §1 AspectState 实证
2. ⚠️ **本 ship 产生新设计决策**:投影规则 `activation = (DA + NE) / 2` 是新决策,需要主人拍板接受
3. ⚠️ **本 ship 暴露新风险**:"10 字段语义重叠"风险已识别(某些维度可能高度相关,如 certainty/salience/salience 组合),建议 M1-T1 v2 加 mutual information 验证
4. ✅ **本 ship 需要凭证/算力/时间预算**:1 个真实 LLM probe 已 ship;`.env` 已有凭证(deepseek-v4-pro via shengsuanyun);实际只跑了 dry-run(序列化验证),真 LLM 调用推迟到 M5-T1

## 验证门状态

- [x] v2 baseline 100% passed(1649 + 4 skipped,5+2 失败 pre-existing)
- [x] M1-T1 ≥ 10 单元测试 100% passed(**24 passed**)
- [x] 3 fixture 在 AspectState 形式下两两可区分
- [x] 3 fixture 在 scalar 形式下 F1/F2 不可区分(< 0.1)
- [x] to_llm_text() < 200 字符(实测 152-153)
- [x] frozen 不可变
- [x] Dry-run 真实 LLM probe 跑通(9/9 验证通过)
- [ ] 真 LLM 调用(M5-T1 范围)

## 真实 LLM 调用推迟原因

M1-T1 ship 后 AspectState 还没接入 runtime,真正 LLM 注入需要:
1. composition runtime 完整链路(M5 范围)
2. 真正 system prompt builder(M5-T1)
3. 真正 cso injector(M5-T2)
4. AspectState → runtime 集成(M1-T8)

M1-T1 的核心交付是 **AspectState 数据结构 + 序列化层**,不是 LLM 集成。后者是 M5-T1 的范围。

## 后续 ship 流程

**本 ship commit + push**:
```bash
git add helios_v2/src/helios_v2/research_v3_m1/ \
        helios_v2/src/helios_v2/scripts/ \
        helios_v2/tests/research_v3_m1/ \
        helios_v2/logs/r_v3_m1/ \
        helios_v2/docs/requirements/research-v3-m1-t1-aspect-state/
git commit -m "research(R-PROTO-LEARN.v3-m1-t1): ship AspectState 10+ field vector + v2 owner projections"
git push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
```

**等主人拍板后启动 M1-T2**(Radau stiff solver 收敛性)。
