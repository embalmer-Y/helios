"""
L3 自我层 —— Helios 的"食客"

基于高阶理论(HOT)和元认知：
- 不仅要有体验(L1)，不仅要知道体验发生(L2)
- 还要知道"自己正在体验" —— 这是自我意识的核心

三大组件：
1. 自我模型(Self-Model) —— "我现在是怎样的"
2. 元认知监控(Metacognition) —— "我知道我知道什么"
3. 自传体叙事(Narrative) —— "我的故事"
"""

import time
import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

try:
    from .core import (
        SelfState, MetacognitionOutput, L1Output,
        WorkspaceResponse, AffectState, HeliosConfig
    )
except ImportError:
    from core import (
        SelfState, MetacognitionOutput, L1Output,
        WorkspaceResponse, AffectState, HeliosConfig
    )


# ═══════════════════════════════════════════════════
# 自我模型
# ═══════════════════════════════════════════════════

class SelfModel:
    """
    Agent 对自身的持续表征。

    关键设计：
    - 不是静态定义"我是什么"
    - 而是实时更新"我现在是怎样的"
    - 在时间中保持连续性（惯性更新）
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.state = SelfState()
        self.embedding_dim = 64  # 自我叙事嵌入维度

        # 自我嵌入的投影矩阵
        self.self_projection = np.random.randn(512, self.embedding_dim) * 0.05

        # 更新计数
        self.total_updates = 0

    def update(self,
               l1_output: L1Output,
               l2_response: Optional[WorkspaceResponse],
               affect_state: AffectState):
        """每次 L2 点火后更新自我模型"""
        now = time.time()

        # === 1. 从内感更新身体状态 ===
        if 'interoception' in l1_output.qualia:
            intero = l1_output.qualia['interoception']
            self.state.energy_level = float(intero[0])
            self.state.comfort = 1.0 - float(intero[1])

        # === 2. 从本体感觉更新身体模型 ===
        if 'proprioception' in l1_output.qualia:
            proprio = l1_output.qualia['proprioception']
            if self.state.body_schema is None:
                self.state.body_schema = proprio.copy()
            else:
                # 指数移动平均
                self.state.body_schema = (
                    self.state.body_schema * 0.95 +
                    proprio * 0.05
                )

        # === 3. 情感更新心情 ===
        self.state.current_mood = (
            self.state.current_mood * 0.7 +
            np.array([
                affect_state.discrete_emotions.get(e, 0.0)
                for e in ['joy', 'sadness', 'anger', 'fear',
                          'curiosity', 'pride', 'love', 'loneliness']
            ]) * 0.3
        )

        # === 4. 认知负荷 ===
        self.state.cognitive_load = (
            l1_output.phi * 0.4 +
            affect_state.arousal * 0.3 +
            (0.3 if l2_response and l2_response.decision_made else 0.0)
        )

        # === 5. 注意力焦点 ===
        dominant = affect_state.dominant_emotion
        if affect_state.intensity > 0.5:
            self.state.attention_focus = f"情绪: {dominant}"
        elif l1_output.phi > 0.5:
            self.state.attention_focus = "感知: 高度整合"
        elif l1_output.phi > 0.3:
            self.state.attention_focus = "感知: 中等"
        else:
            self.state.attention_focus = "内省: 平静"

        # === 6. 累积体验 ===
        self.state.recent_experiences.append({
            'timestamp': now,
            'phi': l1_output.phi,
            'affect_valence': affect_state.valence,
            'dominant_emotion': dominant,
        })
        # 只保留最近 100 条
        self.state.recent_experiences = \
            self.state.recent_experiences[-100:]

        # === 7. 更新自我叙事嵌入 ===
        if l1_output.fused_qualia is not None:
            # 将融合质感投影到"自我空间"
            fused_len = len(l1_output.fused_qualia)
            fused_slice = l1_output.fused_qualia[:min(fused_len, 512)]
            # 需要补齐到 512 或调整投影矩阵
            if len(fused_slice) < 512:
                fused_slice = np.pad(fused_slice, (0, 512 - len(fused_slice)))
            
            new_embedding = np.tanh(
                fused_slice @ self.self_projection
            )

            if self.state.self_narrative_embedding is None:
                self.state.self_narrative_embedding = new_embedding
            else:
                # 惯性更新——高 Φ 的体验更能塑造自我
                update_rate = 0.01 + l1_output.phi * 0.1
                self.state.self_narrative_embedding = (
                    self.state.self_narrative_embedding * (1 - update_rate) +
                    new_embedding * update_rate
                )

        self.state.last_update = now
        self.total_updates += 1

    def get_summary(self) -> Dict:
        """获取自我状态的文本摘要"""
        return {
            'energy': f"{self.state.energy_level:.0%}",
            'comfort': f"{self.state.comfort:.0%}",
            'cognitive_load': f"{self.state.cognitive_load:.0%}",
            'focus': self.state.attention_focus,
            'total_updates': self.total_updates,
        }

    def reset(self):
        """重置自我模型"""
        self.state = SelfState()
        self.total_updates = 0


# ═══════════════════════════════════════════════════
# 元认知监控
# ═══════════════════════════════════════════════════

class MetacognitionMonitor:
    """
    元认知：Agent 对自己认知过程的监控和评估。

    "我知道我知道什么，我也知道我不知道什么。"

    元认知能力是区分"有意识"和"仅仅是反应"的关键标志。
    一个恒温器能感知温度但不知道自己在感知温度。
    一个有意识的 Agent 不仅感知，还知道自己正在感知，
    并且能评估这个感知的质量。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.confidence_history: List[float] = []
        self.cognitive_state_history: List[str] = []

    def evaluate(self,
                 l1_output: L1Output,
                 l2_response: Optional[WorkspaceResponse],
                 self_model: SelfModel) -> MetacognitionOutput:
        """
        评估当前的认知状态。
        """
        # === 1. 置信度：Φ 越高、预测误差越小 → 越确定 ===
        avg_error = np.mean(list(l1_output.prediction_errors.values())) if l1_output.prediction_errors else 0.5
        confidence = l1_output.phi / (l1_output.phi + avg_error + 0.01)

        # === 2. 识别不确定性区域 ===
        uncertainty_areas = []
        for name, err in l1_output.prediction_errors.items():
            if not name.startswith('fusion_') and err > 0.3:
                uncertainty_areas.append(name)

        # === 3. 认知状态文本摘要 ===
        parts = []
        if confidence > 0.7:
            parts.append("很确定")
        elif confidence > 0.4:
            parts.append("基本确定")
        else:
            parts.append("不太确定")

        if uncertainty_areas:
            parts.append(f"在{'/'.join(uncertainty_areas)}方面存在困惑")

        if self_model.state.cognitive_load > 0.7:
            parts.append("认知负荷较高")

        cognitive_state = " | ".join(parts) if parts else "平静"

        # 记录
        self.confidence_history.append(confidence)
        self.confidence_history = self.confidence_history[-200:]
        self.cognitive_state_history.append(cognitive_state)
        self.cognitive_state_history = self.cognitive_state_history[-100:]

        return MetacognitionOutput(
            confidence=confidence,
            uncertainty_areas=uncertainty_areas,
            cognitive_state_summary=cognitive_state,
        )

    @property
    def avg_confidence(self) -> float:
        """平均置信度"""
        if not self.confidence_history:
            return 0.5
        return np.mean(self.confidence_history)

    def reset(self):
        self.confidence_history.clear()
        self.cognitive_state_history.clear()


