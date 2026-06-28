# M3 Boundary Owner 设计

## 架构

```
                External World (外部世界)
                       |
                       | signals (sensory)
                       v
        +-------------------------------+
        |  MarkovBlanketBoundary (MB)   |  <-- Layer 0 (严格 MB)
        |  - 4 类信号检查                |
        |  - conditional_separation 验证 |
        |  - 状态缓冲 (3 组样本)        |
        +-------------------------------+
                       |
                       v
        +----+----------+------+--------+
        | L1 |  L2     |  L3  |   L4   |  <-- 4 nested subsystems
        | AI | SelfModel| Refl | Evol   |     共享 1 个 MB
        +----+----------+------+--------+
                       |
                       | signals (active)
                       v
                External World
```

## 4 类信号

```python
class SignalType(str, Enum):
    SENSORY = "sensory"      # world → system(允许)
    ACTIVE = "active"        # system → world(允许)
    INTERNAL = "internal"    # system 内部(拒绝穿越)
    EXTERNAL = "external"    # world 外部状态(拒绝进入 system)
```

**关键约束**(Pearl 1995 风格):
- 只有 sensory 和 active 信号允许穿越 MB
- internal 和 external 信号尝试穿越 MB → deny
- 这保证 system 内部状态**只**通过 sensory 输入影响

## 数学不变量验证

**核心定理**(v3 design §2.1):
$$\text{internal} \perp\!\!\!\perp \text{external} | \text{sensory}$$

**两种检验方法**:

### 1. 偏相关系数(linear)
```python
def partial_corr(internal, external, sensory):
    # 残差化 internal 和 external(对 sensory 回归)
    internal_resid = internal - proj(internal | sensory)
    external_resid = external - proj(external | sensory)
    # 残差之间的 Pearson r
    return np.corrcoef(internal_resid, external_resid)[0, 1]
```

**通过条件**: |partial_corr| < threshold (默认 0.1) AND p_value > 0.05

### 2. 互信息(non-linear, 辅助)
- 用直方图估计 MI(internal; external)
- 作为 partial_corr 的辅助检验(对非线性关系更敏感)

## MarkovBlanketBoundary 数据结构

```python
@dataclass
class MarkovBlanketBoundary:
    threshold: float = 0.1               # partial_corr |阈值
    max_samples: int = 1000              # 状态缓冲最大长度
    min_samples_for_check: int = 30     # 检验最小样本数

    _internal_samples: dict              # subsystem_name → samples
    _external_samples: list[float]
    _sensory_samples: list[float]

    sensory_signals: list[Signal]        # 通过的 sensory 信号
    active_signals: list[Signal]         # 通过的 active 信号
    external_signals: list[Signal]       # 外部信号(audit 用)
```

## BoundaryOwner 数据结构

```python
class BoundaryOwner:
    subsystems: dict[str, NestedSubsystem]  # 4 nested subsystems
    mb: MarkovBlanketBoundary               # 1 shared MB
    partial_corr_threshold: float = 0.1
    enforce_separation_check: bool = True   # 是否强制不变量检查

    audit_log: list[BoundaryCrossing]       # 所有 crossing 记录
    _n_admitted: int
    _n_denied: int
```

## check_signal 决策树

```
signal received
     |
     v
signal type?
     |
     +--- SENSORY ---> base_admit=True
     |                    |
     |                    v
     |             enforce_check?
     |                    |
     |                    +--- YES ---> check_separation(subsystem)
     |                    |                 |
     |                    |                 +--- PASS ---> admit
     |                    |                 +--- FAIL ---> deny
     |                    +--- NO ----> admit
     |
     +--- ACTIVE ----> same as SENSORY
     |
     +--- INTERNAL --> deny (reason: "should not cross MB")
     |
     +--- EXTERNAL --> deny (reason: "should not enter system")
     |
     v
   write audit log
   update stats
```

## check_signal_dry(测试用)

跟 check_signal 区别:**不**自动调用 `_on_signal_admitted` 记录到 MB。

**为什么需要**:probe / 测试需要手动控制 3 组样本对齐。如果让 check_signal 自动记录,样本数会不对齐,导致 separation check 返回 nan。

**典型用法**:
```python
# 用 check_signal_dry 走 audit log,但不污染 MB 缓冲
bo.check_signal_dry(sensory_signal)

# 手动控制 MB 样本(对齐 3 组)
bo.mb.record_sensory(...)
bo.mb.record_internal(name, ...)
bo.mb.record_external(...)

# 然后验证不变量
result = bo.mb.check_separation(name, method="partial_correlation")
```

