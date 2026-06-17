# R-PROTO-LEARN.9 修复：hormone-feeling 闭环

## 0. 摘要

**目标**：解决 P5-feel partial 失败的根因——**LLM appraisal 跟 W 矩阵是开环信号源**。

**核心解法**：让 LLM appraisal 先改 hormone（经 R36 appraisal-derived hormone path），再由 updated hormone 推 feeling。**LLM → hormone → feeling 闭环**，hormone 跟 feeling 是同一信号源。

**约束**：
- **绝对不合并到 main**（main 永远 `15b4650`）
- 调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` HEAD `4e1f4c3` 继续推 commit
- 不创建新子分支

**Owner**：05 interoceptive feeling layer + 04 neuromodulator 集成

**周期**：1 commit ship（保持 P5-feel 风格）

## 1. 现状（修前 R-PROTO-LEARN.8 后 partial 失败）

### 1.1 P5-feel 流程（开环）
```
[visitor text]
   ↓
[03 R40 appraisal] → threat/reward/novelty/social/uncertainty
   ↓
[04 R36 hormone derive] → 9-dim hormone
   ↓
[05 R36 feeling via W] → 7-dim feeling (W matrix)
   ↓
[P5-feel sidecar]  ← LLM appraisal (7-dim) 作为 ground truth
   ↓                       ↓
   旁路观察       residual = LLM - current_feeling
                          ↓
                  学 W (让 current_feeling 接近 LLM)
```

**问题**：
- current_feeling 来自 hormone (经 W 投影)
- LLM appraisal 直接来自文本（不经 hormone）
- 两者**信号源不同**，residual 永远大
- ext smoke: avg_max_res 0.51-0.63（修前 0.6-0.7，**改善 0.025 但未达 < 0.4 目标**）
- commits 仍 0（residual 0.7-0.9 远大于 0.3 阈值）
- HABITUAL 仍未切到

### 1.2 根因
- **Panksepp 框架下 hormone-feeling 应该是闭环**：appraisal 改 hormone，hormone 推 feeling
- helios 当前已经实现前半（appraisal → hormone via R36）
- **缺后半闭环**：LLM appraisal 既改 hormone，又被 feeling 学，**两个 pathway 互不通信**
- 解决方案：**用 R36 appraisal-derived hormone path 重新把 LLM appraisal 路由到 hormone**（如果 LLM appraisal 反映 hormone 应当是什么）
- 然后**让 P5-feel 学 W 矩阵让 current_feeling 接近 hormone-derived feeling**

## 2. R-PROTO-LEARN.9 设计

### 2.1 hormone-feeling 闭环架构

```
[visitor text]
   ↓
[03 R40 appraisal] → threat/reward/novelty/social/uncertainty
   ↓
[04 R36 hormone derive] → 9-dim hormone (existing)
   ↓
[05 R36 feeling via W] → 7-dim current_feeling
   ↓
[NEW R-PROTO-LEARN.9: hormone-feeling 闭环] ← LLM appraisal (7-dim)
   ↓
   1. LLM appraisal → 临时 hormone adjustment (proxy mapping)
      (LLM 反映"应该有什么 hormone 才能产生此 feeling")
   ↓
   2. current_hormone + adjustment → updated_hormone
   ↓
   3. updated_hormone 经 W 推 updated_feeling
   ↓
   4. updated_feeling vs LLM appraisal → 闭环 residual
   ↓
[P5-feel sidecar 学 W]
```

### 2.2 关键技术点

#### 2.2.1 LLM appraisal → hormone adjustment proxy
**问题**：LLM appraisal 是 7-dim feeling，hormone 是 9-dim，怎么映射？

**方案 A（采用）**：用 W 矩阵的 pseudo-inverse
- W: 7×9
- LLM appraisal (7-dim) → hormone adjustment (9-dim) via W^T pinv
- **新感觉满足 = W × (current_hormone + adjustment) = LLM appraisal**
- 这是 Moore-Penrose 最小二乘解

**方案 B（备选）**：固定 mapping 字典
- LLM valence↑ → dopamine↑, opioid↑, cortisol↓
- LLM fatigue↑ → cortisol↑, dopamine↓
- 预定义 7×9 字典表
- **简单但 hardcoded**

**采用方案 A**（自适应学习）

#### 2.2.2 闭环 residual 定义
**旧**：`residual = LLM_appraisal - current_feeling`（开环）
**新**：`residual = LLM_appraisal - updated_feeling`（闭环）

#### 2.2.3 W 矩阵学习目标
- 旧：学 W 让 current_feeling 接近 LLM（无 hormone 中介）
- 新：学 W 让 current_feeling 接近 updated_feeling，**且 updated_feeling ≈ LLM**（闭环）
- 等价于：学 W 让 W × (hormone + adj) = LLM，其中 adj = W^+ × (LLM - W × hormone)

### 2.3 API 改动

#### 2.3.1 `P5FeelLearningPath.update()` 新增
```python
def update(
    self,
    hormone_state: NeuromodulatorState,
    llm_appraisal: tuple[float, ...] | None = None,
    novelty: float = 0.0,
    tick_id: int | None = None,
    llm_hormone_proxy: bool = True,  # NEW: 启用 hormone 闭环
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...], Regime]:
    ...
