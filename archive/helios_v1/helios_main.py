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
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional


class ConsoleSafeStreamHandler(logging.StreamHandler):
    """Render console logs without UnicodeEncodeError on legacy Windows consoles."""

    def format(self, record):
        message = super().format(record)
        encoding = getattr(self.stream, "encoding", None) or "utf-8"
        try:
            message.encode(encoding)
            return message
        except UnicodeEncodeError:
            return message.encode(encoding, errors="backslashreplace").decode(encoding)

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
from identity_governance import IdentityGovernance, IdentityStore
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
from core.helios_state import ContinuationPressureState, HeliosState, ProactiveObservabilityState
from core.temporal_dynamics import TemporalDynamics, TemporalUpdate
from core.tick_guard import TickGuard
from behavior_registry import RuntimeBehaviorCatalog
from helios_io.channel import ChannelManagementResult, ChannelMessage, ChannelStatus, InputChannel, OutputChannel
from helios_io.channel_gateway import ChannelGateway
from personality_contract import build_personality_contract
from personality_projection import resolve_personality_projection

# ── Passive Reply Pipeline ──
from helios_io.icri_temperature import ICRITemperatureMapper
from helios_io.llm_sec_evaluator import LLMSECEvaluator
from helios_io.optional_channel_bootstrap import (
    OptionalChannelRuntime,
    build_default_optional_channel_runtime,
)
from helios_io.planning import ExecutionPlanner, PolicyEvaluator
from helios_io.response_pipeline import ResponsePipeline
from helios_io.routing_policy import RoutingPreferencePolicy
from helios_io.channels.cli_channel import CLIChannel
from helios_io.channels.qq_channel import QQChannel
from helios_io.channels.tts_channel import TTSChannel
from helios_io.channels.stt_channel import STTChannel
from helios_io.channels.vision_channel import VisionChannel
from helios_io.feedback_recorder import FeedbackRecorder
from helios_io.action_models import ActionDecision, ActionProposal, ThoughtActionProposal
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
    LLM_SEC_TIMEOUT: float = float(os.getenv("HELIOS_LLM_SEC_TIMEOUT", "8.0"))
    IDENTITY_BOOTSTRAP_PATH: str = os.getenv("HELIOS_IDENTITY_BOOTSTRAP_PATH", str(PROJECT_ROOT / "data" / "identity_bootstrap.json"))
    
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
    REQUIRE_CONNECTED_CHANNEL: bool = os.getenv("HELIOS_REQUIRE_CONNECTED_CHANNEL", "1") == "1"
    
    # LLM 对话生成 (G3)
    LLM_SPEECH_ENABLED: bool = os.getenv("HELIOS_LLM_SPEECH_ENABLED", "1") == "1"
    LLM_SPEECH_MODEL: str = os.getenv("HELIOS_LLM_SPEECH_MODEL", "")  # 空=使用全局模型

    # Internal thought (R02)
    INTERNAL_THINK_ENABLED: bool = os.getenv("HELIOS_INTERNAL_THINK_ENABLED", "1") == "1"
    INTERNAL_THINK_LLM_ENABLED: bool = os.getenv("HELIOS_INTERNAL_THINK_LLM_ENABLED", "1") == "1"
    INTERNAL_THINK_AUTOBIO_WRITE: bool = os.getenv("HELIOS_INTERNAL_THINK_AUTOBIO_WRITE", "1") == "1"
    INTERNAL_THINK_EPISODIC_WRITE: bool = os.getenv("HELIOS_INTERNAL_THINK_EPISODIC_WRITE", "0") == "1"
    INTERNAL_THINK_ICRI_THRESHOLD: float = float(os.getenv("HELIOS_INTERNAL_THINK_ICRI_THRESHOLD", "0.10"))
    INTERNAL_THINK_INTERVAL_SECONDS: float = float(os.getenv("HELIOS_INTERNAL_THINK_INTERVAL_SECONDS", "5.0"))
    INTERNAL_THINK_MAX_RESOURCE_PRESSURE: float = float(os.getenv("HELIOS_INTERNAL_THINK_MAX_RESOURCE_PRESSURE", "0.85"))

    # Multimodal channels
    CLI_ENABLED: bool = os.getenv("HELIOS_CLI_ENABLED", "0") == "1"
    CLI_USER_ID: str = os.getenv("HELIOS_CLI_USER_ID", "local_operator")
    CLI_SESSION_NAME: str = os.getenv("HELIOS_CLI_SESSION_NAME", "local_cli")
    OPTIONAL_CHANNEL_BOOTSTRAP_IDS: tuple[str, ...] = tuple(
        channel_id.strip()
        for channel_id in os.getenv("HELIOS_OPTIONAL_CHANNEL_BOOTSTRAP_IDS", "tts,cli,stt,vision").split(",")
        if channel_id.strip()
    )
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
        self.identity_governance = IdentityGovernance()
        self.identity_store: Optional[IdentityStore] = None
        
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
            autobiographical_store=self.autobio,
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
            internal_think_enabled=self.cfg.INTERNAL_THINK_ENABLED,
            llm_enabled=self.cfg.INTERNAL_THINK_LLM_ENABLED,
            api_key=self.cfg.LLM_API_KEY,
            base_url=self.cfg.LLM_BASE_URL,
            model=self.cfg.LLM_MODEL,
            memory_write_enabled=self.cfg.INTERNAL_THINK_AUTOBIO_WRITE,
            available_channels_provider=lambda: self._channel_gateway.get_runtime_snapshot().descriptors,
            available_behavior_schema_provider=lambda: self._build_internal_thought_behavior_schemas(),
        )
        self.thinking_integration.ICRI_THRESHOLD = self.cfg.INTERNAL_THINK_ICRI_THRESHOLD
        self.thinking_integration.GENERATION_INTERVAL = self.cfg.INTERNAL_THINK_INTERVAL_SECONDS
        self.thinking_integration.MAX_RESOURCE_PRESSURE = self.cfg.INTERNAL_THINK_MAX_RESOURCE_PRESSURE
        self.preconscious_policy = PreconsciousPolicy()
        self.last_internal_thought_trace: dict[str, object] = {}
        self.continuation_pressure: float = 0.0
        self.last_continuation_state: dict[str, object] = ContinuationPressureState().to_dict()
        self.last_recall_intent: str = ""
        self.last_memory_handoff: dict[str, object] = {}
        self.last_thought_cycle_result: dict[str, object] = {}
        self.current_stimuli: list[dict[str, object]] = []
        self.last_thought_gate_result: dict[str, object] = {}
        self.last_directed_retrieval_trace: dict[str, object] = {}
        self.last_identity_revision_trace: dict[str, object] = {}
        self.last_proactive_state: dict[str, object] = ProactiveObservabilityState().to_dict()
        self.proactive_counters: dict[str, int] = {
            "ticks_evaluated": 0,
            "ticks_with_drive": 0,
            "proactive_thought_sessions": 0,
            "mixed_thought_sessions": 0,
            "proposal_count": 0,
            "accepted_decisions": 0,
            "policy_rejections": 0,
            "suppressed_ticks": 0,
        }
        
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
        self._channel_gateway.register_runtime_channel(self._qq_channel, connect=False)
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
            timeout=self.cfg.LLM_SEC_TIMEOUT,
        )
        self.response_pipeline = ResponsePipeline(
            llm_speech=self.speech,
            memory_system=self.memory_system,
            autobio_store=self.autobio,
            model=self.cfg.LLM_MODEL,
            api_key=self.cfg.LLM_API_KEY,
            base_url=self.cfg.LLM_BASE_URL,
            channel_descriptor_provider=self._channel_gateway.get_channel_descriptors,
        )

        # ── Multimodal channels (Requirement 30, 31, 32) ──
        self.optional_channels: OptionalChannelRuntime = build_default_optional_channel_runtime(
            cfg=self.cfg,
            state_provider=self.get_state,
            history_provider=lambda user_id, conversation_key: self.response_pipeline.get_history(
                user_id,
                conversation_key=conversation_key or "",
            ),
            sec_evaluator=self.sec_evaluator,
            selected_channel_ids=self.cfg.OPTIONAL_CHANNEL_BOOTSTRAP_IDS,
            register_runtime_channel=self.register_runtime_channel,
            runtime_channel_active=self._channel_gateway.has_channel,
            deregister_runtime_channel=lambda channel_id, disconnect: self.deregister_runtime_channel(channel_id, disconnect=disconnect),
            bootstrap_logger=self.log,
        )

        # ── Behavior execution abstraction (Requirement 29) ──
        self.behavior_executor = BehaviorExecutor()
        self.behavior_executor.set_result_callback(self._on_behavior_result)
        self.limb_bridge = LimbDecisionBridge(self.behavior_executor)
        self.feedback_recorder = FeedbackRecorder(self.behavior_catalog)
        self.routing_policy = RoutingPreferencePolicy()
        self.policy_evaluator = PolicyEvaluator(
            require_connected_channel=self.cfg.REQUIRE_CONNECTED_CHANNEL,
        )
        self.execution_planner = ExecutionPlanner(self.policy_evaluator)
        self.behavior_specs = self.behavior_catalog.snapshot_by_name()
        self.temporal_dynamics = TemporalDynamics(tick_interval=self.cfg.TICK_INTERVAL)
        if not self.cfg.REQUIRE_CONNECTED_CHANNEL:
            self.log.warning(
                "Connected channel gating disabled by configuration; this is a debug-only runtime mode."
            )

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
        self.decisions_rejected_by_connectivity = 0
        self.decisions_failed_after_acceptance = 0
        
        # ── 记忆巩固调度 (Requirement 20) ──
        self._low_phi_counter: int = 0          # consecutive ticks with phi < 0.3
        self._ticks_since_consolidation: int = 0  # ticks elapsed since last consolidation
        
        self.log.debug("Helios 核心初始化完成")

    def _build_consciousness_snapshot(self) -> dict[str, object]:
        if self.phi_engine is None:
            return {"available": False}
        return {
            "available": True,
            "phi": round(float(getattr(self.phi_engine, "phi", 0.0) or 0.0), 4),
            "phi_raw": round(float(getattr(self.phi_engine, "_phi_raw", 0.0) or 0.0), 4),
            "label": str(getattr(getattr(self.phi_engine, "label", None), "value", "") or ""),
            "is_conscious": bool(getattr(self.phi_engine, "is_conscious", False)),
            "is_highly_conscious": bool(getattr(self.phi_engine, "is_highly_conscious", False)),
            "selected_alpha": round(float(getattr(self.phi_engine, "last_selected_alpha", 0.0) or 0.0), 4),
            "sources": {
                "sensory_integration": round(float(getattr(self.phi_engine, "sensory_integration", 0.0) or 0.0), 4),
                "emotional_coherence": round(float(getattr(self.phi_engine, "emotional_coherence", 0.0) or 0.0), 4),
                "temporal_depth": round(float(getattr(self.phi_engine, "temporal_depth", 0.0) or 0.0), 4),
                "self_reflection": round(float(getattr(self.phi_engine, "self_reflection", 0.0) or 0.0), 4),
                "global_ignition": round(float(getattr(self.phi_engine, "global_ignition", 0.0) or 0.0), 4),
            },
            "source_validity": {
                str(key): round(float(value or 0.0), 4)
                for key, value in dict(getattr(self.phi_engine, "_sources_valid", {}) or {}).items()
            },
            "history_tail": [
                round(float(value or 0.0), 4)
                for value in list(getattr(self.phi_engine, "history", []) or [])[-5:]
            ],
        }

    def _build_neurochem_snapshot(self) -> dict[str, object]:
        if self.neurochem is None:
            return {"available": False}

        def _scalar(value: object) -> float:
            current = getattr(value, "current", value)
            try:
                return float(current or 0.0)
            except (TypeError, ValueError):
                return 0.0

        dopamine = _scalar(getattr(self.neurochem, "dopamine", 0.0))
        opioids = _scalar(getattr(self.neurochem, "opioids", 0.0))
        oxytocin = _scalar(getattr(self.neurochem, "oxytocin", 0.0))
        cortisol = _scalar(getattr(self.neurochem, "cortisol", 0.0))
        gate = build_neurochem_gate(
            dopamine=dopamine,
            opioids=opioids,
            oxytocin=oxytocin,
            cortisol=cortisol,
        )
        return {
            "available": True,
            "raw": {
                "dopamine": round(dopamine, 4),
                "opioids": round(opioids, 4),
                "oxytocin": round(oxytocin, 4),
                "cortisol": round(cortisol, 4),
            },
            "gate": gate.to_dict(),
        }

    def _current_behavior_specs(self):
        self.behavior_specs = self.behavior_catalog.snapshot_by_name()
        return self.behavior_specs

    def _build_internal_thought_behavior_schemas(self):
        schemas: list[dict[str, object]] = []
        for spec in self._current_behavior_specs().values():
            op_name = "send" if getattr(spec, "execution_mode", "") == "channel" else "internal_execute"
            schemas.append(
                {
                    "behavior_name": str(getattr(spec, "name", "") or ""),
                    "op_name": op_name,
                    "parameter_schema": dict(getattr(spec, "parameter_schema", {}) or {}),
                    "allowed_channel_ids": list(getattr(spec, "allowed_channel_ids", []) or []),
                }
            )
        return schemas
    
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
        fh = logging.FileHandler(self._log_file_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        ))
        self.log.addHandler(fh)
        
        # 控制台
        ch = ConsoleSafeStreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(asctime)s %(message)s", datefmt="%H:%M:%S"
        ))
        stderr_encoding = (getattr(ch.stream, "encoding", "") or "").lower()
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
        personality_data = self.persistence.load_personality()
        identity_data = self.persistence.load_identity_store()
        if identity_data is None:
            bootstrap_traits = dict(personality_data.get("traits", {}) or {}) if personality_data is not None else self.personality._trait_dict()
            bootstrap_definition, bootstrap_source = self.identity_governance.load_bootstrap_definition(
                path=self.cfg.IDENTITY_BOOTSTRAP_PATH,
                personality_baseline=bootstrap_traits,
            )
            self.identity_store = self.identity_governance.bootstrap_identity_store(
                bootstrap_definition=bootstrap_definition,
                bootstrap_source=bootstrap_source,
            )
            self.identity_governance.apply_identity_store_to_personality(self.identity_store, self.personality)
            self.persistence.save_identity_store(self.identity_store)
            self.log.info("Identity bootstrap completed and locked")
        else:
            self.identity_store = IdentityStore.from_dict(identity_data)
            self.identity_governance.apply_identity_store_to_personality(self.identity_store, self.personality)
            self.log.debug("Identity store loaded; bootstrap skipped")

        # -- Personality runtime state --
        if personality_data is not None:
            self.personality.total_emotion_cycles = personality_data.get("total_emotion_cycles", 0)
            self.log.debug("Loaded personality runtime counters from disk; identity baseline remains locked")
        else:
            self.log.debug("No personality runtime state found; using identity baseline")
        
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
            if self.identity_store is not None:
                self.persistence.save_identity_store(self.identity_store)
        except Exception as e:
            self.log.warning(f"Failed to save identity store: {e}")
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
        imported_count = 0
        imports = self._seed_import_manifest.setdefault("imports", {})

        bootstrap_definition = {}
        if self.identity_store is not None:
            bootstrap_definition = dict(
                getattr(self.identity_store, "identity_metadata", {}).get("bootstrap_definition", {}) or {}
            )
        inline_seed_memories: list[object] = []
        for item in list(bootstrap_definition.get("identity_seed_memories", []) or []):
            if isinstance(item, str) and item.strip():
                inline_seed_memories.append(item.strip())
                continue
            if isinstance(item, dict) and str(item.get("summary", "") or "").strip():
                inline_seed_memories.append(dict(item))
        if inline_seed_memories:
            bootstrap_fingerprint = json.dumps(
                {
                    "bootstrap_version": bootstrap_definition.get("bootstrap_version", ""),
                    "identity_seed_memories": inline_seed_memories,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if imports.get("identity_bootstrap_inline") != bootstrap_fingerprint:
                imported = self.seed_importer.import_inline_memories(
                    inline_seed_memories,
                    source_label="identity_bootstrap",
                )
                if imported:
                    imports["identity_bootstrap_inline"] = bootstrap_fingerprint
                    imported_count += len(imported)
                    self._record_bootstrap_seed_import_trace(
                        fingerprint=bootstrap_fingerprint,
                        inline_seed_memories=inline_seed_memories,
                        imported_count=len(imported),
                        status="imported",
                    )
            elif self.identity_store is not None:
                self._record_bootstrap_seed_import_trace(
                    fingerprint=bootstrap_fingerprint,
                    inline_seed_memories=inline_seed_memories,
                    imported_count=0,
                    status="already_imported",
                )

        if not seeds_dir.exists():
            if imported_count:
                self.autobio.flush()
                self._save_seed_manifest()
                if self.identity_store is not None:
                    self.persistence.save_identity_store(self.identity_store)
                self.log.info("Imported %d seed memories from identity bootstrap", imported_count)
            return imported_count

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
            if self.identity_store is not None:
                self.persistence.save_identity_store(self.identity_store)
            self.log.info("Imported %d seed memories from configured sources", imported_count)

        return imported_count

    def _record_bootstrap_seed_import_trace(
        self,
        *,
        fingerprint: str,
        inline_seed_memories: list[object],
        imported_count: int,
        status: str,
    ) -> None:
        if self.identity_store is None:
            return
        entries: list[dict[str, object]] = []
        for item in inline_seed_memories:
            if isinstance(item, str):
                entries.append(
                    {
                        "summary": item,
                        "source": "identity_bootstrap",
                        "original_section": "",
                    }
                )
                continue
            if isinstance(item, dict):
                entries.append(
                    {
                        "summary": str(item.get("summary", "") or ""),
                        "source": str(item.get("source", "identity_bootstrap") or "identity_bootstrap"),
                        "original_section": str(item.get("original_section", "") or ""),
                    }
                )
        self.identity_store.identity_metadata["bootstrap_seed_import"] = {
            "status": status,
            "bootstrap_version": str(self.identity_store.bootstrap_version or ""),
            "fingerprint": fingerprint,
            "entry_count": len(entries),
            "imported_count": int(imported_count),
            "imported_at_ts": time.time(),
            "entries": entries,
        }

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
        all_stimuli: list[dict[str, object]] = []
        
        for source in self._event_sources:
            try:
                src_triggers = source.poll(state)
                # Merge using max-value semantics for overlapping keys
                for system, intensity in src_triggers.items():
                    merged_triggers[system] = max(
                        merged_triggers.get(system, 0.0), intensity
                    )
                all_messages.extend(source.get_messages())
                all_stimuli.extend(
                    dict(stimulus)
                    for stimulus in list(getattr(source, "get_stimuli", lambda: [])() or [])
                    if isinstance(stimulus, dict)
                )
            except Exception as e:
                self.log.warning(
                    "EventSource %s poll failed: %s",
                    type(source).__name__, e,
                )

        normalized_stimuli: list[dict[str, object]] = []
        if not all_stimuli:
            all_stimuli = [
                dict(msg.get("stimulus", {}) or {})
                for msg in all_messages
                if isinstance(msg.get("stimulus", {}), dict)
            ]

        for stimulus_payload in all_stimuli:
            stimulus = dict(stimulus_payload)
            source_channel = str(stimulus.get("source_channel_id", stimulus.get("channel_id", "unknown")) or "unknown")
            base_intensity = max(
                float(stimulus.get("stimulus_intensity", 0.0) or 0.0),
                float(dict(stimulus.get("cognitive_impact", {}) or {}).get("novelty", 0.0) or 0.0),
                max([float(value or 0.0) for value in dict(stimulus.get("metadata", {}) or {}).get("event_triggers", {}).values()] or [0.0]),
            )
            novelty_factor = self.habituation.get_novelty_factor(
                f"stimulus:{source_channel}",
                self.tick_count,
                arousal=max(float(getattr(state, "mood_arousal", 0.0) or 0.0), 0.0),
            )
            if base_intensity > 0.01:
                self.habituation.register_exposure(f"stimulus:{source_channel}", self.tick_count)
            stimulus.update(
                {
                    "source_channel_id": source_channel,
                    "source_kind": str(stimulus.get("source_kind", "external_message") or "external_message"),
                    "trigger_condition": str(stimulus.get("trigger_condition", "channel_input") or "channel_input"),
                    "stimulus_intensity": max(0.0, min(1.0, base_intensity * novelty_factor)),
                    "novelty_factor": round(float(novelty_factor), 4),
                    "sensitization_factor": round(float(self.habituation.sensitization_level), 4),
                }
            )
            normalized_stimuli.append(stimulus)

        state.current_stimuli = normalized_stimuli
        
        # Handle inbound channel side effects without hard-coding one transport owner.
        if all_messages:
            self._last_master_contact = time.time()
            self._separation_anxiety = 0.0
            for msg in all_messages:
                text = msg.get("text", "")
                user_id = msg.get("user_id", "")
                message_channel_id = str(msg.get("channel_id", "unknown") or "unknown")
                self.log.info(f"📩 {message_channel_id.upper()} [{user_id[:10]}]: {text[:60]}")
                
                # Auto-capture target_id only from QQ private messages.
                if message_channel_id == "qq" and not self.cfg.QQ_TARGET_ID and not msg.get("is_group", False):
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
        optional_channel_snapshot = self.optional_channels.get_runtime_snapshot()
        optional_channel_availability = {
            channel_id: channel_id in optional_channel_snapshot.runtime_active_channel_ids
            for channel_id in optional_channel_snapshot.spec_ids
        }

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
            identity_snapshot=self.identity_store.to_dict() if self.identity_store is not None else {},
            drive_dominant=getattr(self, '_last_drive_dominant', ''),
            drive_urgency=getattr(self, '_last_drive_urgency', 0.0),
            channel_availability=optional_channel_availability,
            rss_mb=self.stability_monitor.rss_mb,
            uptime_hours=self.stability_monitor.uptime_hours,
            continuation_pressure=self.continuation_pressure,
            continuation=ContinuationPressureState.from_payload(self.last_continuation_state),
            last_recall_intent=self.last_recall_intent,
            last_memory_handoff=dict(self.last_memory_handoff),
            last_thought_cycle_result=dict(self.last_thought_cycle_result),
            current_stimuli=list(self.current_stimuli),
            last_thought_gate_result=dict(self.last_thought_gate_result),
            proactive=ProactiveObservabilityState.from_payload(self.last_proactive_state),
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
        self.current_stimuli = list(getattr(state, "current_stimuli", []) or [])
        
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
        retrieval_plan = self.memory_system.build_retrieval_query_plan(
            current_stimuli=list(getattr(state, "current_stimuli", []) or []),
            recall_intent=str(getattr(state, "last_recall_intent", "") or ""),
            limit=3,
            metadata={
                "source": "thought_loop",
                "memory_handoff": dict(getattr(state, "last_memory_handoff", {}) or {}),
                "selected_memory_refs": list(dict(getattr(state, "last_memory_handoff", {}) or {}).get("selected_memory_refs", []) or []),
            },
        )
        directed_bundle = self.memory_system.directed_retrieval(
            retrieval_plan,
            valence=state.valence,
            arousal=state.arousal,
        )
        state.directed_memory_bundle = directed_bundle
        state.last_directed_retrieval_trace = {
            "query_text": retrieval_plan.query_text,
            "recall_intent": retrieval_plan.recall_intent,
            "target_tiers": list(retrieval_plan.target_tiers),
            "retrieval_strategy": retrieval_plan.retrieval_strategy,
            "metadata": dict(retrieval_plan.metadata),
            **directed_bundle.to_observability_payload(),
        }
        thought_result = self.thinking_integration.generate(state)
        thought = getattr(thought_result, "thought", None)
        self.continuation_pressure = max(0.0, min(float(getattr(state, "continuation_pressure", 0.0) or 0.0), 1.0))
        self.last_continuation_state = dict(getattr(state, "continuation_payload", lambda: {})() or {})
        self.last_recall_intent = str(getattr(state, "last_recall_intent", "") or "")
        self.last_memory_handoff = dict(getattr(state, "last_memory_handoff", {}) or {})
        thought_cycle_payload = dict(getattr(state, "last_thought_cycle_result", {}) or {})
        if not thought_cycle_payload:
            thought_cycle_payload = self._coerce_thought_cycle_result_payload(thought_result)
            if thought_cycle_payload:
                state.last_thought_cycle_result = dict(thought_cycle_payload)
        self.last_thought_cycle_result = thought_cycle_payload
        self.last_thought_gate_result = dict(getattr(state, "last_thought_gate_result", {}) or {})
        self.last_directed_retrieval_trace = dict(getattr(state, "last_directed_retrieval_trace", {}) or {})
        if bool(getattr(thought_result, "triggered", False)) and self.phi_engine:
            self.phi_engine.feed_dmn_from_thinking(
                self.thinking_manager.current_mode,
                thought_count=1,
            )
            icri = self.phi_engine.aggregate()
            state.icri = icri
            state.consciousness_label = self.phi_engine.label.value
            state.llm_temperature = ICRITemperatureMapper.map_temperature(state.icri)
            state.speech_style = ICRITemperatureMapper.get_style_label(state.icri)

        if thought is not None:
            self._process_identity_revision(thought, state)

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
                generated_thought=bool(getattr(thought_result, "triggered", False)),
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
                    generated_thought=bool(getattr(thought_result, "triggered", False)),
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
        thought_action_proposals = []
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
            direct_thought_action = self._build_thought_action_bridge_proposal(state=state, thought_result=thought_result)
            if direct_thought_action is not None:
                thought_action_proposals.append(direct_thought_action)
        else:
            self.preconscious_policy.observe_idle_tick(state=state, reason="no_preconscious_thought")
        self.last_internal_thought_trace = dict(getattr(state, "last_internal_thought_trace", {}))
        self.last_identity_revision_trace = dict(getattr(state, "last_identity_revision_trace", {}) or {})
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
                    channel_id=str(msg.get("channel_id") or ""),
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
                rendered_reply = None
                rendered_expression_profile = None
                channel_runtime_snapshot = self._channel_gateway.get_runtime_snapshot()
                ranked_reply_channels = self.routing_policy.rank_reply_channels(
                    message=msg,
                    channel_descriptors=channel_runtime_snapshot.descriptors,
                    channel_statuses=channel_runtime_snapshot.statuses,
                    qq_target_id=self.cfg.QQ_TARGET_ID,
                    personality_projection=getattr(state, "personality_projection", None),
                )
                direct_bridge_proposals, thought_action_proposals = self._consume_matching_thought_externalization_proposals(
                    msg=msg,
                    proposals=thought_action_proposals,
                )
                thought_externalization_proposals = list(direct_bridge_proposals)
                if thought_externalization_proposals:
                    self.log.debug(
                        "Passive thought externalization candidates: user=%s count=%d types=%s",
                        user_id,
                        len(thought_externalization_proposals),
                        [proposal.behavior_name for proposal in thought_externalization_proposals],
                    )
                if thought_externalization_proposals:
                    interaction_proposals = thought_externalization_proposals
                else:
                    interaction_proposals = []
                    self.log.debug(
                        "Passive external fallback suppressed: user=%s reason=thought_origin_action_required thought_type=%s",
                        user_id,
                        getattr(state, "last_thought_type", "") or "",
                    )
                if interaction_proposals:
                    self.log.debug(
                        "Passive trigger candidates: user=%s count=%d types=%s sec=%s",
                        user_id,
                        len(interaction_proposals),
                        [proposal.behavior_name for proposal in interaction_proposals],
                        {
                            "goal_relevance": round(float(sec_result.get("goal_relevance", 0.0)), 3),
                            "novelty": round(float(sec_result.get("novelty", 0.0)), 3),
                            "pleasantness": round(float(sec_result.get("pleasantness", 0.0)), 3),
                        },
                    )
                else:
                    self.log.debug(
                        "Passive trigger not fired: user=%s reason=no_interaction_proposal sec=%s text=%r",
                        user_id,
                        {
                            "goal_relevance": round(float(sec_result.get("goal_relevance", 0.0)), 3),
                            "novelty": round(float(sec_result.get("novelty", 0.0)), 3),
                            "pleasantness": round(float(sec_result.get("pleasantness", 0.0)), 3),
                        },
                        text[:120],
                    )
                for proposal in interaction_proposals:
                    channel_runtime_snapshot = self._channel_gateway.get_runtime_snapshot()
                    decision = self.execution_planner.plan(
                        proposal,
                        self._current_behavior_specs(),
                        channel_runtime_snapshot.descriptors,
                        channel_runtime_snapshot.statuses,
                    )
                    self._log_decision_summary("Passive", proposal, decision)
                    if not decision.accepted:
                        self.log.debug(
                            "Passive interaction proposal %s rejected: %s",
                            proposal.behavior_name,
                            decision.rejection_reason,
                        )
                        self._record_policy_rejection(state=state, proposal=proposal, decision=decision)
                        continue

                    self.log.debug(
                        "Passive trigger accepted: type=%s source=%s proposal_id=%s decision_id=%s channel=%s score=%.3f",
                        proposal.behavior_name,
                        proposal.source_module,
                        proposal.proposal_id,
                        decision.decision_id,
                        decision.selected_channel_id,
                        float(proposal.score_bundle.get("final", 0.0) or 0.0),
                    )

                    state.pending_reply = None
                    if decision.behavior_name == "reply_message":
                        finalized = self._finalize_passive_reply_decision(
                            decision=decision,
                            msg=msg,
                        )
                        if finalized is None:
                            self.log.debug(
                                "Reply decision accepted but execution payload missing: user=%s proposal_id=%s decision_id=%s",
                                user_id,
                                proposal.proposal_id,
                                decision.decision_id,
                            )
                            continue
                        reply = finalized.validated_params.get("outbound_text", "") or None
                        self.limb_bridge.enqueue_decision(finalized)
                    else:
                        self.limb_bridge.enqueue_decision(decision)

                    self._drain_behavior_executor(state)
                    if reply is None:
                        reply = state.pending_reply
                    if rendered_reply is None:
                        rendered_reply = state.pending_rendered_reply
                    if rendered_expression_profile is None:
                        rendered_expression_profile = dict(getattr(self, "_last_outbound_expression_profile", {}) or {})
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
                    rendered_reply=rendered_reply,
                    emotional_context=emotional_context,
                    sec_result=sec_result,
                    expression_profile=rendered_expression_profile,
                    conversation_key=self.response_pipeline._derive_conversation_key(msg),
                )
        
        # 10. 情感调节引擎 (with drive-regulation unification)
        from datetime import datetime
        hour = datetime.now().hour
        dominant_emotions = [name for name, _score in sorted((state.panksepp or {}).items(), key=lambda item: -item[1])[:3]]
        active_accepted = False
        active_stage = ""
        active_accepted_decision: Optional[ActionDecision] = None
        active_rejection_decision: Optional[ActionDecision] = None
        if thought_action_proposals:
            self.log.debug(
                "Thought bridge candidates: count=%d types=%s",
                len(thought_action_proposals),
                [proposal.behavior_name for proposal in thought_action_proposals],
            )
        for proposal in thought_action_proposals:
            channel_runtime_snapshot = self._channel_gateway.get_runtime_snapshot()
            decision = self.execution_planner.plan(
                proposal,
                self._current_behavior_specs(),
                channel_runtime_snapshot.descriptors,
                channel_runtime_snapshot.statuses,
            )
            self._log_decision_summary("ThoughtBridge", proposal, decision)
            if decision.accepted:
                self.log.debug(
                    "Thought bridge accepted: type=%s proposal_id=%s decision_id=%s channel=%s score=%.3f",
                    proposal.behavior_name,
                    proposal.proposal_id,
                    decision.decision_id,
                    decision.selected_channel_id,
                    float(proposal.score_bundle.get("final", 0.0) or 0.0),
                )
                state.last_action = decision.behavior_name
                self.limb_bridge.enqueue_decision(decision)
                active_accepted = True
                active_stage = "thought_bridge"
                break
            self.log.debug(
                "Thought bridge proposal rejected: type=%s reason=%s channel=%s",
                proposal.behavior_name,
                decision.rejection_reason,
                decision.selected_channel_id,
            )
            self._record_policy_rejection(state=state, proposal=proposal, decision=decision)

        def _resolve_active_channels(action: str) -> list[str]:
            channel_runtime_snapshot = self._channel_gateway.get_runtime_snapshot()
            return self.routing_policy.rank_active_channels(
                action=action,
                channel_descriptors=channel_runtime_snapshot.descriptors,
                channel_statuses=channel_runtime_snapshot.statuses,
                qq_target_id=self.cfg.QQ_TARGET_ID,
                personality_projection=state.personality_projection,
            )

        active_proposals = self.regulation.generate_action_proposals(
            panksepp=state.panksepp or {},
            valence=state.valence,
            hour_of_day=hour,
            tick=state.tick,
            timestamp=state.timestamp,
            candidate_channel_resolver=_resolve_active_channels,
            params={"tick": state.tick, "target_user_id": self.cfg.QQ_TARGET_ID},
            drive_urgency=self._last_drive_urgency,
            drive_dominant=self._last_drive_dominant,
            dominant_emotions=dominant_emotions,
            personality_projection=state.personality_projection,
            neurochem_gate=state.neurochem_gate,
            temporal_gate=state.temporal_gate,
        )
        assessment = self.regulation.last_assessment
        if assessment is None:
            self.log.debug("Active trigger not evaluated: reason=no_panksepp_state")
        elif not assessment.wants_regulation:
            self.log.debug(
                "Active trigger not fired: reason=%s deviations=%s dominant=%s drive=%s:%.3f",
                assessment.reason_summary or "not_selected",
                [(name, round(float(score), 3)) for name, score in assessment.deviations[:3]],
                state.dominant_system,
                self._last_drive_dominant,
                self._last_drive_urgency,
            )

        if active_proposals:
            self.log.debug(
                "Active trigger candidates: count=%d types=%s reason=%s",
                len(active_proposals),
                [proposal.behavior_name for proposal in active_proposals],
                (assessment.reason_summary if assessment else ""),
            )
        else:
            self.log.debug("Active trigger candidates: none")
        if not active_accepted:
            for proposal in active_proposals:
                channel_runtime_snapshot = self._channel_gateway.get_runtime_snapshot()
                decision = self.execution_planner.plan(
                    proposal,
                    self._current_behavior_specs(),
                    channel_runtime_snapshot.descriptors,
                    channel_runtime_snapshot.statuses,
                )
                self._log_decision_summary("Active", proposal, decision)
                if decision.accepted:
                    self.log.debug(
                        "Active trigger accepted: type=%s proposal_id=%s decision_id=%s channel=%s score=%.3f",
                        proposal.behavior_name,
                        proposal.proposal_id,
                        decision.decision_id,
                        decision.selected_channel_id,
                        float(proposal.score_bundle.get("final", 0.0) or 0.0),
                    )
                    state.last_action = decision.behavior_name
                    self.limb_bridge.enqueue_decision(decision)
                    active_accepted = True
                    active_stage = "active"
                    active_accepted_decision = decision
                    break
                else:
                    self.log.debug(
                        "Active proposal rejected: type=%s reason=%s channel=%s",
                        proposal.behavior_name,
                        decision.rejection_reason,
                        decision.selected_channel_id,
                    )
                    active_rejection_decision = decision
                    self._record_policy_rejection(state=state, proposal=proposal, decision=decision)

        if not active_accepted:
            if preconscious_proposals:
                self.log.debug(
                    "Preconscious fallback candidates: count=%d types=%s",
                    len(preconscious_proposals),
                    [proposal.behavior_name for proposal in preconscious_proposals],
                )
            else:
                self.log.debug("Preconscious fallback not fired: reason=no_preconscious_proposals")
            for proposal in preconscious_proposals:
                channel_runtime_snapshot = self._channel_gateway.get_runtime_snapshot()
                decision = self.execution_planner.plan(
                    proposal,
                    self._current_behavior_specs(),
                    channel_runtime_snapshot.descriptors,
                    channel_runtime_snapshot.statuses,
                )
                self._log_decision_summary("Preconscious", proposal, decision)
                if decision.accepted:
                    self.log.debug(
                        "Preconscious trigger accepted: type=%s proposal_id=%s decision_id=%s channel=%s",
                        proposal.behavior_name,
                        proposal.proposal_id,
                        decision.decision_id,
                        decision.selected_channel_id,
                    )
                    state.last_action = decision.behavior_name
                    self.limb_bridge.enqueue_decision(decision)
                    break
                self._record_policy_rejection(state=state, proposal=proposal, decision=decision)
                self.preconscious_policy.on_decision_rejected(proposal, decision)
                self.log.debug("Preconscious proposal rejected: %s", decision.rejection_reason)
                state.last_preconscious_trace = self.preconscious_policy.get_observability_snapshot()

        self._drain_behavior_executor(state)
        state.behavior_queue_depth = self.behavior_executor.queue_depth
        state.current_behavior = self.behavior_executor.current.action if self.behavior_executor.current else ""
        state.last_preconscious_trace = self.preconscious_policy.get_observability_snapshot()
        self.last_preconscious_trace = dict(state.last_preconscious_trace)
        state.proactive = ProactiveObservabilityState.from_payload(
            self._build_proactive_observability(
                state=state,
                assessment=assessment,
                active_proposals=active_proposals,
                active_stage=active_stage,
                accepted_decision=active_accepted_decision,
                rejection_decision=active_rejection_decision,
            )
        )
        self.last_proactive_state = state.proactive.to_dict()
        self._update_proactive_counters(self.last_proactive_state, self.last_thought_cycle_result)

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
                identity_snapshot=self.identity_store.to_dict() if self.identity_store is not None else {},
            )

        outbound_text = str(params.get("outbound_text", "") or "")
        outbound_metadata = dict(params.get("outbound_metadata", {}) or {})
        target_user_id = str(params.get("target_user_id", "") or "")
        self.log.debug(
            "owner_path_node=executor_enter action=%s channel_id=%s proposal_id=%s decision_id=%s source_type=%s origin_type=%s outbound_text_present=%s target_user_id_present=%s",
            action,
            channel_id,
            command.proposal_id if command is not None else "",
            command.decision_id if command is not None else "",
            str((command.provenance if command is not None else {}).get("source_type", "") or ""),
            str((command.provenance if command is not None else {}).get("origin_type", "") or ""),
            bool(outbound_text.strip()),
            bool(target_user_id.strip()),
        )
        state.pending_rendered_reply = None
        if command is not None:
            command_nested_provenance = dict(command.provenance.get("provenance", {}) or {})
            outbound_metadata.setdefault("op_name", command.op_name)
            outbound_metadata.setdefault("normalized_intensity", float(getattr(command, "normalized_intensity", 0.0) or 0.0))
            outbound_metadata.setdefault("outbound_intensity", float(getattr(command, "normalized_intensity", 0.0) or 0.0))
            outbound_metadata.setdefault("origin_type", str(command.provenance.get("origin_type", "") or ""))
            outbound_metadata.setdefault("origin_id", str(command.provenance.get("origin_id", "") or ""))
            outbound_metadata.setdefault(
                "session_kind",
                str(command.provenance.get("session_kind", command_nested_provenance.get("session_kind", "")) or ""),
            )
            outbound_metadata.setdefault(
                "dominant_disposition",
                str(
                    command.provenance.get(
                        "dominant_disposition",
                        command_nested_provenance.get("dominant_disposition", ""),
                    )
                    or ""
                ),
            )
            outbound_metadata.setdefault(
                "trigger_sources",
                [
                    str(item)
                    for item in list(
                        command.provenance.get(
                            "trigger_sources",
                            command_nested_provenance.get("trigger_sources", []),
                        )
                        or []
                    )
                    if str(item)
                ],
            )
        if outbound_text:
            if not channel_id:
                self.log.warning(
                    "Action execution rejected: behavior=%s selected_channel_id=%s selected_op=%s rejection_reason=missing_channel_binding",
                    action,
                    channel_id,
                    str((command.params if command else {}).get("selected_op", "") or ""),
                )
                return False
            ok = self._route_outbound_text(
                channel_id=channel_id,
                user_id=target_user_id,
                text=outbound_text,
                metadata=outbound_metadata,
                action_label=action,
                command=command,
            )
            if ok:
                state.pending_reply = outbound_text
                state.pending_rendered_reply = str(outbound_metadata.get("rendered_text", outbound_text) or outbound_text)
            return ok
        
        if action in master_actions:
            if not channel_id:
                self.log.warning(
                    "Action execution rejected: behavior=%s selected_channel_id=%s selected_op=%s rejection_reason=missing_channel_binding",
                    action,
                    channel_id,
                    str((command.params if command else {}).get("selected_op", "") or ""),
                )
                return False
            command_provenance = dict(command.provenance or {}) if command is not None else {}
            thought_origin_action = str(command_provenance.get("origin_type", "") or "") == "thought" or str(
                command_provenance.get("source_type", "") or ""
            ) == "thought_action_bridge"
            if thought_origin_action and not outbound_text:
                self.log.debug(
                    "owner_path_node=executor_blocked action=%s proposal_id=%s decision_id=%s reason=missing_outbound_text owner_path=%s",
                    action,
                    command.proposal_id if command is not None else "",
                    command.decision_id if command is not None else "",
                    str(command_provenance.get("owner_path", "thought_action_bridge") or "thought_action_bridge"),
                )
                self.feedback_recorder.record_execution_consistency_failure(
                    source_path=str(command_provenance.get("source_type", "thought_action_bridge") or "thought_action_bridge"),
                    proposal_id=command.proposal_id if command is not None else "",
                    decision_id=command.decision_id if command is not None else "",
                    behavior_id=command.behavior_id if command is not None else "",
                    channel_id=channel_id,
                    behavior_name=action,
                    op_name=command.op_name if command is not None else "",
                    normalized_intensity=float(getattr(command, "normalized_intensity", 0.0) or 0.0) if command is not None else 0.0,
                    provenance=command_provenance,
                    payload={
                        "reason": "missing_outbound_text",
                        "rejection_reason": "missing_outbound_text",
                        "owner_path": str(command_provenance.get("owner_path", "thought_action_bridge") or "thought_action_bridge"),
                    },
                )
                self.log.warning(
                    "Action execution rejected: behavior=%s selected_channel_id=%s selected_op=%s rejection_reason=missing_outbound_text owner_path=%s",
                    action,
                    channel_id,
                    command.op_name if command is not None else "",
                    str(command_provenance.get("owner_path", "thought_action_bridge") or "thought_action_bridge"),
                )
                return False
            text = self._generate_speech(action, state)
            state.pending_reply = text or None
            if text:
                ok = self._route_outbound_text(
                    channel_id=channel_id,
                    user_id=target_user_id,
                    text=text,
                    metadata=outbound_metadata,
                    action_label=action,
                    command=command,
                )
                if ok:
                    state.pending_rendered_reply = str(outbound_metadata.get("rendered_text", text) or text)
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
        metadata = metadata if isinstance(metadata, dict) else dict(metadata or {})
        resolved_channel = channel_id
        resolved_user_id = user_id
        self.log.debug(
            "owner_path_node=route_outbound_enter action=%s proposal_id=%s decision_id=%s channel_id=%s op_name=%s text_len=%d owner_path=%s",
            action_label,
            command.proposal_id if command else "",
            command.decision_id if command else "",
            resolved_channel,
            getattr(command, "op_name", "") or str(metadata.get("op_name", "") or ""),
            len(str(text or "")),
            str((command.provenance if command else {}).get("owner_path", metadata.get("owner_path", "")) or ""),
        )

        if not resolved_channel:
            self.log.warning(
                "Routing rejected: behavior=%s selected_channel_id=%s selected_op=%s rejection_reason=missing_channel_binding",
                action_label,
                resolved_channel,
                getattr(command, "op_name", "") or "",
            )
            self.decisions_failed_after_acceptance += 1
            self.feedback_recorder.record_execution_consistency_failure(
                source_path=str((command.provenance if command else {}).get("source_type", "channel")),
                behavior_name=action_label,
                proposal_id=command.proposal_id if command else "",
                decision_id=command.decision_id if command else "",
                behavior_id=command.behavior_id if command else "",
                channel_id=resolved_channel,
                op_name=command.op_name if command else "",
                normalized_intensity=float(getattr(command, "normalized_intensity", 0.0) or 0.0),
                provenance=dict(command.provenance) if command else {},
                payload={
                    "rejection_reason": "missing_channel_binding",
                    "user_id": resolved_user_id,
                    "text": text,
                    "message_metadata": metadata,
                },
            )
            return False

        if resolved_channel == "qq":
            if not resolved_user_id:
                self.decisions_failed_after_acceptance += 1
                self.log.warning(
                    "Routing rejected: behavior=%s selected_channel_id=%s selected_op=%s rejection_reason=missing_target_user_id",
                    action_label,
                    resolved_channel,
                    getattr(command, "op_name", "") or "",
                )
                self.feedback_recorder.record_execution_consistency_failure(
                    source_path=str((command.provenance if command else {}).get("source_type", "channel")),
                    behavior_name=action_label,
                    proposal_id=command.proposal_id if command else "",
                    decision_id=command.decision_id if command else "",
                    behavior_id=command.behavior_id if command else "",
                    channel_id=resolved_channel,
                    op_name=command.op_name if command else "",
                    normalized_intensity=float(getattr(command, "normalized_intensity", 0.0) or 0.0),
                    provenance=dict(command.provenance) if command else {},
                    payload={
                        "rejection_reason": "missing_target_user_id",
                        "user_id": resolved_user_id,
                        "text": text,
                        "message_metadata": metadata,
                    },
                )
                return False

        channel_status = self._channel_gateway.get_runtime_snapshot().statuses.get(resolved_channel, ChannelStatus.ERROR)
        if channel_status != ChannelStatus.CONNECTED:
            self.decisions_failed_after_acceptance += 1
            self.log.warning(
                "Routing consistency failure: behavior=%s selected_channel_id=%s selected_op=%s rejection_reason=channel_status:%s",
                action_label,
                resolved_channel,
                getattr(command, "op_name", "") or "",
                channel_status.value,
            )
            self.feedback_recorder.record_execution_consistency_failure(
                source_path=str((command.provenance if command else {}).get("source_type", "channel")),
                behavior_name=action_label,
                proposal_id=command.proposal_id if command else "",
                decision_id=command.decision_id if command else "",
                behavior_id=command.behavior_id if command else "",
                channel_id=resolved_channel,
                op_name=command.op_name if command else "",
                normalized_intensity=float(getattr(command, "normalized_intensity", 0.0) or 0.0),
                provenance=dict(command.provenance) if command else {},
                payload={
                    "rejection_reason": f"channel_status:{channel_status.value}",
                    "user_id": resolved_user_id,
                    "text": text,
                    "message_metadata": metadata,
                },
            )
            return False

        outbound_message = ChannelMessage(
            channel_id=resolved_channel,
            user_id=resolved_user_id,
            text=text,
            timestamp=time.time(),
            metadata=metadata,
            direction="outbound",
        )
        ok = self._channel_gateway.route_outbound(outbound_message)
        rendered_text = str(outbound_message.metadata.get("rendered_text", text) or text)
        expression_profile = dict(outbound_message.metadata.get("expression_profile", {}) or {})
        self._last_outbound_expression_profile = dict(expression_profile)
        self.log.debug(
            "owner_path_node=route_outbound_exit action=%s proposal_id=%s decision_id=%s channel_id=%s ok=%s rendered_text_present=%s",
            action_label,
            command.proposal_id if command else "",
            command.decision_id if command else "",
            resolved_channel,
            ok,
            bool(rendered_text.strip()),
        )
        if ok:
            if resolved_channel == "qq":
                self._last_master_contact = time.time()
                self._separation_anxiety = 0.0
            self.log.info(f"🗣️ [{action_label}] -> {resolved_channel}: {rendered_text[:60]}")
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
            op_name=command.op_name if command else "",
            normalized_intensity=float(getattr(command, "normalized_intensity", 0.0) or 0.0),
            provenance=dict(command.provenance) if command else {},
            original_text=text,
            rendered_text=rendered_text,
            expression_profile=expression_profile,
            metadata={
                "user_id": resolved_user_id,
                "text": text,
                "message_metadata": metadata,
            },
        )
        return ok

    def _record_policy_rejection(
        self,
        *,
        state: HeliosState,
        proposal: ActionProposal,
        decision: ActionDecision,
    ) -> None:
        if self._is_connectivity_rejection(decision):
            self.decisions_rejected_by_connectivity += 1
        proposal_snapshot = dict(decision.proposal_snapshot or {})
        proposal_provenance = dict(proposal_snapshot.get("provenance", {}) or {})
        merged_provenance = {
            **proposal_provenance,
            **dict(proposal.provenance),
            "origin_id": str(proposal.origin_id or proposal_provenance.get("origin_id", "") or ""),
            "origin_type": str(proposal.origin_type or proposal_provenance.get("origin_type", "") or ""),
            "source_type": str(proposal.source_type or proposal_provenance.get("source_type", "") or ""),
        }
        if proposal.source_type == "thought_action_bridge":
            self._record_thought_bridge_deferred_trace(
                state=state,
                proposal=proposal,
                decision=decision,
                merged_provenance=merged_provenance,
            )
        if proposal.source_type == "regulation" or str(merged_provenance.get("session_kind", "") or "") in {"proactive", "mixed"}:
            self._record_proactive_deferred_memory_trace(
                state=state,
                proposal=proposal,
                decision=decision,
                merged_provenance=merged_provenance,
            )
        self.feedback_recorder.record_policy_rejection(
            source_path=str(proposal.source_type or proposal.source_module or "policy"),
            proposal_id=proposal.proposal_id,
            decision_id=decision.decision_id,
            behavior_id=str(decision.behavior_snapshot.get("behavior_id", "") or ""),
            channel_id=decision.selected_channel_id,
            behavior_name=proposal.behavior_name,
            rejection_reason=decision.rejection_reason,
            op_name=proposal.op_name,
            normalized_intensity=decision.normalized_intensity,
            provenance=merged_provenance,
            payload={
                "owner_path": str(merged_provenance.get("owner_path", "") or ""),
                "requested_op": proposal.op_name,
                "candidate_channels": list(proposal.candidate_channels or []),
                "policy_trace": dict(decision.policy_trace),
                "proposal": proposal_snapshot,
            },
        )

    def _record_thought_bridge_deferred_trace(
        self,
        *,
        state: HeliosState,
        proposal: ActionProposal,
        decision: ActionDecision,
        merged_provenance: dict[str, object],
    ) -> None:
        trigger_sources = [
            str(item) for item in list(merged_provenance.get("trigger_sources", []) or []) if str(item)
        ]
        self.last_internal_thought_trace = {
            **dict(self.last_internal_thought_trace),
            "deferred": True,
            "write_result": "deferred",
            "output_destination": "internal_log,deferred_trace",
            "policy_rejection_reason": str(decision.rejection_reason or ""),
            "deferred_behavior": str(proposal.behavior_name or ""),
            "deferred_requested_op": str(proposal.op_name or ""),
            "deferred_candidate_channels": [str(item) for item in list(proposal.candidate_channels or []) if str(item)],
            "session_kind": str(merged_provenance.get("session_kind", "") or self.last_internal_thought_trace.get("session_kind", "")),
            "dominant_disposition": str(
                merged_provenance.get("dominant_disposition", "")
                or self.last_internal_thought_trace.get("dominant_disposition", "")
                or ""
            ),
            "trigger_sources": trigger_sources or list(self.last_internal_thought_trace.get("trigger_sources", []) or []),
            "deferred_provenance": {
                "owner_path": str(merged_provenance.get("owner_path", "") or ""),
                "origin_id": str(merged_provenance.get("origin_id", "") or ""),
                "source_type": str(merged_provenance.get("source_type", "") or ""),
            },
            "policy_trace": dict(decision.policy_trace or {}),
        }
        state.last_internal_thought_trace = dict(self.last_internal_thought_trace)
        self.last_thought_cycle_result = {
            **dict(self.last_thought_cycle_result),
            "deferred": True,
            "policy_rejection_reason": str(decision.rejection_reason or ""),
            "deferred_behavior": str(proposal.behavior_name or ""),
            "deferred_requested_op": str(proposal.op_name or ""),
            "session_kind": str(merged_provenance.get("session_kind", "") or self.last_thought_cycle_result.get("session_kind", "")),
            "dominant_disposition": str(
                merged_provenance.get("dominant_disposition", "")
                or self.last_thought_cycle_result.get("dominant_disposition", "")
                or ""
            ),
            "trigger_sources": trigger_sources or list(self.last_thought_cycle_result.get("trigger_sources", []) or []),
            "deferred_provenance": {
                "owner_path": str(merged_provenance.get("owner_path", "") or ""),
                "origin_id": str(merged_provenance.get("origin_id", "") or ""),
                "source_type": str(merged_provenance.get("source_type", "") or ""),
            },
        }
        state.last_thought_cycle_result = dict(self.last_thought_cycle_result)

    def _record_proactive_deferred_memory_trace(
        self,
        *,
        state: HeliosState,
        proposal: ActionProposal,
        decision: ActionDecision,
        merged_provenance: dict[str, object],
    ) -> None:
        trigger_sources: list[str] = []
        for item in list(merged_provenance.get("trigger_sources", []) or []):
            value = str(item or "")
            if value and value not in trigger_sources:
                trigger_sources.append(value)
        source_type = str(merged_provenance.get("source_type", "") or proposal.source_type or "")
        owner_path = str(merged_provenance.get("owner_path", "") or source_type or "policy")
        session_kind = str(merged_provenance.get("session_kind", "") or ("proactive" if source_type == "regulation" else ""))
        dominant_disposition = str(
            merged_provenance.get("dominant_disposition", "")
            or dict(getattr(state, "last_thought_cycle_result", {}) or {}).get("dominant_disposition", "")
            or dict(getattr(state, "last_internal_thought_trace", {}) or {}).get("dominant_disposition", "")
            or "defer"
        )
        narrative = (
            f"Deferred {session_kind or source_type or 'active'} {dominant_disposition} intent: "
            f"{str(proposal.behavior_name or 'unknown')} ({str(decision.rejection_reason or 'rejected')})"
        )
        moment = self.autobio.record(
            panksepp=dict(getattr(state, "panksepp", {}) or {}),
            valence=float(getattr(state, "valence", 0.0) or 0.0),
            arousal=float(getattr(state, "arousal", 0.0) or 0.0),
            dominant=str(getattr(state, "dominant_system", "") or getattr(state, "dominant", "") or ""),
            phi=float(getattr(state, "icri", 0.0) or self.last_icri or 0.0),
            mood_valence=float(getattr(state, "mood_valence", 0.0) or 0.0),
            mood_arousal=float(getattr(state, "mood_arousal", 0.0) or 0.0),
            mood_label=str(getattr(state, "mood_label", "") or ""),
            allostatic_load=float(getattr(state, "allostatic_load", 0.0) or 0.0),
            narrative=narrative,
            event_trigger=",".join(trigger_sources[:3]) or str(decision.rejection_reason or owner_path or "deferred"),
            cycle=int(getattr(state, "tick", 0) or 0),
            source="proactive_deferred_trace",
        )
        self.feedback_recorder.record_memory_write(
            source_path="proactive_deferred_trace",
            memory_type="autobiographical",
            memory_id=str(getattr(moment, "moment_id", "")),
            summary=str(getattr(moment, "narrative", "") or narrative),
            proposal_id=proposal.proposal_id,
            decision_id=decision.decision_id,
            behavior_id=str(decision.behavior_snapshot.get("behavior_id", "") or ""),
            payload={
                "source_type": source_type,
                "owner_path": owner_path,
                "origin_id": str(merged_provenance.get("origin_id", "") or ""),
                "session_kind": session_kind,
                "dominant_disposition": dominant_disposition,
                "trigger_sources": list(trigger_sources),
                "rejection_reason": str(decision.rejection_reason or ""),
                "behavior_name": str(proposal.behavior_name or ""),
                "requested_op": str(proposal.op_name or ""),
                "candidate_channels": [str(item) for item in list(proposal.candidate_channels or []) if str(item)],
                "tick": int(getattr(state, "tick", 0) or 0),
            },
        )
        if self.identity_store is not None:
            self.identity_governance.record_proactive_deferred_trace(
                store=self.identity_store,
                payload={
                    "recorded_at_ts": time.time(),
                    "tick": int(getattr(state, "tick", 0) or 0),
                    "source_type": source_type,
                    "owner_path": owner_path,
                    "origin_id": str(merged_provenance.get("origin_id", "") or ""),
                    "session_kind": session_kind,
                    "dominant_disposition": dominant_disposition,
                    "trigger_sources": list(trigger_sources),
                    "rejection_reason": str(decision.rejection_reason or ""),
                    "behavior_name": str(proposal.behavior_name or ""),
                    "requested_op": str(proposal.op_name or ""),
                    "candidate_channels": [str(item) for item in list(proposal.candidate_channels or []) if str(item)],
                },
            )
            self.persistence.save_identity_store(self.identity_store)

    def _build_proactive_observability(
        self,
        *,
        state: HeliosState,
        assessment: object,
        active_proposals: list[ActionProposal],
        active_stage: str,
        accepted_decision: Optional[ActionDecision],
        rejection_decision: Optional[ActionDecision],
    ) -> dict[str, object]:
        if assessment is None:
            return ProactiveObservabilityState(
                evaluated=False,
                reason_summary="no_panksepp_state",
                non_externalization_reason="no_panksepp_state",
            ).to_dict()

        candidates = list(getattr(assessment, "candidates", []) or [])
        candidate_actions = [
            str(getattr(candidate, "action_type", "") or "")
            for candidate in candidates[:5]
            if str(getattr(candidate, "action_type", "") or "")
        ]
        if not candidate_actions:
            candidate_actions = [proposal.behavior_name for proposal in list(active_proposals or []) if proposal.behavior_name]

        projection = resolve_personality_projection(projection=getattr(state, "personality_projection", None))
        neurochem_gate = getattr(state, "neurochem_gate", None)
        temporal_gate = getattr(state, "temporal_gate", None)

        social_outward_pressure = max(
            0.0,
            min(
                projection.social_initiation_bias * 0.28
                + projection.expressivity_bias * 0.18
                + float(getattr(neurochem_gate, "social_affinity", 0.0) or 0.0) * 0.32
                + float(getattr(temporal_gate, "expression_window", 0.0) or 0.0) * 0.22,
                1.5,
            ),
        )
        exploration_pressure = max(
            0.0,
            min(
                projection.novelty_bias * 0.26
                + float(getattr(neurochem_gate, "exploration_bias", 0.0) or 0.0) * 0.36
                + float(getattr(neurochem_gate, "initiative_bias", 0.0) or 0.0) * 0.12
                + float(getattr(temporal_gate, "exploration_pressure", 0.0) or 0.0) * 0.26,
                1.5,
            ),
        )
        internal_reflection_pressure = max(
            0.0,
            min(
                projection.persistence_bias * 0.18
                + projection.style("introspection") * 0.22
                + float(getattr(neurochem_gate, "soothing_bias", 0.0) or 0.0) * 0.24
                + float(getattr(temporal_gate, "restorative_pull", 0.0) or 0.0) * 0.24
                + float(getattr(neurochem_gate, "caution_bias", 0.0) or 0.0) * 0.12,
                1.5,
            ),
        )
        caution_pressure = max(
            0.0,
            min(
                projection.style("caution") * 0.18
                + float(getattr(neurochem_gate, "caution_bias", 0.0) or 0.0) * 0.52
                + float(getattr(temporal_gate, "restorative_pull", 0.0) or 0.0) * 0.30,
                1.5,
            ),
        )

        drive_sources: list[str] = []
        drive_dominant = str(getattr(assessment, "drive_dominant", "") or "")
        if drive_dominant:
            drive_sources.append(f"drive:{drive_dominant}")
        dominant_system = str(getattr(state, "dominant_system", "") or "")
        if dominant_system:
            drive_sources.append(f"emotion:{dominant_system}")
        if float(getattr(state, "boredom", 0.0) or 0.0) >= 0.2:
            drive_sources.append("temporal:boredom")
        if float(getattr(state, "novelty_hunger", 0.0) or 0.0) >= 0.2:
            drive_sources.append("temporal:novelty_hunger")
        if float(getattr(neurochem_gate, "initiative_bias", 0.0) or 0.0) >= 0.2:
            drive_sources.append("neurochem:initiative")
        if float(getattr(neurochem_gate, "exploration_bias", 0.0) or 0.0) >= 0.2:
            drive_sources.append("neurochem:exploration")
        if projection.initiative_bias >= 0.1:
            drive_sources.append("personality:initiative")
        if projection.social_initiation_bias >= 0.1:
            drive_sources.append("personality:social")
        if projection.style("introspection") >= 0.45:
            drive_sources.append("personality:introspection")

        wants_regulation = bool(getattr(assessment, "wants_regulation", False))
        reason_summary = str(getattr(assessment, "reason_summary", "") or "")
        non_externalization_reason = ""
        policy_rejection_reason = ""
        deferred = False
        accepted = active_stage == "active" and accepted_decision is not None

        if wants_regulation and not accepted:
            decision_reason = ""
            if rejection_decision is not None:
                decision_reason = str(getattr(rejection_decision, "rejection_reason", "") or "")
            if decision_reason:
                non_externalization_reason = decision_reason
                policy_rejection_reason = decision_reason
                deferred = True
            elif active_stage == "thought_bridge":
                non_externalization_reason = "preempted_by_thought_bridge"
                deferred = True
            elif not active_proposals:
                non_externalization_reason = "no_generated_proposals"
                deferred = True
        elif not wants_regulation:
            non_externalization_reason = reason_summary or "not_selected"

        dominant_disposition = ""
        if accepted and str(getattr(accepted_decision, "selected_channel_id", "") or ""):
            dominant_disposition = "externalize"
        elif policy_rejection_reason:
            dominant_disposition = "defer"
        elif str(getattr(assessment, "selected_action", "") or "") in {"browse", "search", "learn"}:
            dominant_disposition = "explore"
        elif str(getattr(assessment, "selected_action", "") or "") in {"reflect", "idle", "check_system"}:
            dominant_disposition = "reflect"
        else:
            disposition_scores = {
                "externalize": social_outward_pressure,
                "explore": exploration_pressure,
                "reflect": internal_reflection_pressure,
                "defer": caution_pressure + (0.12 if deferred else 0.0),
            }
            dominant_disposition = max(disposition_scores.items(), key=lambda item: item[1])[0]

        recommended_actions = list(candidate_actions)
        if not recommended_actions:
            recommended_actions = {
                "externalize": ["speak_share", "reply_message"],
                "explore": ["browse", "search", "learn"],
                "reflect": ["reflect", "check_system"],
                "defer": [str(getattr(assessment, "selected_action", "") or "")],
            }.get(dominant_disposition, [])
        recommended_actions = [item for item in recommended_actions if item]

        return ProactiveObservabilityState(
            evaluated=True,
            drive_score=float(getattr(assessment, "selected_score", 0.0) or 0.0),
            drive_dominant=str(getattr(assessment, "drive_dominant", "") or ""),
            drive_urgency=float(getattr(assessment, "drive_urgency", 0.0) or 0.0),
            drive_sources=drive_sources,
            wants_regulation=wants_regulation,
            selected_action=str(getattr(assessment, "selected_action", "") or ""),
            selected_score=float(getattr(assessment, "selected_score", 0.0) or 0.0),
            reason_summary=reason_summary,
            candidate_count=max(len(active_proposals or []), len(candidate_actions)),
            candidate_actions=candidate_actions,
            recommended_actions=recommended_actions,
            dominant_emotions=[
                str(item) for item in list(getattr(assessment, "dominant_emotions", []) or [])[:3] if str(item)
            ],
            deviation_sources=[
                str(name) for name, _score in list(getattr(assessment, "deviations", []) or [])[:3] if str(name)
            ],
            dominant_disposition=dominant_disposition,
            social_outward_pressure=social_outward_pressure,
            exploration_pressure=exploration_pressure,
            internal_reflection_pressure=internal_reflection_pressure,
            caution_pressure=caution_pressure,
            accepted=accepted,
            accepted_behavior=str(getattr(accepted_decision, "behavior_name", "") or "") if accepted else "",
            selected_channel_id=str(getattr(accepted_decision, "selected_channel_id", "") or "") if accepted else "",
            non_externalization_reason=non_externalization_reason,
            policy_rejection_reason=policy_rejection_reason,
            deferred=deferred,
        ).to_dict()

    def _coerce_thought_cycle_result_payload(self, thought_result: object) -> dict[str, object]:
        if thought_result is None:
            return {}
        to_state_payload = getattr(thought_result, "to_state_payload", None)
        if callable(to_state_payload):
            payload = to_state_payload()
            if isinstance(payload, dict):
                return dict(payload)
        if isinstance(thought_result, dict):
            return dict(thought_result)

        payload: dict[str, object] = {}
        for key in (
            "triggered",
            "trigger_reason",
            "session_kind",
            "dominant_disposition",
            "thought_type",
        ):
            value = getattr(thought_result, key, None)
            if value not in (None, ""):
                payload[key] = value
        trigger_sources = list(getattr(thought_result, "trigger_sources", []) or [])
        if trigger_sources:
            payload["trigger_sources"] = [str(item) for item in trigger_sources if str(item)]
        action_proposal = getattr(thought_result, "action_proposal", None)
        if isinstance(action_proposal, dict):
            payload["action_proposal"] = dict(action_proposal)
        return payload

    def _update_proactive_counters(
        self,
        proactive_state: dict[str, object],
        thought_cycle_result: Optional[dict[str, object]] = None,
    ) -> None:
        thought_cycle = dict(thought_cycle_result or {})
        if thought_cycle.get("triggered"):
            if thought_cycle.get("session_kind") == "proactive":
                self.proactive_counters["proactive_thought_sessions"] += 1
            elif thought_cycle.get("session_kind") == "mixed":
                self.proactive_counters["mixed_thought_sessions"] += 1
        if not proactive_state.get("evaluated"):
            return
        self.proactive_counters["ticks_evaluated"] += 1
        if proactive_state.get("wants_regulation"):
            self.proactive_counters["ticks_with_drive"] += 1
        self.proactive_counters["proposal_count"] += int(proactive_state.get("candidate_count", 0) or 0)
        if proactive_state.get("accepted"):
            self.proactive_counters["accepted_decisions"] += 1
        if proactive_state.get("policy_rejection_reason"):
            self.proactive_counters["policy_rejections"] += 1
        if proactive_state.get("wants_regulation") and not proactive_state.get("accepted") and proactive_state.get("non_externalization_reason"):
            self.proactive_counters["suppressed_ticks"] += 1

    def _finalize_passive_reply_decision(
        self,
        *,
        decision: ActionDecision,
        msg: dict,
    ) -> Optional[ActionDecision]:
        updated_params = dict(decision.validated_params or {})
        outbound_text = str(updated_params.get("outbound_text", "") or "").strip()
        if not outbound_text:
            proposal_snapshot = dict(decision.proposal_snapshot or {})
            proposal_provenance = dict(proposal_snapshot.get("provenance", {}) or {})
            self.feedback_recorder.record_execution_consistency_failure(
                source_path=str(proposal_provenance.get("source_type", "passive_reply") or "passive_reply"),
                proposal_id=decision.proposal_id,
                decision_id=decision.decision_id,
                behavior_id=str(decision.behavior_snapshot.get("behavior_id", "") or ""),
                channel_id=decision.selected_channel_id,
                behavior_name=decision.behavior_name,
                op_name=decision.selected_op,
                normalized_intensity=decision.normalized_intensity,
                provenance=proposal_provenance,
                payload={
                    "reason": "missing_outbound_text",
                    "message_user_id": str(msg.get("user_id", "") or ""),
                    "message_channel_id": str(msg.get("channel_id", "") or ""),
                },
            )
            return None

        updated_params.setdefault("target_user_id", msg.get("user_id", "unknown"))
        updated_params["outbound_metadata"] = {
            **dict(updated_params.get("outbound_metadata", {}) or {}),
            "message_id": msg.get("message_id", ""),
            "is_group": msg.get("is_group", False),
            "group_id": msg.get("group_id", ""),
        }
        return replace(decision, validated_params=updated_params)

    @staticmethod
    def _is_connectivity_rejection(decision: ActionDecision) -> bool:
        filtered = dict(decision.policy_trace.get("filtered_out_reasons", {}) or {})
        if any(str(reason).startswith("channel_status:") for reason in filtered.values()):
            return True
        return decision.rejection_reason in {"channel_disconnected", "channel_status_unknown"}

    @staticmethod
    def _proposal_targets_message(proposal: ActionProposal, msg: dict) -> bool:
        target_user_id = str(proposal.parameters.get("target_user_id", "") or proposal.op_params.get("target_user_id", "") or "")
        msg_user_id = str(msg.get("user_id", "") or "")
        msg_channel_id = str(msg.get("channel_id", "") or "")
        candidate_channels = [str(item) for item in list(proposal.candidate_channels or []) if str(item)]
        if target_user_id and msg_user_id and target_user_id != msg_user_id:
            return False
        if msg_channel_id and candidate_channels and msg_channel_id not in candidate_channels:
            return False
        return True

    def _consume_matching_thought_externalization_proposals(
        self,
        *,
        msg: dict,
        proposals: list[ActionProposal],
    ) -> tuple[list[ActionProposal], list[ActionProposal]]:
        matched: list[ActionProposal] = []
        remaining: list[ActionProposal] = []
        for proposal in list(proposals or []):
            is_thought_externalization = (
                proposal.source_type == "thought_action_bridge"
                and proposal.origin_type == "thought"
                and proposal.intent_type == "thought_action"
                and proposal.op_name == "send"
            )
            if is_thought_externalization and self._proposal_targets_message(proposal, msg):
                matched.append(proposal)
                continue
            remaining.append(proposal)
        return matched, remaining

    @staticmethod
    def _build_thought_action_bridge_proposal(
        *,
        state: HeliosState,
        thought_result,
    ) -> ActionProposal | None:
        thought_action = ThoughtActionProposal.from_payload(getattr(thought_result, "action_proposal", None))
        if thought_action is None:
            return None
        payload = thought_action.to_dict()

        params = dict(thought_action.params)
        channel_constraints = dict(thought_action.channel_constraints)
        governance_hints = dict(thought_action.governance_hints)
        candidate_channels = [
            str(item)
            for item in list(channel_constraints.get("candidate_channels", []) or payload.get("candidate_channels", []) or [])
            if str(item)
        ]
        constraints: dict[str, object] = {}
        if thought_action.scope == "internal":
            constraints["execution_scope"] = "internal"
        if channel_constraints.get("execution_scope"):
            constraints["execution_scope"] = str(channel_constraints.get("execution_scope") or "")
        if channel_constraints.get("requires_target_user"):
            constraints["requires_target_user"] = True
        if governance_hints.get("requires_deliberate_review"):
            constraints["requires_deliberate_review"] = True

        origin_id = str(thought_action.origin_thought_id or getattr(thought_result, "thought_id", "") or "")
        thought_type = str(thought_action.thought_type or getattr(thought_result, "thought_type", "") or "")
        reason_trace = [str(item) for item in list(thought_action.reason_trace or []) if str(item)]
        session_kind = str(
            getattr(thought_result, "session_kind", "")
            or dict(getattr(state, "last_thought_cycle_result", {}) or {}).get("session_kind", "")
            or dict(getattr(state, "last_thought_gate_result", {}) or {}).get("session_kind", "")
            or "reactive"
        )
        dominant_disposition = str(
            getattr(thought_result, "dominant_disposition", "")
            or dict(getattr(state, "last_thought_cycle_result", {}) or {}).get("dominant_disposition", "")
            or dict(getattr(state, "last_thought_gate_result", {}) or {}).get("dominant_disposition", "")
            or dict(getattr(state, "last_internal_thought_trace", {}) or {}).get("dominant_disposition", "")
            or getattr(getattr(state, "proactive", None), "dominant_disposition", "")
            or ""
        )
        trigger_sources = [
            str(item)
            for item in list(
                getattr(thought_result, "trigger_sources", None)
                or dict(getattr(state, "last_thought_cycle_result", {}) or {}).get("trigger_sources", [])
                or dict(getattr(state, "last_thought_gate_result", {}) or {}).get("trigger_sources", [])
                or dict(getattr(state, "last_internal_thought_trace", {}) or {}).get("trigger_sources", [])
                or []
            )
            if str(item)
        ]
        outbound_intensity = max(0.0, min(1.0, float(thought_action.outbound_intensity or 0.0)))
        score = max(0.0, min(1.0, float(thought_action.score or 0.0)))

        return ActionProposal(
            proposal_id=f"proposal::thought_action_bridge::{origin_id or int(getattr(state, 'timestamp', time.time()) * 1000)}",
            source_type="thought_action_bridge",
            source_module="thinking_integration",
            origin_type="thought",
            origin_id=origin_id,
            intent_type="thought_action",
            behavior_name=thought_action.behavior_name,
            op_name=thought_action.preferred_op,
            op_params=dict(params),
            outbound_intensity=outbound_intensity,
            reason_summary="thought-origin action proposal emitted directly from ThoughtCycleResult",
            score_bundle={"final": score},
            constraints=constraints,
            suggested_modalities=["internal"] if thought_action.preferred_op == "internal_execute" else ["text"],
            candidate_channels=candidate_channels,
            parameters={"tick": int(getattr(state, "tick", 0)), **params},
            provenance={
                "owner_path": "thought_action_bridge",
                "owner_status": "primary",
                "origin_id": origin_id,
                "origin_type": "thought",
                "thought_type": thought_type,
                "requested_op": thought_action.preferred_op,
                "scope": thought_action.scope,
                "session_kind": session_kind,
                "dominant_disposition": dominant_disposition,
                "trigger_sources": trigger_sources,
                "reason_trace": reason_trace,
                "source_type": "thought_action_bridge",
            },
            created_at_tick=int(getattr(state, "tick", 0)),
            created_at_ts=float(getattr(state, "timestamp", time.time())),
        )

    def _log_decision_summary(self, stage: str, proposal: ActionProposal, decision: ActionDecision) -> None:
        policy_trace = dict(getattr(decision, "policy_trace", {}) or {})
        routing_trace = dict(policy_trace.get("routing_trace", {}) or {})
        candidate_order = list(routing_trace.get("candidate_order", []) or policy_trace.get("candidate_channels", []) or [])
        self.log.debug(
            "%s decision: behavior=%s accepted=%s source_type=%s source_module=%s proposal_id=%s decision_id=%s channel=%s op=%s score=%.3f requested_op=%s candidate_order=%s selection_reason=%s rejection_reason=%s executor_ready=%s",
            stage,
            proposal.behavior_name,
            bool(decision.accepted),
            proposal.source_type,
            proposal.source_module,
            proposal.proposal_id,
            decision.decision_id,
            decision.selected_channel_id,
            decision.selected_op,
            float(proposal.score_bundle.get("final", 0.0) or 0.0),
            proposal.op_name,
            candidate_order,
            routing_trace.get("selection_reason", ""),
            decision.rejection_reason,
            routing_trace.get("executor_ready", False),
        )

    def _drain_behavior_executor(self, state: HeliosState):
        current = self.behavior_executor.current
        if current is None:
            return

        self.log.debug(
            "owner_path_node=executor_dispatch action=%s proposal_id=%s decision_id=%s channel_id=%s op_name=%s source_type=%s",
            current.action,
            current.proposal_id,
            current.decision_id,
            current.channel_id,
            current.op_name,
            str(current.provenance.get("source_type", "") or ""),
        )

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
        self.log.debug(
            "owner_path_node=executor_result action=%s proposal_id=%s decision_id=%s success=%s tick=%s source_type=%s",
            command.action,
            command.proposal_id,
            command.decision_id,
            bool(result.get("success", False)),
            int(result.get("tick", 0) or 0),
            str(command.provenance.get("source_type", "") or ""),
        )
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
            source_path=str(getattr(thought, "source_path", "internal_thought_llm") or "internal_thought_llm"),
            memory_type="autobiographical",
            memory_id=str(getattr(moment, "moment_id", "")),
            summary=str(getattr(moment, "narrative", "") or thought.content),
            payload={
                "thought_type": getattr(thought, "type", ""),
                "triggered_by": getattr(thought, "triggered_by", ""),
                "llm_used": bool(getattr(thought, "llm_used", False)),
                "fallback_used": bool(getattr(thought, "fallback_used", False)),
                "behavior_name": str(getattr(thought, "metadata", {}).get("behavior_name", "think_message")),
                "tick": state.tick,
            },
        )
        if self.cfg.INTERNAL_THINK_EPISODIC_WRITE:
            episodic_item = self.memory_system.remember(
                summary=str(getattr(moment, "narrative", "") or thought.content),
                scene="internal_thought",
                semantic_text=str(getattr(thought, "type", "") or "internal_thought"),
                decision="think_message",
                valence=state.valence,
                arousal=state.arousal,
                phi=state.icri,
                content={
                    "thought_type": getattr(thought, "type", ""),
                    "triggered_by": getattr(thought, "triggered_by", ""),
                    "source_path": getattr(thought, "source_path", "internal_thought_llm"),
                    "llm_used": bool(getattr(thought, "llm_used", False)),
                    "fallback_used": bool(getattr(thought, "fallback_used", False)),
                },
            )
            self.feedback_recorder.record_memory_write(
                source_path=str(getattr(thought, "source_path", "internal_thought_llm") or "internal_thought_llm"),
                memory_type="episodic",
                memory_id=str(getattr(episodic_item, "id", "")),
                summary=str(getattr(episodic_item, "summary", "") or thought.content),
                payload={
                    "thought_type": getattr(thought, "type", ""),
                    "triggered_by": getattr(thought, "triggered_by", ""),
                    "behavior_name": "think_message",
                    "tick": state.tick,
                },
            )

    def _process_identity_revision(self, thought, state: HeliosState) -> None:
        proposal_payload = dict(getattr(thought, "metadata", {}).get("self_revision_proposal", {}) or {})
        if not proposal_payload or self.identity_store is None:
            state.last_identity_revision_trace = {}
            return

        proposal = self.identity_governance.build_proposal_from_payload(proposal_payload)
        if proposal is None:
            state.last_identity_revision_trace = {
                "proposal_detected": True,
                "result": "rejected",
                "reason": "invalid_self_revision_payload",
            }
            return

        record = self.identity_governance.apply_self_revision(store=self.identity_store, proposal=proposal)
        if proposal.revision_type == "personality_adjustment" and record.result == "accepted":
            self.identity_governance.apply_identity_store_to_personality(self.identity_store, self.personality)
        self.persistence.save_identity_store(self.identity_store)
        self.feedback_recorder.record_identity_revision(
            source_path=str(getattr(thought, "source_path", "internal_thought_llm") or "internal_thought_llm"),
            revision_id=record.revision_id,
            origin_thought_id=record.origin_thought_id,
            result=record.result,
            payload={
                "requested_change": dict(record.requested_change),
                "applied_change": dict(record.applied_change),
                "reason_trace": list(record.reason_trace),
            },
        )
        state.last_identity_revision_trace = record.to_dict()

    def get_runtime_channel(self, channel_id: str) -> InputChannel | OutputChannel | None:
        return self._channel_gateway.get_channel(channel_id)

    def register_runtime_channel(
        self,
        channel: InputChannel | OutputChannel,
        *,
        connect: bool = True,
        evaluator: object | None = None,
    ) -> ChannelManagementResult:
        return self._channel_gateway.register_runtime_channel(
            channel,
            connect=connect,
            evaluator=evaluator,
        )

    def deregister_runtime_channel(self, channel_id: str, *, disconnect: bool = True) -> ChannelManagementResult:
        return self._channel_gateway.deregister_runtime_channel(channel_id, disconnect=disconnect)

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
                identity_snapshot=self.identity_store.to_dict() if self.identity_store is not None else {},
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

            # 统一人格描述符
            personality_descriptor, personality_trace = build_personality_contract(
                projection=getattr(state, "personality_projection", None),
                traits=state.personality_traits or self.personality._trait_dict(),
                identity_store=getattr(state, "identity_snapshot", {}) or {},
                source_path="active_speech_generation",
            )

            current_stimuli = tuple(getattr(state, "current_stimuli", None) or ())
            current_user_text = ""
            current_user_id = ""
            for stimulus in reversed(current_stimuli):
                payload = dict(dict(stimulus).get("payload", {}) or {})
                text = str(payload.get("text", "") or "").strip()
                user_id = str(payload.get("user_id", "") or "").strip()
                if text:
                    current_user_text = text
                if user_id:
                    current_user_id = user_id
                if current_user_text and current_user_id:
                    break

            relationship_history_count = 0
            if current_user_id:
                try:
                    relationship_history_count = len(self.response_pipeline.get_history(current_user_id))
                except Exception as exc:
                    self.log.debug("读取关系历史失败: %s", exc)
            relationship_stage = "stranger" if relationship_history_count < 3 else "familiar"

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
                current_user_text=current_user_text,
                current_stimuli=current_stimuli,
                relationship_stage=relationship_stage,
                relationship_history_count=relationship_history_count,
                personality_summary=personality_descriptor.persona_text_summary,
                personality_influence_trace=personality_trace.to_dict(),
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
        optional_channel_snapshot = self.optional_channels.get_runtime_snapshot()
        bootstrap_summary = optional_channel_snapshot.last_bootstrap_summary
        
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
            "identity": {
                "initialized": bool(getattr(self.identity_store, "initialized", False)),
                "bootstrap_version": str(getattr(self.identity_store, "bootstrap_version", "") or ""),
                "self_imprint": str(getattr(self.identity_store, "self_imprint", "") or ""),
                "self_definition": str(getattr(self.identity_store, "self_definition", "") or ""),
                "identity_narrative": str(
                    dict(getattr(self.identity_store, "identity_metadata", {}) or {})
                    .get("autobiographical_identity_narrative", {})
                    .get("summary", "")
                    or ""
                ),
                "current_revision": str(getattr(self.identity_store, "current_revision", "") or ""),
                "revision_history_len": len(getattr(self.identity_store, "revision_history", []) or []),
                "latest_revision": dict(self.last_identity_revision_trace),
                "proactive_deferred_trace_count": int(
                    dict(getattr(self.identity_store, "identity_metadata", {}) or {})
                    .get("proactive_deferred_trace_summary", {})
                    .get("total_deferred_traces", 0)
                    or 0
                ),
                "latest_proactive_deferred_trace": dict(
                    dict(getattr(self.identity_store, "identity_metadata", {}) or {})
                    .get("proactive_deferred_trace_summary", {})
                    .get("latest_trace", {})
                    or {}
                ),
                "proactive_governance_signal": dict(
                    dict(getattr(self.identity_store, "identity_metadata", {}) or {})
                    .get("proactive_governance_signal", {})
                    or {}
                ),
            },
            "autobio_moments": autobio_stats.get("total_moments", 0),
            "autobio_chapters": autobio_stats.get("total_chapters", 0),
            "memory": {
                "working_items": mem_stats["working_items"],
                "episodic_items": mem_stats["episodic_items"],
                "semantic_facts": mem_stats["semantic_facts"],
                "autobio_moments": mem_stats["autobio_moments"],
                "episodic_capacity": self.memory_system.episodic.capacity,
                "working_capacity": self.memory_system.working.capacity,
                "public_tiers": [
                    {
                        "tier_name": tier.tier_name,
                        "implementation_scopes": list(tier.implementation_scopes),
                        "capacity_limit": tier.capacity_limit,
                        "decay_policy": tier.decay_policy,
                        "primary_use": tier.primary_use,
                        "retrieval_role": tier.retrieval_role,
                        "boundary_rule": tier.boundary_rule,
                    }
                    for tier in self.memory_system.get_public_memory_tiers()
                ],
                "tier_snapshots": [
                    {
                        "tier_name": snapshot.tier_name,
                        "item_count": snapshot.item_count,
                        "capacity_limit": snapshot.capacity_limit,
                        "boundary_ok": snapshot.boundary_ok,
                        "implementation_scopes": list(snapshot.implementation_scopes),
                    }
                    for snapshot in self.memory_system.get_public_memory_tier_snapshots()
                ],
            },
            "continuation_pressure": round(self.continuation_pressure, 4),
            "continuation": dict(self.last_continuation_state),
            "recall_intent": self.last_recall_intent,
            "memory_handoff": dict(self.last_memory_handoff),
            "current_stimuli": list(self.current_stimuli),
            "thought_gate": dict(self.last_thought_gate_result),
            "thought_cycle": dict(self.last_thought_cycle_result),
            "directed_retrieval": dict(self.last_directed_retrieval_trace),
            "internal_thought": dict(self.last_internal_thought_trace),
            "proactive": {
                **dict(self.last_proactive_state),
                "counters": dict(self.proactive_counters),
            },
            "sec_evaluator": self.sec_evaluator.get_state() if hasattr(self.sec_evaluator, "get_state") else {},
            "optional_channels": {
                "factory_ids": list(optional_channel_snapshot.factory_ids),
                "spec_ids": list(optional_channel_snapshot.spec_ids),
                "runtime_active_channel_ids": list(optional_channel_snapshot.runtime_active_channel_ids),
                "bootstrap_summary": {
                    "active_channel_ids": list(bootstrap_summary.active_channel_ids),
                    "dormant_channel_ids": list(bootstrap_summary.dormant_channel_ids),
                    "failed_channel_ids": list(bootstrap_summary.failed_channel_ids),
                }
                if bootstrap_summary is not None
                else None,
            },
            "regulation": self.regulation.get_state(),
            "preconscious": self.preconscious_policy.get_observability_snapshot(),
            "routing": {
                "require_connected_channel": self.cfg.REQUIRE_CONNECTED_CHANNEL,
                "decisions_rejected_by_connectivity": self.decisions_rejected_by_connectivity,
                "decisions_failed_after_acceptance": self.decisions_failed_after_acceptance,
            },
            "consciousness": self._build_consciousness_snapshot(),
            "neurochem": self._build_neurochem_snapshot(),
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
    cli_group = parser.add_mutually_exclusive_group()
    cli_group.add_argument("--cli", dest="cli_enabled", action="store_true", help="启用 terminal CLI channel")
    cli_group.add_argument("--no-cli", dest="cli_enabled", action="store_false", help="禁用 terminal CLI channel")
    parser.set_defaults(cli_enabled=None)
    parser.add_argument("--cli-user-id", type=str, default=None, help="覆盖 CLI session 的 user_id")
    parser.add_argument("--cli-session-name", type=str, default=None, help="覆盖 CLI session 名称")
    args = parser.parse_args()
    
    config = HeliosConfig()
    if args.interval:
        config.TICK_INTERVAL = args.interval
    if args.cli_enabled is not None:
        config.CLI_ENABLED = bool(args.cli_enabled)
    if args.cli_user_id:
        config.CLI_USER_ID = str(args.cli_user_id)
    if args.cli_session_name:
        config.CLI_SESSION_NAME = str(args.cli_session_name)
    
    helios = Helios(config)
    helios.start()


if __name__ == "__main__":
    main()

