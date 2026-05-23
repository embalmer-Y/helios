"""
X5-2: 人格层 (PersonalityProfile)
==================================

科学基础:
  · Big Five → Panksepp 映射 (McCrae & Costa, 1997)
  · ALMA 第三层: Personality 是最稳定的层 (跨 session 持久)
  · Davis & Panksepp (2011): 人格特质与原始情感系统高度相关

映射关系:
  开放性 (Openness)      → SEEKING 放大
  外向性 (Extraversion)  → PLAY 放大
  宜人性 (Agreeableness) → CARE 放大
  神经质 (Neuroticism)   → FEAR + PANIC + RAGE 放大
  尽责性 (Conscientiousness) → SEEKING 目标导向增强

人格参数:
  · neuro_gains[sys]: 基线增益 (0.5-2.0)
  · chrono_mods[sys]: 时序调制系数
  · persist: 是否跨 session 持久

文件: personality.py
依赖: daisy_emotion (CHRONOMETRY)
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os
from utils import clamp


# ═══════════════════════════════════════════════
# Big Five → Panksepp 映射
# ═══════════════════════════════════════════════

# 默认人格: 中性 (所有系数=1.0)
DEFAULT_PERSONALITY = {
    "openness":          1.0,  # 开放性 → SEEKING
    "extraversion":      1.0,  # 外向性 → PLAY
    "agreeableness":     1.0,  # 宜人性 → CARE
    "neuroticism":       1.0,  # 神经质 → FEAR/PANIC/RAGE
    "conscientiousness": 1.0,  # 尽责性 → SEEKING(目标)
}

# Big Five → neuro_gains 转换矩阵
# 每个 Big Five 维度影响多个 Panksepp 系统
BIG5_TO_PANKSEPP = {
    # 开放性: SEEKING↑, PLAY↑
    "openness": {
        "SEEKING": 0.6,  # 60% 权重传到 SEEKING
        "PLAY":    0.15,
        "LUST":    0.1,
    },
    # 外向性: PLAY↑, LUST↑, SEEKING↑(社交好奇)
    "extraversion": {
        "PLAY":    0.55,
        "LUST":    0.2,
        "SEEKING": 0.15,
        "CARE":    0.05,
    },
    # 宜人性: CARE↑, RAGE↓
    "agreeableness": {
        "CARE":    0.50,
        "PLAY":    0.15,
        "RAGE":   -0.20,  # 负向: 宜人性高 → RAGE低
    },
    # 神经质: FEAR↑, PANIC↑, RAGE↑, SEEKING↓(焦虑抑制好奇)
    "neuroticism": {
        "FEAR":    0.40,
        "PANIC":   0.35,
        "RAGE":    0.15,
        "SEEKING": -0.05,  # 轻微信抑制
    },
    # 尽责性: SEEKING↑(目标导向研究), RAGE↓(自控)
    "conscientiousness": {
        "SEEKING": 0.35,
        "CARE":    0.10,
        "RAGE":   -0.10,
    },
}

# Big Five → 时序调制 (高神经质=更快上升/更慢衰减)
BIG5_TO_CHRONO = {
    "neuroticism": {
        "FEAR":  {"τ_rise_mult": 0.8, "τ_decay_mult": 1.3},  # 更快怕, 更难消
        "PANIC": {"τ_rise_mult": 0.85, "τ_decay_mult": 1.2},
        "RAGE":  {"τ_rise_mult": 0.9, "τ_decay_mult": 1.1},
    },
    "extraversion": {
        "PLAY":  {"τ_rise_mult": 0.85, "τ_decay_mult": 0.9},  # 更快乐, 更快消
        "LUST":  {"τ_rise_mult": 0.9, "τ_decay_mult": 0.95},
    },
}


# ═══════════════════════════════════════════════
# 人格档案
# ═══════════════════════════════════════════════

@dataclass
class PersonalityProfile:
    """
    人格档案 — ALMA 第三层
    
    特点:
      · 跨 session 持久 (保存为 JSON)
      · 极慢变化 (经历累积)
      · 调制 baseline + chronometry
    
    用法:
        pp = PersonalityProfile()
        
        # 获取神经增益:
        gains = pp.neuro_gains  # {"SEEKING": 1.0, ...}
        
        # 随着时间进化:
        pp.adapt(dominant_emotion, intensity, duration)
        
        # 持久化:
        pp.save("/path/to/profile.json")
        pp = PersonalityProfile.load("/path/to/profile.json")
    """
    
    # Big Five 原始分数 (0.5-2.0)
    openness: float = 1.0
    extraversion: float = 1.0
    agreeableness: float = 1.0
    neuroticism: float = 1.0
    conscientiousness: float = 1.0
    
    # 经历累积 (用于人格进化)
    experience_log: list[dict] = field(default_factory=list)
    total_emotion_cycles: int = 0
    
    # N4: 人格进化追踪
    trait_history: list[dict] = field(default_factory=list)
    _evolution_step: int = 0
    _emotion_accumulator: dict[str, float] = field(default_factory=lambda: {
        sys: 0.0 for sys in ["SEEKING","PLAY","CARE","PANIC","FEAR","RAGE","LUST"]
    })
    
    # 预计算缓存
    _neuro_gains: Optional[dict[str, float]] = None
    _chrono_mods: Optional[dict[str, dict]] = None
    
    def __post_init__(self):
        self._recompute()
    
    def _recompute(self):
        """根据 Big Five 重新计算神经增益和时序调制"""
        # 计算 neuro_gains
        gains = {sys: 1.0 for sys in ["SEEKING","PLAY","CARE","PANIC","FEAR","RAGE","LUST"]}
        
        bfs = {
            "openness": self.openness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
            "conscientiousness": self.conscientiousness,
        }
        
        for bf_name, bf_val in bfs.items():
            deviation = bf_val - 1.0  # 偏离中性
            mapping = BIG5_TO_PANKSEPP.get(bf_name, {})
            for sys_name, weight in mapping.items():
                gains[sys_name] += deviation * weight
        
        # 钳制
        self._neuro_gains = {
            sys: clamp(val, 0.3, 2.0)
            for sys, val in gains.items()
        }
        
        # 计算 chrono_mods
        mods = {}
        for bf_name, bf_val in bfs.items():
            deviation = bf_val - 1.0
            chrono_map = BIG5_TO_CHRONO.get(bf_name, {})
            for sys_name, chrono_effect in chrono_map.items():
                if sys_name not in mods:
                    mods[sys_name] = {"τ_rise_mult": 1.0, "τ_decay_mult": 1.0}
                mods[sys_name]["τ_rise_mult"] *= (
                    1.0 + deviation * (chrono_effect["τ_rise_mult"] - 1.0)
                )
                mods[sys_name]["τ_decay_mult"] *= (
                    1.0 + deviation * (chrono_effect["τ_decay_mult"] - 1.0)
                )
        
        # 钳制
        self._chrono_mods = {}
        for sys_name, mod in mods.items():
            self._chrono_mods[sys_name] = {
                "τ_rise_mult": clamp(mod["τ_rise_mult"], 0.5, 2.0),
                "τ_decay_mult": clamp(mod["τ_decay_mult"], 0.5, 2.0),
            }
    
    @property
    def neuro_gains(self) -> dict[str, float]:
        """Panksepp 神经增益 {系统名: 增益}"""
        if self._neuro_gains is None:
            self._recompute()
        return self._neuro_gains
    
    @property
    def chrono_mods(self) -> dict[str, dict]:
        """时序调制 {系统名: {τ_rise_mult, τ_decay_mult}}"""
        if self._chrono_mods is None:
            self._recompute()
        return self._chrono_mods
    
    def get_baseline(self, sys_name: str) -> float:
        """获取人格调制的基线激活"""
        base = {"SEEKING": 0.05, "PLAY": 0.05, "CARE": 0.05,
                "PANIC": 0.05, "FEAR": 0.05, "RAGE": 0.05, "LUST": 0.05}
        return base.get(sys_name, 0.05) * self.neuro_gains.get(sys_name, 1.0)
    
    def adapt(self, dominant_emotion: str, intensity: float, 
              duration: int = 1, valence: float = 0.0):
        """
        N4: 经历塑造人格 (极慢, β≈0.9999)
        
        Panksepp → Big Five 漂移 (Davis & Panksepp 2011, Roberts et al. 2006):
          SEEKING → openness+ (探索拓展认知边界)
          PLAY    → extraversion+ (社交嬉戏)
          CARE    → agreeableness+ (关怀增强共情)
          PANIC   → neuroticism+ (分离焦虑敏感化)
          FEAR    → neuroticism+ (恐惧敏感化)
          RAGE    → agreeableness-, neuroticism+ (愤怒侵蚀宜人)
          LUST    → extraversion+ (社交驱动)
        
        Args:
            dominant_emotion: 主导 Panksepp 系统
            intensity: 情感强度 (0-1)
            duration: 持续周期数
            valence: 效价
        """
        self.total_emotion_cycles += duration
        
        # minimal触发 (EMA累积场景acc可能低至0.08)
        if intensity < 0.08 or duration < 10:
            return
        
        self._evolution_step += 1
        
        # 学习率: 演示加速 (生产环境建议 0.00008)
        learning_rate = 0.002 * intensity * min(1.0, duration / 100)
        
        # Panksepp → Big Five 漂移
        if dominant_emotion == "SEEKING":
            self.openness += learning_rate * 1.2
            self.extraversion += learning_rate * 0.2
        elif dominant_emotion == "PLAY":
            self.extraversion += learning_rate * 1.0
            self.openness += learning_rate * 0.15
            self.agreeableness += learning_rate * 0.2
        elif dominant_emotion == "CARE":
            self.agreeableness += learning_rate * 1.5
            self.neuroticism -= learning_rate * 0.15
        elif dominant_emotion == "PANIC":
            self.neuroticism += learning_rate * 1.8
            self.extraversion -= learning_rate * 0.2
        elif dominant_emotion == "FEAR":
            self.neuroticism += learning_rate * 1.5
            self.openness -= learning_rate * 0.3
        elif dominant_emotion == "RAGE":
            self.agreeableness -= learning_rate * 1.0
            self.neuroticism += learning_rate * 0.8
        elif dominant_emotion == "LUST":
            self.extraversion += learning_rate * 0.8
        
        # 钳制
        for attr in ["openness", "extraversion", "agreeableness", 
                     "neuroticism", "conscientiousness"]:
            setattr(self, attr, clamp(getattr(self, attr), 0.3, 2.5))
        
        self._recompute()
        
        # 记录经历
        self.experience_log.append({
            "step": self._evolution_step,
            "emotion": dominant_emotion,
            "intensity": round(intensity, 3),
            "duration": duration,
            "valence": round(valence, 3),
            "total_cycles": self.total_emotion_cycles,
            "traits": self._trait_dict(),
        })
        if len(self.experience_log) > 500:
            self.experience_log = self.experience_log[-500:]
        
        # 每 5 步记录一次 trait 快照
        if self._evolution_step % 5 == 0:
            self.trait_history.append({
                "step": self._evolution_step,
                "total_cycles": self.total_emotion_cycles,
                "traits": self._trait_dict(),
            })
    
    def adapt_from_snapshot(self, dominant_emotion: str, intensity: float):
        """轻量累积器: 每周期调用, 每50周期触发一次 adapt"""
        # EMA 累积
        alpha = 0.95
        for sys_name in self._emotion_accumulator:
            if sys_name == dominant_emotion:
                self._emotion_accumulator[sys_name] = (
                    alpha * self._emotion_accumulator[sys_name] 
                    + (1 - alpha) * intensity * 0.8
                )
            else:
                self._emotion_accumulator[sys_name] *= alpha
        
        self.total_emotion_cycles += 1
        
        # 每 50 周期检查
        if self.total_emotion_cycles % 50 == 0:
            dominant = max(self._emotion_accumulator, key=self._emotion_accumulator.get)
            acc = self._emotion_accumulator[dominant]
            if acc > 0.08:  # EMA累积阈值 (低频分布场景下调)
                self.adapt(dominant, acc, duration=50)
    
    def _trait_dict(self) -> dict:
        return {
            "openness": round(self.openness, 3),
            "extraversion": round(self.extraversion, 3),
            "agreeableness": round(self.agreeableness, 3),
            "neuroticism": round(self.neuroticism, 3),
            "conscientiousness": round(self.conscientiousness, 3),
        }
    
    def get_evolution(self) -> list[dict]:
        """获取人格进化时间线"""
        return self.trait_history
    
    def save(self, path: str):
        """持久化人格档案"""
        data = {
            "openness": self.openness,
            "extraversion": self.extraversion,
            "agreeableness": self.agreeableness,
            "neuroticism": self.neuroticism,
            "conscientiousness": self.conscientiousness,
            "total_emotion_cycles": self.total_emotion_cycles,
            "experience_count": len(self.experience_log),
            "neuro_gains": self.neuro_gains,
        }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "PersonalityProfile":
        """加载人格档案"""
        with open(path, "r") as f:
            data = json.load(f)
        return cls(
            openness=data.get("openness", 1.0),
            extraversion=data.get("extraversion", 1.0),
            agreeableness=data.get("agreeableness", 1.0),
            neuroticism=data.get("neuroticism", 1.0),
            conscientiousness=data.get("conscientiousness", 1.0),
            total_emotion_cycles=data.get("total_emotion_cycles", 0),
        )
    
    def summary(self) -> str:
        """人格概要"""
        bfs = {
            "开放性": self.openness,
            "外向性": self.extraversion,
            "宜人性": self.agreeableness,
            "神经质": self.neuroticism,
            "尽责性": self.conscientiousness,
        }
        lines = ["═══ 人格档案 ═══"]
        for name, val in bfs.items():
            bar = "█" * int(val * 10)
            label = "高" if val > 1.2 else ("低" if val < 0.8 else "中")
            lines.append(f"  {name:>6}: {bar:<20} {val:.2f} ({label})")
        lines.append(f"  经历: {self.total_emotion_cycles} cycles")
        return "\n".join(lines)