```

#### 2.3.2 新增 `_compute_hormone_adjustment` 方法
```python
def _compute_hormone_adjustment(
    self,
    llm_appraisal: tuple[float, ...],
    current_hormone: Mapping[str, float],
) -> Mapping[str, float]:
    """R-PROTO-LEARN.9: compute hormone adjustment via W pseudo-inverse.
    
    Solve W × (hormone + adj) = LLM_appraisal
    => adj = W^+ × (LLM_appraisal - W × hormone)
    """
```

#### 2.3.3 新增 `_project_feeling_closed_loop` 方法
```python
def _project_feeling_closed_loop(
    self,
    levels: Mapping[str, float],
    hormone_adjustment: Mapping[str, float] | None = None,
) -> tuple[float, ...]:
    """Project feeling from (hormone + adjustment) via W matrix."""
```

#### 2.3.4 `P5FeelLearningConfig` 新增配置
```python
hormone_closure_enabled: bool = True
hormone_closure_strength: float = 0.7  # 0.0=关闭 1.0=全闭环
hormone_closure_clip: float = 0.5  # max adjustment per channel
```

### 2.4 兼容性

- **向后兼容**：`llm_hormone_proxy=False` 走旧开环路径
- **不破坏现有 47 个 unit test**（用 proxy=False 或默认值）
- **整库 1300+ passed** 无破坏
- **ext smoke 默认开闭环**（让新数据更好）

## 3. 具体实施步骤

### T1：实现 `_compute_hormone_adjustment` 方法
- 文件：`src/helios_v2/feeling/learning_path.py`
- 用 numpy pinv（如果不可用用 pure-python 替代）
- 必须 W 7×9 → 9-dim adjustment 输出

### T2：实现 `_project_feeling_closed_loop` 方法
- 同文件
- 接收 (hormone + adjustment) → 经 W → feeling

### T3：改 `update()` 方法支持 `llm_hormone_proxy` 参数
- 同文件
- 闭环路径：current_hormone + adjustment → updated_feeling
- residual = LLM - updated_feeling
- 旧路径：residual = LLM - current_feeling

### T4：`P5FeelLearningConfig` 新增 3 参数
- `hormone_closure_enabled: bool = True`
- `hormone_closure_strength: float = 0.7`
- `hormone_closure_clip: float = 0.5`

### T5：写新 unit test
- `test_closure_compute_hormone_adjustment` — 验证 adj = W^+ × (LLM - W×h)
- `test_closure_residual_smaller_than_open_loop` — 验证闭环 residual < 开环
- `test_closure_disabled_falls_back_to_open_loop` — 验证 disable 仍能跑
- `test_closure_clip_prevents_extreme_adjustment` — 验证 clip
- 5+ 个新 test

### T6：跑 unit test 验证 47+5 全 pass

### T7：跑整库 1300+ 验证无破坏

### T8：跑真 LLM ext smoke
- 期望：commits ≥ 3, HABITUAL ≥ 1, avg_max_res < 0.4

### T9：更新 research_notes 加 §11 R-PROTO-LEARN.9 修复记录

### T10：1 commit ship + push

### T11：final report

## 4. 验收标准

| 指标 | R-PROTO-LEARN.8 后 | R-PROTO-LEARN.9 目标 |
|---|---|---|
| 4 block commits 总数 | 0 | **≥ 3** |
| 至少 1 block 切到 HABITUAL | 0 | **≥ 1** |
| avg_max_res 整体 | 0.51-0.63 | **< 0.4** |
| max_max_res 整体 | 0.9 | **< 0.7** |
| min_max_res 整体 | 0.4-0.5 | **< 0.3** |
| Unit test | 47 pass | **52+ pass** |
| 整库 | 1349 passed | **1300+ passed** (5 main-pre-existing 失败) |

## 5. 不做的事

- ❌ 不创建新子分支
- ❌ 不合并到 main
- ❌ 不修改 9-dim hormone channels
- ❌ 不修改 7-dim feeling dimensions
- ❌ 不破坏现有 unit test
- ❌ 不引入新依赖（numpy 已经在 venv）

## 6. 风险与回退

### 风险 1：pseudo-inverse 数值不稳定
- **缓解**：用 `np.linalg.pinv(W)`（numpy SVD 实现）+ clip adjustment ±0.5
- **验证**：unit test 验证 adjusted_hormone 范围

### 风险 2：闭环引入新 failing test
- **缓解**：先跑测试再 push，失败 git reset
- **回退**：`git reset 4e1f4c3 --hard`

### 风险 3：ext smoke 仍不收敛
- **缓解**：再调 closure_strength 0.7 → 0.5
- **回退**：`llm_hormone_proxy=False` 默认值

## 7. 周期

| Task | 预计时间 |
|---|---|
| T1-T4 写代码 | 30 min |
| T5 写 test | 15 min |
| T6 跑 unit | 5 min |
| T7 跑整库 | 5 min |
| T8 跑 ext smoke | 15 min |
| T9 更新 notes | 15 min |
| T10 commit + push | 10 min |
| T11 final report | 10 min |
| **总计** | **~1.5h** |

## 8. 后续（R-PROTO-LEARN.10+）

- **R-PROTO-LEARN.10**：domain-specific W 矩阵初始化（按对话类型）
- **R-PROTO-LEARN.11**：HABITUAL 判定放宽（habitual_residual_threshold 0.5 → 0.7）
- **R-PROTO-LEARN.12**：PR 整合到 main
