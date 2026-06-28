# M4 Active Inference Owner 需求

## 背景

v3 设计原则 §2.2: Layer 1 Active Inference Subsystem 负责:
- 8 维 generative model (hierarchical)
- variational free energy minimization (v3.0 proxy / v3.1 真 VFE)
- active sampling (policy gradient)

**目前 M1+M2+M3 wave 完成后,缺少**:
- 5 层 HierarchicalGenerativeModel(从 sensory 到 latent)
- proxy_free_energy 实施(诚实的 proxy, NOT 真 VFE)
- predict / compute_proxy_free_energy / minimize_proxy_free_energy / active_sampling 接口
- M8 variational_free_energy_TRUE placeholder(接口预留)

没有 Layer 1,v3 self-evidencing 循环的"minimize F"环节缺失,Layer 2 self-model 的输入 I 缺乏 active sampling 来源。

## 目标

实现 `ActiveInferenceOwner`(Layer 1),提供:

1. **HierarchicalGenerativeModel (5 层)**:
   - Layer dims: sensory(8) → low(16) → mid(8) → high(4) → latent(2)
   - 4 个权重矩阵 (top-down: latent → sensory)
   - generate(latent) → sensory 重建
   - recognize(sensory) → latent 推断
   - train_step(sensory, n_optim_steps) → 优化 latent 最小化 reconstruction error

2. **proxy_free_energy**:**严格 disclaimer, NOT 真 VFE**
   - F = sum((predicted - actual)²)
   - docstring 明确说明是简化版
   - 真 VFE = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]

3. **ActiveInferenceOwner** 4 大方法:
   - `predict(sensory_input) → 8-dim predicted`
   - `compute_proxy_free_energy(sensory_input) → scalar F`
   - `minimize_proxy_free_energy(sensory_input, n_steps) → latent`
   - `active_sampling(sensory_input, n_candidates) → ActionPolicy`

4. **M8 placeholder**:
   - `variational_free_energy_TRUE() → NotImplementedError`
   - 错误信息明确说明 "M8 placeholder"

5. **ActionPolicy** frozen dataclass:
   - action_id / action_vector / expected_proxy_free_energy / confidence

## 验收标准(v3 task §2.2)

1. ✅ 5 层 generative model 正确(layer dims + weight shapes)
2. ✅ proxy_free_energy 计算正确,**明确标注是 proxy**(docstring 测试)
3. ✅ 单调下降验证(monotonic decreasing under gradient descent)
4. ✅ 跟 v3.1 VFE 接口兼容(variational_free_energy_TRUE placeholder)
5. ✅ 1000 tick 不崩溃
6. ✅ 39 个 M4 测试全过(M1+M2+M3+M4 = 232 passed)

## 范围

✅ 包含:
- `HierarchicalGenerativeModel`(5 层 + Glorot init)
- `proxy_free_energy` module-level function
- `compute_proxy_free_energy(hgm, latent, actual)` helper
- `ActiveInferenceOwner` 类(4 大方法 + M8 placeholder)
- `ActionPolicy` frozen dataclass
- `ActiveInferenceStats` dataclass
- 39 个测试
- 1000-tick 探针 + 单调下降验证

❌ 不包含:
- 真 VFE 用 PyMC/NumPyro(M8)
- 权重学习(M4 只优化 latent,不优化权重)
- Bayesian inference / KL divergence estimation(M8)
- Hierarchical message passing(Friston 2010 严格分层,M4 简化版)

## 不在范围

- M8 真 VFE 实现(M8 task)
- M5 System Prompt + CSO(M5 task)
- 跟 v2 RealRPE 集成(M6+)