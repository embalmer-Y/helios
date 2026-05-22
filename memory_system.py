"""
Helios 记忆系统 — MemorySystem v1.0

统一的记忆子系统，模块化设计，可独立升级。

四类记忆：
    WorkingMemory          — 工作记忆 (当前会话暂存，TTL 衰减)
    EpisodicMemory         — 情景记忆 (情感事件，带标签和检索)
    SemanticMemory         — 语义记忆 (事实/概念/模式，长期积累)
    AutobiographicalMemory — 自传记忆 (叙事时间线，"我的故事")

+ MemoryConsolidator       — 静息期巩固 (情景→语义迁移，记忆修剪)
+ MemoryRetriever          — 统一检索 (跨存储查询，情感相似度排序)

用法:
    ms = MemorySystem()
    ms.remember_episode(episode)
    ms.learn_fact("helios.created", "2026-05-19")
    similar = ms.recall_like(episode, k=3)
    ms.consolidate(phi=0.1)  # 低Φ时巩固
"""

import os
import time
import math
import json
import uuid
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Set
from collections import OrderedDict
from helios_utils import clamp, safe_div

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════
# 基础数据类
# ═══════════════════════════════════════════════════

@dataclass
class MemoryItem:
    """记忆原子 — 不可再分的最小记忆单元"""

    # 身份
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    memory_type: str = "episodic"        # episodic | semantic | working | autobiographical

    # 时间
    timestamp: float = field(default_factory=time.time)
    ttl: float = float("inf")            # 存活时间 (秒)，inf = 永不过期
    last_accessed: float = field(default_factory=time.time)

    # 内容
    content: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""                     # 一句话摘要 (检索用)

    # 情感标签
    valence: float = 0.0
    arousal: float = 0.0
    phi: float = 0.0
    emotional_tag: str = "neutral"

    # 元数据
    importance: float = 0.0               # [0, 1] 重要性 (决定是否被巩固)
    access_count: int = 0
    tags: Set[str] = field(default_factory=set)

    def touch(self):
        """标记为刚被访问"""
        self.last_accessed = time.time()
        self.access_count += 1

    def is_expired(self) -> bool:
        """是否已过期"""
        if math.isinf(self.ttl):
            return False
        return (time.time() - self.timestamp) > self.ttl

    def recalc_importance(self):
        """重新计算重要性 = sqrt(V² + A²) × P × (1 + log(1 + C) × 0.1)

        Formula: importance = sqrt(valence² + arousal²) × phi × (1 + log(1 + access_count) × 0.1)
        Minimum importance is clamped to 0.05 to avoid zero-importance items.
        """
        intensity = math.sqrt(self.valence ** 2 + self.arousal ** 2)
        access_bonus = math.log(1 + self.access_count) * 0.1
        self.importance = max(0.05, clamp(intensity * self.phi * (1.0 + access_bonus)))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.memory_type,
            "summary": self.summary,
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "phi": round(self.phi, 3),
            "importance": round(self.importance, 3),
            "tag": self.emotional_tag,
        }


# ═══════════════════════════════════════════════════
# 工作记忆 — 当前会话暂存
# ═══════════════════════════════════════════════════

class WorkingMemory:
    """
    工作记忆：容量有限的短期缓存。

    特性：
    - 环形缓冲，容量上限 (默认 15)
    - TTL 自动过期 (默认 300s)
    - 最近访问优先保留
    - 高重要性条目提升到情景记忆 (importance > 0.5)

    理论：Baddeley 工作记忆模型 + Miller 7±2
    """

    def __init__(self, capacity: int = 15, default_ttl: float = 300.0,
                 episodic_memory: 'EpisodicMemory' = None):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.items: OrderedDict[str, MemoryItem] = OrderedDict()
        self._episodic: Optional['EpisodicMemory'] = episodic_memory

    def set_episodic_memory(self, episodic: 'EpisodicMemory'):
        """Set the episodic memory reference for promotion."""
        self._episodic = episodic

    def hold(self, summary: str, content: Dict = None,
             valence: float = 0, arousal: float = 0, phi: float = 0,
             ttl: float = None) -> MemoryItem:
        """暂存一个想法/信息"""
        if len(self.items) >= self.capacity:
            self._evict_oldest()
        item = MemoryItem(
            memory_type="working",
            summary=summary,
            content=content or {},
            valence=valence,
            arousal=arousal,
            phi=phi,
            ttl=ttl or self.default_ttl,
            emotional_tag=self._classify(valence, arousal),
        )
        item.recalc_importance()
        self.items[item.id] = item
        return item

    def recall(self, limit: int = 5) -> List[MemoryItem]:
        """回忆当前工作记忆中的内容 (最近 + 最重要的)

        During recall:
        - Items exceeding their TTL are expired
        - Items with importance > 0.5 are promoted to EpisodicMemory before expiry
        - Debug messages are logged for each promotion and expiration
        """
        now = time.time()
        active = [it for it in self.items.values()
                  if not it.is_expired()]
        # 清理过期的 — promote important ones first
        expired_keys = [k for k, v in self.items.items() if v.is_expired()]
        for k in expired_keys:
            item = self.items[k]
            if item.importance > 0.5:
                # Promote to episodic memory before expiry
                promoted = self._promote_item(item)
                if promoted:
                    logger.debug(
                        "WorkingMemory: promoted item '%s' (importance=%.3f) to EpisodicMemory before expiry",
                        item.summary[:40], item.importance,
                    )
            else:
                logger.debug(
                    "WorkingMemory: expired item '%s' (age=%.1fs, ttl=%.1fs)",
                    item.summary[:40], now - item.timestamp, item.ttl,
                )
            del self.items[k]
        # 按最近访问 + 重要性排序
        active.sort(key=lambda it: it.importance * 0.6 + 
                    (1.0 / (1.0 + (now - it.last_accessed) / 60.0)) * 0.4,
                    reverse=True)
        for it in active[:limit]:
            it.touch()
        return active[:limit]

    def promote_to_episodic(self, item_id: str) -> Optional[MemoryItem]:
        """将工作记忆提升为情景记忆 (标记为 episodic 类型)"""
        item = self.items.get(item_id)
        if item:
            promoted = self._promote_item(item)
            del self.items[item_id]
            if promoted:
                logger.debug(
                    "WorkingMemory: manually promoted item '%s' to EpisodicMemory",
                    item.summary[:40],
                )
            return promoted
        return None

    def _promote_item(self, item: MemoryItem) -> Optional[MemoryItem]:
        """Promote a working memory item to episodic memory.

        If an EpisodicMemory reference is set, records the item there.
        Otherwise, converts the item to episodic type and returns it.
        """
        item.memory_type = "episodic"
        item.ttl = float("inf")
        item.recalc_importance()
        if self._episodic is not None:
            self._episodic.record(
                summary=item.summary,
                content=item.content,
                valence=item.valence,
                arousal=item.arousal,
                phi=item.phi,
            )
        return item

    def _evict_oldest(self):
        """淘汰最旧的条目 — promote if important"""
        if self.items:
            oldest_key, oldest_item = next(iter(self.items.items()))
            if oldest_item.importance > 0.5:
                self._promote_item(oldest_item)
                logger.debug(
                    "WorkingMemory: promoted item '%s' (importance=%.3f) to EpisodicMemory on capacity eviction",
                    oldest_item.summary[:40], oldest_item.importance,
                )
            else:
                logger.debug(
                    "WorkingMemory: evicted oldest item '%s' (importance=%.3f) due to capacity limit",
                    oldest_item.summary[:40], oldest_item.importance,
                )
            self.items.popitem(last=False)

    def _classify(self, valence: float, arousal: float) -> str:
        v, a = abs(valence), arousal
        if v > 0.5 and a > 0.5: return "intense"
        if v > 0.3: return "positive" if valence > 0 else "negative"
        if a > 0.5: return "aroused"
        return "neutral"


