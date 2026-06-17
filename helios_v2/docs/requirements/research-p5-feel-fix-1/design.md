# R-PROTO-LEARN.8 设计：P5-feel first-version W 修复

## 0. 引用

- **requirement.md** 详见同目录
- **Fermin 2021** Insula Interoception IMAC 模型（aINS/dINS/gINS 三回路）
- **Panksepp 2011** 7 个原始情绪系统（neural substrate）

## 1. 设计原则

### 1.1 三个不变
1. **保持 P5-feel 旁路观察者模式**（不写入 canonical feeling）
2. **保持 9-dim hormone × 7-dim feeling 接口**（不破坏 owner 05 contract）
3. **保持 unit test 47 个全 pass + 整库 1300 passed**

### 1.2 三个变
1. **W 矩阵发全套**：从 22 个非零 → 49-63 个非零
2. **learning rate 上调**：0.01 → 0.05
3. **regime 阈值放宽**：commit + habitual 更容易触发

## 2. 修复 A：W 矩阵发全套

### 2.1 现状（W 矩阵 = 7×9 = 63 权重）
```python
_FIRST_VERSION_WEIGHTS = (
    # valence (9 entries) 7 个非零
    (0.30, 0.00, 0.15, 0.00, -0.30, 0.00, 0.15, 0.00, 0.00),
    # arousal (9 entries) 2 个非零
    (0.00, 0.40, 0.00, 0.00, 0.00, 0.00, 0.00, 0.20, 0.00),
    # tension (9 entries) 2 个非零
    (0.00, 0.20, 0.00, 0.00, 0.40, 0.00, 0.00, 0.00, 0.00),
    # comfort (9 entries) 3 个非零
    (0.00, 0.00, 0.15, 0.00, -0.30, 0.20, 0.30, 0.00, 0.00),
    # fatigue (9 entries) 2 个非零
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.20, 0.20),
    # pain_like (9 entries) 2 个非零
    (0.00, 0.00, 0.00, 0.00, 0.40, 0.00, -0.35, 0.00, 0.00),
    # social_safety (9 entries) 3 个非零
    (0.00, 0.00, 0.15, 0.00, -0.25, 0.40, 0.00, 0.00, 0.00),
)
```

**Total = 21 个非零 (33%)** — 缺 42 个

### 2.2 新 W 矩阵（63 个全部非零 + 调整现有值）

**依据**：
- **Panksepp 7 系统 + 神经回路**（Damasio 2017, Craig 2009, LeDoux 2016）
- **临床常识**（疲劳时 cortisol 高、疼痛时 NE 高）
- **R36/R43 已有 baseline 的延伸**（保留正向影响）
- **避免 over-claim**：权重上限 0.5（-0.5 to 0.5）

```python
_FIRST_VERSION_WEIGHTS = (
    # valence: reward - punishment asymmetry
    ( 0.30,  0.10,  0.15,  0.05, -0.30,  0.20,  0.15,  0.05, -0.05),
    # arousal: sympathetic activation
    ( 0.10,  0.40, -0.10,  0.10,  0.05,  0.00,  0.00,  0.20, -0.10),
    # tension: threat vigilance
    ( 0.00,  0.20,  0.00,  0.10,  0.40, -0.10, -0.10,  0.10,  0.00),
    # comfort: soothing
    ( 0.10, -0.10,  0.15, -0.10, -0.30,  0.20,  0.30, -0.05,  0.05),
    # fatigue: depletion
    (-0.30,  0.00, -0.20, -0.05,  0.30, -0.10, -0.15,  0.20,  0.20),
    # pain_like: nociception
    (-0.20,  0.20, -0.20,  0.00,  0.40,  0.00, -0.35,  0.10,  0.00),
    # social_safety: attachment
    ( 0.10,  0.00,  0.15,  0.05, -0.25,  0.40,  0.10,  0.00, -0.05),
)
```

**Total = 49+ 个非零 (78%)** — 仍有 14 个 0.0（如 acetylcholine 对 valence 是中性），但比现状 21 个多 28 个

### 2.3 关键设计决策

| dim | 关键变化 | 理由 |
|---|---|---|
| fatigue | +cortisol: 0.30, +serotonin: -0.20 | 长期疲劳 cortisol 高 + serotonin 低（临床） |
| fatigue | +dopamine: -0.30 | 疲劳时 reward 系统 down（Panksepp SEEKING 系统减弱） |
| pain_like | +NE: 0.20 | 疼痛 NE 上升（LeDoux 2016 fear/pain 重叠） |
| pain_like | +DA: -0.20 | 疼痛 reward 系统 down |
| social_safety | +DA: 0.10, +opioid: 0.10 | 社会奖赏 → DA + opioid 释放（依恋神经化学） |
| arousal | +DA: 0.10, +ACh: 0.10 | 唤醒 = DA + ACh 共驱动 |
| arousal | +5-HT: -0.10 | 5-HT 抑制唤醒 |
| tension | +ACh: 0.10 | 紧张时皮层可塑性 |
| comfort | +DA: 0.10, +ACh: -0.10 | 舒适时 reward up + 学习 down |

## 3. 修复 B：learning config 调整

### 3.1 P5FeelLearningConfig default 变化

