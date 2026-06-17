# R-PROTO-LEARN.8 任务清单

## 0. 引用

- **requirement.md** 详见同目录
- **design.md** 详见同目录
- **目标 commit**：`research/R-PROTO-LEARN-appraisal-multi-mechanism` 调研分支，HEAD `434006d` 上推 1 commit

## 1. 任务清单

### T1 改 `_FIRST_VERSION_WEIGHTS`（修复 A）⏱️ 30min
**文件**：`src/helios_v2/feeling/learning_path.py`
**改动**：从 21 个非零（33%）扩到 49+ 个非零（78%）

**新 W 矩阵**（详见 design.md §2.2）：
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

**验证**：
- 文件中 `_FIRST_VERSION_WEIGHTS` 替换完成
- 维度 7 + 通道 9 + 49+ 非零
- 用 `python3 -c "from helios_v2.feeling.learning_path import _FIRST_VERSION_WEIGHTS; ..."` 验证 shape

### T2 改 `P5FeelLearningConfig` default（修复 B+C）⏱️ 15min
**文件**：`src/helios_v2/feeling/learning_path.py`
**改动**：

| 参数 | 旧值 | 新值 |
|---|---|---|
| `learning_rate` | 0.01 | 0.05 |
| `commit_threshold` | 0.2 | 0.3 |
| `min_stable_ticks` | 20 | 8 |
| `frozen_ticks_post_commit` | 10 | 5 |
| `flexibility_threshold` | 0.4 | 0.3 |
| `regime_hysteresis_ticks` | 2 | 3 |
| `habitual_recent_window` | 5 | 3 |
| **新增** `habitual_residual_threshold` | — | 0.5 |

**验证**：
- `__post_init__` 验证仍全过
- `commit_threshold` 验证 0.3 ∈ [0, 1]
- `learning_rate` 验证 0.05 ∈ (0, 1]

### T3 改 `_is_habitual_candidate`（修复 C）⏱️ 10min
**文件**：`src/helios_v2/feeling/learning_path.py`
**改动**：使用新 `habitual_residual_threshold`

```python
def _is_habitual_candidate(self) -> bool:
    recent = list(self._residual_history)[-self.config.habitual_recent_window:]
    if len(recent) < self.config.habitual_recent_window:
        return False
    return all(max(abs(v) for v in r) < self.config.habitual_residual_threshold
               for r in recent)
```

### T4 改 extended smoke 默认参数⏱️ 10min
**文件**：`scripts/r_proto_learn_7_p5_feel_extended_smoke.py`
**改动**：删除 hardcoded config（让 learner 用新 default）

**现状**：
```python
learner = P5FeelLearningPath(
    config=P5FeelLearningConfig(
        min_stable_ticks=4, commit_threshold=0.2,
        regime_hysteresis_ticks=2, learning_rate=0.02,
    )
)
```

**新**：
```python
learner = P5FeelLearningPath()  # use new defaults
```

### T5 跑单元测试⏱️ 5min
```bash
cd /root/project/helios/helios_v2
PYTHONPATH=src .venv/bin/python3 -m pytest tests/test_r_proto_learn_7_p5_feel.py -v 2>&1 | tail -80
```

**期望**：47 个全 pass
**失败处理**：git stash 改 test 中 hardcoded threshold（如果新 default 撞 test 边界）

### T6 跑整库测试⏱️ 5min
```bash
cd /root/project/helios/helios_v2
set -a; . /root/project/helios/.env; set +a
.venv/bin/python3 -m pytest tests/ -q --ignore=scratch_r79b 2>&1 | tail -30
```

**期望**：1300+ passed + 3 skipped + 0 failed
**失败处理**：git stash 排查

### T7 跑真 LLM extended smoke⏱️ 15min
```bash
cd /root/project/helios/helios_v2
set -a; . /root/project/helios/.env; set +a
PYTHONPATH=src .venv/bin/python3 scripts/r_proto_learn_7_p5_feel_extended_smoke.py 2>&1 | tail -100
```

**期望数据**：
- 4 block commits 总数 ≥ 3
- 至少 1 block 切到 HABITUAL
- avg_max_res < 0.4
- max_max_res < 0.7

**不达预期处理**：
- 检查 unit test 47 个
- 检查 `commit_threshold` 是否够大（再加 0.05）
- 检查 `learning_rate` 是否够大（再加 0.01）

### T8 更新 research_notes_v2_journals.md⏱️ 15min
**文件**：`docs/requirements/research-p5-feel/research_notes_v2_journals.md`
**改动**：加 §10 "R-PROTO-LEARN.8 修复记录"
- 修复前数据（4 block 0 commits）
- 修复方案 A+B+C
- 修复后数据（4 block commits≥3 + HABITUAL 切换）
- 跟 Panksepp 神经回路对位验证

