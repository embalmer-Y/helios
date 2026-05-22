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

# ── 核心模块 (domain packages) ──
from cognition.daisy_emotion import DaisySystemEngine, PANKSEPP_SYSTEMS
from regulation.allostasis import AllostaticRegulator, AllostasisConfig
from mood_tracker import MoodTracker
from personality import PersonalityProfile
from memory.autobiographical import AutobiographicalStore
from memory.memory_system import MemorySystem
from regulation.regulation import RegulationEngine
from io_qq import QQBotClient, QQMessage
from llm_speech import LLMSpeechGenerator, SpeechContext
from helios_utils import clamp
from utils.persistence import StatePersistence
from regulation.drives import DriveOracle, HeliosSnapshot
from cognition.habituation import HabituationTracker
from cognition.thinking_integration import ThinkingEngineIntegration

try:
    from cognition.phi import UnifiedPhi
    HAS_PHI = True
except ImportError:
    HAS_PHI = False

try:
    from neurochem import NeurochemState
    HAS_NEUROCHEM = True
except ImportError:
    HAS_NEUROCHEM = False

# ── EventSource 插件抽象 ──
from core.event_source import EventSource
from core.separation_source import SeparationAnxietySource
from core.qq_event_source import QQEventSource
from core.drive_source import InternalDriveSource
from core.helios_state import HeliosState

# ── Passive Reply Pipeline ──
import importlib.util as _ilu

_sec_eval_path = str(PROJECT_ROOT / "io" / "llm_sec_evaluator.py")
_sec_eval_spec = _ilu.spec_from_file_location("helios_io_llm_sec_evaluator", _sec_eval_path)
_sec_eval_mod = _ilu.module_from_spec(_sec_eval_spec)
sys.modules["helios_io_llm_sec_evaluator"] = _sec_eval_mod
_sec_eval_spec.loader.exec_module(_sec_eval_mod)
LLMSECEvaluator = _sec_eval_mod.LLMSECEvaluator

_rp_path = str(PROJECT_ROOT / "io" / "response_pipeline.py")
_rp_spec = _ilu.spec_from_file_location("helios_io_response_pipeline", _rp_path)
_rp_mod = _ilu.module_from_spec(_rp_spec)
sys.modules["helios_io_response_pipeline"] = _rp_mod
_rp_spec.loader.exec_module(_rp_mod)
ResponsePipeline = _rp_mod.ResponsePipeline

# ── ICRI Temperature Mapper ──
_icri_temp_path = str(PROJECT_ROOT / "io" / "icri_temperature.py")
_icri_temp_spec = _ilu.spec_from_file_location("helios_io_icri_temperature", _icri_temp_path)
_icri_temp_mod = _ilu.module_from_spec(_icri_temp_spec)
sys.modules["helios_io_icri_temperature"] = _icri_temp_mod
_icri_temp_spec.loader.exec_module(_icri_temp_mod)
ICRITemperatureMapper = _icri_temp_mod.ICRITemperatureMapper

# ── Behavior Execution (Limb) ──
_limb_path = str(PROJECT_ROOT / "io" / "limb.py")
_limb_spec = _ilu.spec_from_file_location("helios_io_limb", _limb_path)
_limb_mod = _ilu.module_from_spec(_limb_spec)
sys.modules["helios_io_limb"] = _limb_mod
_limb_spec.loader.exec_module(_limb_mod)
BehaviorExecutor = _limb_mod.BehaviorExecutor

_bridge_path = str(PROJECT_ROOT / "io" / "limb_decision_bridge.py")
_bridge_spec = _ilu.spec_from_file_location("helios_io_limb_decision_bridge", _bridge_path)
_bridge_mod = _ilu.module_from_spec(_bridge_spec)
sys.modules["helios_io_limb_decision_bridge"] = _bridge_mod
_bridge_spec.loader.exec_module(_bridge_mod)
LimbDecisionBridge = _bridge_mod.LimbDecisionBridge

