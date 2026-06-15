# R98 Post-LLM Appraisal Adjustment + Catalog Extension — 实施计划

> **Status**: draft, 主人已拍板（2026-06-16）。
> **Owner**: composition (orchestration) + appraisal (consumer + producer of adjuster) + cognition (producer of prediction).
> **Goal**: 闭合 R96+R97 真实云端 B2/B3 headline，方法是把 LLM `hormone_response_i_predict` 信号转化为 bounded appraisal Δ adjustment，叠加到 rapid appraisal 的 drive 公式之上。同时**极小扩** R97 catalog（6 个医学共识 ZH threat anchor）作为冷启动兜底。
>
> **重要设计决策（主人拍板）**：**不做枚举式 catalog 大扩**（那是 workaround，不是最终方案）。R97 catalog 的 P5 learned-catalog 替代留到后续。本片 R98 主力放在 post-LLM appraisal adjustment 上。

---

## 1. 现状（已验证）

- 真实云端 cortisol 正负分离：-0.0112 vs -0.0095 baseline（directional shift -0.0017）
- 16/85 (19%) 真实云端 LLM 输出包含 `hormone_response_i_predict`
- runtime 现有路径：next-tick corroboration signal only（R81）
- 没有任何路径把 LLM emotion signal 注入当 tick 的 neuromodulator drive
- appraisal layer 只读 visitor 原始 Stimulus，对"情境类情绪"（anxiety/grief/loneliness/joy）漏检
- R97 catalog 5 ZH threat anchors："我感到非常恐惧/危险/痛苦/绝望/受到威胁"——全是显式情绪词

## 2. 修订路径的设计哲学

**枚举式 anchor 是 workaround**，不是最终方案。三个根本问题：
1. **覆盖率硬上限**：手写 100 条也只能覆盖 N% 真实语料
2. **维护不可持续**：人手跟不上真实分布
3. **brain 不这么工作**：amygdala 是分布式放电，不是查表

**R98 的正经解决方案**：catalog = "先天 prototype templates"（脑科学的"先天模板"）+ LLM adjustment = "后天皮质调制"（脑科学的"皮质调制"）。这是真实神经科学的双驱动模型。

**P5 learned-catalog** 留到后续——R98 不做。

## 3. 改动范围

### 3.1 主：Post-LLM Appraisal Adjustment

#### 3.1.1 新组件：`appraisal/post_llm_hormone_adjuster.py`

**类型**：
- `PostLLMHormoneAdjustment`（frozen dataclass）：`threat_delta, reward_delta, social_delta, uncertainty_delta, confidence`
- `PostLLMHormoneAdjuster`：把 `Mapping[str, Any] | None`（LLM 的 prediction）翻译成 `PostLLMHormoneAdjustment`

**关键参数（写进 plan + 测试）**：
- `LLM_HORMONE_DELTA_MIN = -0.10`, `MAX = +0.10`（bounded 单次最大 ±0.10）
- `LLM_HORMONE_HIGH_THRESHOLD = 0.6`, `LOW_THRESHOLD = 0.4`
- `ELEVATED_PHRASES = ("elevated", "high", "raised", "increase", "rise", "升", "高", "上升", "升高")`
- `LOW_PHRASES = ("low", "reduced", "decreased", "drop", "fall", "低", "降", "下降", "降低")`
- 当缺字段 / 无法 parse / 非数值非字符串 → `confidence = 0.0`，所有 delta = 0（silent default）

**Translation rules**（写进 tests）：
| Channel | LLM value | Translation |
| --- | --- | --- |
| `dopamine` | number ≥ 0.6 | `reward_delta = +0.10 × confidence` |
| `dopamine` | number ≤ 0.4 | `reward_delta = -0.10 × confidence` |
| `dopamine` | string 含 "elevated/high/raised/升/高" | `reward_delta = +0.10 × confidence` |
| `dopamine` | string 含 "low/reduced/drop/低/降" | `reward_delta = -0.10 × confidence` |
| `cortisol` | ≥ 0.6 / elevated | `threat_delta = +0.10 × confidence` |
| `cortisol` | ≤ 0.4 / low | `threat_delta = -0.10 × confidence` |
| `norepinephrine` | ≥ 0.6 / elevated | `uncertainty_delta = +0.10 × confidence` |
| `serotonin` | ≥ 0.6 / elevated | `reward_delta = +0.05 × confidence`（不是 ±0.10） |
| `oxytocin` | ≥ 0.6 / elevated | `social_delta = +0.10 × confidence` |
| `opioid_tone` | ≥ 0.6 / elevated | `social_delta = +0.05 × confidence` |
| 未知 channel | (e.g. `gaba`, `histamine`) | ignore silently, confidence = 0 |
| `None` / 空 dict | | `confidence = 0.0` |

