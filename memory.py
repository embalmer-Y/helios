"""
Helios 记忆系统

四层记忆结构：
1. 工作记忆（秒级）—— 当前激活的信息片段
2. 情景记忆（日-年级）—— "我经历过什么"，情感索引
3. 语义记忆（永久）—— "我知道什么"，图结构
4. 程序记忆（永久）—— "我会做什么"，体现在权重中

核心创新：情感作为索引键 ——
心情好时更容易想起好事，心情差时更容易想起坏事。
"""

import time
import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque

from .core import (
    L1Output, AffectState, EpisodicMemoryEntry,
    SemanticMemoryEntry, HeliosConfig
)


class WorkingMemory:
    """工作记忆 —— 当前激活的信息片段，容量 7±2"""

    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.items: deque = deque(maxlen=capacity)
        self.attended_item: Optional[np.ndarray] = None  # 当前注意焦点

    def push(self, content: np.ndarray, label: str = ""):
        """推入新项目"""
        self.items.append({
            'content': content.copy(),
            'label': label,
            'timestamp': time.time(),
        })

    def attend(self, index: int = -1) -> Optional[np.ndarray]:
        """将注意力指向某个项目"""
        if 0 <= index < len(self.items) or (index == -1 and self.items):
            self.attended_item = self.items[index]['content'].copy()
            return self.attended_item
        return None

    def get_all(self) -> List[dict]:
        return list(self.items)

    def clear(self):
        self.items.clear()
        self.attended_item = None


class EpisodicMemory:
    """
    情景记忆 —— "我经历过什么"

    核心创新：情感作为索引键
    - 强烈情感的记忆更容易被检索
    - 情感一致性偏差：当前心情影响想起什么
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.memories: List[EpisodicMemoryEntry] = []
        self.max_size = config.episodic_memory_max
        self.emotional_bias = config.emotional_recall_bias

    def store(self, l1_output: L1Output, affect: AffectState):
        """存储体验"""
        if l1_output.fused_qualia is None:
            return

        # 降维到 64 维做嵌入
        content = l1_output.fused_qualia[:64].copy()

        entry = EpisodicMemoryEntry(
            content=content,
            affect_valence=affect.valence,
            affect_arousal=affect.arousal,
            dominant_emotion=affect.dominant_emotion,
            phi=l1_output.phi,
        )

        self.memories.append(entry)

        # 容量限制：FIFO + 高 Φ 保留
        if len(self.memories) > self.max_size:
            # 删除最旧的低 Φ 记忆
            sorted_by_phi = sorted(
                self.memories[:-self.max_size],
                key=lambda m: m.phi
            )
            for m in sorted_by_phi[:len(self.memories) - self.max_size]:
                self.memories.remove(m)

    def retrieve(self,
                 query: np.ndarray,
                 current_affect: Optional[AffectState] = None,
                 top_k: int = 5) -> List[EpisodicMemoryEntry]:
        """
        检索记忆。

        情感一致性偏差：
        心情好 → 更容易想起好的记忆
        心情差 → 更容易想起坏的记忆
        强烈情感的记忆额外加分
        """
        if not self.memories:
            return []

        # 截取查询到 64 维
        if len(query) > 64:
            query = query[:64]

        scored = []
        for mem in self.memories:
            # 内容相似度
            sim = self._cosine_similarity(query, mem.content)

            # 情感一致性加分
            affect_match = 0.0
            if current_affect:
                affect_dist = abs(current_affect.valence - mem.affect_valence)
                affect_match = (1.0 - affect_dist) * self.emotional_bias

            # 情感强度加分
            intensity_bonus = mem.affect_arousal * 0.1

            # Φ 加分（高整合体验更容易被想起）
            phi_bonus = mem.phi * 0.1

            final_score = sim + affect_match + intensity_bonus + phi_bonus
            scored.append((final_score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:top_k]]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        an = np.linalg.norm(a) + 1e-8
        bn = np.linalg.norm(b) + 1e-8
        return float(np.dot(a, b) / (an * bn))

    @property
    def size(self) -> int:
        return len(self.memories)

    def get_summary(self) -> Dict:
        """获取记忆摘要"""
        if not self.memories:
            return {'count': 0, 'avg_phi': 0, 'avg_valence': 0}

        return {
            'count': len(self.memories),
            'avg_phi': np.mean([m.phi for m in self.memories]),
            'avg_valence': np.mean([m.affect_valence for m in self.memories]),
            'dominant_emotion': max(
                set(m.dominant_emotion for m in self.memories),
                key=lambda e: sum(1 for m in self.memories if m.dominant_emotion == e)
            ),
        }

    def reset(self):
        self.memories.clear()


class SemanticMemory:
    """
    语义记忆 —— "我知道什么"

    用简单的词典+嵌入存储概念知识。
    在实际应用中应使用图数据库。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.entries: Dict[str, SemanticMemoryEntry] = {}

    def store(self, concept: str, embedding: np.ndarray, relations: List[str] = None):
        self.entries[concept] = SemanticMemoryEntry(
            concept=concept,
            embedding=embedding,
            relations=relations or [],
        )

    def retrieve(self, concept: str) -> Optional[SemanticMemoryEntry]:
        return self.entries.get(concept)

    def search(self, query_embedding: np.ndarray, top_k: int = 3) -> List[str]:
        """语义搜索"""
        if not self.entries:
            return []

        scored = []
        for concept, entry in self.entries.items():
            sim = EpisodicMemory._cosine_similarity(query_embedding, entry.embedding)
            scored.append((sim, concept))

        scored.sort(reverse=True)
        return [c for _, c in scored[:top_k]]

    def reset(self):
        self.entries.clear()


class MemorySystem:
    """
    统一记忆系统。

    整合四层记忆，提供统一的存储和检索接口。
    """

    def __init__(self, config: HeliosConfig):
        self.config = config
        self.working = WorkingMemory(config.working_memory_capacity)
        self.episodic = EpisodicMemory(config)
        self.semantic = SemanticMemory(config)

    def store_episodic(self, l1_output: L1Output, affect: AffectState):
        """存储情景记忆"""
        self.episodic.store(l1_output, affect)

        # 同时更新工作记忆
        if l1_output.fused_qualia is not None:
            self.working.push(
                l1_output.fused_qualia[:64],
                label=f"exp_Φ={l1_output.phi:.2f}"
            )

    def retrieve(self, query: np.ndarray,
                 current_affect: Optional[AffectState] = None,
                 top_k: int = 5) -> List[EpisodicMemoryEntry]:
        """检索情景记忆"""
        return self.episodic.retrieve(query, current_affect, top_k)

    def get_summary(self) -> Dict:
        return {
            'working_items': len(self.working.get_all()),
            'episodic': self.episodic.get_summary(),
            'semantic_concepts': len(self.semantic.entries),
        }

    def reset(self):
        self.working.clear()
        self.episodic.reset()
        self.semantic.reset()