### T9 写修复 commit + push⏱️ 10min
```bash
cd /root/project/helios
git add helios_v2/src/helios_v2/feeling/learning_path.py
git add helios_v2/scripts/r_proto_learn_7_p5_feel_extended_smoke.py
git add helios_v2/tests/test_r_proto_learn_7_p5_feel.py  # if changed
git add helios_v2/docs/requirements/research-p5-feel-fix-1/
git add helios_v2/docs/requirements/research-p5-feel/research_notes_v2_journals.md

git commit -m "fix(R-PROTO-LEARN.8): P5-feel first-version W matrix full + config retune

- Expand _FIRST_VERSION_WEIGHTS from 21 non-zero (33%) to 49+ non-zero
  (78%) using Panksepp 7-system + clinical priors
- Raise learning_rate 0.01 -> 0.05 (5x faster convergence)
- Raise commit_threshold 0.2 -> 0.3 (looser commit gate)
- Lower min_stable_ticks 20 -> 8 (commit within 1 block)
- Lower flexibility_threshold 0.4 -> 0.3 (more sensitive EXPLORATORY)
- New habitual_residual_threshold 0.5 (HABITUAL attainable)
- expected: 4 block commits >= 3, regime 切到 HABITUAL, residual 0.3-0.5"

git push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
```

**验证 push 成功**：
- `git log origin/research/R-PROTO-LEARN-appraisal-multi-mechanism --oneline -3`
- 看到新 commit 在最顶

### T10 写 final report 给小黑⏱️ 10min
**路径**：`/tmp/p5_feel_fix1_report.md`
**内容**：
- 修复前 4 block 数据
- 修复方案 A+B+C
- 修复后 4 block 数据（commits/HABITUAL/residual）
- 测试通过情况（47 + 1300）
- 给小黑的 3 选 1 建议

## 2. 验收清单

| 项目 | 验收标准 | 状态 |
|---|---|---|
| W 矩阵 | 49+ 非零 (78%) | ⬜ T1 |
| learning_rate | 0.05 | ⬜ T2 |
| commit_threshold | 0.3 | ⬜ T2 |
| min_stable_ticks | 8 | ⬜ T2 |
| flexibility_threshold | 0.3 | ⬜ T2 |
| habitual_residual_threshold | 0.5 (新) | ⬜ T2 |
| _is_habitual_candidate | 用新阈值 | ⬜ T3 |
| ext smoke 默认 | 用 learner default | ⬜ T4 |
| Unit test 47 | pass | ⬜ T5 |
| 整库 1300+ | pass | ⬜ T6 |
| Extended smoke commits | ≥ 3 | ⬜ T7 |
| Extended smoke HABITUAL | ≥ 1 block | ⬜ T7 |
| Extended smoke avg_max_res | < 0.4 | ⬜ T7 |
| research_notes 更新 | §10 R-PROTO-LEARN.8 | ⬜ T8 |
| commit + push | 远端可见 | ⬜ T9 |
| final report | 给小黑 | ⬜ T10 |
| **不合并到 main** | main 仍是 `15b4650` | ⬜ 全程 |

## 3. 周期

| Task | 预计时间 |
|---|---|
| T1 | 30 min |
| T2 | 15 min |
| T3 | 10 min |
| T4 | 10 min |
| T5 | 5 min |
| T6 | 5 min |
| T7 | 15 min (含 LLM 调用) |
| T8 | 15 min |
| T9 | 10 min |
| T10 | 10 min |
| **总计** | **~2h** |

## 4. 风险与回退

### 风险 1：unit test 47 个中有 hardcoded 旧值
- **缓解**：先跑测试看哪几个失败，单独调这 1-2 个 test
- **回退**：git reset 434006d --hard

### 风险 2：extended smoke 跑出 commits=0（仍不收敛）
- **缓解**：再调 commit_threshold 0.3 → 0.4 + min_stable_ticks 8 → 5
- **回退**：git reset 434006d --hard + 重新设计

### 风险 3：main 意外污染
- **缓解**：保持调研分支，**不创建新分支**，**不合并到 main**
- **回退**：`git checkout main && git reset --hard origin/main`

## 5. 完成定义（DoD）

- [ ] T1-T10 全 done
- [ ] unit test 47 + 整库 1300+ 全 pass
- [ ] extended smoke 4 block commits≥3 + HABITUAL≥1
- [ ] commit 已 push 到远端 `research/R-PROTO-LEARN-appraisal-multi-mechanism`
- [ ] main 仍是 `15b4650`（无任何变更）
- [ ] final report 已写给小黑
