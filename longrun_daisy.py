#!/usr/bin/env python3
"""
Helios DAISY 1小时长跑测试
===========================
纯情感引擎运行 (无LLM) — 验证全模块协同

运行:
  python3 longrun_daisy.py [--hours 1] [--interval 0.1] [--output logs/]

输出:
  · 终端: 每分钟摘要
  · JSONL: 情感历史 (每周期)
  · 报告: 最终统计报告
"""

import sys
import os
import json
import time
import math
from collections import Counter
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(__file__))

from daisy_emotion import (
    DaisySystemEngine, PANKSEPP_SYSTEMS,
    get_activation_vector
)
from allostasis import AllostaticRegulator, AllostasisConfig
from mood_tracker import MoodTracker
from personality import PersonalityProfile
from autobiographical import AutobiographicalStore, create_autobiographical_store
from helios_utils import clamp

# 可选模块
try:
    from neurochem import NeurochemState
    HAS_NEUROCHEM = True
except ImportError:
    HAS_NEUROCHEM = False

try:
    from phi import UnifiedPhi
    HAS_PHI = True
except ImportError:
    HAS_PHI = False


# ═══════════════════════════════════════════════
# 事件源
# ═══════════════════════════════════════════════

DEMO_EVENTS = [
    # (cycle_offset, {Panksepp trigger})
    (0,    {"FEAR": 0.6, "PANIC": 0.3}),
    (12,   {"CARE": 0.5, "PLAY": 0.2}),
    (25,   {"SEEKING": 0.7, "LUST": 0.3}),
    (40,   {"FEAR": 0.8, "RAGE": 0.4}),
    (55,   {"PLAY": 0.6, "SEEKING": 0.2}),
    (70,   {"PANIC": 0.7, "FEAR": 0.3}),
    (85,   {"CARE": 0.6, "SEEKING": 0.1}),
    (100,  {"RAGE": 0.6, "PANIC": 0.2}),
    (115,  {"PLAY": 0.7, "LUST": 0.4}),
    (130,  {"SEEKING": 0.8, "CARE": 0.3}),
    (150,  {"FEAR": 0.5, "SEEKING": 0.2}),
    (165,  {"PLAY": 0.5, "CARE": 0.5}),
    (180,  {"PANIC": 0.6, "RAGE": 0.3}),
    (200,  {"SEEKING": 0.6, "PLAY": 0.3}),
    (220,  {"CARE": 0.7, "LUST": 0.2}),
    (240,  {"RAGE": 0.7, "FEAR": 0.3}),
    (260,  {"PLAY": 0.8, "SEEKING": 0.4}),
    (280,  {"PANIC": 0.5, "FEAR": 0.5}),
]
EVENT_CYCLE_PERIOD = 300  # 每300周期循环一次事件


def get_event(cycle: int) -> dict:
    """获取当前周期的事件触发"""
    local_cycle = cycle % EVENT_CYCLE_PERIOD
    for offset, triggers in DEMO_EVENTS:
        if local_cycle == offset:
            return dict(triggers)
    return {}


# ═══════════════════════════════════════════════
# 长跑引擎
# ═══════════════════════════════════════════════

