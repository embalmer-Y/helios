"""
L2 广播层 —— Helios 的"传菜铃" / 全局工作空间

基于全局神经工作空间理论(GNW):
- L1 的"质感"需要被"广播"到全系统才能被利用
- 不是所有信息都需要广播——只有"值得的"才点火
- 点火是非线性的——要么全燃，要么不燃
- 点火后自持一段时间，产生"意识时刻"
"""

import time
import numpy as np
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field

try:
    from .core import L1Output, WorkspaceResponse, HeliosConfig, AffectState
except ImportError:
    from core import L1Output, WorkspaceResponse, HeliosConfig, AffectState


# ═══════════════════════════════════════════════════
# 点火判断
# ═══════════════════════════════════════════════════

class IgnitionGate:
    """
    点火门控。

    判断条件（四个维度的加权组合）：
    1. Φ > 阈值 —— 信息足够整合
    2. 新颖性 —— 与上一帧差异足够大
    3. 情感显著性 —— 情感系统标记为"重要"
    4. 惊讶度 —— 预测误差超出预期

    点火是非线性的门控：要么全燃，要么不燃。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.threshold = config.ignition_threshold

    def should_ignite(self,
                      l1_output: L1Output,
                      affect_salience: float,
                      previous_content: Optional[np.ndarray]) -> Tuple[bool, float]:
        """
        判断是否点火。

        Returns:
            (是否点火, 点火得分)
        """
        # === 1. Φ 得分（40%权重） ===
        phi_score = l1_output.phi

        # === 2. 新颖性得分（30%权重） ===
        if previous_content is not None and l1_output.fused_qualia is not None:
            # 余弦相似度 → 新颖性 = 1 - 相似度
            similarity = self._cosine_similarity(
                l1_output.fused_qualia,
                previous_content
            )
            novelty = 1.0 - similarity
            # 加少量噪声避免完全相同的帧得分为0
            novelty = max(0.01, novelty)
        else:
            novelty = 0.5  # 第一次：中等新颖性

        # === 3. 情感显著性得分（30%权重） ===
        # 强烈情感（无论正负）都更容易点火
        emotional_salience = affect_salience

        # === 4. 惊讶度加分（bonus） ===
        avg_error = np.mean(list(l1_output.prediction_errors.values())) if l1_output.prediction_errors else 0.0
        surprise_bonus = min(0.3, avg_error * 2.0)

        # === 综合得分 ===
        ignition_score = (
            phi_score * 0.4 +
            novelty * 0.3 +
            emotional_salience * 0.3 +
            surprise_bonus
        )

        # === 非线性门控 ===
        # sigmoid 让靠近阈值的区域有陡峭的开关行为
        gate_output = 1.0 / (1.0 + np.exp(-(ignition_score - self.threshold) * 10))

        return gate_output > 0.5, ignition_score

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """余弦相似度"""
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))


# ═══════════════════════════════════════════════════
# 点火自持动态
# ═══════════════════════════════════════════════════

class IgnitionDynamics:
    """
    点火的自持动态。

    关键设计：点火后不是立即熄灭，而是自持一段时间。

    原理：
    - 点火后，即使刺激消失，活动仍持续
    - 持续时间 = f(Φ, 情感显著性)
    - 在点火期间抑制新的点火（不应期）

    类比：
    就像你被吓了一跳——即使惊吓源已经消失，
    你的心跳还是快了好几秒。"意识时刻"也需要这种惯性。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.is_ignited = False
        self.ignition_start_time = 0.0
        self.sustain_duration = 0.0
        self.refractory_until = 0.0  # 不应期结束时间

    def ignite(self, phi: float, affect_intensity: float):
        """开始点火，计算自持时长"""
        self.is_ignited = True
        self.ignition_start_time = time.time()

        # Φ 越高、情感越强 → 自持越久
        self.sustain_duration = (
            self.config.sustain_base +
            phi * self.config.sustain_phi_factor +
            affect_intensity * self.config.sustain_affect_factor
        )
        # 范围约：0.1秒 ~ 4秒

        # 设置不应期（点火结束后短暂时间内不会再点火）
        refractory_period = 0.05  # 缩短不应期
        self.refractory_until = (
            self.ignition_start_time +
            self.sustain_duration +
            refractory_period
        )

    def is_active(self) -> bool:
        """检查是否仍处于点火状态"""
        if not self.is_ignited:
            return False
        if time.time() - self.ignition_start_time > self.sustain_duration:
            self.is_ignited = False
            return False
        return True

    def is_refractory(self) -> bool:
        """检查是否处于不应期"""
        return time.time() < self.refractory_until

    @property
    def remaining(self) -> float:
        """剩余点火时间"""
        if not self.is_ignited:
            return 0.0
        elapsed = time.time() - self.ignition_start_time
        return max(0.0, self.sustain_duration - elapsed)


# ═══════════════════════════════════════════════════
# 全局工作空间
# ═══════════════════════════════════════════════════