## 5 nested subsystems 共享 1 MB

```python
subsystems = {
    "active_inference": NestedSubsystem(name="active_inference", state=..., layer=1),
    "self_model":       NestedSubsystem(name="self_model", state=..., layer=2),
    "reflection":       NestedSubsystem(name="reflection", state=..., layer=3),
    "evolution":        NestedSubsystem(name="evolution", state=..., layer=4),
}
bo = BoundaryOwner(subsystems=subsystems, mb=MarkovBlanketBoundary(...))
```

**关键**:
- 1 个 BoundaryOwner 实例 = 1 个 MB(共享)
- 4 个 NestedSubsystem 都通过 update_subsystem() 跟 MB 交互
- MB 内部按 subsystem 分别记录 internal 样本(dict)

## 25 stage 22 接入

```python
def stage_22_boundary_enforcement(self) -> dict:
    sep_results = self.mb.check_all_subsystems(method="partial_correlation")
    all_passed = all(r.passed for r in sep_results.values())
    return {
        "stage": 22,
        "stage_name": "BoundaryEnforcement",
        "all_separations_passed": all_passed,
        "separation_results": {name: {...} for name, r in sep_results.items()},
        "n_admitted": self._n_admitted,
        "n_denied": self._n_denied,
        "audit_log_size": len(self.audit_log),
    }
```

**关键**:简化版 25 stage chain,只实现 stage 22。完整 chain(stage 1-21 + 23-25)留到 M5+ 真集成阶段。

## 测试覆盖(45 个)

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestSignal` | 5 | 4 types / frozen / 唯一 ID / timestamp / 多 payload |
| `TestMarkovBlanketBoundary` | 5 | 默认构造 / max_samples / 未知 subsystem / 类型验证 |
| `TestConditionalSeparation` | 7 | 完美独立 / 违反 / 样本不足 / length mismatch / 阈值 / MI / frozen |
| `TestBoundaryOwnerCheckSignal` | 7 | 4 信号类型 + 空 subsystems + audit log + 计数 |
| `TestBoundaryOwnerAuditLog` | 5 | 过滤 type / admitted_only / clear / frozen / to_dict |
| `TestBoundaryOwnerSubsystemUpdate` | 4 | 记录 internal / 全记录 / 未知 / 自定义 update_fn |
| `TestBoundaryOwnerEmitActive` | 2 | 返回 signal / admitted |
| `TestBoundaryOwnerSeparationEnforcement` | 3 | disable / 违反 deny / 成立 admit |
| `TestBoundaryOwnerStage22` | 3 | dict / separation results / all_passed |
| `TestEndToEnd` | 4 | 1000 tick / 5 subsystems 共享 MB / filter / stats |

## 关键设计决策

### 决策 1:partial_corr 作为主检验,MI 作为辅助

**理由**:
- partial_corr 速度快(线性回归 + Pearson r),适合 1000-tick 实时检验
- MI 估计有 binning bias,只作辅助
- M3 阶段不引入非线性检验(HSIC, d-separation exact),留到 M5+ 真 LLM 阶段

### 决策 2:enforce_separation_check 默认 False

**理由**:
- 默认关闭,避免误判(false positive 拒绝合法信号)
- 真实部署时由运维开启
- 测试用 True 验证 enforce 路径

### 决策 3:check_signal_dry 作为独立方法(非 flag)

**理由**:
- 显式比隐式好(dry 模式是真实用例,不是 hack)
- 减少隐式状态(auto-record 让 probe 难控制样本对齐)
- 跟 check_signal 行为差异明显,便于 review

### 决策 4:audit log 永不清空(except 显式 clear)

**理由**:
- audit 是合规要求(v3 design §5.5)
- 只在测试 / 内存压力下清空
- clear_audit_log() 返回数量,便于监控

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| partial_corr 不能检测非线性关系 | MI 辅助检验;M5+ 引入 HSIC |
| 样本不足导致 nan | min_samples_for_check=30 保护 |
| 5 subsystems 共享 MB 但实际可能不独立 | per-subsystem internal_samples dict |
| runtime/stages.py 完整 25 stage 接入复杂 | M3 只实现 stage 22,其余留到 M5+ |
| check_signal 内部信号验证可能误判 | 4 信号类型 + conditional_separation 双层检查 |