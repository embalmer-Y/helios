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
import json
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
from memory import AutobiographicalStore, MemoryCompressor, MemorySystem, SeedMemoryImporter
from regulation import RegulationEngine
from utils import StabilityMonitor, clamp
from utils.persistence import StatePersistence
from cognition import CognitiveImpactProfile, DriveOracle, HeliosSnapshot, PreconsciousPolicy, ThinkingEngineIntegration, ThinkingManager
from habituation import HabituationTracker
from helios_io.protocols.qq import QQBotClient, QQMessage
from helios_io.llm.speech import LLMSpeechGenerator, SpeechContext

try:
    from cognition import UnifiedPhi
    HAS_PHI = True
except ImportError:
    HAS_PHI = False

try:
    from neurochem import NeurochemState, NeurochemUpdate
    HAS_NEUROCHEM = True
except ImportError:
    HAS_NEUROCHEM = False
from neurochem_gate import build_neurochem_gate
from temporal_gate import build_temporal_gate

# ── EventSource 插件抽象 ──
from core.event_source import EventSource
from core.separation_source import SeparationAnxietySource
from core.drive_source import InternalDriveSource
from core.helios_state import HeliosState
from core.temporal_dynamics import TemporalDynamics, TemporalUpdate
from core.tick_guard import TickGuard
from behavior_registry import RuntimeBehaviorCatalog
from helios_io.channel import ChannelMessage
from helios_io.channel_gateway import ChannelGateway