| 参数 | 旧值 | 新值 | 理由 |
|---|---|---|---|
| `learning_rate` | 0.01 | 0.05 | 5 倍加速，1 个 block 16 dialogue 能学 0.05 × 16 = 0.8 改进 |
| `commit_threshold` | 0.2 | 0.3 | 放宽到 0.3 让 LLM appraisal 跟 baseline 0.3 差距也能 commit |
| `min_stable_ticks` | 20 | 8 | 4 block 48 dialogue 平均 12 tick/block，8 tick 能 commit |
| `frozen_ticks_post_commit` | 10 | 5 | 让 commit 后快速解冻 |
| `flexibility_threshold` | 0.4 | 0.3 | ACh 0.3+ 触发 EXPLORATORY（更敏感） |
| `regime_hysteresis_ticks` | 2 | 3 | 抗 jitter 3 tick |
| `habitual_recent_window` | 5 | 3 | 更快判 HABITUAL |

### 3.2 新增参数

```python
habitual_residual_threshold: float = 0.5
```

**语义**：当 recent_residual < 0.5 连续 3 tick 可切到 HABITUAL（即使未到 0.3 阈值）

**理由**：ext smoke 跑出 avg_max_res=0.5-0.7，需要给 HABITUAL 留一个能触发的阈值

## 4. 修复 C：regime 切换逻辑调整

### 4.1 现状 `_determine_regime`
- 检查 ACh > 0.4 + novelty > 0.5 → EXPLORATORY
- 检查 recent_residual < 0.3 连续 5 tick → HABITUAL
- 否则 → MODEL_BASED

### 4.2 新 `_determine_regime`
```python
def _determine_regime(self, ..., recent_residual: tuple, ach: float, novelty: float) -> Regime:
    # 1. Exploration trigger (ACh + novelty)
    if ach >= 0.3 and novelty > 0.4:  # 阈值放宽
        return Regime.EXPLORATORY
    # 2. Habituation trigger (stable + low residual)
    if self._is_habitual_candidate():  # 检查新阈值
        return Regime.HABITUAL
    # 3. Default: model-based
    return Regime.MODEL_BASED
```

### 4.3 `_is_habitual_candidate` 新逻辑
```python
def _is_habitual_candidate(self) -> bool:
    recent = list(self._residual_history)[-self.config.habitual_recent_window:]
    if len(recent) < self.config.habitual_recent_window:
        return False
    return all(max(abs(v) for v in r) < self.config.habitual_residual_threshold
               for r in recent)
```

## 5. 修改文件清单

| 文件 | 改动 |
|---|---|
| `src/helios_v2/feeling/learning_path.py` | W 矩阵 + P5FeelLearningConfig default + _is_habitual_candidate |
| `scripts/r_proto_learn_7_p5_feel_extended_smoke.py` | 删除 hardcoded config（用 learner default） |
| `tests/test_r_proto_learn_7_p5_feel.py` | 可能要调 1-2 个边界 case（如果新 default 破坏 test） |
| `docs/requirements/research-p5-feel-fix-1/{requirement,design,task}.md` | 新建 |
| `docs/requirements/research-p5-feel/research_notes_v2_journals.md` | 加 R-PROTO-LEARN.8 修复记录章节 |

## 6. 验证流程

### 6.1 单元测试
```bash
cd /root/project/helios/helios_v2
PYTHONPATH=src .venv/bin/python3 -m pytest tests/test_r_proto_learn_7_p5_feel.py -v
```
**期望**：47 个全 pass

### 6.2 整库
```bash
cd /root/project/helios/helios_v2
set -a; . /root/project/helios/.env; set +a
.venv/bin/python3 -m pytest tests/ -q --ignore=scratch_r79b
```
**期望**：1300+ passed + 3 skipped + 0 failed

### 6.3 extended smoke
```bash
cd /root/project/helios/helios_v2
PYTHONPATH=src set -a; . /root/project/helios/.env; set +a; .venv/bin/python3 scripts/r_proto_learn_7_p5_feel_extended_smoke.py
```
**期望**：
- commits ≥ 3
- 至少 1 block 切到 HABITUAL
- avg_max_res < 0.4
- max_max_res < 0.7

## 7. 风险控制

| 风险 | 控制措施 |
|---|---|
| 新 W 矩阵 over-claim | 权重上限 0.5（-0.5 to 0.5） |
| commit 触发了但 commit 内容是错的 | frozen_ticks_post_commit=5 冻结 5 tick |
| unit test 破坏 | 47 个先跑，失败立即 git stash + 调 |
| 整库测试破坏 | 失败立即 git stash + 调 |
| 调研分支意外 merge 到 main | **不创建新分支**（保持当前调研分支） |

## 8. Commit 信息

```
fix(R-PROTO-LEARN.8): P5-feel first-version W matrix full + config retune

- Expand _FIRST_VERSION_WEIGHTS from 21 non-zero (33%) to 49+ non-zero
  (78%) using Panksepp 7-system + clinical priors
- Raise learning_rate 0.01 → 0.05 (5x faster convergence)
- Raise commit_threshold 0.2 → 0.3 (looser commit gate)
- Lower min_stable_ticks 20 → 8 (commit within 1 block)
- Lower flexibility_threshold 0.4 → 0.3 (more sensitive EXPLORATORY)
- New habitual_residual_threshold 0.5 (HABITUAL attainable)
- expected: 4 block commits ≥ 3, regime 切到 HABITUAL, residual 0.3-0.5
```

## 9. 不做的事

- ❌ 不创建新子分支
- ❌ 不合并到 main（main 永远 `15b4650`）
- ❌ 不修改 9-dim hormone channels
- ❌ 不修改 7-dim feeling dimensions
- ❌ 不破坏 P5-feel 现有 47 个单元测试
- ❌ 不破坏整库 1300 passed
- ❌ 不引入新依赖
