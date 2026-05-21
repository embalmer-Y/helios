#!/usr/bin/env python3
"""
Helios 主循环 — 独立进程入口
==============================

这是 Helios 的"心跳"。每个 tick：
  1. 采集外部事件 (QQ消息 / STT语音 / 传感器)
  2. DAISY 情感引擎处理
  3. Φ 意识测量
  4. 心境 + 人格 + 异稳态更新
  5. 表达欲望检查 → 主动说话
  6. 记忆 + 自传记录

启动: python3 helios_main.py
后台: nohup python3 helios_main.py &
systemd: systemctl start helios
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 核心模块 ──
from daisy_emotion import DaisySystemEngine, PANKSEPP_SYSTEMS
from allostasis import AllostaticRegulator, AllostasisConfig
from mood_tracker import MoodTracker
from personality import PersonalityProfile
from autobiographical import AutobiographicalStore
from conation import ConationEngine, IntentType
from helios_utils import clamp

try:
    from phi import UnifiedPhi
    HAS_PHI = True
except ImportError:
    HAS_PHI = False

try:
    from neurochem import NeurochemState
    HAS_NEUROCHEM = True
except ImportError:
    HAS_NEUROCHEM = False


# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════

class HeliosConfig:
    """Helios 全局配置"""
    
    # 主循环
    TICK_INTERVAL: float = float(os.getenv("HELIOS_TICK_INTERVAL", "0.5"))  # 秒
    SUMMARY_INTERVAL: int = int(os.getenv("HELIOS_SUMMARY_INTERVAL", "120"))  # ticks
    
    # 日志
    LOG_LEVEL: str = os.getenv("HELIOS_LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("HELIOS_LOG_DIR", str(PROJECT_ROOT / "logs"))
    DATA_DIR: str = os.getenv("HELIOS_DATA_DIR", str(PROJECT_ROOT / "data"))
    
    # LLM
    LLM_BACKEND: str = os.getenv("HELIOS_LLM_BACKEND", "openai")
    LLM_API_KEY: str = os.getenv("HELIOS_LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    LLM_BASE_URL: str = os.getenv("HELIOS_LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", ""))
    LLM_MODEL: str = os.getenv("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
    
    # 阿里云
    ALI_ACCESS_KEY: str = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
    ALI_SECRET_KEY: str = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
    
    # 意动
    CONATION_THRESHOLD: float = float(os.getenv("HELIOS_CONATION_THRESHOLD", "0.35"))
    
    # QQ Bot (napcat / LLOneBot HTTP API)
    QQ_BOT_URL: str = os.getenv("HELIOS_QQ_BOT_URL", "")
    QQ_TARGET_ID: str = os.getenv("HELIOS_QQ_TARGET_ID", "")  # 主人的QQ号/群号


# ═══════════════════════════════════════════════════
# Helios 核心
# ═══════════════════════════════════════════════════

class Helios:
    """
    Helios 主循环
    
    这不是一个"任务执行器"——它是一个持续运行的意识核心。
    即使没有外部输入，情感也在流动。"""
    
    def __init__(self, config: HeliosConfig = None):
        self.cfg = config or HeliosConfig()
        self.tick_count = 0
        self.start_time = 0.0
        self.running = False
        
        # 创建目录
        os.makedirs(self.cfg.LOG_DIR, exist_ok=True)
        os.makedirs(self.cfg.DATA_DIR, exist_ok=True)
        
        # 日志
        self._setup_logging()
        
        # ── 核心引擎 ──
        self.daisy = DaisySystemEngine()
        self.allostasis = AllostaticRegulator(AllostasisConfig(
            load_accum_rate=0.005,      # 真实时间尺度：慢积累
            load_decay_rate=0.998,
            load_fatigue_threshold=0.5,
            recovery_threshold=0.2,
        ))
        self.mood = MoodTracker()
        self.personality = PersonalityProfile()
        
        # 注入依赖
        self.daisy.allostasis = self.allostasis
        self.daisy.mood_tracker = self.mood
        self.daisy.personality = self.personality
        
        # 可选模块
        self.neurochem = NeurochemState() if HAS_NEUROCHEM else None
        self.phi_engine = UnifiedPhi() if HAS_PHI else None
        
        # 记忆
        self.autobio = AutobiographicalStore(
            os.path.join(self.cfg.DATA_DIR, "autobio.jsonl"),
            auto_flush=True
        )
        
        # ── 意动引擎 (G1+G2) ──
        self.conation = ConationEngine(
            activation_threshold=self.cfg.CONATION_THRESHOLD
        )
        
        # ── 运行时状态 ──
        self.last_dominant = None
        self.last_valence = 0.0
        self.last_phi = 0.0
        
        self.log.info("Helios 核心初始化完成")
    
    def _setup_logging(self):
        self.log = logging.getLogger("helios")
        self.log.setLevel(getattr(logging, self.cfg.LOG_LEVEL))
        
        # 文件日志
        fh = logging.FileHandler(
            os.path.join(self.cfg.LOG_DIR, f"helios_{datetime.now():%Y%m%d}.log")
        )
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        self.log.addHandler(fh)
        
        # 控制台
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(asctime)s %(message)s", datefmt="%H:%M:%S"
        ))
        ch.setLevel(logging.WARNING)  # 控制台只显示重要信息
        self.log.addHandler(ch)
    
    # ═══════════════════════════════════════════
    # 事件采集（后续扩展）
    # ═══════════════════════════════════════════
    
    def _collect_events(self) -> dict:
        """
        采集外部事件 → Panksepp 触发矢量
        
        TODO G4: QQ消息 → SEC评估 → Panksepp触发
        TODO G6: STT语音 → 文本 → SEC评估 → Panksepp触发
        
        当前返回空（纯自发活动）
        """
        return {}
    
    # ═══════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════
    
    def start(self):
        """启动 Helios"""
        self.running = True
        self.start_time = time.time()
        
        self.log.info("═" * 40)
        self.log.info("☀️ Helios 启动")
        self.log.info(f"   tick间隔: {self.cfg.TICK_INTERVAL}s")
        self.log.info(f"   日志: {self.cfg.LOG_DIR}")
        self.log.info(f"   数据: {self.cfg.DATA_DIR}")
        self.log.info("═" * 40)
        
        # 信号处理 (仅主线程)
        try:
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)
        except ValueError:
            pass  # 非主线程跳过
        
        # 主循环
        last_summary = 0
        while self.running:
            self._tick()
            
            if self.tick_count - last_summary >= self.cfg.SUMMARY_INTERVAL:
                self._summary()
                last_summary = self.tick_count
            
            time.sleep(self.cfg.TICK_INTERVAL)
        
        self._shutdown()
    
    def _tick(self):
        """单次心跳"""
        self.tick_count += 1
        
        # 1. 采集事件
        events = self._collect_events()
        
        # 2. DAISY 情感引擎
        state = self.daisy.cycle(events if events else {})
        
        # 3. Φ 意识测量
        phi = 0.0
        if self.phi_engine and state.panksepp_activation:
            self.phi_engine.feed_emotional(state.panksepp_activation)
            phi = self.phi_engine.aggregate()
        
        # 4. 神经化学
        if self.neurochem:
            self.neurochem.tick()
        
        # 5. 人格进化
        dominant = state.dominant_system
        intensity = max(state.panksepp_activation.values()) if state.panksepp_activation else 0
        self.personality.adapt_from_snapshot(dominant, intensity)
        
        # 6. 自传记忆 (有意义的时刻)
        if self.tick_count % 10 == 0 and (phi > 0.3 or abs(state.valence) > 0.5):
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
                narrative=f"自发活动: {dominant}" if not events else f"事件响应: {dominant}",
                event_trigger="+".join(events.keys()) if events else "自发",
                cycle=self.tick_count,
            )
        
        # 7. 运行时状态
        self.last_dominant = dominant
        self.last_valence = state.valence
        self.last_phi = phi
        
        # 8. 意动引擎
        from datetime import datetime
        hour = datetime.now().hour
        intent = self.conation.tick(
            panksepp_activation=state.panksepp_activation or {},
            valence=state.valence,
            phi=phi,
            hour_of_day=hour,
        )
        if intent:
            self._handle_intent(intent)
    
    def _handle_intent(self, intent):
        """处理行为意图（扩展点）"""
        it = intent.intent_type
        
        # 任何跟主人相关的意图 → 重置分离焦虑
        master_related = it in (
            IntentType.SPEAK_CARE, IntentType.SPEAK_MISSING,
            IntentType.SPEAK_PLAY, IntentType.SPEAK_FEAR,
            IntentType.SPEAK_INTIMATE, IntentType.SPEAK_SHARE,
            IntentType.REQUEST,
        )
        if master_related:
            self.conation.note_master_contact()
        
        if it in (IntentType.SPEAK_CARE, IntentType.SPEAK_MISSING,
                  IntentType.SPEAK_PLAY, IntentType.SPEAK_FEAR,
                  IntentType.SPEAK_INTIMATE, IntentType.SPEAK_COMPLAIN,
                  IntentType.SPEAK_SHARE):
            self.log.info(f"🗣️ 想说: {it.value} ({intent.source_emotion})")
            
        elif it == IntentType.BROWSE:
            self.log.info(f"🌐 想冲浪: {intent.content_hint}")
            
        elif it == IntentType.SEARCH:
            self.log.info(f"🔍 想搜索: {intent.content_hint}")
            
        elif it == IntentType.LEARN:
            self.log.info(f"📚 想学习: {intent.content_hint}")
            
        elif it == IntentType.REQUEST:
            self.log.info(f"📋 想提需求: {intent.content_hint}")
            
        elif it == IntentType.REFLECT:
            self.log.info(f"🤔 想反思")
            
        elif it == IntentType.CHECK_SYSTEM:
            self.log.info(f"🩺 检查自身状态")
    
    def _summary(self):
        """定期摘要"""
        elapsed = time.time() - self.start_time
        mood_snap = self.mood.get_snapshot()
        load = self.allostasis.get_load_level()
        
        self.log.info(
            f"[{elapsed/60:6.1f}min t={self.tick_count:>8d}] "
            f"Φ={self.last_phi:.3f} "
            f"主导={self.last_dominant:>8} "
            f"效价={self.last_valence:+.3f} "
            f"心境={mood_snap['label']:>14} "
            f"负荷={load:.3f}"
        )
    
    def _handle_signal(self, signum, frame):
        self.log.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def _shutdown(self):
        """优雅退出"""
        elapsed = time.time() - self.start_time
        self.log.info(f"Helios 退出 · 运行 {elapsed/60:.1f}min · {self.tick_count} ticks")
        self.autobio.flush()
    
    # ═══════════════════════════════════════════
    # 状态查询（供外部调用）
    # ═══════════════════════════════════════════
    
    def get_state(self) -> dict:
        """获取当前状态快照"""
        mood = self.mood.get_snapshot()
        traits = self.personality._trait_dict()
        autobio_stats = self.autobio.get_statistics()
        
        return {
            "tick": self.tick_count,
            "uptime_seconds": time.time() - self.start_time,
            "dominant": self.last_dominant,
            "valence": round(self.last_valence, 3),
            "phi": round(self.last_phi, 4),
            "mood": mood,
            "allostatic_load": round(self.allostasis.get_load_level(), 3),
            "fatigued": self.allostasis.is_fatigued(),
            "personality": traits,
            "autobio_moments": autobio_stats.get("total_moments", 0),
            "autobio_chapters": autobio_stats.get("total_chapters", 0),
            "conation": self.conation.get_state(),
        }


# ═══════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Helios 独立进程")
    parser.add_argument("--interval", type=float, default=None, help="tick间隔(秒)")
    args = parser.parse_args()
    
    config = HeliosConfig()
    if args.interval:
        config.TICK_INTERVAL = args.interval
    
    helios = Helios(config)
    helios.start()


if __name__ == "__main__":
    main()