# ── TTS Module (G5) ──
_tts_path = str(PROJECT_ROOT / "io" / "io_tts.py")
_tts_spec = _ilu.spec_from_file_location("helios_io_tts", _tts_path)
_tts_mod = _ilu.module_from_spec(_tts_spec)
sys.modules["helios_io_tts"] = _tts_mod
_tts_spec.loader.exec_module(_tts_mod)
TTSModule = _tts_mod.TTSModule


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

    # TTS 语音合成 (G5)
    TTS_ENABLED: bool = os.getenv("HELIOS_TTS_ENABLED", "1") == "1"
    TTS_VOICE: str = os.getenv("HELIOS_TTS_VOICE", "xiaoyun")
    ALI_NLS_APP_KEY: str = os.getenv("ALIBABA_NLS_APP_KEY", "")


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
        
        # ── 持久化 ──
        self.persistence = StatePersistence(self.cfg.DATA_DIR)
        self._load_persisted_state()
        
        # 注入依赖
        self.daisy.allostasis = self.allostasis
        self.daisy.mood_tracker = self.mood
        self.daisy.personality = self.personality
        
        # 可选模块
        self.neurochem = NeurochemState() if HAS_NEUROCHEM else None
        self.phi_engine = UnifiedPhi() if HAS_PHI else None
        
        # ── 习惯化追踪器 ──
        self.habituation = HabituationTracker()
        
        # 记忆
        self.autobio = AutobiographicalStore(
            os.path.join(self.cfg.DATA_DIR, "autobio.jsonl"),
            auto_flush=True
        )
        self.memory_system = MemorySystem(
            working_capacity=15,
            episodic_capacity=500,
        )
        
        # ── 情感调节引擎 (G1+G2) ──
        self.regulation = RegulationEngine(
            comfort_deviation=self.cfg.REGULATION_COMFORT_DEVIATION,
            baseline_activation=self.cfg.REGULATION_BASELINE,
            data_dir=self.cfg.DATA_DIR,
        )
        # 加载已有记忆
        self.regulation.load()
        
        # ── 驱动神谕 (Free Energy Drives) ──
        self.drive_oracle = DriveOracle()
        
        # ── 内部思维流 (Requirement 28) ──
        # ThinkingEngineIntegration manages spontaneous thought generation
        # during rest periods. Uses a stub thinking engine if ThinkingManager
        # is not available.
        self._init_thinking_integration()
        
        # ── 行为执行框架 (Requirement 29) ──
        self.behavior_executor = BehaviorExecutor()
        self.limb_bridge = LimbDecisionBridge(self.behavior_executor)
        # Result callback: feed behavior completion results back to RegulationEngine memory
        self.behavior_executor.set_result_callback(self._on_behavior_complete)
        
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
        
        # ── EventSource 注册表 ──
        # Register all pluggable event sources. Each is polled once per tick.
        self._event_sources: list[EventSource] = []
        
        # SeparationAnxietySource — computes PANIC from elapsed separation time
        self._separation_source = SeparationAnxietySource()
        self._event_sources.append(self._separation_source)
        
        # QQEventSource — drains QQ message queue and evaluates via SEC
        self._qq_event_source = QQEventSource(
            msg_queue=self._msg_queue,
            sec_evaluator=_KeywordSECEvaluator(),
        )
        self._event_sources.append(self._qq_event_source)
        
        # InternalDriveSource — maps dominant drive urgency to Panksepp triggers
        self._drive_source = InternalDriveSource()
        self._event_sources.append(self._drive_source)
        
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
        
        # ── TTS 语音合成 (G5) ──
        self.tts = TTSModule(
            access_key=self.cfg.ALI_ACCESS_KEY,
            access_secret=self.cfg.ALI_SECRET_KEY,
            app_key=self.cfg.ALI_NLS_APP_KEY,
            voice=self.cfg.TTS_VOICE,
            enabled=self.cfg.TTS_ENABLED,
        )
        if self.tts._available:
            self.tts.register()
        
        # ── Passive Reply Pipeline (SEC + ResponsePipeline) ──
        self.sec_evaluator = LLMSECEvaluator(
            model=self.cfg.LLM_MODEL,
            api_key=self.cfg.LLM_API_KEY,
            base_url=self.cfg.LLM_BASE_URL,
        )
        self.response_pipeline = ResponsePipeline(
            llm_speech=self.speech,
            memory_system=self.memory_system,
            autobio_store=self.autobio,
            model=self.cfg.LLM_MODEL,
            api_key=self.cfg.LLM_API_KEY,
            base_url=self.cfg.LLM_BASE_URL,
        )
        
        # ── 运行时状态 ──
        self.last_dominant = None
        self.last_valence = 0.0
        self.last_phi = 0.0
        
        # ── 记忆巩固调度 (Requirement 20) ──
        self._low_phi_counter: int = 0          # consecutive ticks with phi < 0.3
        self._ticks_since_consolidation: int = 0  # ticks elapsed since last consolidation
        
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
    # 持久化 (personality + allostasis)
    # ═══════════════════════════════════════════
    
    def _load_persisted_state(self):
        """
        Load personality and allostasis from disk on startup.
        
        If files are missing or corrupted, StatePersistence returns None
        and we keep the freshly-initialized defaults.
        """
        # -- Personality --
        personality_data = self.persistence.load_personality()
        if personality_data is not None:
            traits = personality_data.get("traits", {})
            self.personality.openness = traits.get("openness", self.personality.openness)
            self.personality.extraversion = traits.get("extraversion", self.personality.extraversion)
            self.personality.agreeableness = traits.get("agreeableness", self.personality.agreeableness)
            self.personality.neuroticism = traits.get("neuroticism", self.personality.neuroticism)
            self.personality.conscientiousness = traits.get("conscientiousness", self.personality.conscientiousness)
            self.personality.total_emotion_cycles = personality_data.get("total_emotion_cycles", 0)
            self.personality._recompute()
            self.log.info("Loaded personality state from disk")
        else:
            self.log.info("No personality state found; using defaults")
        
        # -- Allostasis --
        allostasis_data = self.persistence.load_allostasis()
        if allostasis_data is not None:
            # Restore setpoints
            setpoints = allostasis_data.get("setpoints", {})
            for sys_name, sp_val in setpoints.items():
                if sys_name in self.allostasis.states:
                    self.allostasis.states[sys_name].setpoint = sp_val
            # Restore counters
            self.allostasis.fatigue_cycles = allostasis_data.get("fatigue_cycles", 0)
            self.allostasis.recovery_cycles = allostasis_data.get("recovery_cycles", 0)
            self.allostasis.total_cycles = allostasis_data.get("total_cycles", 0)
            self.log.info("Loaded allostasis state from disk")
        else:
            self.log.info("No allostasis state found; using defaults")
    
    def _persist_state(self):
        """Save personality and allostasis state to disk."""
        try:
            self.persistence.save_personality(self.personality)
        except Exception as e:
            self.log.warning(f"Failed to save personality: {e}")
        try:
            self.persistence.save_allostasis(self.allostasis)
        except Exception as e:
            self.log.warning(f"Failed to save allostasis: {e}")
        self.log.debug("Periodic state persistence complete (tick %d)", self.tick_count)
    
    # ═══════════════════════════════════════════
    # 内部思维流初始化 (Requirement 28)
    # ═══════════════════════════════════════════
    
    def _init_thinking_integration(self):
        """
        Initialize ThinkingEngineIntegration with a thinking engine and autobio store.
        
        Uses ThinkingManager if available, otherwise creates a minimal stub that
        satisfies the ThinkingEngineIntegration interface.
        """
        thinking_engine = None
        try:
            from cognition.thinking import ThinkingManager
            thinking_engine = ThinkingManager()
        except (ImportError, Exception) as e:
            self.log.debug(f"ThinkingManager not available, using stub: {e}")
            thinking_engine = _StubThinkingEngine()
        
        self.thinking_integration = ThinkingEngineIntegration(
            thinking_engine=thinking_engine,
            autobio_store=self.autobio,
        )
        self.log.info("ThinkingEngineIntegration 初始化完成")
    
    # ═══════════════════════════════════════════
    # 行为执行反馈 (Requirement 29.5)
    # ═══════════════════════════════════════════
    
    def _on_behavior_complete(self, behavior_cmd):
        """
        Callback invoked when BehaviorExecutor completes a behavior.
        
        Feeds the execution result back to RegulationEngine memory so that
        the regulation system can learn from action outcomes.
        
        Args:
            behavior_cmd: The completed BehaviorCommand with result populated.
        """
        action = behavior_cmd.action
        result = behavior_cmd.result or {}
        self.log.debug(
            f"Behavior completed: '{behavior_cmd.name}' action='{action}' result={result}"
        )
        # Notify regulation engine that the action was executed
        self.regulation.note_action_executed(action)
    
    # ═══════════════════════════════════════════
    # 事件采集（EventSource 注册表模式）
    # ═══════════════════════════════════════════
    
    def _collect_events(self) -> tuple[dict[str, float], list[dict]]:
        """
        采集外部事件 → Panksepp 触发矢量 + 待回复消息
        
        Iterates over all registered EventSources, collects trigger vectors
        and messages, then merges triggers using max-value semantics for
        overlapping Panksepp system keys.
        
        Returns:
            Tuple of (merged_triggers, pending_messages).
        """
        # Build HeliosState snapshot for event sources to read
        sep_hours = (time.time() - self._last_master_contact) / 3600
        state = HeliosState(
            tick=self.tick_count,
            timestamp=time.time(),
            separation_hours=sep_hours,
            drive_dominant=getattr(self, '_last_drive_dominant', ''),
            drive_urgency=getattr(self, '_last_drive_urgency', 0.0),
        )
        return self._poll_event_sources(state)
    
    def _collect_events_with_state(self, state: HeliosState) -> tuple[dict[str, float], list[dict]]:
        """
        采集外部事件 using the tick's HeliosState for forward propagation.
        
        Same as _collect_events but uses the provided state object so that
        EventSources see the current tick's state values.
        
        Args:
            state: The current tick's HeliosState (forward-propagated).
            
        Returns:
            Tuple of (merged_triggers, pending_messages).
        """
        # Populate state with drive info from previous tick for sources that need it
        state.drive_dominant = getattr(self, '_last_drive_dominant', '')
        state.drive_urgency = getattr(self, '_last_drive_urgency', 0.0)
        return self._poll_event_sources(state)
    
    def _poll_event_sources(self, state: HeliosState) -> tuple[dict[str, float], list[dict]]:
        """
        Core event polling logic shared by _collect_events and _collect_events_with_state.
        
        Polls all registered EventSources, merges triggers using max-value semantics,
        and handles QQ-specific side effects.
        """
        # Poll all registered event sources
        merged_triggers: dict[str, float] = {}
        all_messages: list[dict] = []
        
        for source in self._event_sources:
            try:
                src_triggers = source.poll(state)
                # Merge using max-value semantics for overlapping keys
                for system, intensity in src_triggers.items():
                    merged_triggers[system] = max(
                        merged_triggers.get(system, 0.0), intensity
                    )
                all_messages.extend(source.get_messages())
            except Exception as e:
                self.log.warning(
                    "EventSource %s poll failed: %s",
                    type(source).__name__, e,
                )
        
        # Handle QQ-specific side effects: reset separation on message receipt
        if all_messages:
            self._last_master_contact = time.time()
            self._separation_anxiety = 0.0
            for msg in all_messages:
                text = msg.get("text", "")
                user_id = msg.get("user_id", "")
                self.log.info(f"📩 QQ [{user_id[:10]}]: {text[:60]}")
                
                # Auto-capture target_id from first private message
                if not self.cfg.QQ_TARGET_ID and not msg.get("is_group", False):
                    self.cfg.QQ_TARGET_ID = user_id
                    self.log.info(f"🎯 自动捕获主人 openid: {user_id}")
        
        # Track separation anxiety for state queries
        sep_hours = (time.time() - self._last_master_contact) / 3600
        self._separation_anxiety = min(1.0, 1 - 2.71828 ** (-0.4 * sep_hours))
        
        return merged_triggers, all_messages
    
    # ═══════════════════════════════════════════
    # Significant Event Recording (Requirement 13.2)
    # ═══════════════════════════════════════════
    
    def _record_significant_event(self, phi: float, valence: float,
                                  arousal: float, dominant: str,
                                  events: dict) -> None:
        """
        Record a significant event to EpisodicMemory when threshold is met.
        
        Threshold: phi > 0.3 OR |valence| > 0.5
        No recording when: phi <= 0.3 AND |valence| <= 0.5
        
        The MemoryItem stored includes emotional_tag, valence, arousal, phi,
        and timestamp (set automatically by MemoryItem).
        """
        if phi > 0.3 or abs(valence) > 0.5:
            trigger_desc = "+".join(events.keys()) if events else "spontaneous"
            summary = (
                f"[{dominant or 'neutral'}] {trigger_desc} "
                f"(V={valence:+.2f} Φ={phi:.2f})"
            )
            self.memory_system.remember(
                summary=summary,
                valence=valence,
                arousal=arousal,
                phi=phi,
                scene=trigger_desc,
                decision=f"dominant={dominant}",
            )
    
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
        """
        单次心跳 — Enhanced pipeline with full HeliosState forward propagation.
        
        Pipeline order (Requirement 9.4):
          0. Create fresh HeliosState
          1. Collect events from all EventSources
          2. Habituation — apply novelty decay to triggers
          3. DAISY emotion engine (with neurochem modulation)
          4. Neurochem tick
          5. Phi — feed all sources
          6. Personality adaptation
          7. Allostasis update
          8. Drives computation
          9. Regulation engine
         10. Memory — record significant events
         11. Passive reply pipeline
         12. Active expression (regulation → speech)
         13. Consolidation check
         14. Periodic persistence
        
        Each stage writes results into the shared HeliosState so subsequent
        stages observe updated values (forward propagation).
        """
        self.tick_count += 1
        
        # ── 0. Create fresh HeliosState ──
        sep_hours = (time.time() - self._last_master_contact) / 3600
        state = HeliosState(
            tick=self.tick_count,
            timestamp=time.time(),
            separation_hours=sep_hours,
        )
        
        # ── 1. Collect events from all registered EventSources ──
        events, messages = self._collect_events_with_state(state)
        
        # ── 2. Habituation — repeated stimuli → diminishing response ──
        for key, intensity in list(events.items()):
            novelty = self.habituation.get_novelty_factor(
                key, self.tick_count, arousal=self.last_valence
            )
            events[key] = intensity * novelty
            if intensity > 0.01:
                self.habituation.register_exposure(key, self.tick_count)
        
        # ── 3. DAISY emotion engine (with neurochem modulation) ──
        affect = self.daisy.cycle(events if events else {}, neurochem=self.neurochem)
        # Forward propagate: write affect into HeliosState
        state.panksepp = dict(affect.panksepp_activation) if affect.panksepp_activation else {}
        state.valence = affect.valence
        state.arousal = affect.arousal
        state.dominant_system = affect.dominant_system or ""
        
        # ── 4. Neurochem tick ──
        if self.neurochem:
            self.neurochem.tick()
            # Forward propagate neurochem levels into state
            state.dopamine = getattr(self.neurochem, 'dopamine', getattr(self.neurochem, '_dopamine', None))
            state.cortisol = getattr(self.neurochem, 'cortisol', getattr(self.neurochem, '_cortisol', None))
            state.opioids = getattr(self.neurochem, 'opioids', getattr(self.neurochem, '_opioids', None))
            state.oxytocin = getattr(self.neurochem, 'oxytocin', getattr(self.neurochem, '_oxytocin', None))
            # Handle NeurochemState attribute patterns (may be Chemical objects)
            if hasattr(state.dopamine, 'current'):
                state.dopamine = state.dopamine.current
            if hasattr(state.cortisol, 'current'):
                state.cortisol = state.cortisol.current
            if hasattr(state.opioids, 'current'):
                state.opioids = state.opioids.current
            if hasattr(state.oxytocin, 'current'):
                state.oxytocin = state.oxytocin.current
            # Fallback to defaults if attributes not found
            if state.dopamine is None:
                state.dopamine = 0.3
            if state.cortisol is None:
                state.cortisol = 0.2
            if state.opioids is None:
                state.opioids = 0.5
            if state.oxytocin is None:
                state.oxytocin = 0.3
        
        # ── 5. Phi — feed all sources (uses forward-propagated state) ──
        if self.phi_engine:
            # Feed emotional coherence from DAISY output
            if state.panksepp:
                self.phi_engine.feed_emotional(state.panksepp)
            
            # Feed DMN source from thinking mode
            self.phi_engine.feed_dmn_from_thinking(
                thinking_mode="resting",
                thought_count=0,
            )
            
            # Feed self_model from personality trait awareness
            self.phi_engine.feed_self_model_from_personality(
                self.personality._trait_dict()
            )
            
            # Feed ignition from active Panksepp system count
            if state.panksepp:
                self.phi_engine.feed_ignition_from_panksepp(state.panksepp)
            
            # Sensory decays via TTL when no external input (handled internally)
            state.phi = self.phi_engine.aggregate()
            state.consciousness_label = self.phi_engine.label.value if hasattr(self.phi_engine.label, 'value') else str(self.phi_engine.label)
        
        # ── 5b. Internal Thought Stream (Requirement 28) ──
        # Generate spontaneous thoughts after ICRI computation.
        # Writes dmn_active, last_thought_type, thought_generated_this_tick into state.
        # Feeds generated thought content to ICRI dmn_depth source.
        state.thought_generated_this_tick = False
        try:
            thought = self.thinking_integration.generate(state)
            # Determine DMN activity status for state
            dmn_active = True
            if hasattr(self.thinking_integration, '_engine'):
                engine = self.thinking_integration._engine
                if hasattr(engine, 'current_mode'):
                    dmn_active = engine.current_mode != getattr(
                        engine, 'MODE_EXTERNAL', 'external'
                    )
            state.dmn_active = dmn_active
            
            if thought is not None:
                state.thought_generated_this_tick = True
                state.last_thought_type = thought.type
                
                # Feed thought content to ICRI dmn_depth source for consciousness enrichment
                if self.phi_engine and hasattr(self.phi_engine, 'feed_dmn_from_thinking'):
                    self.phi_engine.feed_dmn_from_thinking(
                        thinking_mode="active",
                        thought_count=1,
                    )
                    # Re-aggregate ICRI with updated dmn_depth
                    state.phi = self.phi_engine.aggregate()
                    
                self.log.debug(
                    f"💭 Thought [{thought.type}]: {thought.content[:40]}..."
                )
        except Exception as e:
            self.log.warning(f"ThinkingEngineIntegration error: {e}")
            state.dmn_active = False
        
        # ── 6. Personality adaptation ──
        dominant = state.dominant_system
        intensity = max(state.panksepp.values()) if state.panksepp else 0
        self.personality.adapt_from_snapshot(dominant, intensity)
        # Forward propagate personality traits into state
        state.personality_traits = self.personality._trait_dict()
        
        # ── 7. Allostasis update ──
        self.allostasis.update(state.panksepp)
        # Forward propagate allostasis into state
        state.allostatic_load = self.allostasis.get_load_level()
        state.is_fatigued = self.allostasis.is_fatigued()
        
        # ── 7b. ICRI Temperature Mapping (Requirement 26.6) ──
        # Compute LLM temperature and speech style from current ICRI level
        state.llm_temperature = ICRITemperatureMapper.map_temperature(state.icri)
        state.speech_style = ICRITemperatureMapper.get_style_label(state.icri)
        
        # ── 8. Drives computation (uses forward-propagated phi, valence, arousal) ──
        sep_secs = time.time() - self._last_master_contact
        snapshot = HeliosSnapshot(
            valence=state.valence,
            arousal=state.arousal,
            time_since_last_interaction=sep_secs,
            phi_value=state.phi,
            cognitive_load=state.arousal,  # approximate via arousal
        )
        drive_vector = self.drive_oracle.cycle(snapshot, neurochem=self.neurochem)
        # Forward propagate drives into state
        state.drive_dominant = drive_vector.dominant
        state.drive_urgency = drive_vector.total
        self._last_drive_dominant = drive_vector.dominant
        self._last_drive_urgency = drive_vector.total
        
        # ── 9. Regulation engine (uses forward-propagated state) ──
        hour = datetime.now().hour
        action = self.regulation.tick(
            panksepp=state.panksepp or {},
            valence=state.valence,
            hour_of_day=hour,
            drive_urgency=state.drive_urgency,
            drive_dominant=state.drive_dominant,
        )
        if action:
            state.last_action = action
            # Enqueue via LimbDecisionBridge for priority-ordered execution
            # Use the regulation score (drive_urgency as proxy) for priority mapping
            reg_score = max(state.drive_urgency, abs(state.valence))
            self.limb_bridge.convert_and_enqueue(
                action=action,
                score=reg_score,
                params={"valence": state.valence, "dominant": state.dominant_system},
            )
        
        # ── 9b. Write behavior execution state into HeliosState ──
        state.behavior_queue_depth = self.behavior_executor.queue_depth
        current_cmd = self.behavior_executor.current
        state.current_behavior = current_cmd.name if current_cmd else ""
        
        # ── 9c. Write hardware IO status into HeliosState ──
        state.tts_available = self.tts.is_available
        
        # ── 10. Memory — record significant events ──
        # Autobiographical memory (meaningful moments, sampled every 10 ticks)
        if self.tick_count % 10 == 0 and (state.phi > 0.3 or abs(state.valence) > 0.5):
            # Forward propagate mood into state before recording
            state.mood_valence = self.mood.state.valence
            state.mood_arousal = self.mood.state.arousal
            state.mood_label = self.mood.state.label
            self.autobio.record(
                panksepp=state.panksepp,
                valence=state.valence,
                arousal=state.arousal,
                dominant=dominant,
                phi=state.phi,
                mood_valence=state.mood_valence,
                mood_arousal=state.mood_arousal,
                mood_label=state.mood_label,
                allostatic_load=state.allostatic_load,
                narrative=f"自发活动: {dominant}" if not events else f"事件响应: {dominant}",
                event_trigger="+".join(events.keys()) if events else "自发",
                cycle=self.tick_count,
            )
        
        # Significant event → Episodic Memory (Requirement 13.2)
        self._record_significant_event(
            phi=state.phi,
            valence=state.valence,
            arousal=state.arousal,
            dominant=dominant,
            events=events,
        )
        
        # ── 11. Passive reply pipeline (uses forward-propagated state) ──
        if messages:
            # Ensure mood is populated in state for reply context
            if not state.mood_label or state.mood_label == "neutral":
                state.mood_valence = self.mood.state.valence
                state.mood_arousal = self.mood.state.arousal
                state.mood_label = self.mood.state.label
            
            for msg in messages:
                text = msg.get("text", "")
                user_id = msg.get("user_id", "unknown")
                
                # Get recent conversation context for SEC evaluation
                context = self.response_pipeline.get_history(user_id)
                context_texts = [ex.user_message for ex in context[-3:]]
                
                # Evaluate message via LLM SEC
                sec_result = self.sec_evaluator.evaluate(text, context=context_texts)
                
                # Hold message + SEC result in Working Memory
                self.memory_system.hold(
                    summary=f"QQ [{user_id[:8]}]: {text[:60]}",
                    content={"text": text, "user_id": user_id, "sec_result": sec_result},
                    valence=sec_result.get("pleasantness", 0),
                    arousal=sec_result.get("novelty", 0),
                    phi=state.phi,
                )
                
                # Decide whether to reply and generate (state has full context)
                reply = None
                if self.response_pipeline.should_reply(msg, sec_result):
                    reply = self.response_pipeline.generate_reply(
                        msg, state, sec_result,
                        temperature_override=state.llm_temperature,
                    )
                    if reply and self.qq and self.qq.is_connected():
                        ok = self.qq.send_c2c(user_id, reply)
                        if ok:
                            self.log.info(f"💬 回复 [{user_id[:10]}]: {reply[:60]}")
                        else:
                            self.log.warning(f"💬 回复发送失败 [{user_id[:10]}]")
                    elif reply:
                        self.log.info(f"💬 回复 (无QQ) [{user_id[:10]}]: {reply[:60]}")
                    
                    # TTS: synthesize and play reply audio when available
                    if reply and self.tts.is_available:
                        self.tts.synthesize_and_play(reply)
                    
                    if reply:
                        state.pending_reply = reply
                
                # Record exchange in conversation history
                emotional_context = {
                    "dominant_system": state.dominant_system,
                    "valence": state.valence,
                    "arousal": state.arousal,
                    "mood_label": state.mood_label,
                }
                self.response_pipeline.record_exchange(
                    user_id=user_id,
                    message=text,
                    reply=reply,
                    emotional_context=emotional_context,
                    sec_result=sec_result,
                )
        
        # ── 12. Active expression (regulation → behavior executor → speech) ──
        # Execute the current behavior from the BehaviorExecutor
        current_cmd = self.behavior_executor.current
        if current_cmd and current_cmd.status.value == "executing":
            self._handle_action(current_cmd.action, temperature_override=state.llm_temperature)
            # Mark behavior as completed with result feedback
            self.behavior_executor.complete_current(
                result={"action": current_cmd.action, "tick": self.tick_count}
            )
        
        # ── 13. Consolidation check ──
        self._ticks_since_consolidation += 1
        if state.phi < 0.3:
            self._low_phi_counter += 1
        else:
            self._low_phi_counter = 0
        
        if (self._low_phi_counter > 300
                and self._ticks_since_consolidation > 600):
            stats = self.memory_system.consolidate(state.phi)
            if stats:
                self._ticks_since_consolidation = 0
                self._low_phi_counter = 0
                self.log.info(
                    "🧠 记忆巩固完成 — patterns_extracted=%d, memories_promoted=%d, items_pruned=%d",
                    stats.get("patterns_extracted", 0),
                    stats.get("memories_promoted", 0),
                    stats.get("items_pruned", 0),
                )
        
        # ── 14. Periodic persistence (every 600 ticks) ──
        if self.tick_count % 600 == 0:
            self._persist_state()
        
        # ── Update runtime state for external queries ──
        self.last_dominant = state.dominant_system
        self.last_valence = state.valence
        self.last_phi = state.phi
    
    def _handle_action(self, action: str, temperature_override: Optional[float] = None):
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
            text = self._generate_speech(action, temperature_override=temperature_override)
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
            
            # TTS: synthesize and play audio when available
            if text and self.tts.is_available:
                self.tts.synthesize_and_play(text)
            
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
    
    def _generate_speech(self, action: str, temperature_override: Optional[float] = None) -> str:
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

            # MemorySystem 记忆上下文 (情感相关记忆)
            memory_context = ""
            if self.memory_system:
                try:
                    memory_context = self.memory_system.get_llm_context(
                        valence=self.last_valence,
                        arousal=self.mood.state.arousal if hasattr(self.mood, 'state') else 0.5,
                    )
                except Exception as e:
                    self.log.debug(f"获取记忆上下文失败: {e}")

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
                memory_context=memory_context,
                personality_summary=personality,
                total_messages_sent=self.speech.total_generated,
            )

            text = self.speech.generate(ctx, temperature_override=temperature_override)
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

        # Memory usage monitoring at each summary interval (Requirement 23.1, 23.2, 23.4)
        if self.memory_system:
            self.memory_system.monitor()
    
    def _handle_signal(self, signum, frame):
        self.log.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def _shutdown(self):
        """优雅退出"""
        elapsed = time.time() - self.start_time
        self.log.info(f"Helios 退出 · 运行 {elapsed/60:.1f}min · {self.tick_count} ticks")
        
        # 持久化 personality + allostasis
        self._persist_state()
        
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
        
        state = {
            "tick": self.tick_count,
            "uptime_seconds": time.time() - self.start_time,
            "dominant": self.last_dominant,
            "valence": round(self.last_valence, 3),
            "icri": round(self.last_phi, 4),
            "phi": round(self.last_phi, 4),  # backward compat: deprecated alias
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

        # Expose memory statistics via get_state() (Requirement 23.3)
        if self.memory_system:
            state["memory"] = self.memory_system.get_state()

        return state


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


class _KeywordSECEvaluator:
    """Adapts the keyword-based _qq_text_to_panksepp function to the SECEvaluator protocol.
    
    This satisfies the QQEventSource's SECEvaluator dependency using the existing
    lightweight keyword matching logic. Will be replaced by LLMSECEvaluator in a
    future task.
    """

    def evaluate(self, text: str) -> dict[str, float]:
        """Evaluate text using keyword matching, return Panksepp trigger dictionary."""
        return _qq_text_to_panksepp(text)


class _StubThinkingEngine:
    """Minimal stub for ThinkingEngineIntegration when ThinkingManager is unavailable.
    
    Provides the interface expected by ThinkingEngineIntegration without requiring
    the full ThinkingManager module and its dependencies.
    """

    current_mode = "resting"  # DMN is active in resting mode

    def generate_thoughts(self, valence=0.0, arousal=0.0, panksepp_state=None, limit=1):
        """Return empty list — stub does not generate thoughts via LLM."""
        return []


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
