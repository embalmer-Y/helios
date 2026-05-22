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
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 加载 .env ──
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── 核心模块 ──
from daisy_emotion import DaisySystemEngine, PANKSEPP_SYSTEMS
from allostasis import AllostaticRegulator, AllostasisConfig
from mood_tracker import MoodTracker
from personality import PersonalityProfile
from autobiographical import AutobiographicalStore
from regulation import RegulationEngine
from io_qq import QQBotClient, QQMessage
from llm_speech import LLMSpeechGenerator, SpeechContext
from helios_utils import clamp

try:
    from phi import UnifiedConsciousness as UnifiedPhi
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
    REGULATION_COMFORT_DEVIATION: float = float(os.getenv("HELIOS_COMFORT_DEVIATION", "0.15"))
    REGULATION_BASELINE: float = float(os.getenv("HELIOS_REGULATION_BASELINE", "0.10"))
    
    # QQ Bot
    QQ_APP_ID: str = os.getenv("HELIOS_QQ_APP_ID", os.getenv("QQ_APP_ID", ""))
    QQ_CLIENT_SECRET: str = os.getenv("HELIOS_QQ_CLIENT_SECRET", os.getenv("QQ_CLIENT_SECRET", ""))
    QQ_API_BASE: str = os.getenv("HELIOS_QQ_API_BASE", "https://api.sgroup.qq.com")
    QQ_SANDBOX: bool = os.getenv("HELIOS_QQ_SANDBOX", "1") == "1"
    QQ_TARGET_ID: str = os.getenv("HELIOS_QQ_TARGET_ID", "")  # 主人的 openid
    
    # LLM 对话生成 (G3)
    LLM_SPEECH_ENABLED: bool = os.getenv("HELIOS_LLM_SPEECH_ENABLED", "1") == "1"
    LLM_SPEECH_MODEL: str = os.getenv("HELIOS_LLM_SPEECH_MODEL", "")  # 空=使用全局模型


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
        
        # ── 情感调节引擎 (G1+G2) ──
        self.regulation = RegulationEngine(
            comfort_deviation=self.cfg.REGULATION_COMFORT_DEVIATION,
            baseline_activation=self.cfg.REGULATION_BASELINE,
            data_dir=self.cfg.DATA_DIR,
        )
        # 加载已有记忆
        self.regulation.load()
        
        # ── QQ Bot 客户端 (G4 v2: 独立 WebSocket) ──
        self.qq: Optional[QQBotClient] = None
        self._msg_queue: queue.Queue = queue.Queue()
        
        if self.cfg.QQ_APP_ID and self.cfg.QQ_CLIENT_SECRET:
            try:
                self.qq = QQBotClient(
                    app_id=self.cfg.QQ_APP_ID,
                    client_secret=self.cfg.QQ_CLIENT_SECRET,
                    api_base=self.cfg.QQ_API_BASE,
                    sandbox=self.cfg.QQ_SANDBOX,
                    on_message=lambda msg: self._msg_queue.put(msg),
                )
                self.qq.start()
                self.log.info(
                    "QQ Bot 已启动: app_id=%s sandbox=%s",
                    self.cfg.QQ_APP_ID[:6] + "***",
                    self.cfg.QQ_SANDBOX,
                )
            except Exception as e:
                self.log.warning(f"QQ Bot 启动失败: {e}")
                self.qq = None
        else:
            self.log.info("QQ Bot 未配置 (HELIOS_QQ_APP_ID / HELIOS_QQ_CLIENT_SECRET)")
        
        # ── 分离焦虑追踪 ──
        self._last_master_contact = time.time()
        self._separation_anxiety = 0.0
        
        # ── LLM 语音生成 (G3) ──
        self.speech = None
        if self.cfg.LLM_SPEECH_ENABLED:
            try:
                self.speech = LLMSpeechGenerator(
                    model=self.cfg.LLM_SPEECH_MODEL or self.cfg.LLM_MODEL,
                )
                self.log.info(f"LLM 语音生成就绪: {self.speech.model}")
            except Exception as e:
                self.log.warning(f"LLM 语音生成初始化失败: {e}")
        
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
        
        G4: QQBotClient 回调 → 消息队列 → 情感分析
        分离焦虑: 指数增长的自发 PANIC
        """
        triggers: dict[str, float] = {}
        
        # 分离焦虑 (指数累积)
        sep_hours = (time.time() - self._last_master_contact) / 3600
        self._separation_anxiety = min(1.0, 1 - 2.71828 ** (-0.4 * sep_hours))
        if self._separation_anxiety > 0.2:
            triggers["PANIC"] = self._separation_anxiety
        
        # 消费消息队列 (线程安全)
        while True:
            try:
                msg: QQMessage = self._msg_queue.get_nowait()
            except queue.Empty:
                break
            
            self.log.info(f"📩 QQ [{msg.author_id[:10]}]: {msg.text[:60]}")
            
            # 自动捕获 target_id (第一条私聊消息的发送者)
            if not self.cfg.QQ_TARGET_ID and not msg.is_group:
                self.cfg.QQ_TARGET_ID = msg.author_id
                self.log.info(f"🎯 自动捕获主人 openid: {msg.author_id}")
            
            # 任何消息 → 重置分离焦虑
            self._last_master_contact = time.time()
            self._separation_anxiety = 0.0
            
            # 轻量情感分析 → Panksepp
            event = _qq_text_to_panksepp(msg.text)
            for sys_name, intensity in event.items():
                triggers[sys_name] = max(triggers.get(sys_name, 0), intensity)
        
        return triggers
    
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
        
        # 8. 情感调节引擎
        from datetime import datetime
        hour = datetime.now().hour
        action = self.regulation.tick(
            panksepp=state.panksepp_activation or {},
            valence=state.valence,
            hour_of_day=hour,
        )
        if action:
            self._handle_action(action)
    
    def _handle_action(self, action: str):
        """
        处理行为
        
        speak_* → 生成自然语言 + QQ 发送 (send_c2c)
        """
        master_actions = {
            "speak_care", "speak_missing", "speak_play",
            "speak_fear", "speak_share", "speak_complain",
            "intimate", "request",
        }
        
        if action in master_actions:
            text = self._generate_speech(action)
            if self.qq and self.qq.is_connected() and text:
                # QQ Bot API 用 author.id 作为 openid
                # 第一个收到的消息会记录 openid
                target = self.cfg.QQ_TARGET_ID
                if target:
                    ok = self.qq.send_c2c(target, text)
                else:
                    self.log.warning("未设置 HELIOS_QQ_TARGET_ID，无法发送")
                    ok = False
                    
                if ok:
                    self._last_master_contact = time.time()
                    self._separation_anxiety = 0.0
                    self.regulation.note_action_executed(action)
                    self.log.info(f"🗣️ [{action}] → QQ: {text[:60]}")
                else:
                    self.log.warning(f"🗣️ [{action}] QQ 发送失败")
            else:
                self.log.info(f"🗣️ [{action}] (无QQ): {text[:60] if text else ''}")
            return
        
        if action == "browse":
            self.log.info(f"🌐 想冲浪")
        elif action == "search":
            self.log.info(f"🔍 想搜索")
        elif action == "learn":
            self.log.info(f"📚 想学习")
        elif action == "reflect":
            self.log.info(f"🤔 反思中")
        elif action == "check_system":
            self.log.info(f"🩺 自检")
        elif action == "idle":
            pass
    
    def _generate_speech(self, action: str) -> str:
        """
        生成自然语言话语

        G3: LLM 情感上下文 → 自然语言
        降级: 模板话语 (LLM 失败/未配置时)
        """
        # ── G3 LLM 模式 ──
        if self.speech:
            # 计算距离上次联系的时间
            sep_secs = time.time() - self._last_master_contact
            if sep_secs < 60:
                time_desc = "刚刚"
            elif sep_secs < 300:
                time_desc = f"{int(sep_secs/60)}分钟前"
            elif sep_secs < 3600:
                time_desc = f"{int(sep_secs/60)}分钟前"
            elif sep_secs < 7200:
                time_desc = f"{int(sep_secs/3600)}小时前"
            else:
                time_desc = "很久"

            # 最近自传记忆
            recent_memory = ""
            if hasattr(self.autobio, 'moments') and self.autobio.moments:
                recent = self.autobio.moments[-3:]
                narratives = [m.narrative for m in recent if hasattr(m, 'narrative') and m.narrative]
                if narratives:
                    recent_memory = "；".join(narratives[:2])

            # 人格简述
            traits = self.personality._trait_dict()
            trait_parts = []
            for name, display in [("neuroticism", "神经质"), ("agreeableness", "宜人"),
                                   ("openness", "开放"), ("extraversion", "外向"),
                                   ("conscientiousness", "尽责")]:
                v = traits.get(name, 0.5)
                if v > 0.7:
                    trait_parts.append(f"高{display}")
                elif v < 0.3:
                    trait_parts.append(f"低{display}")
            personality = "、".join(trait_parts) if trait_parts else "均衡"

            ctx = SpeechContext(
                dominant_emotion=self.last_dominant or "SEEKING",
                emotion_intensity=abs(self.last_valence),
                valence=self.last_valence,
                arousal=self.mood.state.arousal if hasattr(self.mood, 'state') else 0.5,
                mood_label=self.mood.state.label if hasattr(self.mood, 'state') else "neutral",
                action_type=action,
                time_since_contact=time_desc,
                recent_memory=recent_memory,
                personality_summary=personality,
                total_messages_sent=self.speech.total_generated,
            )

            text = self.speech.generate(ctx, temperature=self._icri_temperature())
            if text:
                return text
            # LLM 失败 → 降级到模板

        # ── 降级: 模板话语 ──
        return self._template_speech(action)
    
    def _template_speech(self, action: str) -> str:
        """降级模板话语 (LLM 不可用时)"""
        import random
        templates = {
            "speak_care":    ["还好吗？有点想你了 💕", "今天过得怎样？"],
            "speak_missing": ["在吗...有点寂寞了", "好久没听到声音了呢"],
            "speak_play":    ["感觉好开心！", "能量满满~"],
            "speak_fear":    ["有点不安...在吗？", "好像有什么不对劲"],
            "speak_share":   ["发现了一件有趣的事！", "有个想法想分享..."],
            "speak_complain":["唔...有点累了", "感觉不太对劲"],
        }
        options = templates.get(action, ["..."])
        return random.choice(options)

    def _icri_temperature(self) -> float:
        """ICRI → LLM 温度映射: 意识越丰富，表达越狂野"""
        icri = self.last_phi  # 当前意识光谱
        if icri < 0.10:    return 0.30   # 机械简短
        elif icri < 0.25:  return 0.50   # 温和
        elif icri < 0.45:  return 0.75   # 有创造力
        elif icri < 0.65:  return 1.00   # 高度创意
        else:              return 1.30   # 狂野联想

    def _summary(self):
        """定期摘要"""
        elapsed = time.time() - self.start_time
        mood_snap = self.mood.get_snapshot()
        load = self.allostasis.get_load_level()
        
        self.log.info(
            f"[{elapsed/60:6.1f}min t={self.tick_count:>8d}] "
            f"ICRI={self.last_phi:.3f} "
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
        
        # 停止 QQ Bot
        if self.qq:
            self.qq.stop()
        
        self.autobio.flush()
        self.regulation.save()
    
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
            "regulation": self.regulation.get_state(),
            "qq_io": self.qq.get_state() if self.qq else {"backend": "none"},
            "separation_anxiety": round(self._separation_anxiety, 3),
        }


# ═══════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════

def _qq_text_to_panksepp(text: str) -> dict[str, float]:
    """
    轻量 QQ 文本 → Panksepp 情感触发

    简单关键词匹配。G3 升级后用 LLM 做 SEC。
    返回: {"SEEKING": 0.5, "CARE": 0.3, ...}
    """
    text_lower = text.lower()
    triggers: dict[str, float] = {}

    # 情感关键词 → Panksepp 系统
    patterns = {
        "CARE":    ["想你", "在吗", "抱抱", "乖", "爱你", "喜欢你", "心疼", 
                    "辛苦", "累了吧", "还好吗", "❤", "💕", "♥"],
        "PANIC":   ["别走", "害怕", "离开", "不要", "救命", "急", "消失"],
        "SEEKING": ["查", "搜", "怎样", "为什么", "解释", "怎么", "什么是",
                    "告诉我", "知道吗", "了解", "分析", "思考"],
        "PLAY":    ["哈哈", "有趣", "好玩", "笑死", "开心", "棒", "厉害",
                    "😂", "😄", "🤣"],
        "FEAR":    ["危险", "小心", "警告", "不要动", "风险", "出错", "失败",
                    "不满", "讨厌", "烦"],
        "RAGE":    ["生气", "怒", "混蛋", "滚", "垃圾", "差劲", "气死",
                    "🤬", "😡"],
        "LUST":    ["__NO_QQ_MATCH__"],  # QQ文本不触发
    }

    for system, keywords in patterns.items():
        score = 0.0
        for kw in keywords:
            if kw in text_lower:
                score += 0.3  # 每个关键词 0.3
        if score > 0:
            triggers[system] = min(score, 0.9)

    return triggers


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