class LongrunEngine:
    """1小时长跑引擎 — 全部模块协同"""
    
    def __init__(self, output_dir: str = "logs"):
        # 核心
        self.daisy = DaisySystemEngine()
        self.allostasis = AllostaticRegulator(AllostasisConfig(
            load_accum_rate=0.008,    # 1h尺度: 慢积累
            load_decay_rate=0.995,
            load_fatigue_threshold=0.4,
            recovery_threshold=0.15,
        ))
        self.mood = MoodTracker()
        self.personality = PersonalityProfile()
        
        # 注入
        self.daisy.allostasis = self.allostasis
        self.daisy.mood_tracker = self.mood
        self.daisy.personality = self.personality
        
        # 可选
        self.neurochem = NeurochemState() if HAS_NEUROCHEM else None
        self.phi_engine = UnifiedPhi() if HAS_PHI else None
        
        # N1
        os.makedirs(output_dir, exist_ok=True)
        self.autobio = AutobiographicalStore(
            os.path.join(output_dir, "autobio.jsonl"),
            auto_flush=True
        )
        
        # 统计
        self.cycle = 0
        self.start_time = 0.0
        self.dominant_counts = Counter()
        self.phi_values: List[float] = []
        self.valence_values: List[float] = []
        self.mood_snapshots: List[dict] = []
        
        # 日志
        self.output_dir = output_dir
        self.history_file = os.path.join(output_dir, "history.jsonl")
        self._history_fp = None
    
    def start(self):
        self.start_time = time.time()
        print(f"☀️ Helios DAISY 长跑测试开始")
        print(f"   事件数: {len(DEMO_EVENTS)} · 周期: {EVENT_CYCLE_PERIOD}")
        print(f"   预计: ~{int(3600/0.1)} cycles in 1h (interval=0.1s)")
        print(f"   日志: {self.output_dir}/")
        print()
    
    def run(self, hours: float = 1.0, interval: float = 0.1):
        """主循环"""
        total_seconds = hours * 3600
        summary_interval = 600  # 每600周期 (~60s) 输出摘要
        flush_interval = 50     # 每50周期 flush
        
        self.start()
        
        with open(self.history_file, "a") as fp:
            self._history_fp = fp
            last_summary = 0
            
            while time.time() - self.start_time < total_seconds:
                self._step(interval)
                
                if self.cycle - last_summary >= summary_interval:
                    self._print_summary()
                    last_summary = self.cycle
                
                if self.cycle % flush_interval == 0:
                    self._flush()
        
        self._history_fp = None
        self._finish()
    
    def _step(self, interval: float):
        """单周期"""
        triggers = get_event(self.cycle)
        state = self.daisy.cycle(triggers if triggers else {})
        
        # Φ
        phi = 0.0
        if self.phi_engine and state.panksepp_activation:
            self.phi_engine.feed_emotional(state.panksepp_activation)
            phi = self.phi_engine.aggregate()
        
        # 神经化学
        if self.neurochem:
            self.neurochem.tick()
        
        # 统计
        self.dominant_counts[state.dominant_system] += 1
        self.phi_values.append(phi)
        self.valence_values.append(state.valence)
        
        # N4: 人格进化
        dominant = state.dominant_system
        intensity = max(state.panksepp_activation.values()) if state.panksepp_activation else 0
        self.personality.adapt_from_snapshot(dominant, intensity)
        
        # N1: 自传记忆 (Φ>0.3 或极端效价)
        if self.cycle % 5 == 0 and (phi > 0.3 or abs(state.valence) > 0.5):
            narrative = ""
            if phi > 0.5:
                narrative = f"⚡意识闪耀: {dominant}"
            elif abs(state.valence) > 0.5:
                narrative = f"强烈{'正' if state.valence > 0 else '负'}向: {dominant}"
            elif phi > 0.3:
                narrative = f"有意义的时刻: {dominant}"
            
            event_desc = "+".join(triggers.keys()) if triggers else "自发"
            
            self.autobio.record(
                panksepp=dict(state.panksepp_activation),
                valence=state.valence,
                arousal=state.arousal,
                dominant=dominant,
                phi=phi,
                mood_valence=self.mood.state.valence,
                mood_arousal=self.mood.state.arousal,
                mood_label=self.mood.state.label,
                allostatic_load=self.allostasis.get_load_level(),
                narrative=narrative,
                event_trigger=event_desc,
                cycle=self.cycle,
            )
        
        # 历史记录 (仅重要周期)
        if self.cycle % 10 == 0:
            ms = self.mood.get_snapshot()
            self._history_fp.write(json.dumps({
                "cycle": self.cycle,
                "timestamp": time.time(),
                "dominant": dominant,
                "valence": round(state.valence, 3),
                "arousal": round(state.arousal, 3),
                "phi": round(phi, 4),
                "mood": ms["label"],
                "allostatic_load": round(self.allostasis.get_load_level(), 3),
                "panksepp_top3": {
                    k: round(v, 3) for k, v in 
                    sorted(state.panksepp_activation.items(), key=lambda x: -x[1])[:3]
                },
            }, ensure_ascii=False) + "\n")
        
        self.cycle += 1
        time.sleep(interval)
    
    def _print_summary(self):
        elapsed = time.time() - self.start_time
        elapsed_min = elapsed / 60
        phi_avg = sum(self.phi_values[-600:]) / min(len(self.phi_values), 600) if self.phi_values else 0
        mood_snap = self.mood.get_snapshot()
        
        # 主导分布
        recent_counts = Counter()
        total = sum(self.dominant_counts.values())
        top3 = self.dominant_counts.most_common(3)
        
        print(f"  [{elapsed_min:5.1f}min c={self.cycle:>6d}] "
              f"Φ={phi_avg:.3f} 心境={mood_snap['label']:>14} "
              f"负荷={self.allostasis.get_load_level():.3f} "
              f"主导: {' '.join(f'{s}={c/total*100:.0f}%' for s,c in top3)}")
    
    def _flush(self):
        self.autobio.flush()
        if self._history_fp:
            try:
                self._history_fp.flush()
            except (ValueError, IOError):
                pass
    
    def _finish(self):
        self._flush()
        elapsed = time.time() - self.start_time
        
        # 生成报告
        report = self._generate_report(elapsed)
        report_path = os.path.join(self.output_dir, "report.json")
        with open(report_path, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 终端输出
        self._print_report(report, elapsed)
        
        print(f"\n📄 完整报告: {report_path}")
        print(f"📖 自传记忆: {self.autobio.filepath}")
        print(f"📊 历史数据: {self.history_file}")
    
    def _generate_report(self, elapsed: float) -> dict:
        """生成最终报告"""
        # 主导分布
        total_cycles = self.cycle
        dominant_dist = {}
        for sys_name in PANKSEPP_SYSTEMS:
            count = self.dominant_counts.get(sys_name, 0)
            dominant_dist[sys_name] = {
                "count": count,
                "pct": round(count / total_cycles * 100, 1) if total_cycles else 0,
            }
        
        # 7系统覆盖率
        systems_covered = sum(1 for s in PANKSEPP_SYSTEMS if self.dominant_counts.get(s, 0) > 0)
        full_spectrum = systems_covered == 7
        
        # Φ 统计
        phi_avg = sum(self.phi_values) / len(self.phi_values) if self.phi_values else 0
        phi_max = max(self.phi_values) if self.phi_values else 0
        phi_min = min(self.phi_values) if self.phi_values else 0
        
        # 效价统计
        val_avg = sum(self.valence_values) / len(self.valence_values) if self.valence_values else 0
        val_pos = sum(1 for v in self.valence_values if v > 0.1) / len(self.valence_values) * 100 if self.valence_values else 0
        val_neg = sum(1 for v in self.valence_values if v < -0.1) / len(self.valence_values) * 100 if self.valence_values else 0
        
        # 心境
        mood_snap = self.mood.get_snapshot()
        
        # 人格
        personality_traits = {
            "openness": round(self.personality.openness, 4),
            "extraversion": round(self.personality.extraversion, 4),
            "agreeableness": round(self.personality.agreeableness, 4),
            "neuroticism": round(self.personality.neuroticism, 4),
            "conscientiousness": round(self.personality.conscientiousness, 4),
        }
        personality_evolution = len(self.personality.get_evolution())
        
        # 自传记忆
        autobio_stats = self.autobio.get_statistics()
        
        # 全频谱验证
        spectrum_check = all(
            self.dominant_counts.get(s, 0) > 0
            for s in PANKSEPP_SYSTEMS
        )
        
        return {
            "test_info": {
                "duration_seconds": round(elapsed, 1),
                "duration_minutes": round(elapsed / 60, 1),
                "total_cycles": total_cycles,
                "cycle_interval_ms": 100,
                "events_used": len(DEMO_EVENTS),
                "event_period": EVENT_CYCLE_PERIOD,
                "llm_calls": 0,
                "timestamp": datetime.now().isoformat(),
            },
            "spectrum": {
                "full_spectrum": spectrum_check,
                "systems_covered": systems_covered,
                "dominant_distribution": dominant_dist,
            },
            "phi": {
                "average": round(phi_avg, 4),
                "max": round(phi_max, 4),
                "min": round(phi_min, 4),
            },
            "valence": {
                "average": round(val_avg, 4),
                "positive_pct": round(val_pos, 1),
                "negative_pct": round(val_neg, 1),
                "neutral_pct": round(100 - val_pos - val_neg, 1),
            },
            "mood": {
                "final_label": mood_snap["label"],
                "final_valence": round(mood_snap["valence"], 3),
                "final_arousal": round(mood_snap["arousal"], 3),
            },
            "allostasis": {
                "final_load": round(self.allostasis.get_load_level(), 3),
                "fatigued": self.allostasis.is_fatigued(),
                "recovering": self.allostasis.is_recovering(),
            },
            "personality": {
                "initial": {"openness": 1.0, "extraversion": 1.0, "agreeableness": 1.0, "neuroticism": 1.0, "conscientiousness": 1.0},
                "final": personality_traits,
                "drift": {
                    k: round(personality_traits[k] - 1.0, 5)
                    for k in personality_traits
                },
                "evolution_snapshots": personality_evolution,
            },
            "autobiographical": autobio_stats,
        }
    
    def _print_report(self, report: dict, elapsed: float):
        """终端输出报告"""
        info = report["test_info"]
        spectrum = report["spectrum"]
        phi_stats = report["phi"]
        val_stats = report["valence"]
        pers = report["personality"]
        
        print()
        print("═" * 60)
        print("  ☀️ Helios DAISY 1h 长跑测试 — 最终报告")
        print("═" * 60)
        print(f"  耗时: {info['duration_minutes']:.0f}min · {info['total_cycles']} cycles")
        print(f"  LLM调用: 0 (纯情感引擎)")
        print()
        
        print("  ── 全频谱 ──")
        systems_order = sorted(PANKSEPP_SYSTEMS, 
                              key=lambda s: -spectrum["dominant_distribution"][s]["count"])
        for sys_name in systems_order:
            d = spectrum["dominant_distribution"][sys_name]
            bar = "█" * int(d["pct"] / 2)
            print(f"    {sys_name:>10}: {d['count']:>6d} ({d['pct']:5.1f}%) {bar}")
        
        print(f"    全频谱={'✅' if spectrum['full_spectrum'] else '❌ ' + str(spectrum['systems_covered']) + '/7'}")
        print()
        
        print(f"  ── Φ ──")
        print(f"    平均: {phi_stats['average']:.4f}  最大: {phi_stats['max']:.4f}  最小: {phi_stats['min']:.4f}")
        print()
        
        print(f"  ── 效价 ──")
        print(f"    平均: {val_stats['average']:+.3f}  正向: {val_stats['positive_pct']:.0f}%  负向: {val_stats['negative_pct']:.0f}%")
        print()
        
        print(f"  ── 心境 ──")
        m = report["mood"]
        print(f"    终态: {m['final_label']} (v={m['final_valence']:+.3f})")
        print()
        
        print(f"  ── 异稳态 ──")
        a = report["allostasis"]
        print(f"    终态负荷: {a['final_load']:.3f}  疲劳: {a['fatigued']}  恢复中: {a['recovering']}")
        print()
        
        print(f"  ── 人格进化 ──")
        for trait, val in pers["final"].items():
            drift = pers["drift"][trait]
            direction = "↑" if drift > 0 else "↓" if drift < 0 else "→"
            print(f"    {trait:>18}: {1.0:.4f} → {val:.4f} ({drift:+.5f} {direction})")
        print(f"    进化快照: {pers['evolution_snapshots']} 条")
        print()
        
        print(f"  ── 自传记忆 ──")
        ab = report["autobiographical"]
        print(f"    记录时刻: {ab.get('total_moments', 0)}  章节: {ab.get('total_chapters', 0)}")
        print(f"    Φ峰值时刻: {ab.get('phi_peak_moment', 'N/A')}")


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Helios DAISY 长跑测试")
    parser.add_argument("--hours", type=float, default=1.0, help="测试时长 (小时)")
    parser.add_argument("--interval", type=float, default=0.1, help="周期间隔 (秒)")
    parser.add_argument("--output", type=str, default="logs/daisy_1h", help="输出目录")
    args = parser.parse_args()
    
    engine = LongrunEngine(output_dir=args.output)
    
    try:
        engine.run(hours=args.hours, interval=args.interval)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")
        engine._finish()


if __name__ == "__main__":
    main()
