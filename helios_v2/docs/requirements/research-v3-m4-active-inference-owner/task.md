# M4 Active Inference Owner 任务清单

## Step 1: 写 `__init__.py` (M4 package)

- [x] 创建 `helios_v2/src/helios_v2/research_v3_m4/__init__.py`
- [x] 导出 HGM / HGM_LAYER_DIMS / HGM_LAYER_NAMES / DEFAULT_HGM_LR
- [x] 导出 ActiveInferenceOwner / proxy_free_energy / compute_proxy_free_energy
- [x] 导出 ActionPolicy / ActiveInferenceStats

## Step 2: 写 `hierarchical_generative_model.py`

- [x] HGM_LAYER_DIMS 常量 (8, 16, 8, 4, 2)
- [x] HGM_LAYER_NAMES 常量
- [x] DEFAULT_HGM_LR 常量 (0.01)
- [x] `HierarchicalGenerativeModel` dataclass
  - [x] weights / biases / lr / forward_cache / last_recognition_error
  - [x] `__post_init__` 调用 _init_weights + _init_biases
  - [x] `_init_weights` Glorot init,4 个权重矩阵 top-down
  - [x] `_init_biases` 4 个 bias 对应每层输出
  - [x] `generate(latent) → 8-dim sensory`
  - [x] `recognize(sensory) → 2-dim latent`
  - [x] `compute_reconstruction(latent, target) → (recon, error)`
  - [x] `train_step(sensory, latent, n_optim_steps)` 用数值梯度
  - [x] `_numerical_gradient(latent, target, eps)` 中心差分
  - [x] `get_weights_summary()`

## Step 3: 写 `active_inference_owner.py`

- [x] `proxy_free_energy(predicted, actual)` module-level,**严格 disclaimer**
- [x] `compute_proxy_free_energy(hgm, latent, actual)` helper
- [x] `ActionPolicy` frozen dataclass
- [x] `ActiveInferenceStats` dataclass
- [x] `ActiveInferenceOwner` 类
  - [x] `__init__` (hgm, lr, n_minimization_steps, seed)
  - [x] `predict(sensory_input) → 8-dim`
  - [x] `compute_proxy_free_energy(sensory_input) → float`
  - [x] `minimize_proxy_free_energy(sensory_input, n_steps) → latent`
  - [x] `active_sampling(sensory_input, n_candidates) → ActionPolicy`
  - [x] `variational_free_energy_TRUE()` raises NotImplementedError(M8 placeholder)
  - [x] `tick(sensory_input, do_minimize, do_active_sampling) → dict`
  - [x] `get_stats()` / `get_proxy_free_energy_history()`
  - [x] `is_proxy_free_energy_monotonically_decreasing(last_n, tolerance)`

## Step 4: 写测试 `test_active_inference_owner.py`

- [x] `TestHierarchicalGenerativeModel` (8 tests)
- [x] `TestTrainStep` (3 tests)
- [x] `TestProxyFreeEnergy` (5 tests,含 docstring disclaimer 测试)
- [x] `TestActiveInferenceOwner` (10 tests)
- [x] `TestVariationalFreeEnergyTrue` (1 test)
- [x] `TestActiveInferenceTick` (5 tests)
- [x] `TestMonotonicallyDecreasing` (2 tests)
- [x] `TestStats` (2 tests)
- [x] `TestEndToEnd` (3 tests)
- [x] **总计 39 tests 全过**

## Step 5: 写探针 `r_v3_m4_probe.py`

- [x] Test 1: fixed sensory + 1000 gradient steps → monotonic decreasing 验证
- [x] Test 2: 1000 tick AI loop 稳定
- [x] Test 3: variational_free_energy_TRUE placeholder raises
- [x] 输出 summary + trace JSON
- [x] 全局断言:0 NaN, monotonic decreasing True, placeholder raises

## Step 6: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md

## Step 7: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)