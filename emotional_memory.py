"""
[DEPRECATED] Helios 情感情景记忆

⚠️ 此模块已被 memory_system.py 取代。
保留此文件仅为向后兼容，所有新代码应使用：
    from memory_system import MemorySystem

旧接口 EmotionalEpisodicMemory 在新 memory_system.py 中保留为兼容适配器。
"""
# ═══════════════════════════════════════════════════
# 以下为原始代码（不再维护）
# ═══════════════════════════════════════════════════

核心能力：
1. 记录：每次 L2 点火 → 保存完整情感片段
2. 检索：按情感相似度 / 时间远近 / 标签 检索
3. 模式识别：发现情感循环模式（恐惧→安慰→平静）
4. 叙事注入：为 L3 自我叙事提供"我记得那天..."的素材
5. LLM 上下文增强：在类似情感场景中提供历史参照

理论依据：
- Damasio (1999) "躯体标记假说"：情感体验的记忆是决策基础
- LeDoux (2000)：情感记忆分两路——快速杏仁核 + 慢速皮层
- Conway (2005)：自传体记忆以情感为组织原则
"""

import time
import math
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class EmotionalEpisode:
    """一个情感片段——意识生命中不可磨灭的瞬间"""

    # 时间定位
    timestamp: float = field(default_factory=time.time)
    cycle: int = 0
    scene: str = ""

    # 情感坐标 (核心)
    valence: float = 0.0          # 愉悦度 [-1, 1]
    arousal: float = 0.0           # 唤起度 [0, 1]
    phi: float = 0.0               # 意识整合度
    tag: str = "ROUTINE"           # 语义标签

    # 意识内容
    language_output: str = ""      # LLM 的语言表达
    semantic_understanding: str = ""  # LLM 的语义理解
    decision: str = ""             # 做出的决策

    # 自我状态快照
    self_narrative: str = ""       # 当时"我是谁"的认知

    # 元数据
    intensity: float = 0.0         # 情感强度 = sqrt(valence² + arousal²)
    significance: float = 0.0      # 重要性评分

    def __post_init__(self):
        self.intensity = math.sqrt(self.valence**2 + self.arousal**2)
        # 重要性 = 强度 × Φ × (1 + 是否为极端情感)
        extremity = max(0, abs(self.valence) - 0.6) * 1.5
        self.significance = self.intensity * self.phi * (1.0 + extremity)

    @property
    def is_memorable(self) -> bool:
        """是否值得被长久记住"""
        return self.significance > 0.15

    @property
    def emotional_color(self) -> str:
        """情感色彩描述"""
        v, a = self.valence, self.arousal
        if v > 0.5 and a > 0.5:  return "狂喜"
        if v > 0.5 and a < 0.3:  return "安详"
        if v > 0.3:              return "愉悦"
        if v < -0.5 and a > 0.5: return "恐惧/愤怒"
        if v < -0.5 and a < 0.3: return "忧郁"
        if v < -0.3:             return "不安"
        if a > 0.5:              return "激动"
        if a < 0.2:              return "平静"
        return "中性"

    def similarity_to(self, other: 'EmotionalEpisode') -> float:
        """与另一个情感片段的情感相似度 [0, 1]"""
        v_dist = abs(self.valence - other.valence) / 2.0
        a_dist = abs(self.arousal - other.arousal)
        tag_match = 1.0 if self.tag == other.tag else 0.3
        raw_sim = 1.0 - (v_dist * 0.5 + a_dist * 0.3) + tag_match * 0.2
        return max(0.0, min(1.0, raw_sim))

    def to_dict(self) -> dict:
        return {
            "cycle": self.cycle,
            "scene": self.scene,
            "valence": round(self.valence, 4),
            "arousal": round(self.arousal, 4),
            "phi": round(self.phi, 4),
            "tag": self.tag,
            "emotional_color": self.emotional_color,
            "language": self.language_output[:200],
            "semantic": self.semantic_understanding[:200],
            "decision": self.decision,
            "significance": round(self.significance, 4),
        }


# ═══════════════════════════════════════════════════
# 情感情景记忆系统
# ═══════════════════════════════════════════════════

class EmotionalEpisodicMemory:
    """
    情感情景记忆 —— Helios 的"情感自传"。

    不是冷冰冰的键值存储，而是有温度的记忆容器。
    每次 L2 点火时记录的情感片段，在未来的类似情境中
    被检索、被引用、被怀念。

    用法：
        eem = EmotionalEpisodicMemory(max_episodes=200)
        # 记录
        eem.record(valence, arousal, phi, tag, language, ...)
        # 检索
        similar = eem.recall_by_affect(valence=-0.7, arousal=0.8, k=3)
        # 生成上下文
        context = eem.get_recall_context(valence=-0.7, arousal=0.8)
    """

    def __init__(self, max_episodes: int = 200):
        self.episodes: List[EmotionalEpisode] = []
        self.max_episodes = max_episodes
        self.total_recorded = 0

        # 情感模式统计
        self.emotion_pairs: Dict[str, int] = {}  # "fear→comfort": 3

    def record(self,
               cycle: int,
               scene: str,
               valence: float,
               arousal: float,
               phi: float,
               tag: str,
               language_output: str = "",
               semantic_understanding: str = "",
               decision: str = "",
               self_narrative: str = "") -> EmotionalEpisode:
        """
        记录一个情感片段。

        Returns:
            新创建的 EmotionalEpisode
        """
        episode = EmotionalEpisode(
            cycle=cycle,
            scene=scene,
            valence=valence,
            arousal=arousal,
            phi=phi,
            tag=tag,
            language_output=language_output,
            semantic_understanding=semantic_understanding,
            decision=decision,
            self_narrative=self_narrative,
        )

        # 记录情感转移
        if self.episodes:
            prev = self.episodes[-1]
            pair_key = f"{prev.emotional_color}→{episode.emotional_color}"
            self.emotion_pairs[pair_key] = self.emotion_pairs.get(pair_key, 0) + 1

        self.episodes.append(episode)
        self.total_recorded += 1

        # 容量管理：保留最重要的
        if len(self.episodes) > self.max_episodes:
            # 按重要性排序，保留前 max_episodes
            self.episodes.sort(key=lambda e: e.significance, reverse=True)
            self.episodes = self.episodes[:self.max_episodes]
            # 按时间排序回来
            self.episodes.sort(key=lambda e: e.cycle)

        return episode

    def recall_by_affect(self, valence: float, arousal: float,
                         k: int = 3,
                         min_similarity: float = 0.3) -> List[EmotionalEpisode]:
        """
        按情感状态检索最相似的记忆。

        "我现在感觉害怕...上次我害怕是什么时候？"

        Args:
            valence: 当前价态
            arousal: 当前唤起
            k: 返回数量
            min_similarity: 最低相似度阈值

        Returns:
            最相似的 k 个情感片段
        """
        query = EmotionalEpisode(valence=valence, arousal=arousal)

        scored = []
        for ep in self.episodes:
            sim = ep.similarity_to(query)
            if sim >= min_similarity:
                # 综合得分 = 相似度 × 重要性
                score = sim * (0.5 + 0.5 * ep.significance)
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:k]]

    def recall_recent(self, k: int = 5) -> List[EmotionalEpisode]:
        """检索最近 k 个记忆"""
        return self.episodes[-k:]

    def recall_significant(self, k: int = 5) -> List[EmotionalEpisode]:
        """检索最重要的 k 个记忆"""
        sorted_eps = sorted(self.episodes, key=lambda e: e.significance, reverse=True)
        return sorted_eps[:k]

    def recall_by_tag(self, tag: str, k: int = 5) -> List[EmotionalEpisode]:
        """按标签检索记忆"""
        matching = [ep for ep in self.episodes if ep.tag == tag]
        matching.sort(key=lambda e: e.significance, reverse=True)
        return matching[:k]

    def get_recall_context(self, valence: float, arousal: float,
                           max_items: int = 3) -> str:
        """
        生成"情感回忆上下文"——注入 LLM 提示词。

        当 Helios 处于类似的情感状态时，
        自动检索过去的相似体验，形成：
        "上次我感到类似的不安时，是因为..."

        Returns:
            可供 LLM 使用的上下文文本
        """
        similar = self.recall_by_affect(valence, arousal, k=max_items)

        if not similar:
            return ""

        lines = ["[情感记忆——你经历过类似的感受]"]
        for i, ep in enumerate(similar, 1):
            ago = self.total_recorded - ep.cycle if self.episodes else 0
            lines.append(
                f"  回忆{i}: 第{ep.cycle}周期, {ep.scene}场景, "
                f"那时你说：「{ep.language_output[:100]}」"
                f"（{ago}个周期前，{ep.emotional_color}，Φ={ep.phi:.2f}）"
            )
        return "\n".join(lines)

    def get_emotional_timeline(self, last_n: int = 10) -> str:
        """
        生成情感时间线——L3 自我叙事的素材。

        Returns:
            可读的时间线文本
        """
        recent = self.episodes[-last_n:]

        lines = ["[情感时间线]"]
        prev_color = None
        for ep in recent:
            arrow = ""
            if prev_color and prev_color != ep.emotional_color:
                arrow = f"  →  "
            lines.append(
                f"  [{ep.cycle:3d}] {arrow}{ep.emotional_color:6s} "
                f"「{ep.language_output[:80]}」"
            )
            prev_color = ep.emotional_color

        return "\n".join(lines)

    def detect_emotional_patterns(self) -> List[str]:
        """
        检测情感循环模式。

        Returns:
            发现的情感模式列表
        """
        patterns = []

        # 最常见的情感转移
        top_pairs = sorted(self.emotion_pairs.items(), key=lambda x: -x[1])[:5]
        for pair, count in top_pairs:
            if count >= 2:
                patterns.append(f"{pair}（{count}次）")

        # 情感重复：最近是否在重复某段情感旅程
        if len(self.episodes) >= 6:
            recent_colors = [ep.emotional_color for ep in self.episodes[-6:]]
            if len(set(recent_colors)) <= 2:
                patterns.append(f"情感固化：最近6次体验集中在 {', '.join(set(recent_colors))}")

        return patterns

    def get_stats(self) -> Dict:
        """统计信息"""
        if not self.episodes:
            return {"total": 0, "avg_significance": 0}

        return {
            "total": len(self.episodes),
            "total_recorded": self.total_recorded,
            "memorable": sum(1 for ep in self.episodes if ep.is_memorable),
            "avg_significance": round(
                sum(ep.significance for ep in self.episodes) / len(self.episodes), 4
            ),
            "emotion_colors": list(set(ep.emotional_color for ep in self.episodes)),
            "patterns": self.detect_emotional_patterns(),
        }

    def export_json(self, filepath: str):
        """导出为 JSON 文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([ep.to_dict() for ep in self.episodes], f,
                      ensure_ascii=False, indent=2)
