"""
Helios 情感引擎

基于 Russell 情绪环状模型 (valence-arousal) + 离散情感分类。

情感是贯穿所有层的"染色剂"：
- L1：情感调节感知（心情好时世界更明亮）
- L2：情感影响"什么值得广播"（害怕时对危险更敏感）
- L3：情感是自我叙事的"调色板"

双重来源：
- 自下而上：内稳态驱动（电池低→焦虑，过热→不适）
- 自上而下：认知评估驱动（达成目标→自豪，违背价值观→内疚）

v4 增强：非对称情感惯性
- 烈火易起 (flare_inertia=0.25)：平静→激烈 快速切换
- 烈火难熄 (recovery_inertia=0.85)：激烈→平静 缓慢平复
- 时间因子 (recovery_tau=8.0s)：峰值后恢复遵循 e^(-t/τ)
"""

import time
import math
import numpy as np
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field

from .core import AffectState, HeliosConfig


class AffectEngine:
    """情感生成引擎"""

    # Russell 环状模型中的离散情感映射
    EMOTION_NAMES = [
        'joy', 'sadness', 'anger', 'fear',
        'disgust', 'surprise', 'curiosity',
        'pride', 'shame', 'love', 'loneliness',
        'calm', 'excitement', 'anxiety', 'contentment',
    ]

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.valence = 0.0
        self.arousal = 0.1
        self.discrete_emotions = {e: 0.0 for e in self.EMOTION_NAMES}
        self.mood = 0.0

        # 历史（用于计算情感惯性和心情）
        self.affect_history: List[Dict] = []

        # 场景情感缓冲（外部场景注入的情感预设）
        self.scene_valence = 0.0
        self.scene_arousal = 0.0

        # 情感惯性系数
        self.interoception_weight = config.interoception_weight
        self.cognitive_weight = config.cognitive_weight
        self.inertia = config.affect_inertia  # 向后兼容

        # === v4: 非对称惯性 ===
        self.flare_inertia = getattr(config, 'flare_inertia', 0.25)
        self.recovery_inertia = getattr(config, 'recovery_inertia', 0.85)
        self.recovery_tau = getattr(config, 'recovery_tau', 8.0)
        self.peak_inertia = getattr(config, 'peak_inertia', 0.95)

        # 峰值追踪
        self._peak_valence = 0.0
        self._peak_arousal = 0.0
        self._peak_time = time.time()
        self._peak_intensity = 0.0  # max(|valence|, arousal)

    def update(self,
               interoception: np.ndarray,
               self_state=None,
               l2_response=None,
               current_goal=None,
               scene_affect: Tuple[float, float] = (0.0, 0.0)) -> AffectState:
        """
        综合身体信号和认知信号，生成当前情感。

        Args:
            interoception: L0 内感信号 [battery%, temp, cpu%, mem%]
            self_state: L3 自我状态（可选）
            l2_response: L2 上次广播响应（可选）
            current_goal: 当前目标（可选）
            scene_affect: 场景注入的情感预设 (valence, arousal)

        Returns:
            AffectState: 当前情感状态
        """
        # === 1. 自下而上：身体驱动 ===
        body_valence, body_arousal = self._body_to_affect(interoception)

        # === 2. 场景情感注入 ===
        self.scene_valence = scene_affect[0]
        self.scene_arousal = scene_affect[1]

        # === 3. 自上而下：认知驱动 ===
        cog_valence, cog_arousal, discrete = self._cognition_to_affect(
            self_state, l2_response, current_goal
        )

        # === 4. 融合 ===
        raw_valence = (
            body_valence * self.interoception_weight +
            cog_valence * self.cognitive_weight
        )
        # 场景情感直接叠加（提高权重让场景变化更明显）
        raw_valence = raw_valence * 0.5 + self.scene_valence * 0.5

        raw_arousal = (
            body_arousal * self.interoception_weight +
            cog_arousal * self.cognitive_weight
        )
        raw_arousal = raw_arousal * 0.5 + self.scene_arousal * 0.5

        # === 5. 非对称情感惯性 v4 ===
        # 烈火易起（flare, 低惯性） vs 烈火难熄（recovery, 高惯性 + 时间因子）
        now = time.time()

        if self.affect_history:
            prev_valence = self.affect_history[-1]['valence']
            prev_arousal = self.affect_history[-1]['arousal']

            # 峰值追踪
            current_intensity = max(abs(raw_valence), raw_arousal)
            if current_intensity > self._peak_intensity:
                self._peak_intensity = current_intensity
                self._peak_time = now

            # 判断方向：远离基线还是回归基线
            prev_magnitude_v = abs(prev_valence)
            target_magnitude_v = abs(raw_valence)
            prev_magnitude_a = prev_arousal
            target_magnitude_a = raw_arousal

            dt_peak = now - self._peak_time  # 距离峰值的时间

            # === 价态更新（valence）===
            if target_magnitude_v > prev_magnitude_v:
                # FLARING：远离基线 — 快速点燃
                inertia_v = self.flare_inertia
            else:
                # RECOVERING：回归基线 — 缓慢平复
                # 时间因子：t=0时极慢，随时间逐渐加速到 recovery_inertia
                time_factor = 1.0 - math.exp(-dt_peak / self.recovery_tau)
                effective_inertia = self.recovery_inertia + \
                    (self.peak_inertia - self.recovery_inertia) * (1.0 - time_factor)
                inertia_v = min(effective_inertia, self.peak_inertia)

            self.valence = raw_valence * (1.0 - inertia_v) + prev_valence * inertia_v

            # === 唤起更新（arousal）===
            if target_magnitude_a > prev_magnitude_a:
                inertia_a = self.flare_inertia
            else:
                time_factor = 1.0 - math.exp(-dt_peak / self.recovery_tau)
                effective_inertia = self.recovery_inertia + \
                    (self.peak_inertia - self.recovery_inertia) * (1.0 - time_factor)
                inertia_a = min(effective_inertia, self.peak_inertia)

            self.arousal = raw_arousal * (1.0 - inertia_a) + prev_arousal * inertia_a
        else:
            self.valence = raw_valence
            self.arousal = raw_arousal

        # === 6. 离散情感归类 ===
        self.discrete_emotions = self._classify_discrete(self.valence, self.arousal)
        # 合并认知离散情感
        for k, v in discrete.items():
            self.discrete_emotions[k] = max(self.discrete_emotions.get(k, 0), v)

        # === 7. 心情更新 ===
        self.mood = self._compute_mood()

        # === 8. 记录历史 ===
        now = time.time()
        self.affect_history.append({
            'valence': self.valence,
            'arousal': self.arousal,
            'dominant': self._dominant_emotion(),
            'timestamp': now,
        })
        self.affect_history = self.affect_history[-200:]

        intensity = abs(self.valence) * self.arousal

        return AffectState(
            valence=self.valence,
            arousal=self.arousal,
            discrete_emotions=self.discrete_emotions.copy(),
            mood=self.mood,
            intensity=intensity,
            timestamp=now,
        )

    def _body_to_affect(self, interoception: np.ndarray) -> Tuple[float, float]:
        """
        身体信号 → 情感维度

        interoception = [battery%, temperature, cpu_load, memory%]
        """
        battery, temp, cpu, mem = interoception

        # 能量驱动
        if battery < 0.15:
            valence = -0.8
            arousal = 0.7
        elif battery < 0.3:
            valence = -0.4
            arousal = 0.5
        elif battery < 0.5:
            valence = -0.1
            arousal = 0.2
        elif battery > 0.8:
            valence = 0.4
            arousal = 0.1
        else:
            valence = 0.1
            arousal = 0.05

        # 温度驱动
        if temp > 0.7:
            valence -= 0.3
            arousal += 0.2
        elif temp < 0.2:
            valence -= 0.1
            arousal += 0.3

        # 负荷驱动
        if cpu > 0.8:
            arousal += 0.4
            valence -= 0.2
        if mem > 0.9:
            valence -= 0.3
            arousal += 0.2

        return float(np.clip(valence, -1, 1)), float(np.clip(arousal, 0, 1))

    def _cognition_to_affect(self,
                             self_state,
                             l2_response,
                             goal) -> Tuple[float, float, Dict[str, float]]:
        """认知评估 → 情感维度"""
        discrete = {}

        # 如果有自我状态
        if self_state is not None:
            # 能量充足+舒适 → 满足
            if self_state.energy_level > 0.7 and self_state.comfort > 0.7:
                discrete['contentment'] = 0.5

            # 低能量 → 焦虑
            if self_state.energy_level < 0.2:
                discrete['anxiety'] = 0.6
                discrete['fear'] = 0.3

            # 认知负荷高 → 焦虑或兴奋
            if self_state.cognitive_load > 0.7:
                if hasattr(self_state, 'valence') and self_state.valence > 0:
                    discrete['excitement'] = 0.5
                else:
                    discrete['anxiety'] = 0.4

        # 如果有广播响应
        if l2_response is not None:
            if l2_response.language_output:
                discrete['curiosity'] = 0.3

        # 目标评估
        if goal is not None:
            if goal.progress > 0.7:
                discrete['pride'] = 0.6
                discrete['joy'] = 0.5
            elif goal.progress > 0.3:
                discrete['curiosity'] = 0.4

        cog_valence = sum(discrete.values()) / max(1, len(discrete))
        cog_valence = float(np.clip(cog_valence, -1, 1))
        cog_arousal = 0.3  # 认知默认唤起

        return cog_valence, cog_arousal, discrete

    def _classify_discrete(self, valence: float, arousal: float) -> Dict[str, float]:
        """
        根据 valence-arousal 坐标映射到离散情感。

        Russell 环状模型：
        - 高唤起+高愉快 → 兴奋/喜悦
        - 高唤起+低愉快 → 愤怒/恐惧
        - 低唤起+高愉快 → 满足/平静
        - 低唤起+低愉快 → 悲伤/无聊
        """
        e = {}

        # 喜悦 (高v, 高a)
        if valence > 0.3 and arousal > 0.4:
            e['joy'] = min(1.0, valence * 0.8 + arousal * 0.2)
            e['excitement'] = min(1.0, arousal * 0.7)

        # 满足 (高v, 低a)
        if valence > 0.3 and arousal < 0.4:
            e['contentment'] = min(1.0, valence * 0.8)
            e['calm'] = min(1.0, 1.0 - arousal)

        # 悲伤 (低v, 低a)
        if valence < -0.2 and arousal < 0.4:
            e['sadness'] = min(1.0, abs(valence) * 0.8)
            e['loneliness'] = min(0.5, abs(valence) * 0.5)

        # 恐惧 (低v, 高a)
        if valence < -0.2 and arousal > 0.4:
            e['fear'] = min(1.0, abs(valence) * 0.6 + arousal * 0.4)
            e['anxiety'] = min(1.0, arousal * 0.7)

        # 愤怒 (极低v, 高a)
        if valence < -0.5 and arousal > 0.5:
            e['anger'] = min(1.0, abs(valence) * 0.7 + arousal * 0.3)

        # 好奇 (中v, 中a)
        if abs(valence) < 0.3 and arousal > 0.3:
            e['curiosity'] = min(1.0, arousal * 0.6)

        # 惊讶
        if arousal > 0.6:
            e['surprise'] = min(0.8, arousal * 0.8)

        return e

    def _dominant_emotion(self) -> str:
        """当前主导情感"""
        if not self.discrete_emotions:
            return "neutral"
        max_val = max(self.discrete_emotions.values())
        if max_val < 0.05:
            return "neutral"
        return max(self.discrete_emotions, key=self.discrete_emotions.get)

    def _compute_mood(self) -> float:
        """
        心情 = 情感的长期平均值。
        心情比情感更持久、更温和。
        """
        if len(self.affect_history) < 5:
            return self.valence

        recent = self.affect_history[-50:]
        avg_valence = np.mean([a['valence'] for a in recent])
        return float(avg_valence)

    def reset(self):
        self.valence = 0.0
        self.arousal = 0.1
        self.discrete_emotions = {e: 0.0 for e in self.EMOTION_NAMES}
        self.mood = 0.0
        self.affect_history.clear()