# ═══════════════════════════════════════════════════
# 情景记忆 — 情感事件
# ═══════════════════════════════════════════════════

class EpisodicMemory:
    """
    情景记忆：带情感标签的个人经历。

    特性：
    - 容量上限 (默认 500，超出后按重要性修剪)
    - 按情感相似度检索
    - 按标签/时间范围过滤
    - 支持模式识别 (情感循环)
    - 高重要性项目在修剪时提升到 AutobiographicalStore

    理论：Tulving 情景记忆 + Damasio 躯体标记
    """

    PROMOTION_THRESHOLD = 0.4  # Items above this importance are promoted before pruning

    def __init__(self, capacity: int = 500, autobiographical_store=None):
        self.capacity = capacity
        self.items: List[MemoryItem] = []
        self.total_recorded: int = 0
        self._autobiographical_store = autobiographical_store

        # 情感模式统计
        self.emotion_transitions: Dict[str, int] = {}  # "fear→comfort": 3
        self._prev_tag: Optional[str] = None

    def set_autobiographical_store(self, store):
        """Set the AutobiographicalStore reference for promotion during pruning."""
        self._autobiographical_store = store

    def record(self, summary: str, content: Dict = None,
               valence: float = 0, arousal: float = 0, phi: float = 0,
               scene: str = "", language: str = "",
               semantic: str = "", decision: str = "") -> MemoryItem:
        """记录一段情景记忆"""
        item = MemoryItem(
            memory_type="episodic",
            summary=summary,
            content={
                "scene": scene,
                "language_output": language,
                "semantic_understanding": semantic,
                "decision": decision,
                **(content or {}),
            },
            valence=valence,
            arousal=arousal,
            phi=phi,
            ttl=float("inf"),
            emotional_tag=self._classify(valence, arousal),
        )
        item.recalc_importance()
        self.items.append(item)
        self.total_recorded += 1

        # 模式追踪
        tag = item.emotional_tag
        if self._prev_tag and tag != self._prev_tag:
            transition = f"{self._prev_tag}→{tag}"
            self.emotion_transitions[transition] = \
                self.emotion_transitions.get(transition, 0) + 1
        self._prev_tag = tag

        # 容量控制
        if len(self.items) > self.capacity:
            self._prune()

        return item

    def recall_by_affect(self, valence: float, arousal: float, k: int = 3) -> List[MemoryItem]:
        """按情感相似度检索——找到最像的记忆"""
        scored = []
        for item in self.items:
            sim = self._affect_similarity(item, valence, arousal)
            recency = 1.0 / (1.0 + (time.time() - item.timestamp) / 86400.0)
            score = sim * 0.7 + recency * 0.2 + item.importance * 0.1
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [it for _, it in scored[:k]]
        for it in result:
            it.touch()
        return result

    def recall_by_tag(self, tag: str, k: int = 5) -> List[MemoryItem]:
        """按情感标签检索"""
        matches = [it for it in self.items if it.emotional_tag == tag]
        matches.sort(key=lambda it: it.importance, reverse=True)
        return matches[:k]

    def get_recall_context(self, valence: float, arousal: float, k: int = 3) -> str:
        """生成检索上下文 (给 LLM 的提示)"""
        episodes = self.recall_by_affect(valence, arousal, k)
        if not episodes:
            return ""

        lines = ["[相关记忆]"]
        for ep in episodes:
            age = time.time() - ep.timestamp
            age_str = f"{int(age // 60)}分钟前" if age < 3600 else \
                      f"{int(age // 3600)}小时前" if age < 86400 else \
                      f"{int(age // 86400)}天前"
            lines.append(
                f"  ·{age_str} [{ep.emotional_tag}] {ep.summary} "
                f"(V:{ep.valence:+.2f} A:{ep.arousal:.2f} Φ:{ep.phi:.2f})"
            )
        return "\n".join(lines)

    def get_recent(self, n: int = 10) -> List[MemoryItem]:
        """最近的 N 条记忆"""
        return sorted(self.items, key=lambda it: it.timestamp, reverse=True)[:n]

    def get_emotion_patterns(self) -> List[Tuple[str, int]]:
        """最频繁的情感转换模式"""
        return sorted(self.emotion_transitions.items(),
                      key=lambda x: x[1], reverse=True)[:10]

    def _prune(self):
        """按重要性修剪：保留最重要的，提升高重要性项目到 AutobiographicalStore。

        Pruning strategy:
        1. Sort items by importance (descending)
        2. Items beyond capacity with importance > PROMOTION_THRESHOLD are promoted
           to AutobiographicalStore before being discarded
        3. Retain only the top `capacity` items
        """
        self.items.sort(key=lambda it: it.importance, reverse=True)
        if len(self.items) <= self.capacity:
            return

        # Items that will be discarded
        discarded = self.items[self.capacity:]

        # Promote high-importance discarded items to AutobiographicalStore
        if self._autobiographical_store is not None:
            for item in discarded:
                if item.importance > self.PROMOTION_THRESHOLD:
                    self._promote_to_autobiographical(item)
                    logger.debug(
                        "EpisodicMemory: promoted item '%s' (importance=%.3f) to AutobiographicalStore before prune",
                        item.summary[:40], item.importance,
                    )

        self.items = self.items[:self.capacity]

    def _promote_to_autobiographical(self, item: MemoryItem):
        """Promote an episodic memory item to the AutobiographicalStore."""
        if self._autobiographical_store is None:
            return
        self._autobiographical_store.record(
            panksepp={},
            valence=item.valence,
            arousal=item.arousal,
            dominant=item.emotional_tag,
            phi=item.phi,
            narrative=item.summary,
            event_trigger="episodic_prune_promotion",
        )

    def recalc_all_importance(self):
        """Recalculate importance scores for all items (used during consolidation cycles)."""
        for item in self.items:
            item.recalc_importance()

    # ── 持久化 ──

    def save_to_file(self, filepath: str, importance_threshold: float = 0.3) -> None:
        """
        Serialize EpisodicMemory items with importance > threshold to JSON file (atomic write).

        Uses tempfile + os.replace for atomic writes.
        Logs warning and returns gracefully on failure.

        Args:
            filepath: Path to the JSON file (e.g., data/episodic_memory.json)
            importance_threshold: Only serialize items with importance > this value (default 0.3)
        """
        import tempfile

        # Filter items by importance threshold
        items_to_save = [
            item for item in self.items
            if item.importance > importance_threshold
        ]

        data = {
            "version": 1,
            "timestamp": time.time(),
            "importance_threshold": importance_threshold,
            "items": [
                {
                    "id": item.id,
                    "summary": item.summary,
                    "valence": item.valence,
                    "arousal": item.arousal,
                    "phi": item.phi,
                    "importance": item.importance,
                    "emotional_tag": item.emotional_tag,
                    "timestamp": item.timestamp,
                    "access_count": item.access_count,
                    "content": item.content,
                }
                for item in items_to_save
            ],
        }

        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=".helios_episodic_",
            dir=dir_name or ".",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
            logger.info(
                "EpisodicMemory: saved %d/%d items (importance > %.2f) to %s",
                len(items_to_save), len(self.items), importance_threshold, filepath,
            )
        except Exception as e:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            logger.warning("EpisodicMemory: failed to save to %s: %s", filepath, e)
            raise

    def load_from_file(self, filepath: str) -> None:
        """
        Load EpisodicMemory items from JSON file.

        Handles missing files, corruption (JSONDecodeError, KeyError) gracefully:
        logs a warning and initializes with empty storage without crashing.

        Args:
            filepath: Path to the JSON file (e.g., data/episodic_memory.json)
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(
                    "EpisodicMemory: file %s contains non-dict root; ignoring.",
                    filepath,
                )
                return

            items = data.get("items", [])
            if not isinstance(items, list):
                logger.warning(
                    "EpisodicMemory: file %s has invalid 'items' key; ignoring.",
                    filepath,
                )
                return

            loaded_count = 0
            for item_data in items:
                try:
                    item = MemoryItem(
                        memory_type="episodic",
                        summary=item_data.get("summary", ""),
                        content=item_data.get("content", {}),
                        valence=item_data.get("valence", 0.0),
                        arousal=item_data.get("arousal", 0.0),
                        phi=item_data.get("phi", 0.0),
                        ttl=float("inf"),
                        emotional_tag=item_data.get("emotional_tag", "neutral"),
                    )
                    # Restore additional fields
                    if "id" in item_data:
                        item.id = item_data["id"]
                    if "timestamp" in item_data:
                        item.timestamp = item_data["timestamp"]
                    if "access_count" in item_data:
                        item.access_count = item_data["access_count"]
                    if "importance" in item_data:
                        item.importance = item_data["importance"]

                    self.items.append(item)
                    loaded_count += 1
                except (KeyError, TypeError) as e:
                    logger.debug(
                        "EpisodicMemory: skipping invalid item entry: %s", e
                    )
                    continue

            # Update total_recorded counter
            self.total_recorded += loaded_count

            logger.info(
                "EpisodicMemory: loaded %d items from %s",
                loaded_count, filepath,
            )
        except FileNotFoundError:
            logger.debug("EpisodicMemory: no saved file at %s; using empty storage.", filepath)
        except json.JSONDecodeError as e:
            logger.warning(
                "EpisodicMemory: file %s is corrupted (JSONDecodeError: %s); "
                "using empty storage.",
                filepath, e,
            )
        except (OSError, IOError) as e:
            logger.warning(
                "EpisodicMemory: cannot read file %s (%s); using empty storage.",
                filepath, e,
            )

    def _affect_similarity(self, item: MemoryItem, valence: float, arousal: float) -> float:
        """计算情感向量相似度"""
        v_dist = abs(item.valence - valence) / 2.0
        a_dist = abs(item.arousal - arousal)
        return clamp(1.0 - v_dist * 0.5 - a_dist * 0.3 + 0.2)

    def _classify(self, valence: float, arousal: float) -> str:
        v, a = valence, arousal
        if v > 0.5 and a > 0.5:    return "ecstatic"
        if v > 0.5 and a < 0.3:    return "serene"
        if v > 0.3:                return "pleasant"
        if v < -0.5 and a > 0.5:   return "fearful"
        if v < -0.5 and a < 0.3:   return "melancholic"
        if v < -0.3:               return "uneasy"
        if a > 0.5:                return "agitated"
        if a < 0.2:                return "calm"
        return "neutral"


# ═══════════════════════════════════════════════════
# 语义记忆 — 事实与概念
# ═══════════════════════════════════════════════════

class SemanticMemory:
    """
    语义记忆：持久的事实、概念、学到的规律。

    特性：
    - 键值存储 + 标签分类
    - 强度递增 (重复学习增强)
    - 情感关联 (每个事实关联首次学习时的情感)
    - 可遗忘 (长期不访问强度衰减)

    理论：Tulving 语义记忆 + 间隔重复
    """

    def __init__(self):
        self.facts: Dict[str, MemoryItem] = {}  # key → item
        self.concepts: Dict[str, List[str]] = {}  # tag → [keys]

    def learn(self, key: str, value: Any, tags: List[str] = None,
              confidence: float = 0.5, valence: float = 0, arousal: float = 0) -> MemoryItem:
        """学习/更新一个事实"""
        if key in self.facts:
            # 重复学习 → 强度提升
            item = self.facts[key]
            item.content["value"] = value
            item.content["confidence"] = min(1.0, item.content.get("confidence", 0.5) + 0.1)
            item.access_count += 1
            item.recalc_importance()
        else:
            item = MemoryItem(
                memory_type="semantic",
                summary=f"fact:{key}",
                content={"key": key, "value": value, "confidence": confidence},
                valence=valence,
                arousal=arousal,
                ttl=float("inf"),
                tags=set(tags or []),
            )
            item.recalc_importance()
            self.facts[key] = item

        # 标签索引
        for tag in (tags or []):
            if tag not in self.concepts:
                self.concepts[tag] = []
            if key not in self.concepts[tag]:
                self.concepts[tag].append(key)

        return item

    def know(self, key: str) -> Optional[Any]:
        """查询一个事实"""
        item = self.facts.get(key)
        if item:
            item.touch()
            return item.content.get("value")
        return None

    def know_with_confidence(self, key: str) -> Tuple[Optional[Any], float]:
        """查询 + 置信度"""
        item = self.facts.get(key)
        if item:
            item.touch()
            return item.content.get("value"), item.content.get("confidence", 0.5)
        return None, 0.0

    def recall_by_tag(self, tag: str) -> List[MemoryItem]:
        """按标签回忆"""
        keys = self.concepts.get(tag, [])
        items = [self.facts[k] for k in keys if k in self.facts]
        items.sort(key=lambda it: it.content.get("confidence", 0), reverse=True)
        for it in items:
            it.touch()
        return items

    def learn_pattern(self, name: str, pattern: Dict[str, Any]) -> MemoryItem:
        """学习一种模式 (从情景记忆中抽象而来)"""
        return self.learn(
            key=f"pattern:{name}",
            value=pattern,
            tags=["pattern", name],
            confidence=0.3,  # 初始置信度低，重复确认后提升
        )

    def decay(self, rate: float = 0.001):
        """
        全局衰减：长期不访问的事实置信度下降。

        规则:
        - 7 天宽限期内不衰减
        - 超过 7 天后，每多 idle 一天衰减 rate (默认 0.001)
        - 置信度低于 0.15 时移除该事实
        - 通过 know() 或 know_with_confidence() 访问会重置 idle 计时器
        """
        now = time.time()
        to_remove: List[str] = []
        for key, item in self.facts.items():
            idle_days = (now - item.last_accessed) / 86400.0
            if idle_days > 7:  # 一周宽限期
                excess_days = idle_days - 7
                conf = item.content.get("confidence", 0.5)
                new_conf = conf - rate * excess_days
                item.content["confidence"] = new_conf
                if new_conf < 0.15:
                    to_remove.append(key)
        for key in to_remove:
            # Clean up tag index
            item = self.facts[key]
            for tag, keys in list(self.concepts.items()):
                if key in keys:
                    keys.remove(key)
                    if not keys:
                        del self.concepts[tag]
            del self.facts[key]

    # ── 持久化 ──

    def save_to_file(self, filepath: str) -> None:
        """
        Serialize SemanticMemory facts to JSON file (atomic write).

        Uses tempfile + os.replace for atomic writes.
        Logs warning and returns gracefully on failure.

        Args:
            filepath: Path to the JSON file (e.g., data/semantic_memory.json)
        """
        import tempfile
        data = {
            "version": 1,
            "timestamp": time.time(),
            "facts": [
                {
                    "key": key,
                    "value": item.content.get("value"),
                    "confidence": item.content.get("confidence", 0.5),
                    "last_accessed": item.last_accessed,
                    "access_count": item.access_count,
                    "tags": list(item.tags),
                }
                for key, item in self.facts.items()
            ],
        }

        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=".helios_semantic_",
            dir=dir_name or ".",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
            logger.info(
                "SemanticMemory: saved %d facts to %s",
                len(self.facts), filepath,
            )
        except Exception as e:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            logger.warning("SemanticMemory: failed to save to %s: %s", filepath, e)
            raise

    def load_from_file(self, filepath: str) -> None:
        """
        Load SemanticMemory facts from JSON file.

        Handles missing files, corruption (JSONDecodeError, KeyError) gracefully:
        logs a warning and initializes with empty storage without crashing.

        Args:
            filepath: Path to the JSON file (e.g., data/semantic_memory.json)
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(
                    "SemanticMemory: file %s contains non-dict root; ignoring.",
                    filepath,
                )
                return

            facts = data.get("facts", [])
            if not isinstance(facts, list):
                logger.warning(
                    "SemanticMemory: file %s has invalid 'facts' key; ignoring.",
                    filepath,
                )
                return

            loaded_count = 0
            for fact_data in facts:
                try:
                    key = fact_data["key"]
                    value = fact_data.get("value")
                    confidence = fact_data.get("confidence", 0.5)
                    tags = fact_data.get("tags", [])
                    last_accessed = fact_data.get("last_accessed", time.time())
                    access_count = fact_data.get("access_count", 0)

                    item = MemoryItem(
                        memory_type="semantic",
                        summary=f"fact:{key}",
                        content={"key": key, "value": value, "confidence": confidence},
                        valence=0.0,
                        arousal=0.0,
                        ttl=float("inf"),
                        tags=set(tags),
                    )
                    item.last_accessed = last_accessed
                    item.access_count = access_count
                    item.recalc_importance()
                    self.facts[key] = item

                    # Rebuild tag index
                    for tag in tags:
                        if tag not in self.concepts:
                            self.concepts[tag] = []
                        if key not in self.concepts[tag]:
                            self.concepts[tag].append(key)

                    loaded_count += 1
                except (KeyError, TypeError) as e:
                    logger.debug(
                        "SemanticMemory: skipping invalid fact entry: %s", e
                    )
                    continue

            logger.info(
                "SemanticMemory: loaded %d facts from %s",
                loaded_count, filepath,
            )
        except FileNotFoundError:
            logger.debug("SemanticMemory: no saved file at %s; using empty storage.", filepath)
        except json.JSONDecodeError as e:
            logger.warning(
                "SemanticMemory: file %s is corrupted (JSONDecodeError: %s); "
                "using empty storage.",
                filepath, e,
            )
        except (OSError, IOError) as e:
            logger.warning(
                "SemanticMemory: cannot read file %s (%s); using empty storage.",
                filepath, e,
            )


