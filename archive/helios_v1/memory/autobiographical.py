"""
N1: 自传记忆持久化 (AutobiographicalStore)
============================================

科学基础:
  · Conway (2005) Self-Memory System — 自传体记忆组织模型
  · Pillemer (1998) Momentous Events — Φ峰值标记关键记忆
  · Rubin & Umanath (2015) Event Segmentation — 事件边界检测

设计:
  · JSONL 持久化: 追加写入, 崩溃安全
  · 双重写入: 内存镜像 + 磁盘
  · 自动保存: 每 N 条 flush
  · 三层检索: 时间范围 / 情感查询 / Φ峰值
  · 章节分割: 长期运行中自动切分"人生章节"

与 memory_system.py 的关系:
  · AutobiographicalMemory: 运行时内存对象 (fast, ephemeral)
  · AutobiographicalStore: 持久化存储层 (disk,跨session)
  · 两者互补 — 运行中用内存对象, 存储/加载用 Store

文件: autobiographical.py
依赖: 无外部依赖
"""

import json
import logging
import time
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from .backend import AutobiographicalBackend, JsonlAutobiographicalBackend

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════

@dataclass
class AutobiographicalMoment:
    """一个自传时刻 — 包含完整情感快照"""
    
    # 标识
    moment_id: str = ""            # 唯一ID (时间戳+序号)
    timestamp: float = 0.0         # Unix时间
    cycle: int = 0                 # 引擎周期
    
    # 情感快照
    dominant: str = ""             # 主导 Panksepp 系统
    panksepp: Dict[str, float] = field(default_factory=dict)  # 7系统矢量
    valence: float = 0.0
    arousal: float = 0.0
    phi: float = 0.0
    
    # 心境 + 异稳态
    mood_valence: float = 0.0
    mood_arousal: float = 0.0
    mood_label: str = "neutral"
    allostatic_load: float = 0.0
    
    # 叙事
    narrative: str = ""            # 一句话叙事摘要
    significance: float = 0.0      # 重要性评分 (0-1)
    tags: List[str] = field(default_factory=list)
    
    # 上下文
    chapter: str = ""              # 章节名
    event_trigger: str = ""        # 触发事件描述
    source: str = ""               # 来源标签 (organic / seed import / compression)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp_iso"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.localtime(self.timestamp)
        )
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "AutobiographicalMoment":
        # 兼容旧格式
        for key in ["panksepp", "tags"]:
            if key not in d:
                d[key] = {} if key == "panksepp" else []
        return cls(**{k: d.get(k, "") for k in [
            "moment_id", "timestamp", "cycle", "dominant",
            "panksepp", "valence", "arousal", "phi",
            "mood_valence", "mood_arousal", "mood_label",
            "allostatic_load", "narrative", "significance",
            "tags", "chapter", "event_trigger", "source",
        ]})


@dataclass
class Chapter:
    """自传章节 — 一段"人生时期" """
    title: str = ""
    start_moment_id: str = ""
    end_moment_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    phi_peak: float = 0.0
    dominant_theme: str = ""       # 主导情感主题
    summary: str = ""
    moment_count: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "Chapter":
        return cls(**{k: d.get(k, "") for k in [
            "title", "start_moment_id", "end_moment_id",
            "start_time", "end_time", "phi_peak",
            "dominant_theme", "summary", "moment_count",
        ]})


# ═══════════════════════════════════════════════
# 持久化存储
# ═══════════════════════════════════════════════

