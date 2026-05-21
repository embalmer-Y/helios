"""
X6: 异稳态调节器 (AllostaticRegulator)
=======================================

科学基础:
  · Sterling & Eyer (1988) Allostasis: 通过变化维持稳定
  · McEwen (1998) Allostatic Load: 累积适应成本
  · Schulkin (2003) Rethinking Homeostasis

核心区分:
  Homeostasis:  维持固定 setpoint (恒温器)
  Allostasis:   根据预测需求调整 setpoint (智能恒温器)

设计:
  · setpoint[sys] = baseline[sys] + predicted_demand[sys] + load_penalty
  · 双向调节: 可上调也可下调
  · Allostatic Load 累积 → 疲劳感 → 需要静息期恢复
  · 预测需求基于近期激活历史

文件: allostasis.py
依赖: helios_utils (clamp)
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from helios_utils import clamp
import math


# ═══════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════

PANKSEPP_SYSTEMS = ["SEEKING", "PLAY", "CARE", "PANIC", "FEAR", "RAGE", "LUST"]

@dataclass
class AllostasisConfig:
    """异稳态配置参数"""
    
    # 预测需求: EMA 系数
    demand_alpha: float = 0.7     # 历史权重 (高=慢适应)
    demand_beta: float = 0.3      # 新信息权重 (低=不敏感)
    
    # 负荷累积
    load_accum_rate: float = 0.02  # 每周期负荷累积率
    load_decay_rate: float = 0.999 # 负荷衰减率 (极慢, 0.999^500=0.606)
    
    # 负荷效应
    load_fatigue_threshold: float = 0.3  # 负荷超此值 → 疲劳
    load_anhedonia_threshold: float = 0.6  # 负荷超此值 → 快感缺失
    load_penalty_max: float = 0.4    # 最大惩罚幅度
    
    # setpoint 漂移限幅
    setpoint_min: float = 0.02
    setpoint_max: float = 0.85
    drift_rate: float = 0.05  # setpoint 每周期最大漂移
    
    # 恢复
    recovery_threshold: float = 0.15  # 负荷低于此 → 恢复期
    recovery_boost: float = 0.02      # 恢复期 setpoint 回升速率


# ═══════════════════════════════════════════════
# 系统状态
# ═══════════════════════════════════════════════

@dataclass
class AllostaticState:
    """单个系统的异稳态状态"""
    setpoint: float = 0.05          # 当前 setpoint (目标值)
    predicted_demand: float = 0.0   # 预测需求
    allostatic_load: float = 0.0    # 累积负荷
    baseline: float = 0.05          # 原始基线
    
    # 统计
    peak_activation: float = 0.0
    recent_activations: List[float] = field(default_factory=list)
    recent_max_len: int = 50
    
    def update_demand(self, current_activation: float, config: AllostasisConfig):
        """更新预测需求 (基于近期峰值)"""
        self.recent_activations.append(current_activation)
        if len(self.recent_activations) > self.recent_max_len:
            self.recent_activations.pop(0)
        
        # 近期最大值 (EMA)
        if self.recent_activations:
            recent_max = max(self.recent_activations[-20:]) if len(self.recent_activations) >= 20 else current_activation
            self.predicted_demand = clamp(
                config.demand_alpha * self.predicted_demand
                + config.demand_beta * recent_max,
                0.0, 1.0
            )
        
        # 峰值记忆 (慢衰减)
        self.peak_activation = max(self.peak_activation * 0.995, current_activation)
    
    def accumulate_load(self, config: AllostasisConfig):
        """累积异稳态负荷"""
        deviation = abs(self.setpoint - self.baseline)
        self.allostatic_load += deviation * config.load_accum_rate
        # 缓慢自发衰减
        self.allostatic_load *= config.load_decay_rate
        self.allostatic_load = clamp(self.allostatic_load, 0.0, 1.0)
    
    def update_setpoint(self, config: AllostasisConfig):
        """更新 setpoint = baseline + demand - load_penalty"""
        # 需求推动 setpoint 上移
        demand_contribution = self.predicted_demand * 0.3
        
        # 负荷惩罚
        load_penalty = 0.0
        if self.allostatic_load > config.load_fatigue_threshold:
            # 疲劳: setpoint 下移
            fatigue = (self.allostatic_load - config.load_fatigue_threshold) / (
                1.0 - config.load_fatigue_threshold
            )
            load_penalty = fatigue * config.load_penalty_max
        
        if self.allostatic_load > config.load_anhedonia_threshold:
            # 快感缺失: 正向系统 setpoint 额外下移
            pass  # 在 AllostaticRegulator 层处理
        
        # 恢复检查
        recovery = 0.0
        if self.allostatic_load < config.recovery_threshold and self.predicted_demand < 0.2:
            recovery = config.recovery_boost  # 回到基线
        
        # 新的 setpoint (朝目标缓慢漂移)
        target = clamp(
            self.baseline + demand_contribution - load_penalty + recovery,
            config.setpoint_min, config.setpoint_max
        )
        
        # 限制漂移速率
        drift = target - self.setpoint
        max_drift = config.drift_rate
        drift_clamped = clamp(drift, -max_drift, max_drift)
        self.setpoint = clamp(self.setpoint + drift_clamped, config.setpoint_min, config.setpoint_max)
    
    def to_dict(self) -> dict:
        return {
            "setpoint": round(self.setpoint, 4),
            "predicted_demand": round(self.predicted_demand, 4),
            "allostatic_load": round(self.allostatic_load, 4),
            "peak_activation": round(self.peak_activation, 4),
        }


# ═══════════════════════════════════════════════
# 异稳态调节器
# ═══════════════════════════════════════════════

class AllostaticRegulator:
    """
    异稳态调节器 — 替代粗糙的 homeostatic_pressure
    
    用法:
        ar = AllostaticRegulator()
        
        # 每周期:
        activations = daisy.cycle(triggers).panksepp_activation
        ar.update(activations)  # 更新预测需求+负荷
        
        # 获取调节后的激活:
        modulated = ar.regulate(activations)
        # → 激活被拉向 setpoint (可上可下)
    
    数学:
        setpoint[t] = baseline + α×demand[t] - β×load[t]
        activation[t] → activation[t] + γ × (setpoint[t] - activation[t])
    
    与 v2.5 的对比:
        v2.5:  only downward, fixed baseline, no load
        X6:    bidirectional, dynamic setpoint, load accumulation
    """
    
    def __init__(self, config: Optional[AllostasisConfig] = None):
        self.cfg = config or AllostasisConfig()
        
        # 每个系统一个状态
        self.states: Dict[str, AllostaticState] = {}
        for sys_name in PANKSEPP_SYSTEMS:
            self.states[sys_name] = AllostaticState(
                baseline=0.05,
                setpoint=0.05,
            )
        
        # 全局统计
        self.total_cycles = 0
        self.fatigue_cycles = 0  # 疲劳周期数
        self.recovery_cycles = 0
    
    def update(self, activations: Dict[str, float]):
        """
        更新异稳态状态
        
        Args:
            activations: {"SEEKING": 0.4, "FEAR": 0.3, ...}
        """
        self.total_cycles += 1
        
        for sys_name, state in self.states.items():
            current_act = activations.get(sys_name, state.baseline)
            
            # 1. 更新预测需求
            state.update_demand(current_act, self.cfg)
            
            # 2. 累积负荷
            state.accumulate_load(self.cfg)
            
            # 3. 更新 setpoint
            state.update_setpoint(self.cfg)
        
        # 全局疲劳检测
        total_load = sum(s.allostatic_load for s in self.states.values()) / len(self.states)
        if total_load > self.cfg.load_fatigue_threshold:
            self.fatigue_cycles += 1
        elif total_load < self.cfg.recovery_threshold:
            self.recovery_cycles += 1
    
    def regulate(self, activations: Dict[str, float]) -> Dict[str, float]:
        """
        调节激活 → 朝 setpoint 拉近
        
        Args:
            activations: 当前激活
        
        Returns:
            调节后的激活
        """
        regulated = {}
        for sys_name, act in activations.items():
            state = self.states.get(sys_name)
            if state is None:
                regulated[sys_name] = act
                continue
            
            sp = state.setpoint
            
            # 快感缺失: 高负荷 → 正向系统无法激活
            if sys_name in ("SEEKING", "PLAY", "CARE", "LUST"):
                if state.allostatic_load > self.cfg.load_anhedonia_threshold:
                    # 正向系统被压缩
                    anhedonia = (state.allostatic_load - self.cfg.load_anhedonia_threshold) / (
                        1.0 - self.cfg.load_anhedonia_threshold
                    )
                    sp = max(sp, state.baseline * 0.5)  # 至少有一半基线
                    act = act * (1.0 - anhedonia * 0.6)  # 快感缺失惩罚
            
            # 朝 setpoint 拉近 (γ=0.15 调节速率)
            pull_rate = 0.15
            regulated[sys_name] = clamp(
                act + (sp - act) * pull_rate,
                0.0, 1.0
            )
        
        return regulated
    
    def get_load_level(self) -> float:
        """全局负荷水平 (0-1)"""
        if not self.states:
            return 0.0
        return sum(s.allostatic_load for s in self.states.values()) / len(self.states)
    
    def get_dominant_setpoint(self) -> str:
        """当前最高 setpoint 的系统"""
        return max(self.states, key=lambda s: self.states[s].setpoint)
    
    def is_fatigued(self) -> bool:
        """是否处于疲劳状态"""
        return self.get_load_level() > self.cfg.load_fatigue_threshold
    
    def is_recovering(self) -> bool:
        """是否处于恢复期"""
        return (self.get_load_level() < self.cfg.recovery_threshold
                and self.fatigue_cycles > 0)
    
    def snapshot(self) -> dict:
        """完整快照"""
        return {
            "total_cycles": self.total_cycles,
            "fatigue_cycles": self.fatigue_cycles,
            "recovery_cycles": self.recovery_cycles,
            "global_load": round(self.get_load_level(), 4),
            "is_fatigued": self.is_fatigued(),
            "is_recovering": self.is_recovering(),
            "systems": {
                sys: state.to_dict()
                for sys, state in self.states.items()
            },
        }
    
    def set_baseline(self, sys_name: str, value: float):
        """设置系统基线 (由 PersonalityProfile 调用)"""
        if sys_name in self.states:
            self.states[sys_name].baseline = clamp(value, 0.01, 0.5)
            self.states[sys_name].setpoint = clamp(
                self.states[sys_name].setpoint,
                0.01, 0.85
            )
    
    def reset(self):
        """重置所有状态"""
        for state in self.states.values():
            state.setpoint = state.baseline
            state.predicted_demand = 0.0
            state.allostatic_load = 0.0
            state.peak_activation = 0.0
            state.recent_activations.clear()
        self.total_cycles = 0
        self.fatigue_cycles = 0
        self.recovery_cycles = 0
