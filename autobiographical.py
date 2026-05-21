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
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path


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
            "tags", "chapter", "event_trigger",
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
    
    def __init__(self, filepath: str = "memory/autobio.jsonl", auto_flush: bool = True):
        self.filepath = Path(filepath)
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
            timestamp=time.time(),
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
        """将所有未写入的时刻 flush 到磁盘"""
        if not self.moments:
            return
        
        try:
            with open(self.filepath, "a") as f:
                # 只写入未持久化的
                start_idx = self._last_persisted_count
                for moment in self.moments[start_idx:]:
                    line = json.dumps(moment.to_dict(), ensure_ascii=False)
                    f.write(line + "\n")
            
            self._last_persisted_count = len(self.moments)
            self._unflushed_count = 0
        except IOError as e:
            print(f"⚠️ 自传记忆写入失败: {e}")
    
    def save_chapters(self, chapters_path: str = None):
        """保存章节元数据"""
        if chapters_path is None:
            chapters_path = str(self.filepath).replace(".jsonl", "_chapters.json")
        
        with open(chapters_path, "w") as f:
            json.dump(
                [ch.to_dict() for ch in self.chapters],
                f, ensure_ascii=False, indent=2
            )
    
    def close(self):
        """关闭存储 (flush all)"""
        self.flush()
        self.save_chapters()
    
    # ── 内部 ──
    
    def _load(self):
        """从 JSONL 加载已有记忆"""
        if not self.filepath.exists():
            self._last_persisted_count = 0
            return
        
        try:
            with open(self.filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            d = json.loads(line)
                            moment = AutobiographicalMoment.from_dict(d)
                            self.moments.append(moment)
                            self._moment_counter = max(
                                self._moment_counter,
                                int(moment.moment_id.split("-")[-1])
                                if "-" in moment.moment_id else 0
                            )
                        except (json.JSONDecodeError, KeyError):
                            pass  # 跳过损坏行
            
            self._last_persisted_count = len(self.moments)
            
            # 加载章节
            chapters_path = str(self.filepath).replace(".jsonl", "_chapters.json")
            if os.path.exists(chapters_path):
                try:
                    with open(chapters_path, "r") as f:
                        chapters_data = json.load(f)
                        self.chapters = [Chapter.from_dict(ch) for ch in chapters_data]
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # 恢复当前章节
            if self.chapters:
                self.current_chapter = self.chapters[-1]
        
        except IOError as e:
            print(f"⚠️ 自传记忆加载失败: {e}")
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
