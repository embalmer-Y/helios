# M3 Boundary Owner 需求

## 背景

v3 设计原则 §0:"v3 = 5 个嵌套自组织系统(仅最外层为严格 Markov blanket)"。Layer 0 Markov Blanket 是 v3 的**唯一**严格 Markov blanket,维护以下数学不变量:

$$p(\text{int}, \text{ext} | \text{sensory}) = p(\text{int} | \text{sensory}) \cdot p(\text{ext} | \text{sensory})$$

即:在给定 sensory 的条件下,internal 和 external 条件独立。

**目前 M1+M2 wave 完成后,缺少**:
- Layer 0 Markov Blanket 实现
- 4 类信号定义(sensory / active / internal / external)
- conditional_separation 验证方法
- 5 nested subsystems 共享 1 MB 的协调机制
- 25 stage 22 BoundaryEnforcement 接入

没有 Layer 0,v3 设计中"5 个嵌套自组织系统由 1 个 MB 保护"的架构承诺无法验证。

## 目标

实现 `BoundaryOwner`(Layer 0 边界 owner),提供:

1. **4 类信号定义**:SignalType enum + Signal frozen dataclass
   - SENSORY: world → system
   - ACTIVE: system → world
   - INTERNAL: system 内部(不穿越 MB)
   - EXTERNAL: world 外部(不直接进入 system)

2. **MarkovBlanketBoundary**:数学不变量验证器
   - 3 组状态缓冲:internal_samples / sensory_samples / external_samples
   - 2 种独立性检验:
     - `check_conditional_separation_partial_corr`(线性,fast)
     - `check_conditional_separation_mutual_info`(非线性,辅助)

3. **BoundaryOwner**:协调 4 nested subsystems + 1 MB
   - `check_signal(signal)` - 检查信号是否允许穿越 MB
   - `update_subsystem(name, sensory)` - 更新子系统 + 记录 internal 状态
   - `emit_active(source, target, payload)` - 子系统发 active 信号
   - `record_external(value)` - 记录外部世界状态
   - `stage_22_boundary_enforcement()` - 25 stage 接入

4. **Audit log**:所有 boundary_crossing 记录
   - BoundaryCrossing frozen dataclass
   - 支持按 signal_type 过滤 + admitted_only 过滤
   - to_dict() 输出结构化日志

5. **`check_signal_dry()`** 不自动记录模式(probe / 测试用)

## 验收标准

1. ✅ 4 信号类型处理正确(sensory/active admit,internal/external deny)
2. ✅ conditional_separation 数学不变量在受控样本下能检测违反
3. ✅ 1000 tick 不崩溃
4. ✅ Stage 22 BoundaryEnforcement 返回正确 separation 结果
5. ✅ 45 个 M3 测试全过(M1+M2+M3 = 193 passed)
6. ✅ audit_log 完整记录所有 crossing

## 范围

✅ 包含:
- `Signal` + `SignalType`(4 类)
- `MarkovBlanketBoundary`(3 状态缓冲 + 2 种独立性检验)
- `ConditionalSeparationResult` frozen dataclass
- `NestedSubsystem` dataclass
- `BoundaryCrossing` frozen dataclass
- `BoundaryOwner` 类
- `check_signal_dry()` 不自动记录模式
- 45 个测试
- 1000-tick 探针

❌ 不包含:
- d-separation exact check(M5+ 真 LLM 阶段考虑)
- HSIC 或非线性检验(M3 阶段 partial_corr 已够)
- runtime/stages.py 升级(25 stage → stage 22 BoundaryEnforcement 的完整 chain 接入,留到 M5+)
- 跨 session audit log 持久化(M8)

## 不在范围

- 真 LLM 边界检查(M5-T1)
- 真 VFE 跟 MB 整合(M8)
- 跨 subsystem 信号路由的拓扑优化(M6+)