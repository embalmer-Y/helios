"""
X5-1: 心境追踪器 (MoodTracker)
===============================

科学基础:
  · ALMA 三层模型 (Gebhard, 2005): Emotion → Mood → Personality
  · Kuppens (2010) Emotional Inertia: 心境比情绪慢一个数量级
  · Russell (1980) Circumplex: Valence × Arousal 二维空间

设计:
  Mood 是 Emotion 的缓慢累积残留
  · β_mood ≈ 0.90-0.95 (远慢于 Emotion 的 α ≈ 0.35-0.55)
  · 心境调制情绪: 负向心境放大负向事件, 抑制正向事件
  · 唤醒心境加速/减缓情感反应

文件: mood_tracker.py
依赖: daisy_emotion (AffectState)
"""

from dataclasses import dataclass, field
from typing import Optional
from utils import clamp


# ═══════════════════════════════════════════════
# 配置参数
# ═══════════════════════════════════════════════

@dataclass
class MoodConfig:
    """心境层配置 (可自定义)"""
    # 心境更新速率 (0=纯情绪, 1=纯心境, 之间=混合)
    beta_valence: float = 0.92      # 效价惯性 (Kuppens: β≈0.85-0.95)
    beta_arousal: float = 0.90      # 唤醒惯性 (稍快, 唤醒变化快)
    
    # 心境→情感调制强度
    mood_gain_valence: float = 0.15 # 心境效价对事件效价的偏置
    mood_gain_arousal: float = 0.10 # 心境唤醒对事件唤醒的偏置
    
    # 情感→心境累积率
    emotion_to_mood_valence: float = 0.08   # 1-β_valence
    emotion_to_mood_arousal: float = 0.10   # 1-β_arousal


# ═══════════════════════════════════════════════
# 心境状态
# ═══════════════════════════════════════════════

@dataclass
class MoodState:
    """心境快照"""
    valence: float = 0.0   # -1 (极负) ~ +1 (极正)
    arousal: float = 0.3   # 0 (平静) ~ 1 (激动)
    
    # 衍生标签
    label: str = "neutral"
    
    def __post_init__(self):
        self._update_label()
    
    def _update_label(self):
        """Russell 环状模型标签"""
        v, a = self.valence, self.arousal
        if a < 0.3:
            if v > 0.1:
                self.label = "calm-content"
            elif v < -0.1:
                self.label = "sad-lethargic"
            else:
                self.label = "neutral-calm"
        elif a < 0.6:
            if v > 0.1:
                self.label = "pleased"
            elif v < -0.1:
                self.label = "uneasy"
            else:
                self.label = "alert-neutral"
        else:
            if v > 0.1:
                self.label = "excited-joyful"
            elif v < -0.1:
                self.label = "distressed-anxious"
            else:
                self.label = "aroused-neutral"
    
    @property
    def is_positive(self) -> bool:
        return self.valence > 0.1
    
    @property
    def is_negative(self) -> bool:
        return self.valence < -0.1
    
    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 4),
            "arousal": round(self.arousal, 4),
            "label": self.label,
        }


# ═══════════════════════════════════════════════
# 心境追踪器
# ═══════════════════════════════════════════════

class MoodTracker:
    """
    心境追踪器 — ALMA 第二层
    
    用法:
        mood = MoodTracker()
        
        # 每周期:
        emotion_state = daisy.cycle(triggers)
        mood.update(emotion_state)     # 累积到心境
        
        # 心境调制事件触发:
        v_mod, a_mod = mood.modulate_event(v_raw, a_raw)
    
    数学:
        mood_v[t] = β_v × mood_v[t-1] + (1-β_v) × emotion_v[t]
        mood_a[t] = β_a × mood_a[t-1] + (1-β_a) × emotion_a[t]
    """
    
    def __init__(self, config: Optional[MoodConfig] = None):
        self.cfg = config or MoodConfig()
        self.state = MoodState()
        self.history: list[MoodState] = []
        self.max_history = 500
        
        # 统计
        self.cycles_since_update = 0
        self.total_cycles = 0
    
    def update(self, emotion_valence: float, emotion_arousal: float):
        """
        用当前情绪更新心境
        
        Args:
            emotion_valence: -1~+1
            emotion_arousal: 0~1
        """
        # 心境更新 (EMA)
        self.state.valence = clamp(
            self.cfg.beta_valence * self.state.valence
            + self.cfg.emotion_to_mood_valence * emotion_valence,
            -1.0, 1.0
        )
        self.state.arousal = clamp(
            self.cfg.beta_arousal * self.state.arousal
            + self.cfg.emotion_to_mood_arousal * emotion_arousal,
            0.0, 1.0
        )
        
        self.state._update_label()
        self.total_cycles += 1
        self.cycles_since_update += 1
        
        # 记录历史
        if self.total_cycles % 10 == 0:  # 每10周期采样
            self.history.append(MoodState(
                valence=self.state.valence,
                arousal=self.state.arousal,
            ))
            if len(self.history) > self.max_history:
                self.history.pop(0)
    
    def modulate_event(self, raw_valence: float, raw_arousal: float
                       ) -> tuple[float, float]:
        """
        心境调制事件感知
        
        负向心境 → 事件看起来更负面
        正向心境 → 事件看起来更正面
        高唤醒心境 → 事件看起来更紧迫
        
        Returns:
            (modulated_valence, modulated_arousal)
        """
        # 效价偏置: 心境效价拉向心境方向
        v_mod = clamp(
            raw_valence + self.state.valence * self.cfg.mood_gain_valence,
            -1.0, 1.0
        )
        # 唤醒偏置: 心境唤醒叠加
        a_mod = clamp(
            raw_arousal + self.state.arousal * self.cfg.mood_gain_arousal,
            0.0, 1.0
        )
        return v_mod, a_mod
    
    def modulate_triggers(self, triggers: dict[str, float]
                          ) -> dict[str, float]:
        """
        心境调制 Panksepp 触发器
        
        负向心境 → 放大了负向系统, 压制正向系统
        正向心境 → 放大了正向系统, 压制负向系统
        """
        if not triggers:
            return triggers
        
        mood_v = self.state.valence
        
        modulated = {}
        for sys_name, val in triggers.items():
            # 正向系统: 被正向心境放大
            if sys_name in ("SEEKING", "PLAY", "CARE", "LUST"):
                if mood_v > 0:
                    val *= (1.0 + mood_v * 0.2)  # 正向心境 → 放大
                else:
                    val *= (1.0 + mood_v * 0.15)  # 负向心境 → 轻微压制
            # 负向系统: 被负向心境放大
            elif sys_name in ("FEAR", "RAGE", "PANIC"):
                if mood_v < 0:
                    val *= (1.0 + abs(mood_v) * 0.25)  # 负向心境 → 放大
                else:
                    val *= (1.0 - mood_v * 0.1)  # 正向心境 → 轻微压制
            
            modulated[sys_name] = clamp(val, 0.0, 1.0)
        
        return modulated
    
    def get_snapshot(self) -> dict:
        """返回心境快照 (用于 JSON 存档)"""
        return {
            **self.state.to_dict(),
            "total_cycles": self.total_cycles,
            "beta_valence": self.cfg.beta_valence,
        }
    
    def reset(self):
        """重置心境状态"""
        self.state = MoodState()
        self.history.clear()
        self.total_cycles = 0
        self.cycles_since_update = 0

