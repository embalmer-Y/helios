# M1-T5 SelfModelOwner 任务清单

## Step 1: 写 `self_model.py`

- [x] dataclass `SelfModelOwner` (cds, emergence, tick_count, experience_history)
- [x] `__post_init__` 初始化空 list(防 mutable default 陷阱)
- [x] `tick(I=None, reflect=None, reward=0.0) -> dict`
  - [x] cds.tick(I=I)
  - [x] emergence.detect(cds)
  - [x] self_experience = cds.self_experience()
  - [x] tick_count += 1, history.append
  - [x] return full dict
- [x] `get_state_for_llm() -> dict`
  - [x] state.copy()
  - [x] C 矩阵统计 (max, mean, top3 eig)
  - [x] R, rochat_level_*, self_unity, agency_strength, tick_count
- [x] `seed_prior_state(state, C=None)`
- [x] `default()` classmethod
- [x] `to_dict() / from_dict()` 预留(checkpoint 用,M2 启用)

## Step 2: 更新 `__init__.py`

- [x] 添加 `from .self_model import SelfModelOwner`
- [x] 添加到 `__all__`

## Step 3: 写测试 `test_emergence_and_self_model.py`

- [x] `TestSelfModelOwner` 8 个测试
- [x] `TestSelfModelOwnerEndToEnd` 2 个测试
- [x] 全部通过

## Step 4: 写探针 `r_v3_m1_t56_probe.py`

- [x] 1000 tick
- [x] 输出 trace + summary JSON
- [x] 检查 solver/NAN/emergence

## Step 5: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md (完成后补)

## Step 6: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)