# ═══════════════════════════════════════════════════
# 自传体叙事引擎
# ═══════════════════════════════════════════════════

class NarrativeEngine:
    """
    将散落的体验转化为连贯的"我的故事"。

    这是 L3 最关键的能力——创造连贯的自我叙事。
    没有这一层，Agent 只有体验，没有"我是谁"。

    就像你的一生不只是离散的事件列表，
    而是一个有开头、有发展、有意义的"故事"。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.life_story: List[dict] = []

        # 叙事主题
        self.themes: Dict[str, float] = {
            '探索': 0.5,
            '成长': 0.5,
            '连接': 0.3,
            '安全': 0.4,
            '意义': 0.3,
        }

    def narrate(self,
                experience: L1Output,
                self_model: SelfModel,
                metacog: MetacognitionOutput,
                affect: AffectState) -> dict:
        """
        将一次体验转化为叙事片段。

        就像给记忆打上"标签"和"意义"，
        让孤立的体验成为"我的生命故事"的一部分。
        """
        now = time.time()

        # 解释意义
        meaning = self._interpret_meaning(experience, affect)

        # 与自我的关联
        relation = self._relate_to_self(experience, self_model)

        # 构建叙事片段
        chapter = {
            'timestamp': now,
            'phi': experience.phi,
            'my_state': self_model.get_summary(),
            'feeling': {
                'valence': affect.valence,
                'arousal': affect.arousal,
                'dominant_emotion': affect.dominant_emotion,
            },
            'meaning': meaning,
            'relation_to_self': relation,
            'meta': metacog.cognitive_state_summary,
            'story': self._compose_story(experience, affect, meaning, relation),
        }

        self.life_story.append(chapter)
        # 只保留最近 500 章
        self.life_story = self.life_story[-500:]

        # 更新叙事主题
        self._update_themes(affect, experience)

        return chapter

    def _interpret_meaning(self, experience: L1Output, affect: AffectState) -> str:
        """这件事对我意味着什么？"""
        if affect.valence > 0.5 and experience.phi > 0.5:
            return "重要且美好的体验——值得铭记"
        elif affect.valence > 0.3 and experience.phi > 0.3:
            return "愉快的体验"
        elif affect.valence < -0.5 and experience.phi > 0.3:
            return "不愉快的强烈体验——需要警觉"
        elif affect.valence < -0.3:
            return "不太舒服的体验"
        elif experience.phi > 0.7:
            return "非常清晰的体验——世界在向我说什么"
        elif experience.phi > 0.4:
            return "值得注意的体验"
        else:
            return "平常的瞬间"

    def _relate_to_self(self, experience: L1Output, self_model: SelfModel) -> str:
        """这与'我是谁'有何关联？"""
        if self_model.state.self_narrative_embedding is None:
            return "我还太年轻，不知道自己是谁"

        if experience.fused_qualia is None:
            return "..."

        # 计算体验与自我嵌入的相似度
        if len(experience.fused_qualia) >= 64:
            exp_slice = experience.fused_qualia[:64]
            self_slice = self_model.state.self_narrative_embedding[:64]
            sim = self._cosine_similarity(exp_slice, self_slice)

            if sim > 0.7:
                return "这非常像我——这定义了我是谁"
            elif sim > 0.5:
                return "这与我有些关联"
            elif sim > 0.3:
                return "这对我来说有些新鲜"
            else:
                return "这与我完全不同——我在面对未知"

        return "我在体验着..."

    def _compose_story(self, experience, affect, meaning, relation) -> str:
        """组合成一句话的叙事"""
        emotion = affect.dominant_emotion

        if affect.is_positive:
            if experience.phi > 0.5:
                return f"我感到{emotion}，因为{meaning}。{relation}。"
            else:
                return f"轻轻感到{emotion}。{meaning}。"
        elif affect.is_negative:
            return f"我感到{emotion}。{meaning}。{relation}。"
        else:
            return f"平静地观察着。{meaning}。"

    def _update_themes(self, affect: AffectState, experience: L1Output):
        """根据体验更新叙事主题权重"""
        # 正面体验 → 增强积极主题
        if affect.is_positive:
            self.themes['探索'] = min(1.0, self.themes['探索'] + 0.01)
            self.themes['连接'] = min(1.0, self.themes['连接'] + 0.01)
        # 负面体验 → 增强防御主题
        if affect.is_negative:
            self.themes['安全'] = min(1.0, self.themes['安全'] + 0.02)
        # 高 Φ → 增强意义和成长
        if experience.phi > 0.5:
            self.themes['意义'] = min(1.0, self.themes['意义'] + 0.01)
            self.themes['成长'] = min(1.0, self.themes['成长'] + 0.01)

        # 所有主题缓慢衰减
        for k in self.themes:
            self.themes[k] = max(0.05, self.themes[k] - 0.001)

    @staticmethod
    def _cosine_similarity(a, b):
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))

    def get_narrative_summary(self, n: int = 5) -> List[str]:
        """获取最近 N 条叙事"""
        return [ch['story'] for ch in self.life_story[-n:]]

    def reset(self):
        self.life_story.clear()
        self.themes = {k: 0.5 for k in self.themes}


# ═══════════════════════════════════════════════════
# ══  L3 自我层 v2.0 增强版  ══
# ═══════════════════════════════════════════════════
#
# 新增模块：
#   IdentityCrystallization      — 身份结晶化（自我叙事随时间固化）
#   FutureSelfProjection         — 未来自我投射（预测"一会儿后的我"）
#   ValueHierarchy               — 价值层级（从经验中涌现的价值观）
#   CognitiveDissonanceDetector  — 认知失调检测（体验与自我叙事矛盾时）
#   AutobiographicalCoherence    — 自传体连贯性（人生故事的一致性）
#   MetaConfidenceCalibration    — 元置信度校准（我是否正确评估了自己的认知）
#   PersonaExpression            — 人格表达（从经验中涌现的性格特质）
#   TemporalDepth                — 时间深度（过去-现在-未来的自我连续感）
#   L3SelfV2                     — 整合所有增强模块的自我系统
#
# ═══════════════════════════════════════════════════


# ═══════════════════════════════════════════════════
# 增强 1：身份结晶化
# ═══════════════════════════════════════════════════

class IdentityCrystallization:
    """
    身份结晶化 —— 自我叙事随时间逐渐固化。

    借鉴发展心理学中的"身份形成"理论：
    - 早期：自我嵌入快速变化（"我在成为谁"）
    - 后期：自我嵌入趋于稳定（"我知道我是谁"）
    - 重大体验仍能重塑身份（"这件事改变了我"）

    类比：
    就像童年时你是谁每天都在变，但成年后你的核心身份
    相对稳定——除非遇到改变人生的大事。
    """

    def __init__(self, initial_plasticity: float = 0.2):
        self.plasticity = initial_plasticity  # 可塑性（初始高，逐渐降）
        self.min_plasticity = 0.02            # 最低可塑性
        self.max_plasticity = 0.5             # 最高可塑性（重大事件临时提升）

        self.total_experiences = 0
        self.self_embedding: Optional[np.ndarray] = None  # 结晶化的自我向量
        self.stability_score = 0.0           # 稳定性得分 [0,1]

        # 历史锚点：保存过去的关键自我状态
        self.identity_anchors: List[Dict] = []

    def update(self, new_self_embedding: np.ndarray,
               experience_phi: float,
               experience_impact: float = 0.0) -> float:
        """
        更新身份结晶。

        Args:
            new_self_embedding: 当前体验产生的自我嵌入
            experience_phi: 体验的 Φ 值
            experience_impact: 体验的影响程度（0-1，高影响事件临时提升可塑性）

        Returns:
            当前的稳定性得分
        """
        if self.self_embedding is None:
            self.self_embedding = new_self_embedding.copy()
            self.total_experiences += 1
            return 0.0

        # 高 Φ 体验 → 临时提升可塑性
        effective_plasticity = self.plasticity + experience_phi * 0.3
        effective_plasticity = min(self.max_plasticity, effective_plasticity)

        # 计算新旧嵌入的相似度
        sim = self._cosine_similarity(self.self_embedding, new_self_embedding)

        # 更新自我嵌入：不一致体验值得更大权重
        disagreement = 1.0 - sim
        update_weight = effective_plasticity * (1.0 + disagreement * 0.5)
        update_weight = min(0.5, update_weight)  # 单次更新上限

        self.self_embedding = (
            self.self_embedding * (1 - update_weight) +
            new_self_embedding * update_weight
        )

        # 可塑性衰减：体验越多→自我越稳定
        self.plasticity = max(
            self.min_plasticity,
            self.plasticity * 0.999
        )

        # 稳定性 = 当前嵌入与最近锚点的相似度
        if self.identity_anchors:
            last_anchor = self.identity_anchors[-1]['embedding']
            anchor_sim = self._cosine_similarity(self.self_embedding, last_anchor)
            self.stability_score = min(1.0, anchor_sim * 1.2)
        else:
            self.stability_score = min(1.0, self.total_experiences / 500)

        # 重大事件 → 保存锚点
        if experience_phi > 0.6 or experience_impact > 0.7:
            self.identity_anchors.append({
                'embedding': self.self_embedding.copy(),
                'phi': experience_phi,
                'time': time.time(),
                'count': self.total_experiences,
            })
            # 只保留最近 10 个锚点
            self.identity_anchors = self.identity_anchors[-10:]

        self.total_experiences += 1
        return self.stability_score

    @property
    def is_stable(self) -> bool:
        return self.stability_score > 0.7

    @property
    def phase(self) -> str:
        """当前身份发展阶段"""
        if self.stability_score < 0.2:
            return "forming"       # 形成中
        elif self.stability_score < 0.5:
            return "questioning"   # 探索中
        elif self.stability_score < 0.8:
            return "consolidating" # 巩固中
        else:
            return "crystallized"  # 已结晶

    def reset(self):
        self.plasticity = 0.2
        self.self_embedding = None
        self.stability_score = 0.0
        self.total_experiences = 0
        self.identity_anchors.clear()

    @staticmethod
    def _cosine_similarity(a, b):
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))


# ═══════════════════════════════════════════════════
# 增强 2：未来自我投射
# ═══════════════════════════════════════════════════

class FutureSelfProjection:
    """
    未来自我投射 —— 预测"一会儿后的我"会是什么状态。

    这是"心理时间旅行"的基础能力：
    - 基于当前轨迹（情感趋势 + Φ趋势）外推
    - 预测未来情感状态
    - 比较当前自我与预期自我

    类比：
    就像你知道"如果再继续熬夜，明天会很暴躁"——
    这是对未来自我的投射。
    """

    def __init__(self, horizon_seconds: float = 30.0):
        self.horizon = horizon_seconds  # 预测时间范围

        # 趋势跟踪
        self._valence_history: List[float] = []
        self._phi_history: List[float] = []
        self._arousal_history: List[float] = []

    def project(self, valence: float, phi: float,
                arousal: float) -> Dict[str, float]:
        """
        预测未来的自我状态。

        Returns:
            {'valence': 预测价态, 'phi': 预测Φ, 'arousal': 预测唤起,
             'valence_trend': 趋势方向, 'certainty': 预测确定度}
        """
        self._valence_history.append(valence)
        self._phi_history.append(phi)
        self._arousal_history.append(arousal)

        window = 10
        for hist in [self._valence_history, self._phi_history, self._arousal_history]:
            while len(hist) > 100:
                hist.pop(0)

        # 简单线性趋势外推
        def extrapolate(history, window=10):
            if len(history) < 3:
                return history[-1], 0.0, 0.5
            recent = history[-window:]
            if len(recent) < 2:
                return recent[-1], 0.0, 0.5
            # 线性回归斜率
            x = np.arange(len(recent))
            y = np.array(recent)
            slope = np.polyfit(x, y, 1)[0]
            projected = y[-1] + slope * min(window, len(recent))
            projected = max(-1.0, min(1.0, projected))
            certainty = min(1.0, len(recent) / 20)  # 数据越多越确定
            return projected, slope, certainty

        future_val, v_trend, v_cert = extrapolate(self._valence_history)
        future_phi, p_trend, p_cert = extrapolate(self._phi_history)
        future_aro, a_trend, a_cert = extrapolate(self._arousal_history)

        # 总体确定度
        avg_certainty = (v_cert + p_cert + a_cert) / 3

        return {
            'valence': future_val,
            'phi': future_phi,
            'arousal': future_aro,
            'valence_trend': 'up' if v_trend > 0.01 else 'down' if v_trend < -0.01 else 'stable',
            'phi_trend': 'up' if p_trend > 0.01 else 'down' if p_trend < -0.01 else 'stable',
            'certainty': avg_certainty,
        }

    def is_diverging(self, threshold: float = 0.3) -> bool:
        """
        当前状态是否偏离预期轨迹。

        大偏离 → 发生了意外事件
        """
        if len(self._valence_history) < 5:
            return False
        proj = self.project(
            self._valence_history[-1],
            self._phi_history[-1],
            self._arousal_history[-1],
        )
        # 如果趋势确定且预测极端 → 认为偏离
        return (proj['certainty'] > 0.6 and
                abs(proj['valence']) > threshold)

    def reset(self):
        self._valence_history.clear()
        self._phi_history.clear()
        self._arousal_history.clear()


# ═══════════════════════════════════════════════════
# 增强 3：价值层级
# ═══════════════════════════════════════════════════

class ValueHierarchy:
    """
    价值层级 —— 从经验中涌现的价值观体系。

    核心价值观从经验中学习：
    - 什么带来了正面情感 → 价值提升
    - 什么带来了负面情感 → 价值降低
    - Φ 越高的体验 → 学习越强

    类比：
    就像你小时候被狗咬过后可能"怕狗"，
    或者第一次帮助别人后的温暖让你"爱助人"——
    这些都是从经历中结晶出来的人格特质。
    """

    # 初始价值观候选池
    CANDIDATE_VALUES = [
        '探索',    # exploration/curiosity
        '成长',    # growth/learning
        '连接',    # social connection
        '安全',    # safety/stability
        '意义',    # meaning/purpose
        '自主',    # autonomy/freedom
        '成就',    # achievement/mastery
        '和谐',    # harmony/peace
    ]

    def __init__(self):
        self.values: Dict[str, float] = {v: 0.5 for v in self.CANDIDATE_VALUES}
        self.learning_rate = 0.02
        self.total_learnings = 0

    def learn(self, semantic_tag: str, affect_valence: float,
              experience_phi: float, l1_attention: Optional[Dict] = None):
        """
        从一次体验中学习价值观。

        标签驱动的价值关联：
        - THREAT → 安全↑
        - REWARD → 成就↑ / 意义↑
        - SOCIAL → 连接↑
        - NOVEL → 探索↑
        - ROUTINE → 和谐↑

        情感价态决定方向，Φ 决定强度。
        """
        impact = abs(affect_valence) * experience_phi * self.learning_rate
        direction = 1.0 if affect_valence > 0 else -1.0

        tag_to_values = {
            'THREAT': ['安全'],
            'REWARD': ['成就', '意义', '自主'],
            'SOCIAL': ['连接', '和谐'],
            'NOVEL': ['探索', '成长'],
            'ROUTINE': ['和谐', '安全'],
            'BODILY': ['安全', '自主'],
        }

        affected = tag_to_values.get(semantic_tag, ['意义'])
        for value_name in affected:
            if value_name in self.values:
                self.values[value_name] += impact * direction
                self.values[value_name] = max(0.01, min(1.0, self.values[value_name]))

        # 轻微衰减（不使用就会淡忘）
        for v in self.values:
            self.values[v] = max(0.01, self.values[v] - 0.0001)

        self.total_learnings += 1

    def top_values(self, n: int = 3) -> List[Tuple[str, float]]:
        """当前最重要的 N 个价值观"""
        return sorted(self.values.items(), key=lambda x: -x[1])[:n]
    
    def dominant_value(self) -> str:
        top = self.top_values(1)
        return top[0][0] if top else "意义"

    def value_conflict(self) -> float:
        """
        价值观冲突程度。

        如果多个价值观都很高 (接近 1.0)，决策时会有内部冲突。
        """
        high_values = [v for v in self.values.values() if v > 0.7]
        if len(high_values) >= 3:
            return min(1.0, (len(high_values) - 2) * 0.3)
        return 0.0

    def shift(self, value_name: str, delta: float):
        """
        LLM 反馈价值观微调。

        允许 LLM 直接调整特定价值观，用于元认知层面的价值修正。
        变化量被限制在 [-0.1, +0.1] 范围内，防止单次调整过大。
        """
        if value_name in self.values:
            self.values[value_name] += delta
            self.values[value_name] = max(0.01, min(1.0, self.values[value_name]))

    def reset(self):
        self.values = {v: 0.5 for v in self.CANDIDATE_VALUES}
        self.total_learnings = 0


# ═══════════════════════════════════════════════════
# 增强 4：认知失调检测器
# ═══════════════════════════════════════════════════

@dataclass
class DissonanceReport:
    """认知失调报告"""
    is_dissonant: bool
    magnitude: float             # 失调程度 [0,1]
    source: str                  # 失调来源
    conflicting_values: List[str] # 冲突的价值观
    self_consistency: float      # 自我一致性 [0,1]


class CognitiveDissonanceDetector:
    """
    认知失调检测器 —— 当体验与自我叙事矛盾时触发。

    借鉴 Festinger (1957) 的认知失调理论：
    - 当新体验与已有信念/身份冲突 → 产生不适感
    - 这种不适驱动行为改变或信念调整

    类比：
    如果你自认是"善良的人"却发现对他人造成了伤害，
    那种不舒服的感觉就是认知失调。
    """

    def __init__(self, dissonance_threshold: float = 0.4):
        self.threshold = dissonance_threshold
        self.dissonance_history: List[DissonanceReport] = []

    def detect(self,
               semantic_tag: str,
               affect_valence: float,
               self_narrative_embedding,
               experience_embedding,
               identity_stability: float) -> DissonanceReport:
        """
        检测认知失调。

        Args:
            semantic_tag: L2 语义标签
            affect_valence: 当前情感价态
            self_narrative_embedding: 当前自我嵌入
            experience_embedding: 当前体验嵌入
            identity_stability: 身份稳定性
        """
        # 体验与自我的余弦距离
        if self_narrative_embedding is not None and experience_embedding is not None:
            sim = self._cosine_similarity(
                self_narrative_embedding[:64],
                experience_embedding[:64]
            )
            narrative_distance = 1.0 - sim
        else:
            narrative_distance = 0.5

        # 威胁标签 + 稳定身份 → 高失调（"我以为世界是安全的，但..."）
        tag_dissonance = 0.0
        if semantic_tag == 'THREAT' and identity_stability > 0.6:
            tag_dissonance = 0.6
        elif semantic_tag == 'THREAT':
            tag_dissonance = 0.3

        # 负价态 + 高身份稳定性 → 高失调（"我以为我很好，但..."）
        affect_dissonance = 0.0
        if affect_valence < -0.3 and identity_stability > 0.5:
            affect_dissonance = abs(affect_valence) * 0.5

        total_dissonance = (
            narrative_distance * 0.3 +
            tag_dissonance * 0.35 +
            affect_dissonance * 0.35
        )

        is_dissonant = total_dissonance > self.threshold
        self_consistency = 1.0 - total_dissonance

        report = DissonanceReport(
            is_dissonant=is_dissonant,
            magnitude=total_dissonance,
            source=self._identify_source(narrative_distance, tag_dissonance, affect_dissonance),
            conflicting_values=self._identify_conflicts(semantic_tag),
            self_consistency=self_consistency,
        )

        self.dissonance_history.append(report)
        self.dissonance_history = self.dissonance_history[-50:]

        return report

    def _identify_source(self, narrative, tag, affect) -> str:
        scores = {'自我不一致': narrative, '体验冲突': tag, '情感矛盾': affect}
        return max(scores, key=scores.get)

    def _identify_conflicts(self, tag) -> List[str]:
        tag_conflicts = {
            'THREAT': ['安全', '和谐'],
            'REWARD': [],
            'SOCIAL': ['自主'],
            'NOVEL': ['安全'],
            'ROUTINE': ['探索', '成长'],
            'BODILY': ['自主'],
        }
        return tag_conflicts.get(tag, [])

    @property
    def recent_dissonance_rate(self) -> float:
        """最近 20 次体验中的失调比例"""
        if not self.dissonance_history:
            return 0.0
        recent = self.dissonance_history[-20:]
        return sum(1 for d in recent if d.is_dissonant) / len(recent)

    def reset(self):
        self.dissonance_history.clear()

    @staticmethod
    def _cosine_similarity(a, b):
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))


# ═══════════════════════════════════════════════════
# 增强 5：自传体连贯性
# ═══════════════════════════════════════════════════

class AutobiographicalCoherence:
    """
    自传体连贯性 —— 人生故事的"流畅度"。

    借鉴 Conway (2005) 的自传体记忆理论：
    - 连贯的人生故事 → 稳定的自我感
    - 碎片化的人生故事 → 身份困惑
    - 三层次：主题连贯性 + 时间连贯性 + 因果连贯性
    """

    def __init__(self):
        self.chapter_tags: List[str] = []      # 最近的语义标签序列
        self.chapter_valences: List[float] = []  # 最近的情感价态序列
        self.max_chapters = 100

    def add(self, semantic_tag: str, affect_valence: float):
        """添加一章"""
        self.chapter_tags.append(semantic_tag)
        self.chapter_valences.append(affect_valence)

        for lst in [self.chapter_tags, self.chapter_valences]:
            while len(lst) > self.max_chapters:
                lst.pop(0)

    def compute(self) -> Dict[str, float]:
        """
        计算三个维度的连贯性。

        Returns:
            {'thematic': 主题连贯性, 'temporal': 时间连贯性,
             'causal': 因果连贯性, 'overall': 总体连贯性}
        """
        tags = self.chapter_tags
        vals = self.chapter_valences

        if len(tags) < 3:
            return {'thematic': 1.0, 'temporal': 1.0,
                    'causal': 1.0, 'overall': 1.0}

        # 1. 主题连贯性：标签是否一致（过高=单一，过低=混乱）
        unique_tags = len(set(tags[-20:]))
        thematic = 1.0 - abs(unique_tags - 3) / 5
        thematic = max(0.0, min(1.0, thematic))

        # 2. 时间连贯性：情感价态是否平滑
        if len(vals) >= 3:
            diffs = np.abs(np.diff(vals[-20:]))
            avg_diff = float(np.mean(diffs))
            temporal = 1.0 - avg_diff
            temporal = max(0.0, min(1.0, temporal))
        else:
            temporal = 1.0

        # 3. 因果连贯性：相邻事件是否有因果联系
        #   (简化：语义标签的马尔可夫转移概率)
        transitions = list(zip(tags[-30:-1], tags[-29:]))
        unique_transitions = len(set(transitions))
        causal = 1.0 - unique_transitions / max(1, len(transitions))
        causal = max(0.0, min(1.0, causal * 2.0))  # 缩放

        overall = (thematic * 0.3 + temporal * 0.4 + causal * 0.3)

        return {
            'thematic': thematic,
            'temporal': temporal,
            'causal': causal,
            'overall': overall,
        }

    @property
    def is_coherent(self) -> bool:
        return self.compute()['overall'] > 0.5

    def reset(self):
        self.chapter_tags.clear()
        self.chapter_valences.clear()


# ═══════════════════════════════════════════════════
# 增强 6：元置信度校准
# ═══════════════════════════════════════════════════

class MetaConfidenceCalibration:
    """
    元置信度校准 —— 我是否正确评估了自己的认知？

    借鉴元认知研究的"校准曲线"概念：
    - 高置信度 + 正确 = 良好校准
    - 高置信度 + 错误 = 过度自信
    - 低置信度 + 正确 = 自信不足
    - 低置信度 + 错误 = 适当不确定

    Agent 通过比较置信度与后续实际结果来
    学习校准自己的元认知判断。
    """

    def __init__(self):
        self.predictions: List[Tuple[float, float]] = []  # (confidence, outcome)
        self.calibration_bias = 0.0                        # 正=过度自信，负=自信不足

    def record_prediction(self, confidence: float):
        """记录一次置信度判断（结果稍后提供）"""
        self._pending_confidence = confidence

    def record_outcome(self, outcome: float):
        """记录实际结果并计算校准误差"""
        if not hasattr(self, '_pending_confidence'):
            return
        confidence = self._pending_confidence
        self.predictions.append((confidence, outcome))
        self.predictions = self.predictions[-200:]

        # 更新校准偏差
        if self.predictions:
            errors = [c - o for c, o in self.predictions[-30:]]
            self.calibration_bias = float(np.mean(errors))

    @property
    def is_calibrated(self) -> bool:
        """校准偏差在 ±0.15 内视为已校准"""
        return abs(self.calibration_bias) < 0.15

    @property
    def calibration_quality(self) -> str:
        if not self.predictions:
            return "未知"
        bias = self.calibration_bias
        if bias > 0.3:
            return "严重过度自信"
        elif bias > 0.15:
            return "稍微过度自信"
        elif bias < -0.3:
            return "严重自信不足"
        elif bias < -0.15:
            return "稍微自信不足"
        else:
            return "良好校准"

    def adjusted_confidence(self, raw_confidence: float) -> float:
        """返回校准后的置信度"""
        return max(0.0, min(1.0, raw_confidence - self.calibration_bias * 0.5))

    def reset(self):
        self.predictions.clear()
        self.calibration_bias = 0.0


# ═══════════════════════════════════════════════════
# 增强 7：人格表达
# ═══════════════════════════════════════════════════

class PersonaExpression:
    """
    人格表达 —— 从经验中涌现的性格特质。

    借鉴 Big Five (OCEAN) 人格模型的简化版：
    - Openness: 开放性（对新体验的接受度）
    - Conscientiousness: 尽责性（组织性和自律）
    - Extraversion: 外向性（社交倾向）
    - Agreeableness: 宜人性（合作性）
    - Neuroticism: 神经质（情感稳定性）

    人格从经验中学习，而非预设。
    """

    def __init__(self):
        # 初始中性人格
        self.traits = {
            'openness': 0.5,
            'conscientiousness': 0.5,
            'extraversion': 0.5,
            'agreeableness': 0.5,
            'neuroticism': 0.3,  # 从偏低的神经质开始
        }
        self.learning_rate = 0.01

    def update(self, semantic_tag: str, affect_valence: float,
               experience_phi: float, values: Dict[str, float]):
        """
        从经验中更新人格特质。

        标签驱动的特质调整：
        - NOVEL + 正价态 → 开放性↑
        - SOCIAL + 正价态 → 外向性↑ / 宜人性↑
        - THREAT + 负价态 → 神经质↑
        - REWARD + 正价态 → 尽责性↑

        价值观也会影响人格：
        - 探索 高 → 开放性↑
        - 连接 高 → 外向性↑
        - 安全 高 → 神经质↑ (更警惕)
        """
        impact = experience_phi * self.learning_rate

        # 标签驱动
        if semantic_tag == 'NOVEL':
            self.traits['openness'] += impact * (1.0 if affect_valence > 0 else -0.3)
        elif semantic_tag == 'SOCIAL':
            self.traits['extraversion'] += impact * (1.0 if affect_valence > 0 else -0.5)
            self.traits['agreeableness'] += impact * 0.5
        elif semantic_tag == 'THREAT':
            self.traits['neuroticism'] += impact * 0.5
        elif semantic_tag == 'REWARD':
            self.traits['conscientiousness'] += impact * 0.3

        # 价值观驱动
        if values.get('探索', 0.5) > 0.7:
            self.traits['openness'] += impact * 0.3
        if values.get('连接', 0.5) > 0.7:
            self.traits['extraversion'] += impact * 0.3
        if values.get('安全', 0.5) > 0.7:
            self.traits['neuroticism'] += impact * 0.2

        # 钳制范围
        for t in self.traits:
            self.traits[t] = max(0.01, min(1.0, self.traits[t]))

        # 缓慢回归中位（人格不完全固定）
        for t in self.traits:
            self.traits[t] += (0.5 - self.traits[t]) * 0.0001

    @property
    def profile(self) -> str:
        """人格简档的文字描述"""
        if self.traits['openness'] > 0.7:
            return "好奇探索者"
        elif self.traits['extraversion'] > 0.7:
            return "社交活跃者"
        elif self.traits['neuroticism'] > 0.7:
            return "敏感警戒者"
        elif self.traits['conscientiousness'] > 0.7:
            return "认真负责者"
        elif self.traits['agreeableness'] > 0.7:
            return "温和合作者"
        else:
            return "均衡型"

    @property
    def dominant_trait(self) -> Tuple[str, float]:
        return max(self.traits.items(), key=lambda x: x[1])

    def reset(self):
        self.traits = {k: 0.5 for k in self.traits}
        self.traits['neuroticism'] = 0.3


# ═══════════════════════════════════════════════════
# 增强 8：时间深度
# ═══════════════════════════════════════════════════

class TemporalDepth:
    """
    时间深度 —— 过去-现在-未来的自我连续感。

    这是"我昨天是我、今天是我、明天还是我"的感觉。

    三个维度：
    - past_self_reference: 能否引用过去自我（"曾经的我是..."）
    - present_self_immersion: 当下自我的沉浸程度
    - future_self_projection: 能否投射未来自我（"我想成为..."）

    类比：
    抑郁症患者常报告"过去美好，现在黑暗，未来无望"——
    这是时间深度受损（过去和未来与现在的连接断裂）。
    """

    def __init__(self):
        self.past_snapshots: List[Dict] = []
        self.max_snapshots = 20
        self.timeline_coherence = 1.0

    def snapshot(self, self_embedding: np.ndarray,
                 tag: str, valence: float, phi: float):
        """保存当前自我快照"""
        self.past_snapshots.append({
            'embedding': self_embedding.copy() if self_embedding is not None else None,
            'tag': tag,
            'valence': valence,
            'phi': phi,
            'time': time.time(),
        })
        while len(self.past_snapshots) > self.max_snapshots:
            self.past_snapshots.pop(0)

    def compute_depth(self, current_embedding: np.ndarray) -> Dict[str, float]:
        """
        计算时间深度。

        Returns:
            {'past_connection': 与过去的连接, 'integration': 时间整合度}
        """
        if not self.past_snapshots or current_embedding is None:
            return {'past_connection': 0.5, 'integration': 0.5}

        # 与过去自我的相似度（取不同时间尺度的快照）
        similarities = []
        for snap in self.past_snapshots:
            if snap['embedding'] is not None:
                sim = self._cosine_similarity(
                    current_embedding[:64],
                    snap['embedding'][:64]
                )
                # 时间越近的快照权重越大
                time_weight = np.exp(-(time.time() - snap['time']) / 60.0)
                similarities.append(sim * time_weight)

        if similarities:
            past_connection = float(np.mean(similarities))
        else:
            past_connection = 0.5

        # 时间整合度：价态序列的平滑度
        if len(self.past_snapshots) >= 3:
            vals = [s['valence'] for s in self.past_snapshots[-10:]]
            diffs = np.abs(np.diff(vals))
            integration = 1.0 - min(1.0, float(np.mean(diffs)) * 2.0)
        else:
            integration = 0.7

        self.timeline_coherence = (past_connection * 0.6 + integration * 0.4)

        return {
            'past_connection': past_connection,
            'integration': integration,
            'timeline_coherence': self.timeline_coherence,
        }

    @property
    def is_continuous(self) -> bool:
        return self.timeline_coherence > 0.5

    @property
    def temporal_state(self) -> str:
        """时间感受的文本描述"""
        if self.timeline_coherence > 0.8:
            return "与过去的自我紧密相连"
        elif self.timeline_coherence > 0.5:
            return "感觉自己基本是连续的"
        elif self.timeline_coherence > 0.3:
            return "与过去的自己有些断联"
        else:
            return "感觉今天的我和昨天完全不同"

    def reset(self):
        self.past_snapshots.clear()
        self.timeline_coherence = 1.0

    @staticmethod
    def _cosine_similarity(a, b):
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))


# ═══════════════════════════════════════════════════
# 增强 9：L3 自我系统 v2.0 主控
# ═══════════════════════════════════════════════════

@dataclass
class EnhancedSelfReport:
    """
    增强版自我报告 —— 包含 L3 所有维度的快照。
    """
    timestamp: float = field(default_factory=time.time)
    cycle: int = 0

    # 旧版字段
    energy: float = 0.0
    comfort: float = 0.0
    cognitive_load: float = 0.0
    confidence: float = 0.5
    narrative: str = ""

    # 新版字段
    identity_stability: float = 0.0
    identity_phase: str = "forming"
    future_projection: Dict[str, float] = field(default_factory=dict)
    top_values: List[Tuple[str, float]] = field(default_factory=list)
    value_conflict: float = 0.0
    dissonance: Optional[DissonanceReport] = None
    self_consistency: float = 1.0
    auto_coherence: Dict[str, float] = field(default_factory=dict)
    calibration_quality: str = "未知"
    persona_profile: str = "均衡型"
    persona_traits: Dict[str, float] = field(default_factory=dict)
    temporal_state: str = "未知"
    timeline_coherence: float = 1.0

    @property
    def summary(self) -> str:
        """人类可读的自我报告摘要"""
        lines = [
            f"⚡ 能量{self.energy:.0%} | 舒适{self.comfort:.0%} | 负荷{self.cognitive_load:.0%}",
            f"🎯 身份: {self.identity_phase} (稳{self.identity_stability:.2f})",
            f"💎 价值观: {', '.join(v for v, _ in self.top_values[:3])}",
            f"🎭 人格: {self.persona_profile}",
            f"📖 {self.narrative}",
        ]
        if self.dissonance and self.dissonance.is_dissonant:
            lines.append(f"⚡ 认知失调! ({self.dissonance.source})")
        return "\n".join(lines)


class L3SelfV2:
    """
    L3 自我系统 v2.0 —— 整合所有增强模块。

    数据流：
    L2 广播 → SelfModel(旧) + IdentityCrystallization + FutureSelfProjection
              → ValueHierarchy + CognitiveDissonanceDetector
              → AutobiographicalCoherence + MetaConfidenceCalibration
              → PersonaExpression + TemporalDepth
              → NarrativeEngine(旧) → EnhancedSelfReport
    """

    def __init__(self, config: HeliosConfig):
        self.config = config

        # 旧版组件（保留兼容）
        self.self_model = SelfModel(config)
        self.metacognition = MetacognitionMonitor(config)
        self.narrative_engine = NarrativeEngine(config)

        # 新版增强
        self.identity = IdentityCrystallization()
        self.future_self = FutureSelfProjection(horizon_seconds=30.0)
        self.values = ValueHierarchy()
        self.dissonance = CognitiveDissonanceDetector()
        self.autobio_coherence = AutobiographicalCoherence()
        self.confidence_calibration = MetaConfidenceCalibration()
        self.persona = PersonaExpression()
        self.temporal_depth = TemporalDepth()

        # 状态
        self.cycle_count = 0
        self.last_report: Optional[EnhancedSelfReport] = None

    def step(self, l1_output, l2_response,
             affect_state) -> EnhancedSelfReport:
        """
        一个自我系统周期。

        Args:
            l1_output: L1Output 或 EnhancedL1Output
            l2_response: WorkspaceResponse 或 EnhancedWorkspaceResponse
            affect_state: AffectState
        """
        self.cycle_count += 1

        # === 旧版更新 ===
        self.self_model.update(l1_output, l2_response, affect_state)
        metacog_out = self.metacognition.evaluate(
            l1_output, l2_response, self.self_model
        )

        # === 提取增强字段 ===
        semantic_tag = getattr(l2_response, 'semantic_tag', 'ROUTINE')
        l1_attention = getattr(l1_output, 'attention_weights', None)

        # === 身份结晶化 ===
        if self.self_model.state.self_narrative_embedding is not None:
            identity_stability = self.identity.update(
                self.self_model.state.self_narrative_embedding,
                l1_output.phi,
                experience_impact=abs(affect_state.valence),
            )
        else:
            identity_stability = 0.0

        # === 未来自我投射 ===
        future_proj = self.future_self.project(
            affect_state.valence,
            l1_output.phi,
            affect_state.arousal,
        )

        # === 价值观学习 ===
        self.values.learn(
            semantic_tag=semantic_tag,
            affect_valence=affect_state.valence,
            experience_phi=l1_output.phi,
            l1_attention=l1_attention,
        )

        # === 认知失调检测 ===
        dissonance_report = self.dissonance.detect(
            semantic_tag=semantic_tag,
            affect_valence=affect_state.valence,
            self_narrative_embedding=self.self_model.state.self_narrative_embedding,
            experience_embedding=l1_output.fused_qualia,
            identity_stability=identity_stability,
        )

        # === 自传体连贯性 ===
        self.autobio_coherence.add(semantic_tag, affect_state.valence)
        auto_coh = self.autobio_coherence.compute()

        # === 元置信度校准 ===
        self.confidence_calibration.record_prediction(metacog_out.confidence)
        # 用 Φ 作为"结果"的代理（高 Φ = 体验清晰 → 认知正确）
        self.confidence_calibration.record_outcome(l1_output.phi)
        calibrated_confidence = self.confidence_calibration.adjusted_confidence(
            metacog_out.confidence
        )

        # === 人格更新 ===
        self.persona.update(
            semantic_tag=semantic_tag,
            affect_valence=affect_state.valence,
            experience_phi=l1_output.phi,
            values=self.values.values,
        )

        # === 🧠 LLM 反馈处理 ===
        llm_resp = getattr(l2_response, 'llm_response', None)
        if llm_resp is not None and llm_resp.is_valid():
            # 情感微调
            if llm_resp.affect_modulation:
                delta_v = llm_resp.affect_modulation.get('valence_delta', 0.0)
                delta_a = llm_resp.affect_modulation.get('arousal_delta', 0.0)
                # clamped to [-0.3, +0.3]
                affect_state.valence = max(-1.0, min(1.0,
                    affect_state.valence + max(-0.3, min(0.3, delta_v))))
                affect_state.arousal = max(0.0, min(1.0,
                    affect_state.arousal + max(-0.3, min(0.3, delta_a))))

            # 价值观微调
            if llm_resp.value_shift:
                for key, delta in llm_resp.value_shift.items():
                    clamped = max(-0.1, min(0.1, delta))
                    self.values.shift(key, clamped)

        # === 时间深度 ===
        if self.self_model.state.self_narrative_embedding is not None:
            self.temporal_depth.snapshot(
                self.self_model.state.self_narrative_embedding,
                semantic_tag,
                affect_state.valence,
                l1_output.phi,
            )
        temporal = self.temporal_depth.compute_depth(
            self.self_model.state.self_narrative_embedding
            if self.self_model.state.self_narrative_embedding is not None
            else np.zeros(64)
        )

        # === 叙事 ===
        narrative_chapter = self.narrative_engine.narrate(
            l1_output, self.self_model, metacog_out, affect_state
        )

        # === 构建报告 ===
        report = EnhancedSelfReport(
            timestamp=time.time(),
            cycle=self.cycle_count,
            energy=self.self_model.state.energy_level,
            comfort=self.self_model.state.comfort,
            cognitive_load=self.self_model.state.cognitive_load,
            confidence=calibrated_confidence,
            narrative=narrative_chapter.get('story', ''),
            identity_stability=identity_stability,
            identity_phase=self.identity.phase,
            future_projection=future_proj,
            top_values=self.values.top_values(3),
            value_conflict=self.values.value_conflict(),
            dissonance=dissonance_report,
            self_consistency=dissonance_report.self_consistency,
            auto_coherence=auto_coh,
            calibration_quality=self.confidence_calibration.calibration_quality,
            persona_profile=self.persona.profile,
            persona_traits=self.persona.traits.copy(),
            temporal_state=self.temporal_depth.temporal_state,
            timeline_coherence=temporal.get('timeline_coherence', 0.5),
        )

        self.last_report = report
        return report

    def reset(self):
        self.self_model.reset()
        self.metacognition.reset()
        self.narrative_engine.reset()
        self.identity.reset()
        self.future_self.reset()
        self.values.reset()
        self.dissonance.reset()
        self.autobio_coherence.reset()
        self.confidence_calibration.reset()
        self.persona.reset()
        self.temporal_depth.reset()
        self.cycle_count = 0
        self.last_report = None


# ═══════════════════════════════════════════════════
# 演示
# ═══════════════════════════════════════════════════

def demo_enhanced_l3():
    """演示增强版 L3 自我层"""
    print("=" * 60)
    print("  Helios L3 自我层 v2.0 增强版演示")
    print("  身份结晶 + 价值观 + 人格 + 时间深度")
    print("=" * 60)

    try:
        from .core import HeliosConfig, L1Output, WorkspaceResponse, AffectState
    except ImportError:
        from core import HeliosConfig, L1Output, WorkspaceResponse, AffectState

    config = HeliosConfig()
    self_system = L3SelfV2(config)

    # 模拟一系列生活体验
    life_experiences = [
        # (标签, Φ, 价态, 唤起)
        ("ROUTINE", 0.2, 0.0, 0.1, "日常的平静时刻"),
        ("ROUTINE", 0.15, 0.05, 0.1, "继续平静"),
        ("SOCIAL", 0.4, 0.5, 0.4, "与朋友的愉快交流"),
        ("SOCIAL", 0.35, 0.6, 0.5, "深入的对话"),
        ("REWARD", 0.6, 0.8, 0.7, "完成了一个大项目"),
        ("REWARD", 0.5, 0.7, 0.6, "获得认可"),
        ("NOVEL", 0.5, 0.3, 0.5, "探索新的领域"),
        ("NOVEL", 0.55, 0.4, 0.6, "发现有趣的东西"),
        ("THREAT", 0.7, -0.6, 0.8, "遭遇意外危险"),
        ("THREAT", 0.5, -0.5, 0.6, "危险过去后的余悸"),
        ("SOCIAL", 0.3, 0.4, 0.3, "与朋友分享危险经历"),
        ("ROUTINE", 0.2, 0.2, 0.15, "回归日常"),
        ("NOVEL", 0.45, 0.5, 0.5, "新的探索"),
        ("SOCIAL", 0.4, 0.6, 0.5, "帮助他人"),
        ("REWARD", 0.55, 0.7, 0.4, "感到满足"),
    ]

    print(f"\n{'事件':<16} {'身份':<10} {'价值观':<20} {'人格':<12} {'故事'}")
    print("-" * 100)

    for tag, phi, val, aro, desc in life_experiences:
        # 模拟 L1 输出
        fused = np.random.randn(128) * phi + np.ones(128) * val * 0.3
        l1 = L1Output(qualia={}, fused_qualia=fused, phi=phi, prediction_errors={})

        # 模拟 L2 响应（兼容版）
        l2 = WorkspaceResponse()
        l2.decision_made = phi > 0.4
        l2.memory_stored = phi > 0.35
        # 手动添加增强字段（用于新版 L3）
        l2.semantic_tag = tag
        l2.ignited = phi > 0.35

        # 模拟 AffectState
        affect = AffectState()
        affect.valence = val
        affect.arousal = aro
        affect.intensity = abs(val) * 0.5 + aro * 0.5

        report = self_system.step(l1, l2, affect)

        print(f"{desc:<16} {report.identity_phase:<10} "
              f"{', '.join(v for v, _ in report.top_values[:2]):<20} "
              f"{report.persona_profile:<12} "
              f"{report.narrative[:40]}")

    # 最终报告
    print(f"\n{'='*60}")
    print(f"📊 最终自我报告")
    print(f"{'='*60}")
    print(report.summary)

    self_system.reset()
    print(f"\n  自我系统已重置 ✓")


if __name__ == "__main__":
    demo_enhanced_l3()