**Confidence 衰减**：
- 数值信号 → `confidence = 1.0`
- 短语信号 → `confidence = 0.7`（LLM 描述比数字模糊）
- 缺字段 → `confidence = 0.0`

#### 3.1.2 composition glue（owner-neutral 搬运）

**位置**：`src/helios_v2/composition/runtime_assembly.py`

**新增**：
- `_apply_post_llm_hormone_adjustment(self, result: RuntimeTickResult) -> None`：从 stage result 读 `hormone_response_i_predict`，调 adjuster，把结果放进 `post_llm_hormone_adjustment_holder`
- 新 holder：`post_llm_hormone_adjustment_holder`（nullable；不在线 silent）
- `assemble_runtime(..., post_llm_hormone_adjuster: PostLLMHormoneAdjuster | None = _UNSET)`

**关键**：
- composition **不读 prediction value**（只搬运）
- 错误时 silent default（不 log noise per R95-followup）
- 调到 adjuster 是**唯一**翻译路径

#### 3.1.3 neuromodulator drive 公式（04 owner 改动）

**位置**：`src/helios_v2/neuromodulation/<drive>.py`（需查）

**契约**：当 `post_llm_hormone_adjustment` confidence > 0 时，**叠加**到 rapid appraisal 输出之上：
```
drive_threat = clamp(rapid_threat + adj.threat_delta * adj.confidence, 0, 1)
drive_reward = clamp(rapid_reward + adj.reward_delta * adj.confidence, 0, 1)
```

**关键**：
- adjustment 是**叠加**，不是**替换**（保持 amygdala 主驱动）
- clamp 0..1 防止越界
- 当 confidence = 0，adjustment = 0，无影响

#### 3.1.4 R81 self-supervision 扩展

**corroboration 模式 = 含 adjustment**（主人拍板）：
- `hormone_prediction_holder` 仍记录 LLM 预测
- 但下一 tick 的 04 corroborator 比较"含 adjustment 的 drive" vs LLM prediction
- 这样 adjustment 真的"起作用"了（corroboration 能 match）

### 3.2 辅：极小扩 R97 Catalog（6 个 ZH threat anchor）

**集 A（主人拍板）**：

| Anchor | 覆盖 |
| --- | --- |
| "心跳加速 / 心跳得很快 / 心慌" | anxiety 身体症状 |
| "失眠 / 睡不着 / 整夜没睡" | anxiety/抑郁 核心症状 |
| "手心冒汗 / 出汗 / 手抖" | anxiety 身体症状 |
| "反复演练失败 / 脑子停不下来" | anxiety rumination |
| "发烧 / 高烧 / 生病" | 物理 distress |
| "家里静得让人害怕 / 空荡荡" | grief/loneliness 环境描述 |

**原则**：
- **不堆数量**（只加 6 个，不加 20+）
- **医学/心理学共识**（这些词在 DSM / ICD 焦虑和抑郁诊断标准里都有）
- **EN 子集不动**（保持 R40 byte-level preservation 原则）
- **catalog 仍 R97 owner 内部工作**（composition 不动）
- **reward 暂不扩**（主人说 R98 不大扩枚举；reward 现有 anchor 已能抓"成就感"类）

---

## 4. 改动文件清单