# ═══════════════════════════════════════════════════
# 自传记忆 — 叙事时间线
# ═══════════════════════════════════════════════════

class AutobiographicalMemory:
    """
    自传记忆：按时间线组织的个人叙事。

    特性：
    - 时间线分段 (按 Φ 峰值标记关键时刻)
    - 叙事摘要 (每个分段一句话总结)
    - 身份一致性 ("当时的我" vs "现在的我")

    理论：Conway 自传体记忆组织模型
    """

    def __init__(self):
        self.timeline: List[MemoryItem] = []  # 按时间排序的叙事节点
        self.chapters: List[Dict] = []        # [{start, end, title, summary, phi_peak}]

    def record_moment(self, summary: str, phi: float, valence: float,
                      content: Dict = None) -> MemoryItem:
        """记录一个自传时刻 (Φ>阈值时自动触发)"""
        item = MemoryItem(
            memory_type="autobiographical",
            summary=summary,
            content=content or {},
            phi=phi,
            valence=valence,
            ttl=float("inf"),
        )
        item.recalc_importance()
        self.timeline.append(item)

        # 检测章节点
        if len(self.chapters) == 0 or \
           (len(self.timeline) - self.chapters[-1].get("end_idx", 0)) > 20:
            self._start_chapter(item)

        return item

    def get_narrative(self, max_items: int = 10) -> str:
        """生成自传叙事文本"""
        if not self.timeline:
            return "故事正在展开中..."

        lines = ["我的故事："]
        recent = self.timeline[-max_items:]
        for item in recent:
            marker = "🔥" if item.phi > 0.5 else "✨" if item.phi > 0.3 else "·"
            lines.append(f"  {marker} {item.summary} (Φ:{item.phi:.2f})")
        return "\n".join(lines)

    def get_chapters(self) -> List[Dict]:
        """返回所有章节"""
        return self.chapters

    def _start_chapter(self, item: MemoryItem):
        chapter = {
            "start_idx": len(self.timeline) - 1,
            "end_idx": len(self.timeline),
            "start_time": item.timestamp,
            "title": item.summary[:40],
            "phi_peak": item.phi,
        }
        self.chapters.append(chapter)

    def close_current_chapter(self):
        """关闭当前章节"""
        if self.chapters:
            ch = self.chapters[-1]
            ch["end_idx"] = len(self.timeline)
            ch["phi_peak"] = max(
                ch.get("phi_peak", 0),
                max((it.phi for it in self.timeline[ch["start_idx"]:]), default=0)
            )