class AutobiographicalStore:
    """
    自传记忆持久化存储
    
    用法:
        store = AutobiographicalStore("memory/autobio.jsonl")
        
        # 记录时刻
        moment = store.record(state_snapshot, narrative="发现新事物")
        
        # 查询
        recent = store.query_recent(20)
        high_phi = store.query_by_phi(min_phi=0.5)
        by_emotion = store.query_by_emotion("FEAR")
        
        # 自动保存
        store.flush()  # 或 auto_flush=True 自动
    """
    
    def __init__(
        self,
        filepath: str = "memory/autobio.jsonl",
        auto_flush: bool = True,
        backend: Optional[AutobiographicalBackend] = None,
    ):
        self.filepath = Path(filepath)
        self.backend = backend or JsonlAutobiographicalBackend(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        self.moments: List[AutobiographicalMoment] = []
        self.chapters: List[Chapter] = []
        self.current_chapter: Optional[Chapter] = None
        
        self.auto_flush = auto_flush
        self.flush_interval = 10          # 每10条flush
        self._unflushed_count = 0
        self._moment_counter = 0
        
        # 加载已有数据
        self._load()
    
    # ── 记录 ──
    
    def record(self, 
               panksepp: Dict[str, float],
               valence: float,
               arousal: float,
               dominant: str = "",
               phi: float = 0.0,
               mood_valence: float = 0.0,
               mood_arousal: float = 0.0,
               mood_label: str = "neutral",
               allostatic_load: float = 0.0,
               narrative: str = "",
               event_trigger: str = "",
               cycle: int = 0,
               timestamp_override: Optional[float] = None,
               source: str = "",
               ) -> AutobiographicalMoment:
        """
        记录一个自传时刻
        
        Args:
            panksepp: 7系统激活矢量
            valence: 效价 (-1 to 1)
            arousal: 唤醒度 (0 to 1)
            dominant: 主导系统
            phi: Φ值
            narrative: 叙事摘要
            event_trigger: 触发事件
        
        Returns:
            AutobiographicalMoment
        """
        self._moment_counter += 1
        
        moment = AutobiographicalMoment(
            moment_id=f"{int(time.time())}-{self._moment_counter:06d}",
            timestamp=timestamp_override if timestamp_override is not None else time.time(),
            cycle=cycle,
            dominant=dominant,
            panksepp=dict(panksepp),
            valence=valence,
            arousal=arousal,
            phi=phi,
            mood_valence=mood_valence,
            mood_arousal=mood_arousal,
            mood_label=mood_label,
            allostatic_load=allostatic_load,
            narrative=narrative,
            significance=self._calc_significance(phi, valence, arousal),
            tags=self._generate_tags(panksepp, dominant),
            chapter=self.current_chapter.title if self.current_chapter else "",
            event_trigger=event_trigger,
            source=source,
        )
        
        self.moments.append(moment)
        
        # 章节管理
        self._update_chapters(moment)
        
        # 自动保存
        if self.auto_flush:
            self._unflushed_count += 1
            if self._unflushed_count >= self.flush_interval:
                self.flush()
        
        return moment
    
    # ── 查询 ──
    
    def query_recent(self, n: int = 20) -> List[AutobiographicalMoment]:
        """最近 N 个时刻"""
        return self.moments[-n:]
    
    def query_by_phi(self, min_phi: float = 0.4) -> List[AutobiographicalMoment]:
        """按 Φ 值查询 (关键时刻)"""
        return [m for m in self.moments if m.phi >= min_phi]
    
    def query_by_emotion(self, system: str, min_activation: float = 0.3) -> List[AutobiographicalMoment]:
        """按情感系统查询"""
        return [
            m for m in self.moments
            if m.panksepp.get(system, 0) >= min_activation
        ]
    
    def query_time_range(self, start: float, end: float = None) -> List[AutobiographicalMoment]:
        """按时间范围查询"""
        if end is None:
            end = time.time()
        return [
            m for m in self.moments
            if start <= m.timestamp <= end
        ]
    
    def query_by_valence(self, min_valence: float = 0.0, max_valence: float = 1.0) -> List[AutobiographicalMoment]:
        """按效价查询"""
        return [
            m for m in self.moments
            if min_valence <= m.valence <= max_valence
        ]

    def get_moments_for_date(self, date_string: str) -> List[AutobiographicalMoment]:
        """Return all moments whose local calendar date matches date_string."""
        return [
            moment for moment in self.moments
            if self._date_string(moment.timestamp) == date_string
        ]

    def replace_with_summary(self, date_string: str, summary) -> Optional[AutobiographicalMoment]:
        """Replace a day's active in-memory moments with a summary placeholder.

        This intentionally mutates only the in-memory active view. The append-only
        JSONL history on disk is left untouched.
        """
        day_moments = self.get_moments_for_date(date_string)
        if not day_moments:
            return None

        remaining = [
            moment for moment in self.moments
            if self._date_string(moment.timestamp) != date_string
        ]

        summary_timestamp = max(moment.timestamp for moment in day_moments)
        summary_phi = max((moment.phi for moment in day_moments), default=0.0)
        summary_dominant = next(
            (moment.dominant for moment in reversed(day_moments) if moment.dominant),
            "compressed",
        )
        summary_tags = ["compressed_summary", date_string]
        summary_tags.extend(tag for tag in getattr(summary, "key_events", [])[:3] if tag)

        summary_moment = AutobiographicalMoment(
            moment_id=f"compressed-{date_string}",
            timestamp=summary_timestamp,
            cycle=0,
            dominant=summary_dominant,
            panksepp={summary_dominant: 1.0} if summary_dominant else {},
            valence=0.0,
            arousal=0.0,
            phi=summary_phi,
            narrative=getattr(summary, "summary", ""),
            significance=max((moment.significance for moment in day_moments), default=0.0),
            tags=summary_tags[:5],
            chapter=day_moments[-1].chapter,
            event_trigger=f"compressed:{date_string}",
            source="compression",
        )

        remaining.append(summary_moment)
        remaining.sort(key=lambda moment: moment.timestamp)
        self.moments = remaining
        self._last_persisted_count = len(self.moments)
        return summary_moment

    def query_related(
        self,
        topic_text: str = "",
        user_id: str = "",
        history_texts: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[AutobiographicalMoment]:
        """按用户/话题相关性检索自传体记忆。"""
        if not self.moments or limit <= 0:
            return []

        history_texts = history_texts or []
        query_terms = self._extract_query_terms(topic_text, history_texts)
        scored: List[Tuple[float, AutobiographicalMoment]] = []

        for moment in self.moments:
            score = self._score_related_moment(moment, query_terms, topic_text, user_id)
            if score > 0:
                scored.append((score, moment))

        scored.sort(key=lambda item: (item[0], item[1].timestamp), reverse=True)
        return [moment for _, moment in scored[:limit]]
    
    def get_statistics(self) -> dict:
        """统计概览"""
        if not self.moments:
            return {"total_moments": 0}
        
        # 主导情感分布
        dom_dist = {}
        for m in self.moments:
            dom_dist[m.dominant] = dom_dist.get(m.dominant, 0) + 1
        
        # Φ 统计
        phi_values = [m.phi for m in self.moments]
        phi_avg = sum(phi_values) / len(phi_values)
        phi_max = max(phi_values)
        phi_peak_moment = max(self.moments, key=lambda m: m.phi)
        
        # 时间范围
        time_start = min(m.timestamp for m in self.moments)
        time_end = max(m.timestamp for m in self.moments)
        
        return {
            "total_moments": len(self.moments),
            "total_chapters": len(self.chapters),
            "dominant_distribution": dom_dist,
            "phi_average": round(phi_avg, 4),
            "phi_max": round(phi_max, 4),
            "phi_peak_moment": phi_peak_moment.narrative if phi_peak_moment.narrative else f"cycle {phi_peak_moment.cycle}",
            "time_start": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time_start)),
            "time_end": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time_end)),
            "duration_seconds": time_end - time_start,
        }
    
    def get_narrative(self, max_items: int = 15) -> str:
        """生成自传叙事文本"""
        if not self.moments:
            return "故事尚未开始..."
        
        lines = []
        lines.append(f"═══ 我的故事 ({len(self.moments)}个时刻, {len(self.chapters)}个章节) ═══")
        lines.append("")
        
        for ch in self.chapters:
            lines.append(f"📖 {ch.title}")
            lines.append(f"   {ch.summary}")
            lines.append("")
        
        lines.append("── 最近的关键时刻 ──")
        # 最近的高 Φ 时刻
        high_phi = sorted(self.query_by_phi(0.3), key=lambda m: m.timestamp, reverse=True)[:max_items]
        for m in high_phi:
            marker = "🔥" if m.phi > 0.5 else "✨" if m.phi > 0.3 else "·"
            ts = time.strftime("%m-%d %H:%M", time.localtime(m.timestamp))
            lines.append(f"  {marker} [{ts}] {m.narrative or m.dominant} (Φ:{m.phi:.2f} v:{m.valence:+.2f})")
        
        return "\n".join(lines)
    
    # ── 持久化 ──

    def flush(self):
        """将所有未写入的时刻 flush 到磁盘 (append-only JSONL)"""
        if not self.moments:
            return
        
        start_idx = self._last_persisted_count
        if start_idx >= len(self.moments):
            # Nothing new to flush
            self._unflushed_count = 0
            return

        try:
            self.backend.append_moments(moment.to_dict() for moment in self.moments[start_idx:])
            self._last_persisted_count = len(self.moments)
            self._unflushed_count = 0
        except IOError as e:
            logger.error(f"自传记忆写入失败: {e}")
            return

        # Save chapter metadata on every flush
        self.save_chapters()

        # Check archive threshold after flush
        self._check_archive_rotation()

    def _count_lines_on_disk(self) -> int:
        """Count the number of lines in the active JSONL file."""
        try:
            return self.backend.count_moments()
        except IOError:
            return 0

    def _check_archive_rotation(self):
        """
        Archive rotation: when JSONL exceeds 50000 lines, archive with 
        timestamp suffix and retain only the most recent 5000 moments.
        """
        line_count = self._count_lines_on_disk()
        if line_count <= 50000:
            return

        # Generate archive filename with timestamp
        timestamp_suffix = time.strftime("%Y%m%d_%H%M%S")
        try:
            self.backend.archive_active_log(timestamp_suffix)
            archive_name = self.filepath.stem + f"_{timestamp_suffix}" + self.filepath.suffix
            archive_path = self.filepath.parent / archive_name
            logger.info(f"Archived autobio JSONL to {archive_path} ({line_count} lines)")
        except OSError as e:
            logger.error(f"Failed to archive autobio JSONL: {e}")
            return

        # Retain most recent 5000 moments in new active file
        recent_moments = self.moments[-5000:] if len(self.moments) > 5000 else self.moments[:]
        
        try:
            self.backend.overwrite_active_moments(moment.to_dict() for moment in recent_moments)
        except IOError as e:
            logger.error(f"Failed to write new active file after archive: {e}")
            return

        # Update in-memory state: keep only recent moments
        self.moments = recent_moments
        self._last_persisted_count = len(self.moments)
        logger.info(f"Retained {len(self.moments)} most recent moments in active file")

    def save_chapters(self, chapters_path: str = None):
        """保存章节元数据到单独的 JSON 文件"""
        if chapters_path is not None:
            try:
                with open(chapters_path, "w", encoding="utf-8") as f:
                    json.dump(
                        [ch.to_dict() for ch in self.chapters],
                        f, ensure_ascii=False, indent=2
                    )
            except IOError as e:
                logger.error(f"Failed to save chapter metadata: {e}")
            return
        
        try:
            self.backend.save_chapter_payloads([ch.to_dict() for ch in self.chapters])
        except IOError as e:
            logger.error(f"Failed to save chapter metadata: {e}")
    
    def close(self):
        """关闭存储 (flush all + save chapters)"""
        self.flush()
        self.save_chapters()
    
    # ── 内部 ──
    
    def _load(self):
        """从 JSONL 加载已有记忆 — 跳过损坏行并记录警告"""
        if not self.filepath.exists() and isinstance(self.backend, JsonlAutobiographicalBackend):
            self._last_persisted_count = 0
            return
        
        try:
            if isinstance(self.backend, JsonlAutobiographicalBackend):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            d = json.loads(line)
                            moment = AutobiographicalMoment.from_dict(d)
                            self.moments.append(moment)
                            self._moment_counter = max(
                                self._moment_counter,
                                int(moment.moment_id.split("-")[-1])
                                if "-" in moment.moment_id else 0
                            )
                        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                            logger.warning(
                                f"Skipping malformed JSON at line {line_num} in "
                                f"{self.filepath}: {e}"
                            )
            else:
                for payload in self.backend.load_moment_payloads():
                    moment = AutobiographicalMoment.from_dict(payload)
                    self.moments.append(moment)
                    self._moment_counter = max(
                        self._moment_counter,
                        int(moment.moment_id.split("-")[-1])
                        if "-" in moment.moment_id else 0
                    )
            
            self._last_persisted_count = len(self.moments)
            
            # 加载章节
            try:
                chapters_data = self.backend.load_chapter_payloads()
                self.chapters = [Chapter.from_dict(ch) for ch in chapters_data]
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                logger.warning(f"Failed to load chapter metadata from {self.filepath}")
            
            # 恢复当前章节
            if self.chapters:
                self.current_chapter = self.chapters[-1]
        
        except IOError as e:
            logger.error(f"自传记忆加载失败: {e}")
            self._last_persisted_count = 0
    
    def _calc_significance(self, phi: float, valence: float, arousal: float) -> float:
        """计算时刻重要性"""
        # Φ 主导 (60%) + 极端效价 (20%) + 高唤醒 (20%)
        phi_score = phi
        valence_extreme = abs(valence)  # 越极端越重要
        arousal_score = arousal
        
        return min(1.0, phi_score * 0.6 + valence_extreme * 0.2 + arousal_score * 0.2)
    
    def _generate_tags(self, panksepp: Dict[str, float], dominant: str) -> List[str]:
        """生成情感标签"""
        tags = [dominant] if dominant else []
        
        # 高激活系统打标签
        thresholds = {
            "FEAR": 0.4, "RAGE": 0.4, "PANIC": 0.4,
            "SEEKING": 0.5, "PLAY": 0.5, "CARE": 0.5, "LUST": 0.5,
        }
        for sys_name, act in panksepp.items():
            if sys_name != dominant and act >= thresholds.get(sys_name, 0.4):
                tags.append(sys_name)
        
        return tags[:5]  # 最多5个标签

    def _score_related_moment(
        self,
        moment: AutobiographicalMoment,
        query_terms: List[str],
        topic_text: str,
        user_id: str,
    ) -> float:
        haystack_parts = [
            moment.narrative,
            moment.event_trigger,
            moment.chapter,
            moment.dominant,
            " ".join(moment.tags),
        ]
        haystack = " ".join(part for part in haystack_parts if part).lower()
        if not haystack:
            return 0.0

        score = 0.0
        lowered_topic = (topic_text or "").strip().lower()
        lowered_user = (user_id or "").strip().lower()

        if lowered_user and lowered_user in haystack:
            score += 4.0
        if lowered_topic and lowered_topic in haystack:
            score += 3.0

        overlap = sum(1.0 for term in query_terms if term and term in haystack)
        score += overlap

        if score <= 0:
            return 0.0

        return score + moment.phi * 0.5 + moment.significance * 0.25

    def _extract_query_terms(self, topic_text: str, history_texts: List[str]) -> List[str]:
        terms: List[str] = []
        seen = set()
        for text in [topic_text, *history_texts]:
            for term in self._tokenize_text(text):
                if term not in seen:
                    seen.add(term)
                    terms.append(term)
        return terms

    @staticmethod
    def _tokenize_text(text: str) -> List[str]:
        if not text:
            return []

        tokens: List[str] = []
        lowered = text.lower()
        for token in re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]+", lowered):
            if all("\u4e00" <= ch <= "\u9fff" for ch in token):
                if len(token) <= 2:
                    tokens.append(token)
                else:
                    tokens.extend(token[i:i + 2] for i in range(len(token) - 1))
            else:
                tokens.append(token)
        return tokens

    @staticmethod
    def _date_string(timestamp: float) -> str:
        return time.strftime("%Y-%m-%d", time.localtime(timestamp))
    
    def _update_chapters(self, moment: AutobiographicalMoment):
        """自动章节管理"""
        # 新章节: 每50个时刻 或 Φ尖峰 > 0.6
        should_new_chapter = False
        chapter_reason = ""
        
        if self.current_chapter is None:
            should_new_chapter = True
            chapter_reason = "开始"
        elif moment.phi > 0.6 and self.current_chapter.phi_peak < moment.phi:
            # Φ 尖峰 → 新章节
            should_new_chapter = True
            chapter_reason = f"Φ尖峰 {moment.phi:.2f}"
        elif (self.current_chapter.moment_count or 0) >= 50:
            should_new_chapter = True
            chapter_reason = f"时长 ({self.current_chapter.moment_count}+ 时刻)"
        
        if should_new_chapter:
            # 关闭旧章节
            if self.current_chapter:
                self.current_chapter.end_moment_id = moment.moment_id
                self.current_chapter.end_time = moment.timestamp
            
            # 创建新章节
            ch_title = f"第{len(self.chapters)+1}章"
            if chapter_reason != "开始":
                ch_title += f" — {chapter_reason}"
            
            ch = Chapter(
                title=ch_title,
                start_moment_id=moment.moment_id,
                start_time=moment.timestamp,
                phi_peak=moment.phi,
                dominant_theme=moment.dominant,
                summary=moment.narrative or f"{moment.dominant}主导的时期",
                moment_count=1,
            )
            self.chapters.append(ch)
            self.current_chapter = ch
        else:
            # 更新当前章节
            self.current_chapter.end_moment_id = moment.moment_id
            self.current_chapter.end_time = moment.timestamp
            self.current_chapter.phi_peak = max(
                self.current_chapter.phi_peak, moment.phi
            )
            self.current_chapter.moment_count = (
                self.current_chapter.moment_count or 0
            ) + 1
            # 更新主导主题 (出现最多的情感)
            if moment.dominant:
                # 简单多数 — 实际可以更精确
                if moment.phi > self.current_chapter.phi_peak * 0.8:
                    self.current_chapter.dominant_theme = moment.dominant
            self.current_chapter.summary = (
                f"{self.current_chapter.dominant_theme}主导的时期"
                f" ({self.current_chapter.moment_count}个时刻)"
            )


# ═══════════════════════════════════════════════
# 便捷工厂
# ═══════════════════════════════════════════════

def create_autobiographical_store(data_dir: str = "memory") -> AutobiographicalStore:
    """创建自传记忆存储"""
    filepath = os.path.join(data_dir, "autobio.jsonl")
    return AutobiographicalStore(filepath)