class GlobalWorkspace:
    """
    L2 全局工作空间。

    点火时，将 L1 的质感广播到所有子系统：
    - 记忆写入
    - 语言生成
    - 决策引擎
    - 动作规划
    - 情感表达

    这是"传菜铃"响起后的完整连锁反应。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.current_content: Optional[np.ndarray] = None
        self.previous_content: Optional[np.ndarray] = None

        # 子组件
        self.gate = IgnitionGate(config)
        self.dynamics = IgnitionDynamics(config)

        # 点火统计
        self.total_ignitions: int = 0
        self.ignition_history: List[dict] = []

    def cycle(self,
              l1_output: L1Output,
              affect_state: AffectState,
              memory_system,
              self_model,
              decision_engine,
              verbose: bool = False) -> Optional[WorkspaceResponse]:
        """
        L2 主循环步骤。

        检查是否应该点火，如果点火则广播到所有子系统。

        Returns:
            WorkspaceResponse if ignited, None otherwise
        """
        # 如果不处于点火自持状态且不在不应期，检查是否触发新的点火
        if not self.dynamics.is_active() and not self.dynamics.is_refractory():
            should_fire, score = self.gate.should_ignite(
                l1_output,
                affect_salience=affect_state.intensity,
                previous_content=self.current_content,
            )

            if should_fire:
                # 🔥 点火！
                self.dynamics.ignite(l1_output.phi, affect_state.intensity)
                self.total_ignitions += 1
                self.steps_since_ignition = 0  # 点火时重置步数计数

                # 更新工作空间内容
                self.previous_content = self.current_content
                if l1_output.fused_qualia is not None:
                    self.current_content = l1_output.fused_qualia.copy()

                # === 广播到所有子系统 ===
                response = WorkspaceResponse()

                # 1. 记忆存储
                if hasattr(memory_system, 'store_episodic'):
                    memory_system.store_episodic(l1_output, affect_state)

                # 2. 语言生成（简化版——基于当前体验生成描述）
                lang = self._generate_language(l1_output, affect_state)
                response.language_output = lang

                # 3. 决策
                if hasattr(decision_engine, 'decide'):
                    decision = decision_engine.decide(
                        l1_output, affect_state, memory_system, self_model
                    )
                    response.decision_made = decision is not None

                # 4. 情感表达
                response.affect_expression = self._express_affect(affect_state)

                # 记录
                self.ignition_history.append({
                    'timestamp': time.time(),
                    'phi': l1_output.phi,
                    'score': score,
                    'affect_valence': affect_state.valence,
                    'affect_arousal': affect_state.arousal,
                })
                # 只保留最近 100 次
                self.ignition_history = self.ignition_history[-100:]

                if verbose:
                    print(f"  🔥 IGNITION! Φ={l1_output.phi:.3f} "
                          f"score={score:.3f} affect={affect_state.valence:+.2f} "
                          f"(#{self.total_ignitions})")

                return response

        elif self.dynamics.is_active():
            # 点火自持中——继续广播当前内容
            if verbose:
                print(f"  💫 sustaining... ({self.dynamics.remaining:.2f}s left)")

        return None

    def _generate_language(self, l1_output: L1Output, affect: AffectState) -> str:
        """简化的语言生成——将体验转化为文字描述"""
        phi = l1_output.phi

        # 基于 Φ 和情感的组合来生成描述
        if affect.is_positive and phi > 0.5:
            return "这感觉很清晰、很美好..."
        elif affect.is_positive and phi > 0.3:
            return "嗯，还不错的感觉"
        elif affect.is_negative and phi > 0.5:
            return "一种强烈的...不舒服的感觉"
        elif affect.is_negative:
            return "有点不对劲..."
        elif phi > 0.6:
            return "感受到了什么，很清晰"
        elif phi > 0.3:
            return "有某种模糊的感知"
        else:
            return "..."

    def _express_affect(self, affect: AffectState) -> str:
        """情感表达"""
        if affect.is_positive and affect.arousal > 0.5:
            return "😊 兴奋/喜悦"
        elif affect.is_positive:
            return "🙂 满足/平静"
        elif affect.is_negative and affect.arousal > 0.5:
            return "😰 焦虑/恐惧"
        elif affect.is_negative:
            return "😞 低落/不适"
        else:
            return "😐 中性"

    @property
    def avg_phi(self) -> float:
        """平均点火 Φ 值"""
        if not self.ignition_history:
            return 0.0
        return np.mean([h['phi'] for h in self.ignition_history])

    @property
    def recent_ignition_rate(self) -> float:
        """最近的点火频率（次/秒）"""
        if len(self.ignition_history) < 2:
            return 0.0
        recent = self.ignition_history[-20:]
        if len(recent) < 2:
            return 0.0
        duration = recent[-1]['timestamp'] - recent[0]['timestamp']
        return len(recent) / max(0.01, duration)

    def reset(self):
        """重置工作空间"""
        self.current_content = None
        self.previous_content = None
        self.total_ignitions = 0
        self.ignition_history.clear()


# ═══════════════════════════════════════════════════
# ══  L2 广播层 v2.0 增强版  ══
# ═══════════════════════════════════════════════════
#
# 新增模块：
#   IgnitionGateV2          — 增强版门控（利用 L1 v2 的注意力/连贯性/惊奇度）
#   SemanticTagger          — 语义标签提取（threat/reward/social/novel/routine）
#   WorkingMemorySlots      — 有限工作记忆槽位（7±2，借鉴 GNW 容量限制）
#   InhibitionControl       — 抑制控制（自适应阈值，防假阳性）
#   BroadcastDecayCurve     — 广播衰减曲线（内容渐消而非瞬间消失）
#   RhythmicOscillator      — 节律振荡器（Theta/Gamma 相位采样）
#   BroadcastHistory        — 广播历史与重复抑制
#   AttentionGatedBroadcast — 注意力门控分发（不同子系统收到不同强度的广播）
#   GlobalWorkspaceV2       — 整合所有增强模块的主工作空间
#
# ═══════════════════════════════════════════════════


# ═══════════════════════════════════════════════════
# 增强 1：增强版点火门控
# ═══════════════════════════════════════════════════

class IgnitionGateV2:
    """
    增强版点火门控 —— 利用 L1 v2 的丰富输出。

    相比旧版 IgnitionGate 的改进：
    1. 五维评分：Φ + 新颖性 + 情感显著性 + L1注意力 + 惊奇度
    2. 门控曲线可自适应陡峭度
    3. 最低点火间隔（防止短时间内反复点火浪费）
    4. 点火元数据（哪些维度贡献最大）供下游使用
    """

    def __init__(self, config: HeliosConfig,
                 min_inter_ignition_steps: int = 3):
        self.config = config
        self.threshold = config.ignition_threshold
        self.min_steps = min_inter_ignition_steps
        self.steps_since_ignition = 999  # 初始值很大，允许立即点火
        self.total_ignitions = 0

        # 可学习的维度权重（初始值，会被 InhibitionControl 微调）
        self.weights = {
            'phi': 0.35,
            'novelty': 0.20,
            'affect': 0.20,
            'attention': 0.10,
            'surprise': 0.15,
        }

    def should_ignite(self,
                      l1_output,
                      affect_salience: float,
                      previous_content,
                      l1_attention_weights=None,
                      l1_surprise: float = 0.0) -> Tuple[bool, float, Dict[str, float]]:
        """
        判断是否点火。

        Args:
            l1_output: L1Output 或 EnhancedL1Output
            affect_salience: 情感显著性 (0-1)
            previous_content: 上一帧融合向量
            l1_attention_weights: L1 v2 的注意力权重 {modality: weight}
            l1_surprise: L1 v2 的惊奇度

        Returns:
            (是否点火, 综合得分, 各维度贡献)
        """
        # 最小间隔检查（基于步数而非时间）
        if self.steps_since_ignition < self.min_steps:
            self.steps_since_ignition += 1
            return False, 0.0, {}

        # === 1. Φ 得分（35%） ===
        phi_score = l1_output.phi

        # === 2. 新颖性得分（20%） ===
        if previous_content is not None and l1_output.fused_qualia is not None:
            similarity = self._cosine_similarity(
                l1_output.fused_qualia, previous_content
            )
            novelty = max(0.01, 1.0 - similarity)
        else:
            novelty = 0.5

        # === 3. 情感显著性（20%） ===
        emotional_salience = affect_salience

        # === 4. L1 注意力得分（10%） ===
        # 注意力集中（某模态显著高于其他）→ 更容易点火
        if l1_attention_weights and len(l1_attention_weights) > 1:
            weights_sorted = sorted(l1_attention_weights.values(), reverse=True)
            # 最高权重与第二高的差距 → 注意力集中度
            attention_focus = weights_sorted[0] - weights_sorted[1] if len(weights_sorted) > 1 else weights_sorted[0]
            attention_focus = max(0.0, min(1.0, attention_focus * 3.0))
        else:
            attention_focus = 0.3

        # === 5. 惊奇度得分（15%） ===
        surprise_score = min(1.0, l1_surprise * 0.5) if l1_surprise > 0 else 0.0

        # === 综合得分 ===
        contributions = {
            'phi': phi_score,
            'novelty': novelty,
            'affect': emotional_salience,
            'attention': attention_focus,
            'surprise': surprise_score,
        }

        ignition_score = sum(
            self.weights[k] * v for k, v in contributions.items()
        )

        # === 自适应陡峭度的 sigmoid 门控 ===
        # 根据总点火次数调整陡峭度：点火越多→门控越陡（更严格）
        steepness = 8.0 + self.total_ignitions * 0.05
        gate_output = 1.0 / (1.0 + np.exp(
            -(ignition_score - self.threshold) * steepness
        ))

        is_ignited = gate_output > 0.5
        if is_ignited:
            self.steps_since_ignition = 0
            self.total_ignitions += 1

        return is_ignited, ignition_score, contributions

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))


# ═══════════════════════════════════════════════════
# 增强 2：语义标签提取器
# ═══════════════════════════════════════════════════

class SemanticTagger:
    """
    语义标签提取器 —— 为广播内容打上分类标签。

    标签类别（借鉴 Panksepp 情感系统和 GNW 分类）：
    - THREAT: 威胁信号（负价态+高唤起）
    - REWARD: 奖赏信号（正价态+高唤起）
    - SOCIAL: 社交信号（文字模态+中等唤起）
    - NOVEL: 新奇信号（高新奇度+中等唤起）
    - ROUTINE: 常规信号（低新奇度+低唤起）
    - BODILY: 身体信号（内感/本体感主导）

    用途：
    - 记忆系统按标签索引
    - 广播历史按标签做重复抑制
    - L3 叙事引擎按标签组织自传体
    """

    TAG_CATEGORIES = ['THREAT', 'REWARD', 'SOCIAL', 'NOVEL', 'ROUTINE', 'BODILY']

    def tag(self, l1_output,
            affect_state=None,
            l1_attention=None) -> Tuple[str, Dict[str, float]]:
        """
        为当前 L1 体验打标签。

        Returns:
            (主标签, {标签: 分数})
        """
        scores = {tag: 0.0 for tag in self.TAG_CATEGORIES}

        # 从 affect_state 获取价态和唤起
        valence = getattr(affect_state, 'valence', 0.0) if affect_state else 0.0
        arousal = getattr(affect_state, 'arousal', 0.0) if affect_state else 0.0

        # THREAT: 负价态 + 高唤起 + 高惊奇
        threat_score = (
            max(0.0, -valence) * 0.5 +
            arousal * 0.3 +
            (l1_output.surprise if hasattr(l1_output, 'surprise') else 0.0) * 0.2
        )
        scores['THREAT'] = min(1.0, threat_score)

        # REWARD: 正价态 + 高唤起
        reward_score = (
            max(0.0, valence) * 0.6 + arousal * 0.4
        )
        scores['REWARD'] = min(1.0, reward_score)

        # SOCIAL: 文字模态主导
        social_score = 0.0
        if l1_attention:
            text_attn = l1_attention.get('text', 0.0)
            social_score = text_attn * 0.7 + abs(valence) * 0.3
        scores['SOCIAL'] = min(1.0, social_score)

        # NOVEL: 高新奇度
        if hasattr(l1_output, 'coherence') and l1_output.coherence:
            novelty = 1.0 - l1_output.coherence.coherence_score
        else:
            novelty = 0.5
        scores['NOVEL'] = min(1.0, novelty * 0.8 + arousal * 0.2)

        # ROUTINE: 默认标签，低新奇+低唤起
        # 但如果 THREAT 或 REWARD 得分足够高，ROUTINE 不应当覆盖它们
        routine_score = (1.0 - novelty) * 0.7 + (1.0 - arousal) * 0.3
        # 弱化 ROUTINE：当 THREAT > 0.4 或 REWARD > 0.4 时，ROUTINE 打折
        if scores['THREAT'] > 0.4:
            routine_score *= 0.3  # 严重削弱
        elif scores['REWARD'] > 0.4:
            routine_score *= 0.5
        scores['ROUTINE'] = min(1.0, routine_score)

        # BODILY: 内感/本体感主导
        if l1_attention:
            body_attn = l1_attention.get('interoception', 0.0) + \
                        l1_attention.get('proprioception', 0.0)
            scores['BODILY'] = min(1.0, body_attn * 1.5)

        # 返回最高分标签
        primary = max(scores, key=scores.get)
        return primary, scores


# ═══════════════════════════════════════════════════
# 增强 3：有限工作记忆槽位
# ═══════════════════════════════════════════════════

@dataclass
class MemorySlot:
    """工作记忆中的一个槽位"""
    content: np.ndarray           # 广播内容（融合质感向量）
    tag: str = "ROUTINE"          # 语义标签
    salience: float = 0.0         # 显著性（点火得分）
    timestamp: float = 0.0        # 入槽时间
    decay_rate: float = 0.05      # 衰减率
    access_count: int = 0         # 被访问次数

    @property
    def decayed_salience(self) -> float:
        """随时间衰减后的显著性"""
        elapsed = time.time() - self.timestamp
        return self.salience * np.exp(-self.decay_rate * elapsed)


class WorkingMemorySlots:
    """
    有限工作记忆槽位 —— 借鉴 GNW 的容量限制。

    关键特性：
    1. 固定槽位数（默认 5，类似 Miller 的 7±2 但更保守）
    2. 新内容与已有内容竞争：最不显著的被驱逐
    3. 语义相似的内容合并（而非重复存储）
    4. 衰减：旧内容随时间逐渐失去显著度

    类比：
    你只能同时记住 ~5 件事。新的事情进来，
    最不重要/最旧的那件就被"挤出去"了。
    """

    def __init__(self, slot_count: int = 5, merge_similarity: float = 0.85):
        self.slot_count = slot_count
        self.merge_threshold = merge_similarity
        self.slots: List[MemorySlot] = []

    def insert(self, content: np.ndarray, tag: str = "ROUTINE",
               salience: float = 0.5) -> Optional[int]:
        """
        尝试插入新内容。

        Returns:
            插入的槽位索引，None 表示被拒绝（所有现有内容都更显著）
        """
        # 检查是否与已有内容高度相似 → 合并（更新显著性）
        for i, slot in enumerate(self.slots):
            sim = self._cosine_similarity(content, slot.content)
            if sim > self.merge_threshold:
                # 合并：取较高显著度
                slot.salience = max(slot.salience, salience)
                slot.timestamp = time.time()
                slot.access_count += 1
                return i

        # 若还有空位，直接插入
        if len(self.slots) < self.slot_count:
            slot = MemorySlot(
                content=content.copy() if isinstance(content, np.ndarray) else content,
                tag=tag,
                salience=float(salience),
                timestamp=time.time(),
            )
            self.slots.append(slot)
            return len(self.slots) - 1

        # 无空位：竞争驱逐
        min_idx = 0
        min_salience = float('inf')
        for i, slot in enumerate(self.slots):
            if slot.decayed_salience < min_salience:
                min_salience = slot.decayed_salience
                min_idx = i

        if salience > self.slots[min_idx].decayed_salience:
            self.slots[min_idx] = MemorySlot(
                content=content.copy(),
                tag=tag,
                salience=salience,
                timestamp=time.time(),
            )
            return min_idx

        return None  # 新内容不够显著，被拒绝

    def get_active_tags(self) -> List[str]:
        """返回当前活跃标签列表"""
        return [s.tag for s in self.slots]

    def get_most_salient(self) -> Optional[MemorySlot]:
        """返回最显著的槽位"""
        if not self.slots:
            return None
        return max(self.slots, key=lambda s: s.decayed_salience)

    def prune(self) -> None:
        """清理衰减到零的槽位"""
        self.slots = [s for s in self.slots if s.decayed_salience > 0.01]

    @property
    def is_full(self) -> bool:
        return len(self.slots) >= self.slot_count

    @property
    def load(self) -> float:
        """认知负荷 (0-1)"""
        return len(self.slots) / self.slot_count

    def reset(self):
        self.slots.clear()

    @staticmethod
    def _cosine_similarity(a, b):
        a_norm = np.linalg.norm(a) + 1e-8
        b_norm = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (a_norm * b_norm))


# ═══════════════════════════════════════════════════
# 增强 4：抑制控制
# ═══════════════════════════════════════════════════

class InhibitionControl:
    """
    抑制控制 —— 自适应阈值调节，防止假阳性/假阴性。

    借鉴前额叶皮层的抑制功能：
    1. 频繁点火 → 提高阈值（疲劳效应，防过度兴奋）
    2. 长期不点火 → 降低阈值（敏感化，防漏检）
    3. 高惊奇度内容 → 暂时降低阈值（"惊吓通道"快速响应）
    4. 情感极性强 → 适当降低阈值（情感事件不该被过滤）

    类比：
    就像你熬夜后对噪音特别敏感（阈值降低），
    或者专注工作时忽略背景声音（阈值升高）。
    """

    def __init__(self, base_threshold: float = 0.25,
                 adaptation_rate: float = 0.03,
                 target_ignition_rate: float = 0.25):
        self.base_threshold = base_threshold
        self.current_threshold = base_threshold
        self.adaptation_rate = adaptation_rate
        self.target_rate = target_ignition_rate  # 目标点火率 ~15%

        self._ignition_history: List[bool] = []
        self._window_size = 50

    def get_threshold(self, surprise: float = 0.0,
                      affect_intensity: float = 0.0) -> float:
        """
        获取当前自适应阈值。

        高惊奇 → 暂时降阈值（更快点火）
        高情感强度 → 暂时降阈值（情感事件优先）
        """
        base = self.current_threshold

        # 惊奇度修饰：惊奇度 > 0.3 时降低阈值
        surprise_mod = max(0.0, surprise - 0.3) * 0.35  # 最多降 ~0.24

        # 情感修饰：情感越强，阈值越低
        affect_mod = max(0.0, affect_intensity - 0.3) * 0.25  # 最多降 ~0.17

        return max(0.1, base - surprise_mod - affect_mod)

    def update(self, did_ignite: bool) -> None:
        """
        根据本次是否点火更新自适应阈值。

        点火率 > 目标 → 升阈值
        点火率 < 目标 → 降阈值
        """
        self._ignition_history.append(did_ignite)
        if len(self._ignition_history) > self._window_size:
            self._ignition_history.pop(0)

        if len(self._ignition_history) >= 10:
            recent_rate = sum(self._ignition_history[-20:]) / min(20, len(self._ignition_history))
            error = recent_rate - self.target_rate
            self.current_threshold += self.adaptation_rate * error
            self.current_threshold = max(0.1, min(0.8, self.current_threshold))

    @property
    def recent_ignition_rate(self) -> float:
        if not self._ignition_history:
            return 0.0
        window = self._ignition_history[-min(20, len(self._ignition_history)):]
        return sum(window) / len(window) if window else 0.0

    def reset(self):
        self.current_threshold = self.base_threshold
        self._ignition_history.clear()


# ═══════════════════════════════════════════════════
# 增强 5：广播衰减曲线
# ═══════════════════════════════════════════════════

@dataclass
class DecayState:
    """广播衰减状态"""
    content: np.ndarray
    initial_intensity: float
    decay_rate: float
    start_time: float
    tag: str = "ROUTINE"

    @property
    def current_intensity(self) -> float:
        """当前剩余强度"""
        elapsed = time.time() - self.start_time
        return self.initial_intensity * np.exp(-self.decay_rate * elapsed)

    @property
    def is_active(self) -> bool:
        """强度大于阈值才视为活跃"""
        return self.current_intensity > 0.05


class BroadcastDecayCurve:
    """
    广播衰减曲线 —— 点火后内容渐消而非瞬间消失。

    对比旧版 IgnitionDynamics：
    旧版：点火 → 固定时长 → 熄灭（二进制开关）
    新版：点火 → 指数衰减 → 逐渐消失（连续过渡）

    优势：
    1. 下游子系统可以在衰减期内继续访问"余晖"
    2. 记忆编码强度与衰减率相关（回忆更深的东西衰减慢）
    3. 多个活跃广播的叠加产生更丰富的意识体验
    """

    def __init__(self, default_decay_rate: float = 2.0):
        self.default_decay = default_decay_rate
        self.active_broadcasts: List[DecayState] = []
        self.max_concurrent = 3  # 最多同时活跃的广播

    def ignite(self, content: np.ndarray,
               intensity: float = 1.0,
               tag: str = "ROUTINE",
               decay_rate: Optional[float] = None) -> None:
        """
        点火：创建新的衰减状态。

        Φ 越高、情感越强 → 衰减越慢
        """
        if decay_rate is None:
            # 强度越高 → 衰减越慢
            decay_rate = self.default_decay * (1.0 - intensity * 0.7)

        state = DecayState(
            content=content.copy(),
            initial_intensity=intensity,
            decay_rate=decay_rate,
            start_time=time.time(),
            tag=tag,
        )
        self.active_broadcasts.append(state)

        # 限制并发数：保留最强的前 N 个
        if len(self.active_broadcasts) > self.max_concurrent:
            self.active_broadcasts.sort(
                key=lambda s: s.current_intensity, reverse=True
            )
            self.active_broadcasts = self.active_broadcasts[:self.max_concurrent]

    def get_active(self, min_intensity: float = 0.1) -> List[DecayState]:
        """获取当前活跃的广播（强度 > 阈值）"""
        return [b for b in self.active_broadcasts
                if b.current_intensity > min_intensity]

    def prune(self) -> None:
        """清理已衰减完的广播"""
        self.active_broadcasts = [
            b for b in self.active_broadcasts if b.is_active
        ]

    @property
    def is_any_active(self) -> bool:
        return any(b.is_active for b in self.active_broadcasts)

    @property
    def dominant_tag(self) -> str:
        """返回当前最强广播的标签"""
        active = self.get_active()
        if not active:
            return "NONE"
        return max(active, key=lambda b: b.current_intensity).tag

    def reset(self):
        self.active_broadcasts.clear()


# ═══════════════════════════════════════════════════
# 增强 6：节律振荡器
# ═══════════════════════════════════════════════════

class RhythmicOscillator:
    """
    节律振荡器 —— 模拟 Theta/Gamma 频段的注意力采样。

    借鉴神经科学的发现：
    - Gamma (30-80 Hz): 快速感知采样，对应"细节加工"
    - Theta (4-8 Hz): 慢速注意采样，对应"上下文切换"
    - Theta-Gamma 耦合：Gamma 波嵌套在 Theta 波上

    在 Helios 中的应用：
    - Theta 相位解析：决定当前是"采样状态"还是"整合状态"
    - 点火倾向受 Theta 相位调制：某些相位更容易点火
    """

    def __init__(self, theta_hz: float = 6.0, gamma_hz: float = 40.0):
        self.theta_hz = theta_hz
        self.gamma_hz = gamma_hz
        self._t0 = time.time()

    @property
    def theta_phase(self) -> float:
        """当前 Theta 相位 [0, 2π]"""
        elapsed = time.time() - self._t0
        return (elapsed * self.theta_hz * 2 * np.pi) % (2 * np.pi)

    @property
    def gamma_phase(self) -> float:
        """当前 Gamma 相位 [0, 2π]"""
        elapsed = time.time() - self._t0
        return (elapsed * self.gamma_hz * 2 * np.pi) % (2 * np.pi)

    @property
    def phase_type(self) -> str:
        """
        当前相位类型。

        Theta 相位解释：
        - 0 ~ π/2:     "编码" — 适合接收新信息
        - π/2 ~ π:     "巩固" — 适合整合已有信息
        - π ~ 3π/2:    "检索" — 适合回忆
        - 3π/2 ~ 2π:   "重置" — 清理准备下一周期
        """
        p = self.theta_phase
        if p < np.pi / 2:
            return "encode"
        elif p < np.pi:
            return "consolidate"
        elif p < 3 * np.pi / 2:
            return "retrieve"
        else:
            return "reset"

    def ignition_modulation(self) -> float:
        """
        相位对点火的调制系数。

        "编码"相位：↑ 更容易点火（开门迎客）
        "重置"相位：↓ 更难点火（关门整理）
        """
        p = self.theta_phase
        # 在编码相位（0-π/2）时调制系数最高
        if p < np.pi / 2:
            return 1.0 + 0.2 * np.sin(p * 2)  # 1.0 - 1.2
        elif p < np.pi:
            return 1.0  # 中性
        elif p < 3 * np.pi / 2:
            return 0.9  # 检索期稍降
        else:
            return 0.8  # 重置期最低

    def sampling_window(self) -> float:
        """当前 Gamma 周期的采样窗口 [0, 1]，1=最适合采样"""
        return (np.sin(self.gamma_phase) + 1.0) / 2.0

    def reset(self):
        self._t0 = time.time()


# ═══════════════════════════════════════════════════
# 增强 7：广播历史与重复抑制
# ═══════════════════════════════════════════════════

class BroadcastHistory:
    """
    广播历史 —— 记录最近广播，实现重复抑制。

    原理（借鉴感觉适应和重复抑制效应）：
    - 同一标签短时间内重复广播 → 降低其新颖性得分
    - 类似你重复听到同一个词几十遍后，它就"失去意义"了
    - 但不同标签的广播不受影响

    数据结构：固定大小的环形缓冲区，存 (tag, timestamp, signature_hash)
    """

    def __init__(self, maxlen: int = 50, suppression_window: float = 0.3):
        self.maxlen = maxlen
        self.suppression_window = suppression_window
        self._history: List[Tuple[str, float, int]] = []  # (tag, time, hash)

    def record(self, tag: str, content: np.ndarray):
        """记录一次广播"""
        content_hash = hash(content.tobytes()[:64])
        self._history.append((tag, time.time(), content_hash))
        while len(self._history) > self.maxlen:
            self._history.pop(0)

    def suppression_factor(self, tag: str) -> float:
        """
        计算重复抑制因子 [0, 1]。

        1.0 = 不抑制（最近没有同标签广播）
        0.0 = 完全抑制（最近频繁出现同标签广播）
        """
        now = time.time()
        recent_same_tag = [
            (t, ts) for t, ts, _ in self._history
            if t == tag and now - ts < self.suppression_window
        ]

        if not recent_same_tag:
            return 1.0

        # 越多相同标签 → 抑制越强
        count = len(recent_same_tag)
        recency = min(now - recent_same_tag[-1][1], self.suppression_window)
        recency_factor = recency / self.suppression_window  # 越近→越低

        return max(0.1, recency_factor * (1.0 - count * 0.3))

    @property
    def recent_tags(self) -> List[str]:
        """最近 suppression_window 内的标签"""
        now = time.time()
        return list(set(
            t for t, ts, _ in self._history
            if now - ts < self.suppression_window
        ))

    def reset(self):
        self._history.clear()


# ═══════════════════════════════════════════════════
# 增强 8：注意力门控广播
# ═══════════════════════════════════════════════════

class AttentionGatedBroadcast:
    """
    注意力门控广播 —— 不同子系统收到不同强度的广播。

    旧版 GlobalWorkspace 对所有 subscriber 等权广播。
    新版根据内容和子系统特性做差异化分发：

    - memory_episodic: 偏好"新奇的" → THREAT/NOVEL 标签增益
    - memory_semantic: 偏好"可归类的" → ROUTINE/SOCIAL 标签增益
    - decision: 偏好"高显著性的" → 高 ignition_score 增益
    - action: 偏好"紧急的" → THREAT 标签增益
    - language: 偏好"可表达的" → SOCIAL/ROUTINE 标签增益
    - affect: 偏好"情感极性的" → 高 |valence| 增益
    """

    # 每个子系统对不同标签的增益因子
    SUBSYSTEM_GAINS = {
        'memory_episodic': {
            'THREAT': 1.3, 'NOVEL': 1.3, 'REWARD': 1.1,
            'SOCIAL': 0.9, 'ROUTINE': 0.6, 'BODILY': 0.7,
        },
        'memory_semantic': {
            'THREAT': 1.0, 'NOVEL': 0.8, 'REWARD': 1.0,
            'SOCIAL': 1.2, 'ROUTINE': 1.1, 'BODILY': 0.9,
        },
        'decision': {
            'THREAT': 1.4, 'NOVEL': 1.1, 'REWARD': 1.2,
            'SOCIAL': 1.0, 'ROUTINE': 0.5, 'BODILY': 0.8,
        },
        'action': {
            'THREAT': 1.5, 'NOVEL': 0.9, 'REWARD': 1.1,
            'SOCIAL': 0.8, 'ROUTINE': 0.4, 'BODILY': 1.2,
        },
        'language': {
            'THREAT': 1.0, 'NOVEL': 1.0, 'REWARD': 1.0,
            'SOCIAL': 1.4, 'ROUTINE': 1.2, 'BODILY': 0.6,
        },
        'affect': {
            'THREAT': 1.4, 'NOVEL': 0.8, 'REWARD': 1.4,
            'SOCIAL': 1.1, 'ROUTINE': 0.5, 'BODILY': 1.0,
        },
    }

    def get_gain(self, subsystem: str, tag: str) -> float:
        """获取某子系统对某标签的增益"""
        return self.SUBSYSTEM_GAINS.get(subsystem, {}).get(tag, 1.0)

    def compute_intensity(self, subsystem: str, tag: str,
                          base_intensity: float) -> float:
        """计算某子系统应接收的广播强度"""
        gain = self.get_gain(subsystem, tag)
        return min(1.0, base_intensity * gain)


# ═══════════════════════════════════════════════════
# 增强 9：全局工作空间 v2.0 主控
# ═══════════════════════════════════════════════════

@dataclass
class EnhancedWorkspaceResponse:
    """
    增强版广播响应 —— 比旧版 WorkspaceResponse 更丰富。
    """
    timestamp: float = field(default_factory=time.time)
    ignited: bool = False
    ignition_score: float = 0.0
    contributions: Dict[str, float] = field(default_factory=dict)
    semantic_tag: str = "ROUTINE"
    tag_scores: Dict[str, float] = field(default_factory=dict)
    content: Optional[np.ndarray] = None

    # 解码结果
    memory_update: Optional[Dict] = None
    language_output: Optional[str] = None
    decision: Optional[Dict] = None
    action: Optional[Dict] = None
    affect_expression: Optional[str] = None
    decision_made: bool = False  # 兼容旧版 SelfModel
    memory_stored: bool = False  # 兼容旧版
    llm_response: Optional[Any] = None  # LLM 桥接响应

    @property
    def summary(self) -> str:
        if not self.ignited:
            return "未点火。"
        return (f"🔥 [{self.semantic_tag}] "
                f"score={self.ignition_score:.3f} "
                f"top={max(self.contributions, key=self.contributions.get) if self.contributions else '?'}")


class GlobalWorkspaceV2:
    """
    L2 全局工作空间 v2.0 —— 整合所有增强模块。

    数据流：
    L1Output → IgnitionGateV2 → [点火?]
      ├─ YES → SemanticTagger → WorkingMemorySlots
      │          → BroadcastDecayCurve → BroadcastHistory
      │          → AttentionGatedBroadcast → 各子系统
      └─ NO  → 继续采样（RhythmicOscillator 调制）

    相比旧版 GlobalWorkspace 的改进：
    1. 五维点火评分（Φ+新颖性+情感+注意力+惊奇）
    2. 语义标签（THREAT/REWARD/SOCIAL/NOVEL/ROUTINE/BODILY）
    3. 有限工作记忆槽位（5 slots，竞争驱逐）
    4. 抑制控制（自适应阈值）
    5. 广播衰减曲线（渐消而非瞬间灭）
    6. Theta/Gamma 节律振荡（相位调制点火倾向）
    7. 广播历史（重复抑制）
    8. 注意力门控分发（差异化的子系统强度）
    """

    def __init__(self, config: HeliosConfig, llm_bridge=None):
        self.config = config

        # 核心组件
        self.gate = IgnitionGateV2(config)
        self.semantic_tagger = SemanticTagger()
        self.working_memory = WorkingMemorySlots(slot_count=5)
        self.inhibition = InhibitionControl(base_threshold=config.ignition_threshold)
        self.decay_curve = BroadcastDecayCurve()
        self.oscillator = RhythmicOscillator(theta_hz=6.0, gamma_hz=40.0)
        self.broadcast_history = BroadcastHistory()
        self.attn_gated = AttentionGatedBroadcast()

        # LLM 桥接（可选，用于点火时调用 LLM）
        self.llm_bridge = llm_bridge

        # 保留旧版自持动态（向后兼容）
        self.dynamics = IgnitionDynamics(config)

        # 状态
        self.current_content: Optional[np.ndarray] = None
        self.previous_content: Optional[np.ndarray] = None
        self.last_response: Optional[EnhancedWorkspaceResponse] = None
        self.total_ignitions = 0

    def cycle(self, l1_output,
              affect_state=None,
              self_state=None,
              emotional_recall: str = "") -> EnhancedWorkspaceResponse:
        """
        一个工作空间周期。

        Args:
            l1_output: L1Output 或 EnhancedL1Output
            affect_state: AffectState
            self_state: L3 自我状态（可选，供 LLM Bridge 使用）
            emotional_recall: 情感回忆上下文（可选，供 LLM 使用）

        Returns:
            EnhancedWorkspaceResponse
        """
        # === 0. 提取 L1 v2 增强字段（兼容旧版 L1Output） ===
        l1_attention = getattr(l1_output, 'attention_weights', None)
        l1_surprise = getattr(l1_output, 'surprise', 0.0)
        l1_coherence = getattr(l1_output, 'coherence', None)

        # 情感显著性
        affect_salience = 0.0
        affect_intensity = 0.0
        if affect_state:
            affect_salience = abs(getattr(affect_state, 'valence', 0.0)) * 0.7 + \
                              getattr(affect_state, 'arousal', 0.0) * 0.3
            affect_intensity = getattr(affect_state, 'intensity', 0.0)

        # === 1. 自适应阈值 ===
        adaptive_threshold = self.inhibition.get_threshold(
            surprise=l1_surprise,
            affect_intensity=affect_intensity,
        )
        self.gate.threshold = adaptive_threshold

        # === 2. 节律调制 ===
        rhythm_mod = self.oscillator.ignition_modulation()

        # === 3. 点火判断 ===
        ignited, score, contributions = self.gate.should_ignite(
            l1_output=l1_output,
            affect_salience=affect_salience,
            previous_content=self.previous_content,
            l1_attention_weights=l1_attention,
            l1_surprise=l1_surprise,
        )

        # 节律调制：编码相更容易点火
        if not ignited and rhythm_mod > 1.05:
            # 在编码相位，降低有效阈值
            score_boosted = score * rhythm_mod
            ignited = score_boosted > adaptive_threshold * 0.85

        # === 4. 语义标签 ===
        tag = "ROUTINE"
        tag_scores = {}
        if l1_output.fused_qualia is not None:
            tag, tag_scores = self.semantic_tagger.tag(
                l1_output, affect_state, l1_attention
            )

        # === 5. 重复抑制 ===
        if ignited:
            suppression = self.broadcast_history.suppression_factor(tag)
            if suppression < 0.05:  # 几乎完全抑制时才阻止
                ignited = False  # 重复太多，抑制
            else:
                score *= suppression

        # === 6. 构建响应 ===
        response = EnhancedWorkspaceResponse(
            ignited=ignited,
            ignition_score=score,
            contributions=contributions,
            semantic_tag=tag,
            tag_scores=tag_scores,
            content=l1_output.fused_qualia,
        )

        # === 7. 点火后处理 ===
        if ignited and l1_output.fused_qualia is not None:
            self.total_ignitions += 1
            self.steps_since_ignition = 0  # 点火时重置步数计数

            # 自持动态
            self.dynamics.ignite(l1_output.phi, affect_intensity)

            # 衰减曲线
            self.decay_curve.ignite(
                content=l1_output.fused_qualia,
                intensity=score,
                tag=tag,
            )

            # 工作记忆
            self.working_memory.insert(
                content=l1_output.fused_qualia,
                tag=tag,
                salience=score,
            )

            # 广播历史
            self.broadcast_history.record(tag, l1_output.fused_qualia)

            # 更新当前内容
            self.current_content = l1_output.fused_qualia.copy()

            response.content = l1_output.fused_qualia
            response.decision_made = True
            response.memory_stored = True

            # === 🧠 LLM Bridge: 点火时调用 LLM ===
            if self.llm_bridge is not None:
                try:
                    llm_resp = self.llm_bridge.think(
                        l1_output=l1_output,
                        affect_state=affect_state,
                        ws_response=response,
                        self_state=self_state,
                        emotional_recall=emotional_recall,
                    )
                    response.llm_response = llm_resp
                    response.language_output = llm_resp.language_output
                    if llm_resp.decision:
                        response.decision = llm_resp.decision
                except Exception as e:
                    # LLM 失败不影响主循环，但记录一下
                    print(f"  ⚠️ LLM 调用失败: {e}", file=__import__('sys').stderr)

        # === 8. 更新抑制控制 ===
        self.inhibition.update(ignited)

        # === 9. 维护 ===
        self.previous_content = self.current_content
        if self.current_content is not None:
            self.decay_curve.prune()
            self.working_memory.prune()

        self.last_response = response
        return response

    def get_broadcast_intensity(self, subsystem: str) -> float:
        """获取某子系统应接收的当前广播强度"""
        if self.last_response is None or not self.last_response.ignited:
            return 0.0
        return self.attn_gated.compute_intensity(
            subsystem=subsystem,
            tag=self.last_response.semantic_tag,
            base_intensity=self.last_response.ignition_score,
        )

    @property
    def active_tags(self) -> List[str]:
        return self.working_memory.get_active_tags()

    @property
    def cognitive_load(self) -> float:
        return self.working_memory.load

    @property
    def adaptive_threshold(self) -> float:
        return self.inhibition.current_threshold

    @property
    def rhythm_phase(self) -> str:
        return self.oscillator.phase_type

    def reset(self):
        self.gate = IgnitionGateV2(self.config)
        self.working_memory.reset()
        self.inhibition.reset()
        self.decay_curve.reset()
        self.oscillator.reset()
        self.broadcast_history.reset()
        self.dynamics = IgnitionDynamics(self.config)
        self.current_content = None
        self.previous_content = None
        self.total_ignitions = 0
        self.last_response = None


# ═══════════════════════════════════════════════════
# 演示
# ═══════════════════════════════════════════════════

def demo_enhanced_l2():
    """演示增强版 L2 广播层"""
    print("=" * 60)
    print("  Helios L2 广播层 v2.0 增强版演示")
    print("  五维门控 + 语义标签 + 工作记忆 + 节律振荡")
    print("=" * 60)

    try:
        from .core import HeliosConfig, L1Output
    except ImportError:
        from core import HeliosConfig, L1Output

    config = HeliosConfig()
    workspace = GlobalWorkspaceV2(config)

    print(f"\n初始自适应阈值: {workspace.adaptive_threshold:.3f}")
    print(f"当前节律相位: {workspace.rhythm_phase}")

    # 模拟多种场景
    scenarios = [
        # (name, phi, affect_valence, affect_arousal, attention, surprise)
        ("无聊", 0.1, 0.0, 0.1, {'vision': 0.5, 'audio': 0.5}, 0.05),
        ("日出", 0.4, 0.5, 0.3, {'vision': 0.7, 'audio': 0.3}, 0.1),
        ("威胁!", 0.6, -0.8, 0.9, {'vision': 0.5, 'audio': 0.4, 'touch': 0.1}, 0.8),
        ("威胁!!", 0.55, -0.7, 0.85, {'vision': 0.4, 'audio': 0.5, 'touch': 0.1}, 0.6),
        ("威胁!!!" , 0.5, -0.75, 0.8, {'vision': 0.35, 'audio': 0.55, 'touch': 0.1}, 0.5),
        ("社交", 0.35, 0.4, 0.4, {'text': 0.6, 'vision': 0.3, 'audio': 0.1}, 0.15),
        ("社交", 0.3, 0.35, 0.35, {'text': 0.55, 'vision': 0.35, 'audio': 0.1}, 0.1),
        ("安慰", 0.5, 0.7, 0.2, {'touch': 0.5, 'audio': 0.4, 'vision': 0.1}, 0.05),
        ("恢复", 0.2, 0.2, 0.15, {'vision': 0.6, 'audio': 0.4}, 0.02),
        ("恢复", 0.15, 0.1, 0.1, {'vision': 0.55, 'audio': 0.45}, 0.01),
    ]

    print(f"\n{'场景':<8} {'相位':<12} {'阈值':<6} {'Φ':<6} {'标签':<8} {'得分':<6} {'🔥':<4} {'工作记忆'}")
    print("-" * 80)

    for name, phi, val, aro, attn, surp in scenarios:
        # 模拟 L1 输出
        fused = np.random.randn(128) * phi + np.ones(128) * val * 0.5
        l1 = L1Output(
            qualia={},
            fused_qualia=fused,
            phi=phi,
            prediction_errors={},
        )
        # 手动添加增强字段
        l1.attention_weights = attn
        l1.surprise = surp

        # 模拟 AffectState
        class MockAffect:
            def __init__(self, v, a):
                self.valence = v
                self.arousal = a
                self.intensity = abs(v) * 0.5 + a * 0.5
        affect = MockAffect(val, aro)

        response = workspace.cycle(l1, affect)

        phase = workspace.rhythm_phase
        thresh = workspace.adaptive_threshold
        mem_tags = workspace.active_tags
        fire = "🔥" if response.ignited else "  "

        print(f"{name:<8} {phase:<12} {thresh:<6.3f} {phi:<6.3f} "
              f"{response.semantic_tag:<8} {response.ignition_score:<6.3f} "
              f"{fire:<4} [{', '.join(mem_tags[:3])}]")

    # 最终统计
    print(f"\n--- 最终统计 ---")
    print(f"  总点火次数: {workspace.total_ignitions}/{len(scenarios)}")
    print(f"  自适应阈值: {workspace.adaptive_threshold:.3f}")
    print(f"  认知负荷: {workspace.cognitive_load:.1%}")
    print(f"  活跃广播: {len(workspace.decay_curve.active_broadcasts)}")
    print(f"  工作记忆标签: {workspace.active_tags}")
    print(f"  广播历史: {workspace.broadcast_history.recent_tags}")

    workspace.reset()
    print(f"\n  工作空间已重置 ✓")


if __name__ == "__main__":
    demo_enhanced_l2()