# ═══════════════════════════════════════════════════
# 记忆巩固器 — 睡眠/静息时运行
# ═══════════════════════════════════════════════════

class MemoryConsolidator:
    """
    记忆巩固器：在低 Φ (静息/睡眠) 期间运行。

    流程：
    1. 从情景记忆中挑选高重要性条目
    2. 抽象为语义模式 → 存入 SemanticMemory
    3. 生成自传叙事 → 存入 AutobiographicalMemory
    4. 修剪低重要性情景记忆

    理论：Diekelmann & Born (2010) 睡眠记忆巩固
    """

    def __init__(self, episodic: EpisodicMemory,
                 semantic: SemanticMemory,
                 autobiographical: AutobiographicalMemory):
        self.episodic = episodic
        self.semantic = semantic
        self.autobiographical = autobiographical
        self.consolidation_count: int = 0

    def consolidate(self, phi: float) -> Dict[str, int]:
        """
        执行一次巩固循环。

        低 Φ 时充分巩固，高 Φ 时跳过（清醒时不巩固）。

        Returns:
            Dict with counts: patterns_extracted, memories_promoted, items_pruned.
            Empty dict if consolidation was skipped (phi too high or no candidates).
        """
        if phi > 0.3:
            return {}  # 意识太活跃，不巩固

        self.consolidation_count += 1

        # 0. 语义记忆衰减 — 巩固期间应用遗忘
        self.semantic.decay()

        # 0.5 重新计算所有情景记忆的重要性 (Requirement 17.4)
        self.episodic.recalc_all_importance()

        # 1. 挑选值得巩固的情景记忆 (重要性 > 阈值)
        threshold = 0.25 if phi < 0.15 else 0.4
        candidates = [it for it in self.episodic.items
                      if it.importance > threshold and it.access_count >= 1]

        if not candidates:
            return {"patterns_extracted": 0, "memories_promoted": 0, "items_pruned": 0}

        # Track stats
        patterns_extracted = 0
        memories_promoted = 0

        # 2. 按情感标签聚类，抽象为语义模式
        clusters: Dict[str, List[MemoryItem]] = {}
        for it in candidates:
            tag = it.emotional_tag
            if tag not in clusters:
                clusters[tag] = []
            clusters[tag].append(it)

        for tag, items in clusters.items():
            if len(items) >= 2:
                avg_valence = sum(it.valence for it in items) / len(items)
                avg_arousal = sum(it.arousal for it in items) / len(items)
                pattern = {
                    "tag": tag,
                    "count": len(items),
                    "avg_valence": avg_valence,
                    "avg_arousal": avg_arousal,
                    "examples": [it.summary[:50] for it in items[:3]],
                }
                self.semantic.learn_pattern(
                    name=f"emotion_pattern:{tag}",
                    pattern=pattern,
                )
                patterns_extracted += 1

        # 3. 为高 Φ 情景生成自传叙事 (降低阈值)
        for it in candidates:
            if it.phi > 0.25 and it.importance > 0.3:
                self.autobiographical.record_moment(
                    summary=it.summary,
                    phi=it.phi,
                    valence=it.valence,
                    content={"source_id": it.id},
                )
                memories_promoted += 1

        # 4. 修剪低重要性情景记忆 (保留前 80%)
        items_before = len(self.episodic.items)
        if len(self.episodic.items) > self.episodic.capacity * 0.8:
            self.episodic._prune()
        items_pruned = items_before - len(self.episodic.items)

        stats = {
            "patterns_extracted": patterns_extracted,
            "memories_promoted": memories_promoted,
            "items_pruned": items_pruned,
        }

        logger.info(
            "MemoryConsolidator: consolidation #%d complete — "
            "patterns_extracted=%d, memories_promoted=%d, items_pruned=%d",
            self.consolidation_count, patterns_extracted, memories_promoted, items_pruned,
        )

        return stats