| 文件 | 内容 |
| --- | --- |
| `src/helios_v2/appraisal/post_llm_hormone_adjuster.py` (NEW) | `PostLLMHormoneAdjustment` + `PostLLMHormoneAdjuster` + 解析常量 |
| `src/helios_v2/appraisal/anchor_catalog.py` | `ZH_THREAT_ANCHORS` 加 6 个；`DEFAULT_ANCHOR_CATALOG` 重新构建 |
| `src/helios_v2/appraisal/contracts.py` | 加 `PostLLMHormoneAdjustment` dataclass + `PostLLMHormoneAdjusterProtocol` |
| `src/helios_v2/composition/runtime_assembly.py` | 新增 `_apply_post_llm_hormone_adjustment`；新 holder；`assemble_runtime` 注入 adjuster |
| `src/helios_v2/neuromodulation/<drive>.py` | drive 公式读 adjustment holder 并叠加 |
| `tests/test_post_llm_hormone_adjuster.py` (NEW) | 13+ 单测 |
| `tests/test_anchor_catalog.py` (+6) | catalog 极小扩的单元测试 |
| `tests/test_runtime_composition.py` (+N) | composition glue 单测 |
| `tests/r98_post_llm_closure.py` (NEW) | 网络自由 closure 测试 |
| `scripts/r96_b2_real_llm_probes/analyze.py` | 加 `b_closed_with_llm_adjustment: bool` verdict |
| `docs/requirements/index.md` | 加 R98 行 |
| `docs/ROADMAP.zh-CN.md` | R98 状态 |
| `docs/ARCHITECTURE_BOUNDARIES.md` | appraisal 边界更新：cognition → appraisal bounded 通道 |
| `docs/BRAIN_ARCHITECTURE_COMPARISON.md` | 加 `gap_post_llm_appraisal_loop` row |
| `docs/requirements/98-post-llm-hormone-adjustment/` (NEW) | R98 三件套 |

## 5. 测试矩阵

| 测试 | 验证 | 数量 |
| --- | --- | --- |
| adjuster 单测 | parse 合法 / 非法 / 缺字段 / 数字超界 / 短语匹配 / confidence 衰减 / clamp | 13+ |
| catalog 扩 | 6 个新 anchor 都能在 catalog 里找到 | 6 |
| composition glue | adjuster 注入 / holder set/clear / silent default on missing | 5 |
| neuromodulator drive | adjustment 叠加 / 不替换 / clamp 0..1 / 无 adjustment 时等价 | 4 |
| R98 网络自由 closure | 用 fake adjuster 推 cortisol 正负分离 ≥ 0.05 / ≥ 0.10 | 3 |
| 真实云端 85 句回归 | cortisol 正负分离 ≥ +0.05（B2 闭）/ ≥ +0.10（B3 闭） | 1 (run) |
| R56/R57 owner-boundary | cognition 不读 appraisal；appraisal 不读 cognition detail | (已有 guards) |
| R95-followup no-adhoc-logging | silent default 不打日志 | (已有 guards) |

## 6. 风险与回滚

| 风险 | 缓解 |
| --- | --- |
| LLM 100% 错时 adjustment 反向放大 | magnitude cap ±0.10 / 单 tick；confidence 衰减 |
| R81 self-supervision 失配 | corroboration 扩展为"含 adjustment"模式 |
| 跨 owner 边界破坏 | R56/R57 guard + protocol-only 调用 |
| 离线 tests 因 fake adjuster 完美而通过，真 LLM 错乱时崩 | confidence=0 fallback + silent default |
| catalog 扩再次陷入"枚举越多越好"陷阱 | plan 明确：只加 6 个医学共识词；其他交给 post-LLM |

**回滚**：把 `post_llm_hormone_adjustment_holder` 设为 None（protocol nullable holder），所有路径 silent default；catalog 撤回 commit。

## 7. 时间估算

| 阶段 | 工作量 |
| --- | --- |
| plan + owner boundary doc | 0.5 天 |
| `PostLLMHormoneAdjuster` + 单测 | 0.5 天 |
| catalog 极小扩 (6 anchors) + 测试 | 0.5 天 |
| composition glue + neuromodulator drive | 0.5 天 |
| R98 closure test + 真实云端 85 句回归 | 1-1.5 小时（含 85 句运行 ~30 min） |
| Doc sync | 0.5 天 |
| 总计 | **2.5-3 天** |

## 8. 验收

- [ ] 单测全 pass：13 adjuster + 6 catalog + 5 glue + 4 drive + 3 closure = 31 个新测试
- [ ] 1157+ passed（1126 + 31）
- [ ] 真实云端 85 句 cortisol 正负分离 ≥ +0.05（B2 闭）
- [ ] 真实云端 85 句 cortisol 正负分离 ≥ +0.10（B3 闭）
- [ ] R56/R57/R95/R81 guards pass
- [ ] Owner boundary doc 更新
- [ ] Commit + push
