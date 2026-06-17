# R-PROTO-LEARN Tier 1 Tasks (R11-R15)

## 总体任务 (R11-R15 1 commit ship)

### 阶段 1: 统一学习框架 (T1-T2)
- [ ] T1: 创建 `helios_v2/learning/` 目录
- [ ] T2: 写 `helios_v2/learning/contracts.py` (LearnerConfig, Regime, Learner Protocol)
- [ ] T3: 写 `helios_v2/learning/framework.py` (LearnerABC 通用基类 + numpy pinv closure)
- [ ] T4: 写 `helios_v2/learning/__init__.py` (统一导出)

### 阶段 2: 5 owner learner 子类 (T5-T9)
- [ ] T5: R11 `helios_v2/learning/memory_learner.py` (owner 06)
  - [ ] T5a: `MemoryLearnerConfig` (5-dim input, 3 policies)
  - [ ] T5b: `MemoryLearner` 子类 (3 policies: replay/priority/consolidation/family_write)
  - [ ] T5c: owner 06 memory/engine.py 集成 opt-in `p5_learner` 字段
- [ ] T6: R12 `helios_v2/learning/thought_gating_learner.py` (owner 09)
  - [ ] T6a: `ThoughtGatingLearnerConfig` (6-dim signal input, 4-dim continuation, 5-dim gate)
  - [ ] T6b: `ThoughtGatingLearner` 子类
  - [ ] T6c: owner 09 thought_gating/engine.py 集成
- [ ] T7: R13 `helios_v2/learning/retrieval_learner.py` (owner 10)
  - [ ] T7a: `RetrievalLearnerConfig` (6-dim tier, 5-dim planning, 4-dim window)
  - [ ] T7b: `RetrievalLearner` 子类
  - [ ] T7c: owner 10 directed_retrieval/engine.py 集成
- [ ] T8: R14 `helios_v2/learning/internal_thought_learner.py` (owner 11)
  - [ ] T8a: `InternalThoughtLearnerConfig` (6-dim generation, 4-dim sufficiency, 5-dim emission)
  - [ ] T8b: `InternalThoughtLearner` 子类
  - [ ] T8c: owner 11 internal_thought/engine.py 集成
- [ ] T9: R15 `helios_v2/learning/autonomy_learner.py` (owner 18)
  - [ ] T9a: `AutonomyLearnerConfig` (7-dim drive, 4-dim carry, 5-dim proactive)
  - [ ] T9b: `AutonomyLearner` 子类
  - [ ] T9c: owner 18 autonomy/engine.py 集成

### 阶段 3: 单元测试 (T10-T15)
- [ ] T10: `tests/test_learning_framework.py` (统一框架 16+ test)
  - [ ] numpy pinv helper
  - [ ] 3 态 Regime 切换
  - [ ] DA precision gate
  - [ ] ACh flexibility gate
  - [ ] commit_if_stable
  - [ ] module requires numpy (硬耦合)
- [ ] T11: `tests/test_r_proto_learn_11_memory_learner.py` (16+ test)
- [ ] T12: `tests/test_r_proto_learn_12_thought_gating_learner.py` (16+ test)
- [ ] T13: `tests/test_r_proto_learn_13_retrieval_learner.py` (16+ test)
- [ ] T14: `tests/test_r_proto_learn_14_internal_thought_learner.py` (16+ test)
- [ ] T15: `tests/test_r_proto_learn_15_autonomy_learner.py` (16+ test)

### 阶段 4: 真 LLM smoke (T16)
- [ ] T16: `scripts/r_proto_learn_tier1_smoke.py` (4 block × 48 对话)
  - [ ] 5 owner 旁路同时跑
  - [ ] 验证 P5 learning 不破坏 canonical state
  - [ ] 比较 R11-R15 之前 vs 之后

### 阶段 5: 整库验证 (T17)
- [ ] T17: 整库跑
  - [ ] R21 guard clean
  - [ ] 1440+ passed (1368 baseline + 80+ new)
  - [ ] 5 failed 是 main 已有失败（与 R11-R15 无关）

### 阶段 6: 文档 + commit (T18-T20)
- [ ] T18: 4 件套调研文档
  - [ ] requirement.md ✅
  - [ ] design.md ✅
  - [ ] task.md ✅ (本文件)
  - [ ] result.md (T20)
- [ ] T19: 1 commit ship 5 slice
  - [ ] `git -C /root/project/helios add ...`
  - [ ] `git -C /root/project/helios commit -m "feat(R-PROTO-LEARN.Tier1): R11-R15 神经机制对位 5 owner 真学习"`
  - [ ] `git -C /root/project/helios push origin research/R-PROTO-LEARN-appraisal-multi-mechanism`
- [ ] T20: 写 result.md (实施后总结 + 数据对比)

## 验收标准
- 80+ 新 unit test 全 pass
- 整库 1440+ passed
- 真 LLM smoke 跑通
- R21 guard clean
- 调研分支不 merge main
- 1 commit ship 5 slice

## 风险
- 5 owner 同时集成测试可能超 timeout → 分批跑
- W 矩阵 dim 跟 state 字段对不上 → 每个 owner 仔细 audit
- 真 LLM 性能 → 旁路 opt-in 默认 None 关闭

## 进度节点
- 阶段 1-2 编码 (~30 分钟)
- 阶段 3 测试 (~30 分钟)
- 阶段 4-5 验证 (~30 分钟)
- 阶段 6 文档+commit (~10 分钟)
- **总计 ~1.5-2 小时**