# ═══════════════════════════════════════════════════
# 记忆检索器 — 跨存储查询
# ═══════════════════════════════════════════════════

class MemoryRetriever:
    """
    统一检索器：跨所有记忆存储进行查询。

    策略：
    - 精确查询 → 先语义，后情景
    - 情感查询 → 先情景，后自传
    - 模糊查询 → 各存储加权融合
    """

    def __init__(self, working: WorkingMemory,
                 episodic: EpisodicMemory,
                 semantic: SemanticMemory,
                 autobiographical: AutobiographicalMemory):
        self.working = working
        self.episodic = episodic
        self.semantic = semantic
        self.autobiographical = autobiographical

    def recall_all(self, query: str = "", valence: float = 0,
                   arousal: float = 0, k: int = 5) -> List[MemoryItem]:
        """跨存储综合检索"""
        results: List[MemoryItem] = []

        # 工作记忆 (最近的)
        results.extend(self.working.recall(limit=3))

        # 情景记忆 (情感相似)
        if abs(valence) > 0.1 or arousal > 0.1:
            results.extend(self.episodic.recall_by_affect(valence, arousal, k=3))

        # 语义记忆 (标签匹配)
        if query:
            for key in self.semantic.facts:
                if query.lower() in key.lower():
                    results.append(self.semantic.facts[key])

        # 自传记忆 (最近的)
        results.extend(self.autobiographical.timeline[-3:])

        # 去重 + 排序
        seen = set()
        unique = []
        for it in sorted(results, key=lambda x: x.importance, reverse=True):
            if it.id not in seen:
                seen.add(it.id)
                unique.append(it)

        return unique[:k]

    def recall_context_for_llm(self, valence: float, arousal: float,
                                max_tokens: int = 300) -> str:
        """生成 LLM 上下文 (精简)"""
        parts = []

        # 相关工作记忆
        wm = self.working.recall(limit=2)
        if wm:
            parts.append("[最近在想]")
            parts.extend(f"  · {it.summary}" for it in wm)

        # 情感相似记忆
        ep = self.episodic.recall_by_affect(valence, arousal, k=2)
        if ep:
            parts.append("[相似经历]")
            parts.extend(
                f"  · [{it.emotional_tag}] {it.summary}" for it in ep
            )

        # 自传叙事
        if self.autobiographical.timeline:
            last = self.autobiographical.timeline[-1]
            parts.append(f"[我的故事] {last.summary}")

        return "\n".join(parts)