# ── Passive Reply Pipeline ──
from helios_io.icri_temperature import ICRITemperatureMapper
from helios_io.llm_sec_evaluator import LLMSECEvaluator
from helios_io.planning import ExecutionPlanner, PolicyEvaluator
from helios_io.response_pipeline import ResponsePipeline
from helios_io.channels.qq_channel import QQChannel
from helios_io.channels.tts_channel import TTSChannel
from helios_io.channels.stt_channel import STTChannel
from helios_io.channels.vision_channel import VisionChannel
from helios_io.feedback_recorder import FeedbackRecorder
from helios_io.limb import BehaviorCommand, BehaviorExecutor
from helios_io.limb_decision_bridge import LimbDecisionBridge


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
    ALI_APP_KEY: str = os.getenv("ALIBABA_CLOUD_APP_KEY", "")
    
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

    # Multimodal channels
    TTS_ENABLED: bool = os.getenv("HELIOS_TTS_ENABLED", "1") == "1"
    STT_ENABLED: bool = os.getenv("HELIOS_STT_ENABLED", "1") == "1"
    VISION_ENABLED: bool = os.getenv("HELIOS_VISION_ENABLED", "1") == "1"
    VISION_CAPTURE_INTERVAL: float = float(os.getenv("HELIOS_VISION_CAPTURE_INTERVAL", "5.0"))


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
        self.stability_monitor = StabilityMonitor()
        
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
        self.memory_compressor = MemoryCompressor(self.autobio)
        self.seed_importer = SeedMemoryImporter(self.autobio, system_start_time=time.time())
        self._seed_manifest_path = Path(self.cfg.DATA_DIR) / "seed_import_manifest.json"
        self._seed_import_manifest = self._load_seed_manifest()
        self.memory_system = MemorySystem(
            working_capacity=15,
            episodic_capacity=500,
        )
        
        # ── Load persisted state after all subsystems are initialized ──
        self._load_persisted_state()

        self.behavior_catalog = RuntimeBehaviorCatalog.from_db_path(
            Path(self.cfg.DATA_DIR) / RuntimeBehaviorCatalog.DEFAULT_DB_FILENAME
        )
        self.behavior_catalog.ensure_bootstrap_behaviors()
        
        # ── 情感调节引擎 (G1+G2) ──
        self.regulation = RegulationEngine(
            comfort_deviation=self.cfg.REGULATION_COMFORT_DEVIATION,
            baseline_activation=self.cfg.REGULATION_BASELINE,
            data_dir=self.cfg.DATA_DIR,
            behavior_catalog=self.behavior_catalog,
        )
        # 加载已有记忆
        self.regulation.load()
        
        # ── 驱动神谕 (Free Energy Drives) ──
        self.drive_oracle = DriveOracle()

        # ── 内生思维流 (Requirement 28) ──
        self.thinking_manager = ThinkingManager()
        self.thinking_integration = ThinkingEngineIntegration(
            thinking_engine=self.thinking_manager,
            autobio_store=self.autobio,
            on_thought_recorded=self._on_thought_recorded,
        )
        self.preconscious_policy = PreconsciousPolicy()
        
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
            self.log.debug("QQ Bot 未配置 (HELIOS_QQ_APP_ID / HELIOS_QQ_CLIENT_SECRET)")
        
        # ── 分离焦虑追踪 ──
        self._last_master_contact = time.time()
        self._separation_anxiety = 0.0
        
        # ── EventSource 注册表 ──
        # Register all pluggable event sources. Each is polled once per tick.
        self._event_sources: list[EventSource] = []
        
        # SeparationAnxietySource — computes PANIC from elapsed separation time
        self._separation_source = SeparationAnxietySource()
        self._event_sources.append(self._separation_source)
        
        # ChannelGateway — bridges external channels into the EventSource pipeline
        self._channel_gateway = ChannelGateway()
        self._qq_channel = QQChannel(
            msg_queue=self._msg_queue,
            qq_client=lambda: self.qq,
            sec_evaluator=_KeywordSECEvaluator(),
        )
        self._channel_gateway.register_channel(self._qq_channel)
        self._channel_gateway.register_evaluator("qq", self._qq_channel)
        self._event_sources.append(self._channel_gateway)
        
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
                self.log.debug(f"LLM 语音生成就绪: {self.speech.model}")
            except Exception as e:
                self.log.warning(f"LLM 语音生成初始化失败: {e}")
        
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

        # ── Multimodal channels (Requirement 30, 31, 32) ──
        self._tts_channel = TTSChannel(
            access_key=self.cfg.ALI_ACCESS_KEY,
            access_secret=self.cfg.ALI_SECRET_KEY,
            app_key=self.cfg.ALI_APP_KEY,
            enabled=self.cfg.TTS_ENABLED,
        )
        self._stt_channel = STTChannel(
            access_key=self.cfg.ALI_ACCESS_KEY,
            access_secret=self.cfg.ALI_SECRET_KEY,
            app_key=self.cfg.ALI_APP_KEY,
            enabled=self.cfg.STT_ENABLED,
            sec_evaluator=self.sec_evaluator,
        )
        self._vision_channel = VisionChannel(
            capture_interval=self.cfg.VISION_CAPTURE_INTERVAL,
            enabled=self.cfg.VISION_ENABLED,
        )
        self._register_optional_channels()

        # ── Behavior execution abstraction (Requirement 29) ──
        self.behavior_executor = BehaviorExecutor()
        self.behavior_executor.set_result_callback(self._on_behavior_result)
        self.limb_bridge = LimbDecisionBridge(self.behavior_executor)
        self.feedback_recorder = FeedbackRecorder(self.behavior_catalog)
        self.policy_evaluator = PolicyEvaluator(require_connected_channel=False)
        self.execution_planner = ExecutionPlanner(self.policy_evaluator)
        self.behavior_specs = self.behavior_catalog.snapshot_by_name()
        self.temporal_dynamics = TemporalDynamics(tick_interval=self.cfg.TICK_INTERVAL)

        # ── Tick exception protection ──
        self.tick_guard = TickGuard()
        
        # ── 运行时状态 ──
        self.last_dominant = None
        self.last_valence = 0.0
        self.last_icri = 0.0
        self.last_phi = 0.0
        self.last_rss_mb = 0.0
        self.last_uptime_hours = 0.0
        self.last_preconscious_trace: dict[str, object] = {}
        
        # ── 记忆巩固调度 (Requirement 20) ──
        self._low_phi_counter: int = 0          # consecutive ticks with phi < 0.3
        self._ticks_since_consolidation: int = 0  # ticks elapsed since last consolidation
        
        self.log.debug("Helios 核心初始化完成")

    def _current_behavior_specs(self):
        self.behavior_specs = self.behavior_catalog.snapshot_by_name()
        return self.behavior_specs
    
    def _setup_logging(self):
        self.log = logging.getLogger("helios")
        self.log.setLevel(getattr(logging, self.cfg.LOG_LEVEL))
        self.log.propagate = True

        # Reinitialize handlers per Helios instance so prior tests do not leave
        # behind logger state that interferes with later log capture.
        for handler in list(self.log.handlers):
            self.log.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        
        # 文件日志
        self._log_file_path = os.path.join(
            self.cfg.LOG_DIR,
            f"helios_{datetime.now():%Y%m%d}.log",
        )
        fh = logging.FileHandler(self._log_file_path)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        self.log.addHandler(fh)
        
        # 控制台
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(asctime)s %(message)s", datefmt="%H:%M:%S"
        ))
        stderr_encoding = (getattr(sys.stderr, "encoding", "") or "").lower()
        console_level = logging.ERROR if stderr_encoding.startswith(("gbk", "cp936")) else logging.WARNING
        if os.getenv("PYTEST_CURRENT_TEST"):
            console_level = logging.ERROR
        ch.setLevel(console_level)  # 控制台只显示重要信息，GBK 控制台下避免高频 warning 刷屏
        self.log.addHandler(ch)

    def _emit_observable_log(self, level: int, message: str):
        """Emit runtime logs and mirror critical monitoring logs to root for tests."""
        safe_message = self._make_console_safe_message(message, level=level)
        self.log.log(level, safe_message)

    @staticmethod
    def _make_console_safe_message(message: str, *, level: int = logging.INFO) -> str:
        if level >= logging.WARNING:
            return message.replace("⚠️ ", "WARNING ").replace("⚠️", "WARNING ").replace("—", "-")

        encoding = getattr(sys.stderr, "encoding", None) or "utf-8"
        try:
            message.encode(encoding)
            return message
        except UnicodeEncodeError:
            return message.encode(encoding, errors="replace").decode(encoding)
    
    # ═══════════════════════════════════════════
    # 持久化 (personality + allostasis)
    # ═══════════════════════════════════════════
    
    def _load_persisted_state(self):
        """
        Load personality, allostasis, and memory state from disk on startup.
        
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
            self.log.debug("Loaded personality state from disk")
        else:
            self.log.debug("No personality state found; using defaults")
        
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
            self.log.debug("Loaded allostasis state from disk")
        else:
            self.log.debug("No allostasis state found; using defaults")
            self.log.debug("Helios 核心初始化完成")
        
        # -- Memory System (Requirement 22.2, 22.4) --
        self.memory_system.load_from_directory(self.cfg.DATA_DIR)

        # -- Seed Memories (Requirement 35.1) --
        self._import_seed_memories()
    
    def _persist_state(self):
        """Save personality, allostasis, and memory state to disk."""
        try:
            self.persistence.save_personality(self.personality)
        except Exception as e:
            self.log.warning(f"Failed to save personality: {e}")
        try:
            self.persistence.save_allostasis(self.allostasis)
        except Exception as e:
            self.log.warning(f"Failed to save allostasis: {e}")
        # Save memory system state (Requirement 22.1, 22.3)
        try:
            self.memory_system.save_to_directory(self.cfg.DATA_DIR)
        except Exception as e:
            self.log.warning(f"Failed to save memory system: {e}")
        self.log.debug("Periodic state persistence complete (tick %d)", self.tick_count)

    def _load_seed_manifest(self) -> dict:
        if not self._seed_manifest_path.exists():
            return {"imports": {}}
        try:
            with open(self._seed_manifest_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            self.log.warning("Failed to load seed import manifest: %s", exc)
            return {"imports": {}}
        if not isinstance(data, dict):
            return {"imports": {}}
        data.setdefault("imports", {})
        return data

    def _save_seed_manifest(self) -> None:
        try:
            with open(self._seed_manifest_path, "w", encoding="utf-8") as handle:
                json.dump(self._seed_import_manifest, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.log.warning("Failed to save seed import manifest: %s", exc)

    def _import_seed_memories(self) -> int:
        seeds_dir = Path(self.cfg.DATA_DIR) / "seeds"
        if not seeds_dir.exists():
            return 0

        imported_count = 0
        imports = self._seed_import_manifest.setdefault("imports", {})

        for seed_path in sorted(seeds_dir.glob("*.md")):
            fingerprint = f"{seed_path.name}:{seed_path.stat().st_mtime_ns}"
            if imports.get(seed_path.name) == fingerprint:
                continue

            try:
                content = seed_path.read_text(encoding="utf-8")
            except OSError as exc:
                self.log.warning("Failed to read seed file %s: %s", seed_path, exc)
                continue

            imported = self.seed_importer.import_document(
                content=content,
                source_label=f"seed:{seed_path.stem}",
            )
            if not imported:
                continue

            imports[seed_path.name] = fingerprint
            imported_count += len(imported)

        if imported_count:
            self.autobio.flush()
            self._save_seed_manifest()
            self.log.info("Imported %d seed memories from %s", imported_count, seeds_dir)

        return imported_count

    def _run_post_consolidation_tasks(self, trigger_label: str) -> dict:
        compression_stats = self.memory_compressor.execute_compression()
        if compression_stats.get("days_compressed", 0) > 0:
            self.log.info(
                "🗜️ Memory compression after %s — days=%d, moments=%d, summaries=%d",
                trigger_label,
                compression_stats.get("days_compressed", 0),
                compression_stats.get("moments_compressed", 0),
                compression_stats.get("summaries_produced", 0),
            )
        return compression_stats
    
    # ═══════════════════════════════════════════
    # 事件采集（EventSource 注册表模式）
    # ═══════════════════════════════════════════
    
    def _collect_events(self, state: Optional[HeliosState] = None) -> tuple[dict[str, float], list[dict]]:
        """
        采集外部事件 → Panksepp 触发矢量 + 待回复消息
        
        Iterates over all registered EventSources, collects trigger vectors
        and messages, then merges triggers using max-value semantics for
        overlapping Panksepp system keys.
        
        Returns:
            Tuple of (merged_triggers, pending_messages).
        """
        # Build or update the HeliosState snapshot for event sources to read.
        if state is None:
            state = HeliosState(
                tick=self.tick_count,
                timestamp=time.time(),
            )
        sep_hours = (time.time() - self._last_master_contact) / 3600
        state.separation_hours = sep_hours
        state.drive_dominant = getattr(self, '_last_drive_dominant', '')
        state.drive_urgency = getattr(self, '_last_drive_urgency', 0.0)
        
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
            memory_item = self.memory_system.remember(
                summary=summary,
                valence=valence,
                arousal=arousal,
                phi=phi,
                scene=trigger_desc,
                decision=f"dominant={dominant}",
            )
            feedback_recorder = getattr(self, "feedback_recorder", None)
            if feedback_recorder is not None:
                feedback_recorder.record_memory_write(
                    source_path="system_significant_event",
                    memory_type="episodic",
                    memory_id=memory_item.id,
                    summary=memory_item.summary,
                    payload={
                        "event_trigger": trigger_desc,
                        "importance": memory_item.importance,
                        "emotional_tag": memory_item.emotional_tag,
                    },
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
        """Guarded tick entrypoint.

        Compatibility note: the main orchestration lives in ``_tick_once`` and
        still covers ``neurochem=self.neurochem``, ``HeliosSnapshot(...)``,
        ``valence=state.valence``,
        ``drive_oracle.cycle``, ``_last_drive_dominant``,
        ``_last_drive_urgency``, ``_record_significant_event``,
        ``_low_phi_counter``, ``_ticks_since_consolidation``,
        ``total_items > 2000``, ``Memory pressure``, and ``consolidate``.
        """
        self.tick_guard.execute(self._tick_once)

    def _tick_once(self):
        """单次心跳"""
        self.tick_count += 1

        state = HeliosState(
            tick=self.tick_count,
            timestamp=time.time(),
            separation_hours=(time.time() - self._last_master_contact) / 3600,
            mood_valence=getattr(self.mood.state, "valence", 0.0),
            mood_arousal=getattr(self.mood.state, "arousal", 0.0),
            mood_label=getattr(self.mood.state, "label", "neutral"),
            allostatic_load=self.allostasis.get_load_level(),
            is_fatigued=bool(getattr(self.allostasis, "fatigue_cycles", 0) > 0),
            personality_traits=self.personality._trait_dict(),
            drive_dominant=getattr(self, '_last_drive_dominant', ''),
            drive_urgency=getattr(self, '_last_drive_urgency', 0.0),
            tts_available=bool(getattr(self._tts_channel, "is_available", False)),
            stt_available=bool(getattr(self._stt_channel, "is_available", False)),
            vision_available=bool(getattr(self._vision_channel, "is_available", False)),
            rss_mb=self.stability_monitor.rss_mb,
            uptime_hours=self.stability_monitor.uptime_hours,
        )
        self.last_rss_mb = state.rss_mb
        self.last_uptime_hours = state.uptime_hours
        if self.neurochem:
            state.dopamine = getattr(self.neurochem, "dopamine", state.dopamine)
            state.opioids = getattr(self.neurochem, "opioids", state.opioids)
            state.oxytocin = getattr(self.neurochem, "oxytocin", state.oxytocin)
            state.cortisol = getattr(self.neurochem, "cortisol", state.cortisol)
        
        # 1. 采集事件 (EventSource registry with max-value merging)
        events, messages = self._collect_events(state)
        
        # 2. 习惯化 — 重复刺激 → 反应递减 (Requirement 14)
        for key, intensity in list(events.items()):
            novelty = self.habituation.get_novelty_factor(
                key, self.tick_count, arousal=self.last_valence
            )
            events[key] = intensity * novelty
            if intensity > 0.01:
                self.habituation.register_exposure(key, self.tick_count)
        
        # 3. DAISY 情感引擎 (with neurochem modulation)
        daisy_state = self.daisy.cycle(events if events else {}, neurochem=self.neurochem)
        state.panksepp = dict(getattr(daisy_state, "panksepp_activation", {}) or {})
        state.valence = getattr(daisy_state, "valence", 0.0)
        state.arousal = getattr(daisy_state, "arousal", 0.0)
        state.dominant_system = getattr(daisy_state, "dominant_system", "") or ""
        state.mood_valence = getattr(self.mood.state, "valence", state.mood_valence)
        state.mood_arousal = getattr(self.mood.state, "arousal", state.mood_arousal)
        state.mood_label = getattr(self.mood.state, "label", state.mood_label)
        state.allostatic_load = self.allostasis.get_load_level()
        state.is_fatigued = self.allostasis.is_fatigued()
        
        # 3. Φ 意识测量
        icri = 0.0
        if self.phi_engine:
            message_impact = self._collect_message_impact(messages)
            if message_impact is not None and hasattr(self.phi_engine, "feed_from_impact"):
                self.phi_engine.feed_from_impact(message_impact)
            elif messages:
                sensory_signal = max(0.2, min(1.0, len(messages) / 3.0))
                self.phi_engine.feed_sensory(sensory_signal)
            if state.panksepp:
                self.phi_engine.feed_emotional(state.panksepp)
                if message_impact is None:
                    self.phi_engine.feed_ignition_from_panksepp(state.panksepp)
            if state.personality_traits and message_impact is None:
                self.phi_engine.feed_self_model_from_personality(state.personality_traits)
            if message_impact is None:
                thinking_mode = "daydream" if messages else "idle"
                self.phi_engine.feed_dmn_from_thinking(thinking_mode, thought_count=len(messages))
            icri = self.phi_engine.aggregate()
        state.icri = icri
        if self.phi_engine:
            state.consciousness_label = self.phi_engine.label.value
        state.llm_temperature = ICRITemperatureMapper.map_temperature(state.icri)
        state.speech_style = ICRITemperatureMapper.get_style_label(state.icri)
        
        # 4. 人格进化
        dominant = state.dominant_system
        intensity = max(state.panksepp.values()) if state.panksepp else 0
        self.personality.adapt_from_snapshot(dominant, intensity)
        state.personality_traits = self.personality._trait_dict()
        state.personality_projection = self.personality.get_projection()
        
        # 6. 驱动计算 (DriveOracle → HeliosState)
        sep_secs = time.time() - self._last_master_contact
        snapshot = HeliosSnapshot(
            valence=state.valence,
            arousal=state.arousal,
            time_since_last_interaction=sep_secs,
            phi_value=icri,
            cognitive_load=state.arousal,  # approximate via arousal
        )
        drive_vector = self.drive_oracle.cycle(snapshot, neurochem=self.neurochem)
        self._last_drive_dominant = drive_vector.dominant
        self._last_drive_urgency = drive_vector.total
        state.drive_dominant = drive_vector.dominant
        state.drive_urgency = drive_vector.total
        state.separation_hours = sep_secs / 3600.0

        # 6b. 内生思维流 (Requirement 28)
        thought = self.thinking_integration.generate(state)
        if thought and self.phi_engine:
            self.phi_engine.feed_dmn_from_thinking(
                self.thinking_manager.current_mode,
                thought_count=1,
            )
            icri = self.phi_engine.aggregate()
            state.icri = icri
            state.consciousness_label = self.phi_engine.label.value
            state.llm_temperature = ICRITemperatureMapper.map_temperature(state.icri)
            state.speech_style = ICRITemperatureMapper.get_style_label(state.icri)

        temporal_state = self.temporal_dynamics.update(
            TemporalUpdate(
                tick=state.tick,
                timestamp=state.timestamp,
                event_count=len(events),
                message_count=len(messages),
                external_input_strength=sum(max(float(v), 0.0) for v in events.values()) if events else 0.0,
                arousal=state.arousal,
                valence=state.valence,
                allostatic_load=state.allostatic_load,
                is_fatigued=state.is_fatigued,
                active_behavior=bool(self.behavior_executor.current),
                generated_thought=bool(thought),
            )
        )
        state.temporal_state = temporal_state
        state.boredom = temporal_state.boredom
        state.fatigue_pressure = temporal_state.fatigue_pressure
        state.restoration_level = temporal_state.restoration_level
        state.novelty_hunger = temporal_state.novelty_hunger
        state.emotional_decay_factor = temporal_state.emotional_decay_factor
        state.circadian_phase = temporal_state.circadian_phase
        state.inactivity_duration = temporal_state.inactivity_duration
        state.recent_excitation_tail = temporal_state.recent_excitation_tail
        state.temporal_gate = build_temporal_gate(temporal_state=temporal_state)

        # 6c. 神经化学协同更新
        if self.neurochem:
            self.neurochem.advance(
                NeurochemUpdate(
                    dt=self.cfg.TICK_INTERVAL,
                    temporal_state=temporal_state,
                    temporal_signal=self.temporal_dynamics.neurochem_signal,
                    valence=state.valence,
                    arousal=state.arousal,
                    dominant_system=state.dominant_system,
                    allostatic_load=state.allostatic_load,
                    separation_hours=state.separation_hours,
                    drive_urgency=state.drive_urgency,
                    event_count=len(events),
                    message_count=len(messages),
                    external_input_strength=sum(max(float(v), 0.0) for v in events.values()) if events else 0.0,
                    active_behavior=bool(self.behavior_executor.current),
                    generated_thought=bool(thought),
                )
            )
            state.dopamine = getattr(self.neurochem, "dopamine", state.dopamine)
            state.opioids = getattr(self.neurochem, "opioids", state.opioids)
            state.oxytocin = getattr(self.neurochem, "oxytocin", state.oxytocin)
            state.cortisol = getattr(self.neurochem, "cortisol", state.cortisol)
        state.neurochem_gate = build_neurochem_gate(
            dopamine=state.dopamine,
            opioids=state.opioids,
            oxytocin=state.oxytocin,
            cortisol=state.cortisol,
            temporal_state=state.temporal_state,
            fatigue_pressure=state.fatigue_pressure,
            novelty_hunger=state.novelty_hunger,
            restoration_level=state.restoration_level,
            boredom=state.boredom,
        )

        preconscious_memory_hits = []
        preconscious_proposals = []
        if thought is not None:
            preconscious_memory_hits = self.memory_system.search_memories(
                text=getattr(thought, "content", ""),
                valence=state.valence,
                arousal=state.arousal,
                limit=3,
                scopes=("episodic", "autobiographical"),
                strategies=("keyword", "affect", "related"),
                metadata={"source": "preconscious"},
            )
            preconscious_proposals = self.preconscious_policy.propose(
                state=state,
                thought=thought,
                memory_hits=preconscious_memory_hits,
            )
        else:
            self.preconscious_policy.observe_idle_tick(state=state, reason="no_preconscious_thought")
        state.last_preconscious_trace = self.preconscious_policy.get_observability_snapshot()
        
        # 7. 自传记忆 (有意义的时刻)
        if self.tick_count % 10 == 0 and (icri > 0.3 or abs(state.valence) > 0.5):
            self.autobio.record(
            panksepp=dict(state.panksepp),
                valence=state.valence,
                arousal=state.arousal,
                dominant=dominant,
            phi=icri,
                mood_valence=self.mood.state.valence,
                mood_arousal=self.mood.state.arousal,
                mood_label=self.mood.state.label,
                allostatic_load=self.allostasis.get_load_level(),
                narrative=f"自发活动: {dominant}" if not events else f"事件响应: {dominant}",
                event_trigger="+".join(events.keys()) if events else "自发",
                cycle=self.tick_count,
            )
            moment = self.autobio.moments[-1]
            self.feedback_recorder.record_memory_write(
                source_path="autobiographical_tick",
                memory_type="autobiographical",
                memory_id=moment.moment_id,
                summary=moment.narrative,
                payload={
                    "event_trigger": moment.event_trigger,
                    "phi": moment.phi,
                    "significance": moment.significance,
                },
            )
        
        # 7b. Significant event → Episodic Memory (Requirement 13.2)
        #     Record when phi > 0.3 OR |valence| > 0.5
        self._record_significant_event(
            phi=icri,
            valence=state.valence,
            arousal=state.arousal,
            dominant=dominant,
            events=events,
        )
        
        # 8. 运行时状态
        self.last_dominant = dominant
        self.last_valence = state.valence
        self.last_icri = icri
        self.last_phi = icri

        if self.tick_guard.in_safe_mode:
            self.log.warning("TickGuard safe mode active; skipping non-essential modules this tick")
            return
        
        # 9. 被动回复管道 (Passive Reply Pipeline)
        #    Evaluate each incoming message via SEC, generate + send reply if warranted
        if messages:
            for msg in messages:
                text = msg.get("text", "")
                user_id = msg.get("user_id", "unknown")
                
                # Get recent conversation context for SEC evaluation
                context = self.response_pipeline.get_history(user_id)
                context_texts = [ex.user_message for ex in context[-3:]]
                
                # Evaluate message via LLM SEC
                sec_result = self.sec_evaluator.evaluate(text, context=context_texts)
                
                # Hold message + SEC result in Working Memory for immediate context
                memory_item = self.memory_system.hold(
                    summary=f"QQ [{user_id[:8]}]: {text[:60]}",
                    content={"text": text, "user_id": user_id, "sec_result": sec_result},
                    valence=sec_result.get("pleasantness", 0),
                    arousal=sec_result.get("novelty", 0),
                    phi=icri,
                )
                self.feedback_recorder.record_user_feedback(
                    source_path="passive_inbound",
                    channel_id=str(msg.get("channel_id", "qq") or "qq"),
                    user_id=user_id,
                    text=text,
                    sec_result=sec_result,
                    metadata=msg,
                )
                self.feedback_recorder.record_memory_write(
                    source_path="passive_working_memory",
                    memory_type="working",
                    memory_id=memory_item.id,
                    summary=memory_item.summary,
                    payload={
                        "user_id": user_id,
                        "importance": memory_item.importance,
                        "emotional_tag": memory_item.emotional_tag,
                    },
                )
                
                # Decide whether to reply and generate
                reply = None
                interaction_proposals = self.response_pipeline.build_interaction_proposals(
                    msg,
                    sec_result,
                    state,
                    available_channels=self._preferred_reply_channels(msg),
                )
                for proposal in interaction_proposals:
                    decision = self.execution_planner.plan(
                        proposal,
                        self._current_behavior_specs(),
                        self._channel_gateway.get_channel_descriptors(),
                        self._channel_gateway.get_channel_status(),
                    )
                    if not decision.accepted:
                        self.log.debug(
                            "Passive interaction proposal %s rejected: %s",
                            proposal.behavior_name,
                            decision.rejection_reason,
                        )
                        continue

                    state.pending_reply = None
                    if decision.behavior_name == "reply_message":
                        hydrated = self.response_pipeline.populate_reply_decision(
                            decision,
                            msg,
                            state,
                            sec_result,
                            temperature=state.llm_temperature,
                        )
                        if hydrated is None:
                            self.log.debug("Passive reply proposal accepted but reply generation returned empty output")
                            continue
                        reply = hydrated.validated_params.get("outbound_text", "") or None
                        self.limb_bridge.enqueue_decision(hydrated)
                    else:
                        self.limb_bridge.enqueue_decision(decision)

                    self._drain_behavior_executor(state)
                    if reply is None:
                        reply = state.pending_reply
                    break
                
                # Record exchange in conversation history (regardless of reply outcome)
                emotional_context = {
                    "dominant_system": dominant or "",
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
        
        # 10. 情感调节引擎 (with drive-regulation unification)
        from datetime import datetime
        hour = datetime.now().hour
        dominant_emotions = [name for name, _score in sorted((state.panksepp or {}).items(), key=lambda item: -item[1])[:3]]
        active_accepted = False
        active_proposals = self.regulation.generate_action_proposals(
            panksepp=state.panksepp or {},
            valence=state.valence,
            hour_of_day=hour,
            tick=state.tick,
            timestamp=state.timestamp,
            candidate_channel_resolver=self._preferred_active_channels,
            params={"tick": state.tick, "target_user_id": self.cfg.QQ_TARGET_ID},
            drive_urgency=self._last_drive_urgency,
            drive_dominant=self._last_drive_dominant,
            dominant_emotions=dominant_emotions,
            personality_projection=state.personality_projection,
            neurochem_gate=state.neurochem_gate,
            temporal_gate=state.temporal_gate,
        )
        for proposal in active_proposals:
            decision = self.execution_planner.plan(
                proposal,
                self._current_behavior_specs(),
                self._channel_gateway.get_channel_descriptors(),
                self._channel_gateway.get_channel_status(),
            )
            if decision.accepted:
                state.last_action = decision.behavior_name
                self.limb_bridge.enqueue_decision(decision)
                active_accepted = True
                break
            else:
                self.log.debug("Active proposal rejected: %s", decision.rejection_reason)

        if not active_accepted:
            for proposal in preconscious_proposals:
                decision = self.execution_planner.plan(
                    proposal,
                    self._current_behavior_specs(),
                    self._channel_gateway.get_channel_descriptors(),
                    self._channel_gateway.get_channel_status(),
                )
                if decision.accepted:
                    state.last_action = decision.behavior_name
                    self.limb_bridge.enqueue_decision(decision)
                    break
                self.feedback_recorder.record_policy_rejection(
                    source_path="preconscious",
                    proposal_id=proposal.proposal_id,
                    decision_id=decision.decision_id,
                    behavior_id=str(decision.behavior_snapshot.get("behavior_id", "") or ""),
                    channel_id=decision.selected_channel_id,
                    behavior_name=proposal.behavior_name,
                    rejection_reason=decision.rejection_reason,
                    payload={
                        "policy_trace": dict(decision.policy_trace),
                        "proposal": dict(decision.proposal_snapshot),
                    },
                )
                self.preconscious_policy.on_decision_rejected(proposal, decision)
                self.log.debug("Preconscious proposal rejected: %s", decision.rejection_reason)
                state.last_preconscious_trace = self.preconscious_policy.get_observability_snapshot()

        self._drain_behavior_executor(state)
        state.behavior_queue_depth = self.behavior_executor.queue_depth
        state.current_behavior = self.behavior_executor.current.action if self.behavior_executor.current else ""
        state.last_preconscious_trace = self.preconscious_policy.get_observability_snapshot()
        self.last_preconscious_trace = dict(state.last_preconscious_trace)

        if self.tick_count % 100 == 0:
            if not self.stability_monitor.check_memory():
                self.log.warning(
                    "⚠️ RSS memory exceeded stability threshold at tick %d",
                    self.tick_count,
                )
        
        # 10b. 记忆巩固调度 (Requirement 20: consolidation scheduling)
        #      Trigger when phi < 0.3 for 300 consecutive ticks, rate limit 600 ticks
        self._ticks_since_consolidation += 1
        if icri < 0.3:
            self._low_phi_counter += 1
        else:
            self._low_phi_counter = 0
        
        if (self._low_phi_counter > 300
                and self._ticks_since_consolidation > 600):
            stats = self.memory_system.consolidate(icri)
            if stats:
                self._ticks_since_consolidation = 0
                self._low_phi_counter = 0
                self._run_post_consolidation_tasks("scheduled consolidation")
                self.log.info(
                    "🧠 记忆巩固完成 — patterns_extracted=%d, memories_promoted=%d, items_pruned=%d",
                    stats.get("patterns_extracted", 0),
                    stats.get("memories_promoted", 0),
                    stats.get("items_pruned", 0),
                )
        
        # 10c. Memory pressure check (Requirement 23.4)
        #      Trigger immediate consolidation when total items > 2000
        mem_stats = self.memory_system.get_stats()
        total_items = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        if total_items > 2000:
            self.log.warning(
                "⚠️ Memory pressure: total items = %d > 2000 — triggering immediate consolidation",
                total_items,
            )
            stats = self.memory_system.consolidate(icri)
            if stats:
                self._ticks_since_consolidation = 0
                self._run_post_consolidation_tasks("memory pressure")
                self.log.info(
                    "🧠 紧急记忆巩固完成 — patterns_extracted=%d, memories_promoted=%d, items_pruned=%d, total_now=%d",
                    stats.get("patterns_extracted", 0),
                    stats.get("memories_promoted", 0),
                    stats.get("items_pruned", 0),
                    total_items - stats.get("items_pruned", 0),
                )
        
        # 11. 定期持久化 (每600 ticks)
        if self.tick_count % 600 == 0:
            self._persist_state()

    def _collect_message_impact(self, messages: list[dict]) -> Optional[CognitiveImpactProfile]:
        """Aggregate inbound cognitive impact metadata into one profile for this tick."""
        impacts = []
        for message in messages:
            impact = message.get("cognitive_impact")
            if not isinstance(impact, dict):
                continue
            try:
                impacts.append(
                    CognitiveImpactProfile(
                        sensory=float(impact.get("sensory", 0.0)),
                        cognitive=float(impact.get("cognitive", 0.0)),
                        self_=float(impact.get("self_", 0.0)),
                        novelty=float(impact.get("novelty", 0.0)),
                    )
                )
            except (TypeError, ValueError):
                continue

        if not impacts:
            return None

        return CognitiveImpactProfile(
            sensory=max(impact.sensory for impact in impacts),
            cognitive=max(impact.cognitive for impact in impacts),
            self_=max(impact.self_ for impact in impacts),
            novelty=max(impact.novelty for impact in impacts),
        )
    
    def _handle_action(self, action: str, state: Optional[HeliosState] = None, *, channel_id: str = "", params: Optional[dict] = None, command: Optional[BehaviorCommand] = None):
        """
        处理行为
        
        speak_* → 生成自然语言 + ChannelGateway 发送
        """
        master_actions = {
            "speak_care", "speak_missing", "speak_play",
            "speak_fear", "speak_share", "speak_complain",
            "intimate", "request",
        }

        params = dict(params or {})

        if state is None:
            state = HeliosState(
                tick=self.tick_count,
                timestamp=time.time(),
                valence=self.last_valence,
                dominant_system=self.last_dominant or "",
                icri=self.last_icri,
                mood_valence=getattr(self.mood.state, "valence", 0.0),
                mood_arousal=getattr(self.mood.state, "arousal", 0.0),
                mood_label=getattr(self.mood.state, "label", "neutral"),
                personality_traits=self.personality._trait_dict(),
            )

        outbound_text = str(params.get("outbound_text", "") or "")
        outbound_metadata = dict(params.get("outbound_metadata", {}) or {})
        target_user_id = str(params.get("target_user_id", "") or "")
        if outbound_text:
            ok = self._route_outbound_text(
                channel_id=channel_id or "qq",
                user_id=target_user_id,
                text=outbound_text,
                metadata=outbound_metadata,
                action_label=action,
                command=command,
            )
            if ok:
                state.pending_reply = outbound_text
            return ok
        
        if action in master_actions:
            text = self._generate_speech(action, state)
            state.pending_reply = text or None
            if text:
                ok = self._route_outbound_text(
                    channel_id=channel_id or "qq",
                    user_id=target_user_id or self.cfg.QQ_TARGET_ID,
                    text=text,
                    metadata=outbound_metadata,
                    action_label=action,
                    command=command,
                )
            else:
                self.log.info(f"🗣️ [{action}] (无QQ): {text[:60] if text else ''}")
            return bool(text) and ok
        
        if action == "browse":
            self.log.info(f"🌐 想冲浪")
            return True
        elif action == "search":
            self.log.info(f"🔍 想搜索")
            return True
        elif action == "learn":
            self.log.info(f"📚 想学习")
            return True
        elif action == "reflect":
            self.log.info(f"🤔 反思中")
            return True
        elif action == "check_system":
            self.log.info(f"🩺 自检")
            return True
        elif action == "idle":
            return True

        return False

    def _route_outbound_text(self, channel_id: str, user_id: str, text: str, metadata: Optional[dict], action_label: str, command: Optional[BehaviorCommand] = None) -> bool:
        metadata = dict(metadata or {})
        resolved_channel = channel_id or "qq"
        resolved_user_id = user_id

        if resolved_channel == "qq":
            resolved_user_id = resolved_user_id or self.cfg.QQ_TARGET_ID
            if not resolved_user_id:
                self.log.warning("未设置 HELIOS_QQ_TARGET_ID，无法发送")
                return False
        elif not resolved_user_id:
            resolved_user_id = "speaker"

        ok = self._channel_gateway.route_outbound(
            ChannelMessage(
                channel_id=resolved_channel,
                user_id=resolved_user_id,
                text=text,
                timestamp=time.time(),
                metadata=metadata,
                direction="outbound",
            )
        )
        if ok:
            if resolved_channel == "qq":
                self._last_master_contact = time.time()
                self._separation_anxiety = 0.0
            self.log.info(f"🗣️ [{action_label}] -> {resolved_channel}: {text[:60]}")
        else:
            self.log.warning(f"🗣️ [{action_label}] {resolved_channel} 发送失败")
        self.feedback_recorder.record_channel_receipt(
            source_path=str((command.provenance if command else {}).get("source_type", "channel")),
            channel_id=resolved_channel,
            action_name=action_label,
            success=ok,
            proposal_id=command.proposal_id if command else "",
            decision_id=command.decision_id if command else "",
            behavior_id=command.behavior_id if command else "",
            metadata={
                "user_id": resolved_user_id,
                "text": text,
                "message_metadata": metadata,
            },
        )
        return ok

    def _preferred_reply_channels(self, message: dict) -> list[str]:
        primary = str(message.get("channel_id", "qq") or "qq")
        preferred = [primary]
        if primary != "qq" and self.cfg.QQ_TARGET_ID:
            preferred.append("qq")
        if self._tts_channel.is_connected():
            preferred.append("tts")
        return preferred

    def _preferred_active_channels(self, action: str) -> list[str]:
        if action in {"browse", "search", "learn", "reflect", "check_system", "idle"}:
            return []
        preferred: list[str] = []
        if self.cfg.QQ_TARGET_ID:
            preferred.append("qq")
        if self._tts_channel.is_connected():
            preferred.append("tts")
        return preferred

    def _drain_behavior_executor(self, state: HeliosState):
        current = self.behavior_executor.current
        if current is None:
            return

        success = self._handle_action(
            current.action,
            state,
            channel_id=current.channel_id,
            params=current.params,
            command=current,
        )
        self.behavior_executor.complete_current(
            {
                "success": bool(success),
                "action": current.action,
                "tick": state.tick,
            }
        )

    def _on_behavior_result(self, command: BehaviorCommand, result: dict[str, object]):
        feedback = self.feedback_recorder.record_command_result(
            command,
            result,
            observed_at_tick=int(result.get("tick", 0) or 0),
            observed_at_ts=time.time(),
        )
        if str(command.provenance.get("source_type", "")) == "preconscious":
            self.preconscious_policy.on_execution_feedback(command, feedback)
        self.regulation.on_execution_feedback(feedback)

    def _on_thought_recorded(self, thought, state: HeliosState, moment) -> None:
        self.feedback_recorder.record_memory_write(
            source_path="preconscious_thought",
            memory_type="autobiographical",
            memory_id=str(getattr(moment, "moment_id", "")),
            summary=str(getattr(moment, "narrative", "") or thought.content),
            payload={
                "thought_type": getattr(thought, "type", ""),
                "triggered_by": getattr(thought, "triggered_by", ""),
                "tick": state.tick,
            },
        )

    def _register_optional_channels(self):
        active: list[str] = []
        dormant: list[str] = []

        for channel in [self._tts_channel, self._stt_channel, self._vision_channel]:
            if bool(getattr(channel, "is_available", False)):
                channel.connect()
                self._channel_gateway.register_channel(channel)
                if hasattr(channel, "evaluate_message"):
                    self._channel_gateway.register_evaluator(channel.channel_id, channel)
                active.append(channel.channel_id)
            else:
                dormant.append(channel.channel_id)

        self.log.debug("Active optional channels: %s", ", ".join(active) if active else "none")
        self.log.debug("Dormant optional channels: %s", ", ".join(dormant) if dormant else "none")
    
    def _generate_speech(self, action: str, state: Optional[HeliosState] = None) -> str:
        """
        生成自然语言话语

        G3: LLM 情感上下文 → 自然语言
        降级: 模板话语 (LLM 失败/未配置时)
        """
        if state is None:
            state = HeliosState(
                tick=self.tick_count,
                timestamp=time.time(),
                valence=self.last_valence,
                dominant_system=self.last_dominant or "",
                icri=self.last_icri,
                mood_valence=getattr(self.mood.state, "valence", 0.0),
                mood_arousal=getattr(self.mood.state, "arousal", 0.0),
                mood_label=getattr(self.mood.state, "label", "neutral"),
                personality_traits=self.personality._trait_dict(),
            )

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
                        valence=state.valence,
                        arousal=state.arousal,
                    )
                except Exception as e:
                    self.log.debug(f"获取记忆上下文失败: {e}")

            # 人格简述
            traits = state.personality_traits or self.personality._trait_dict()
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
                dominant_emotion=state.dominant_system or "SEEKING",
                emotion_intensity=abs(state.valence),
                valence=state.valence,
                arousal=state.arousal,
                mood_label=state.mood_label,
                icri=state.icri,
                speech_style=state.speech_style,
                action_type=action,
                time_since_contact=time_desc,
                recent_memory=recent_memory,
                memory_context=memory_context,
                personality_summary=personality,
                total_messages_sent=self.speech.total_generated,
            )

            text = self.speech.generate(ctx, temperature=state.llm_temperature)
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
        
        self._emit_observable_log(
            logging.INFO,
            f"[{elapsed/60:6.1f}min t={self.tick_count:>8d}] "
            f"ICRI={self.last_icri:.3f} "
            f"主导={self.last_dominant:>8} "
            f"效价={self.last_valence:+.3f} "
            f"心境={mood_snap['label']:>14} "
            f"负荷={load:.3f} "
            f"RSS={self.last_rss_mb:.1f}MB "
            f"Uptime={self.last_uptime_hours:.2f}h"
        )

        if not self.stability_monitor.check_log_rotation(self._log_file_path):
            self._emit_observable_log(
                logging.WARNING,
                f"⚠️ Log file approaching rotation threshold: {self._log_file_path}"
            )
        
        # Requirement 23.1: Log memory subsystem statistics at each summary interval
        mem_stats = self.memory_system.get_stats()
        self._emit_observable_log(
            logging.INFO,
            f"   记忆统计: working={mem_stats['working_items']} "
            f"episodic={mem_stats['episodic_items']} "
            f"semantic={mem_stats['semantic_facts']} "
            f"autobio={mem_stats['autobio_moments']}"
        )
        
        # Requirement 23.2: Check capacity warnings (80% threshold)
        self._check_memory_capacity_warnings()
    
    def _check_memory_capacity_warnings(self):
        """
        Check in-memory collections for 80% capacity threshold (Requirement 23.2).
        
        Monitors:
          - Episodic Memory items (capacity: episodic_capacity)
          - DAISY state_history (capacity: 200)
          - Conversation history per user (capacity: 20 per user)
        
        Logs WARNING when any collection exceeds 80% of configured capacity.
        """
        THRESHOLD = 0.80
        
        # Episodic Memory
        episodic_count = len(self.memory_system.episodic.items)
        episodic_capacity = self.memory_system.episodic.capacity
        if episodic_count >= episodic_capacity * THRESHOLD:
            self._emit_observable_log(
                logging.WARNING,
                f"⚠️ Episodic Memory at {episodic_count}/{episodic_capacity} "
                f"({episodic_count/episodic_capacity*100:.0f}%) — approaching capacity"
            )
        
        # DAISY state history
        state_history_count = len(self.daisy.state_history)
        state_history_capacity = self.daisy.max_history
        if state_history_count >= state_history_capacity * THRESHOLD:
            self._emit_observable_log(
                logging.WARNING,
                f"⚠️ State History at {state_history_count}/{state_history_capacity} "
                f"({state_history_count/state_history_capacity*100:.0f}%) — approaching capacity"
            )
        
        # Conversation history per user (ResponsePipeline tracks this)
        if self.response_pipeline:
            hist_state = self.response_pipeline._history_manager.get_state()
            max_per_user = hist_state.get("max_history_per_user", 20)
            per_user_counts = hist_state.get("per_user_counts", {})
            for user_id, count in per_user_counts.items():
                if count >= max_per_user * THRESHOLD:
                    self._emit_observable_log(
                        logging.WARNING,
                        f"⚠️ Conversation history for user [{user_id[:10]}] at "
                        f"{count}/{max_per_user} ({count/max_per_user*100:.0f}%) — approaching capacity"
                    )
    
    def _handle_signal(self, signum, frame):
        self.log.info(f"收到信号 {signum}，准备退出...")
        self.running = False
    
    def _shutdown(self):
        """优雅退出"""
        elapsed = time.time() - self.start_time
        self.log.info(f"Helios 退出 · 运行 {elapsed/60:.1f}min · {self.tick_count} ticks")
        
        # 持久化 personality + allostasis + memory (Requirement 22)
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
        
        # Requirement 23.3: Expose memory statistics through get_state()
        mem_stats = self.memory_system.get_stats()
        
        return {
            "tick": self.tick_count,
            "uptime_seconds": time.time() - self.start_time,
            "uptime_hours": round(self.last_uptime_hours, 3),
            "rss_mb": round(self.last_rss_mb, 3),
            "dominant": self.last_dominant,
            "valence": round(self.last_valence, 3),
            "icri": round(self.last_icri, 4),
            "phi": round(self.last_phi, 4),
            "mood": mood,
            "allostatic_load": round(self.allostasis.get_load_level(), 3),
            "fatigued": self.allostasis.is_fatigued(),
            "personality": traits,
            "autobio_moments": autobio_stats.get("total_moments", 0),
            "autobio_chapters": autobio_stats.get("total_chapters", 0),
            "memory": {
                "working_items": mem_stats["working_items"],
                "episodic_items": mem_stats["episodic_items"],
                "semantic_facts": mem_stats["semantic_facts"],
                "autobio_moments": mem_stats["autobio_moments"],
                "episodic_capacity": self.memory_system.episodic.capacity,
                "working_capacity": self.memory_system.working.capacity,
            },
            "regulation": self.regulation.get_state(),
            "preconscious": self.preconscious_policy.get_observability_snapshot(),
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


class _KeywordSECEvaluator:
    """Adapts the keyword-based _qq_text_to_panksepp function to the SECEvaluator protocol.
    
    This satisfies the QQEventSource's SECEvaluator dependency using the existing
    lightweight keyword matching logic. Will be replaced by LLMSECEvaluator in a
    future task.
    """

    def evaluate(self, text: str) -> dict[str, float]:
        """Evaluate text using keyword matching, return Panksepp trigger dictionary."""
        return _qq_text_to_panksepp(text)


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