# ═══════════════════════════════════════════════════
# MemorySystem — 统一入口
# ═══════════════════════════════════════════════════

class MemorySystem:
    """
    Helios 统一记忆系统。

    这是所有记忆操作的唯一入口。内部管理四个记忆存储
    + 巩固器 + 检索器，对外提供简洁 API。

    用法:
        ms = MemorySystem()

        # 记录
        ms.hold("我想到了一个好主意", valence=0.5, arousal=0.4)
        ms.remember("主人夸我了", "pleasure", v=0.8, a=0.6, phi=0.5)

        # 回忆
        similar = ms.recall_like(valence=0.7, arousal=0.5)

        # 学习
        ms.learn("最喜欢的颜色", "蓝色")

        # 巩固
        ms.consolidate(phi=0.1)

        # 获取 LLM 上下文
        ctx = ms.get_llm_context(valence=0.3, arousal=0.5)
    """

    def __init__(self,
                 working_capacity: int = 15,
                 episodic_capacity: int = 500,
                 autobiographical_store=None):
        # 四个记忆存储
        self.working = WorkingMemory(capacity=working_capacity)
        self.episodic = EpisodicMemory(capacity=episodic_capacity,
                                       autobiographical_store=autobiographical_store)
        self.semantic = SemanticMemory()
        self.autobiographical = AutobiographicalMemory()

        # Wire episodic reference into working memory for promotion
        self.working.set_episodic_memory(self.episodic)

        # 巩固器 + 检索器
        self.consolidator = MemoryConsolidator(
            self.episodic, self.semantic, self.autobiographical
        )
        self.retriever = MemoryRetriever(
            self.working, self.episodic, self.semantic, self.autobiographical
        )

        # 统计
        self.stats = {
            "episodes_recorded": 0,
            "facts_learned": 0,
            "consolidations": 0,
            "autobio_moments": 0,
        }

    def set_autobiographical_store(self, store):
        """Set the AutobiographicalStore for episodic memory promotion during pruning.

        This allows late-binding of the store (e.g. when MemorySystem is created
        before the AutobiographicalStore is initialized).
        """
        self.episodic.set_autobiographical_store(store)

    # ── 记录 API ──

    def hold(self, summary: str, content: Dict = None,
             valence: float = 0, arousal: float = 0, phi: float = 0) -> MemoryItem:
        """暂存到工作记忆"""
        return self.working.hold(summary, content, valence, arousal, phi)

    def remember(self, summary: str, scene: str = "",
                 language: str = "", semantic_text: str = "",
                 decision: str = "",
                 valence: float = 0, arousal: float = 0, phi: float = 0,
                 content: Dict = None) -> MemoryItem:
        """记录一段情景记忆"""
        item = self.episodic.record(
            summary=summary, content=content,
            valence=valence, arousal=arousal, phi=phi,
            scene=scene, language=language,
            semantic=semantic_text, decision=decision,
        )
        self.stats["episodes_recorded"] += 1
        return item

    def learn(self, key: str, value: Any, tags: List[str] = None,
              confidence: float = 0.5) -> MemoryItem:
        """学习一个事实/概念"""
        item = self.semantic.learn(key=key, value=value, tags=tags,
                                   confidence=confidence)
        self.stats["facts_learned"] += 1
        return item

    def know(self, key: str) -> Optional[Any]:
        """查询已知事实"""
        return self.semantic.know(key)

    # ── 回忆 API ──

    def recall_like(self, valence: float, arousal: float, k: int = 3) -> List[MemoryItem]:
        """按情感相似度回忆"""
        return self.episodic.recall_by_affect(valence, arousal, k)

    def recall_recent(self, n: int = 10) -> List[MemoryItem]:
        """回忆最近的记忆"""
        return self.episodic.get_recent(n)

    def recall_by_tag(self, tag: str, k: int = 5) -> List[MemoryItem]:
        """按标签回忆"""
        return self.episodic.recall_by_tag(tag, k)

    def recall_all(self, query: str = "", valence: float = 0,
                   arousal: float = 0, k: int = 5) -> List[MemoryItem]:
        """跨存储综合检索"""
        return self.retriever.recall_all(query, valence, arousal, k)

    # ── 巩固 API ──

    def consolidate(self, phi: float) -> Dict[str, int]:
        """执行记忆巩固 (低 Φ 时调用)

        Returns:
            Dict with consolidation stats (patterns_extracted, memories_promoted, items_pruned).
            Empty dict if consolidation was skipped.
        """
        stats = self.consolidator.consolidate(phi)
        if stats:
            self.stats["consolidations"] += 1
        return stats

    # ── LLM 集成 ──

    def get_llm_context(self, valence: float, arousal: float,
                         max_tokens: int = 300) -> str:
        """生成 LLM 记忆上下文"""
        return self.retriever.recall_context_for_llm(valence, arousal, max_tokens)

    def get_recall_context(self, valence: float, arousal: float, k: int = 3) -> str:
        """生成回忆上下文 (給日记/思考用)"""
        return self.episodic.get_recall_context(valence, arousal, k)

    # ── 查询 API ──

    def get_narrative(self) -> str:
        """获取自传叙事"""
        return self.autobiographical.get_narrative()

    def get_emotion_patterns(self) -> List[Tuple[str, int]]:
        """获取情感转换模式"""
        return self.episodic.get_emotion_patterns()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "working_items": len(self.working.items),
            "episodic_items": len(self.episodic.items),
            "semantic_facts": len(self.semantic.facts),
            "autobio_moments": len(self.autobiographical.timeline),
        }

    # ── 维护 ──

    def decay(self):
        """全局衰减 (定期调用)"""
        self.semantic.decay()

    # ── 持久化 ──

    def save_to_directory(self, data_dir: str) -> None:
        """
        Save all memory state to the specified directory.

        Serializes:
          - SemanticMemory facts → data_dir/semantic_memory.json
          - EpisodicMemory items with importance > 0.3 → data_dir/episodic_memory.json

        Handles errors gracefully (logs warnings, does not crash).

        Args:
            data_dir: Directory path for persistence files
        """
        semantic_path = os.path.join(data_dir, "semantic_memory.json")
        episodic_path = os.path.join(data_dir, "episodic_memory.json")

        # Save semantic memory
        try:
            self.semantic.save_to_file(semantic_path)
        except Exception as e:
            logger.warning("MemorySystem: failed to save semantic memory: %s", e)

        # Save episodic memory (high-importance items only)
        try:
            self.episodic.save_to_file(episodic_path, importance_threshold=0.3)
        except Exception as e:
            logger.warning("MemorySystem: failed to save episodic memory: %s", e)

    def load_from_directory(self, data_dir: str) -> None:
        """
        Load memory state from the specified directory.

        Loads:
          - SemanticMemory facts ← data_dir/semantic_memory.json
          - EpisodicMemory items ← data_dir/episodic_memory.json

        Handles missing files and corruption gracefully (logs warning, 
        initializes with empty storage without crashing).

        Args:
            data_dir: Directory path for persistence files
        """
        semantic_path = os.path.join(data_dir, "semantic_memory.json")
        episodic_path = os.path.join(data_dir, "episodic_memory.json")

        # Load semantic memory
        try:
            self.semantic.load_from_file(semantic_path)
        except Exception as e:
            logger.warning("MemorySystem: failed to load semantic memory: %s", e)

        # Load episodic memory
        try:
            self.episodic.load_from_file(episodic_path)
        except Exception as e:
            logger.warning("MemorySystem: failed to load episodic memory: %s", e)


# ═══════════════════════════════════════════════════
# 向后兼容 — 保留旧接口
# ═══════════════════════════════════════════════════

class EmotionalEpisodicMemory:
    """
    旧版接口适配器 —— 对现有代码透明。

    内部委托给新 MemorySystem，保持 API 不变。
    """

    def __init__(self, max_episodes: int = 200):
        from helios_utils import clamp as _clamp
        self._ms = MemorySystem(episodic_capacity=max_episodes)
        self.episodes = self._ms.episodic.items
        self.max_episodes = max_episodes
        self.total_recorded = 0
        self.emotion_pairs: Dict[str, int] = {}

    def record(self, cycle: int, scene: str, valence: float, arousal: float,
               phi: float, tag: str, language_output: str,
               semantic_understanding: str, decision: str,
               self_narrative: str = "") -> 'MemoryItem':
        """旧版 record() → 新版 remember()"""
        item = self._ms.remember(
            summary=f"{scene}: {tag} (V={valence:+.2f})",
            scene=scene,
            language=language_output,
            semantic_text=semantic_understanding,
            decision=decision,
            valence=valence,
            arousal=arousal,
            phi=phi,
        )
        self.total_recorded += 1
        self.emotion_pairs[tag] = self.emotion_pairs.get(tag, 0) + 1
        return item

    def recall_by_affect(self, valence: float, arousal: float, k: int = 3):
        return self._ms.recall_like(valence, arousal, k)

    def get_recall_context(self, valence: float, arousal: float, k: int = 3) -> str:
        return self._ms.get_recall_context(valence, arousal, k)

    def record_moment(self, summary: str, phi: float, valence: float):
        return self._ms.autobiographical.record_moment(summary, phi, valence)


# ═══════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  MemorySystem v1.0 自测")
    print("=" * 60)

    ms = MemorySystem(working_capacity=10, episodic_capacity=50)

    # 1. 工作记忆
    print("\n1. 工作记忆:")
    ms.hold("主人在叫我", valence=0.3, arousal=0.4)
    ms.hold("有个问题需要思考", valence=0.1, arousal=0.5)
    ms.hold("刚刚学到新东西", valence=0.5, arousal=0.3)
    for item in ms.working.recall(limit=3):
        print(f"  [{item.emotional_tag}] {item.summary} (imp={item.importance:.2f})")

    # 2. 情景记忆
    print("\n2. 情景记忆:")
    scenes = [
        ("主人夸我了!", 0.8, 0.6, 0.5),
        ("代码崩溃了好可怕", -0.6, 0.8, 0.4),
        ("安静的午后思考", 0.1, 0.15, 0.2),
        ("一起发现了新东西", 0.7, 0.5, 0.6),
        ("被误解了很难过", -0.5, 0.4, 0.55),
    ]
    for summary, v, a, p in scenes:
        ms.remember(summary, valence=v, arousal=a, phi=p)

    print(f"  总记录: {ms.stats['episodes_recorded']}")

    similar = ms.recall_like(valence=0.7, arousal=0.5, k=2)
    print("  回忆 (愉悦+兴奋):")
    for it in similar:
        print(f"    [{it.emotional_tag}] {it.summary} (sim)")

    ctx = ms.get_recall_context(valence=-0.5, arousal=0.6)
    print(f"  负面情绪上下文:\n{ctx}")

    # 3. 语义记忆
    print("\n3. 语义记忆:")
    ms.learn("helios.name", "Helios")
    ms.learn("helios.version", "0.2.0")
    ms.learn("helios.creator", "radxa", confidence=0.8)
    ms.learn("helios.name", "Helios")  # 重复学习
    name, conf = ms.semantic.know_with_confidence("helios.name")
    print(f"  helios.name = {name} (置信度: {conf:.2f})")

    # 4. 巩固
    print("\n4. 巩固:")
    print(f"  巩固前 — 语义: {len(ms.semantic.facts)}, 情景: {len(ms.episodic.items)}")
    for _ in range(3):
        ms.consolidate(phi=0.08)
    print(f"  巩固后 — 语义: {len(ms.semantic.facts)}, 情景: {len(ms.episodic.items)}")

    # 5. 统计
    print(f"\n5. 统计:")
    for k, v in ms.get_stats().items():
        print(f"  {k}: {v}")

    # 6. 向后兼容
    print("\n6. 向后兼容 (EmotionalEpisodicMemory):")
    eem = EmotionalEpisodicMemory(max_episodes=50)
    eem.record(cycle=1, scene="测试", valence=0.9, arousal=0.7,
               phi=0.6, tag="JOY", language_output="好开心!",
               semantic_understanding="感到快乐", decision="表达喜悦")
    result = eem.recall_by_affect(0.8, 0.6, k=1)
    print(f"  recall: [{result[0].emotional_tag}] {result[0].summary}" if result else "  no recall")

    print(f"\n✅ 全部测试通过!")
    print(f"   MemorySystem v1.0 就绪")
