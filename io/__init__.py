"""
io/ — Helios I/O 层

包含 LLM SEC 评估、对话历史管理、响应管道、QQ 接口等。
"""

import importlib.util
import sys
from pathlib import Path

# Load modules directly to avoid 'io' name conflict with Python stdlib
_pkg_dir = Path(__file__).parent

_ch_mod_name = "helios_io_conversation_history"
if _ch_mod_name not in sys.modules:
    _ch_spec = importlib.util.spec_from_file_location(
        _ch_mod_name, str(_pkg_dir / "conversation_history.py")
    )
    _ch_mod = importlib.util.module_from_spec(_ch_spec)
    sys.modules[_ch_mod_name] = _ch_mod
    _ch_spec.loader.exec_module(_ch_mod)
else:
    _ch_mod = sys.modules[_ch_mod_name]

_rp_mod_name = "helios_io_response_pipeline"
if _rp_mod_name not in sys.modules:
    _rp_spec = importlib.util.spec_from_file_location(
        _rp_mod_name, str(_pkg_dir / "response_pipeline.py")
    )
    _rp_mod = importlib.util.module_from_spec(_rp_spec)
    sys.modules[_rp_mod_name] = _rp_mod
    _rp_spec.loader.exec_module(_rp_mod)
else:
    _rp_mod = sys.modules[_rp_mod_name]

_it_mod_name = "helios_io_icri_temperature"
if _it_mod_name not in sys.modules:
    _it_spec = importlib.util.spec_from_file_location(
        _it_mod_name, str(_pkg_dir / "icri_temperature.py")
    )
    _it_mod = importlib.util.module_from_spec(_it_spec)
    sys.modules[_it_mod_name] = _it_mod
    _it_spec.loader.exec_module(_it_mod)
else:
    _it_mod = sys.modules[_it_mod_name]

_limb_mod_name = "helios_io_limb"
if _limb_mod_name not in sys.modules:
    _limb_spec = importlib.util.spec_from_file_location(
        _limb_mod_name, str(_pkg_dir / "limb.py")
    )
    _limb_mod = importlib.util.module_from_spec(_limb_spec)
    sys.modules[_limb_mod_name] = _limb_mod
    _limb_spec.loader.exec_module(_limb_mod)
else:
    _limb_mod = sys.modules[_limb_mod_name]

_ldb_mod_name = "helios_io_limb_decision_bridge"
if _ldb_mod_name not in sys.modules:
    _ldb_spec = importlib.util.spec_from_file_location(
        _ldb_mod_name, str(_pkg_dir / "limb_decision_bridge.py")
    )
    _ldb_mod = importlib.util.module_from_spec(_ldb_spec)
    sys.modules[_ldb_mod_name] = _ldb_mod
    _ldb_spec.loader.exec_module(_ldb_mod)
else:
    _ldb_mod = sys.modules[_ldb_mod_name]

_tts_mod_name = "helios_io_tts"
if _tts_mod_name not in sys.modules:
    _tts_spec = importlib.util.spec_from_file_location(
        _tts_mod_name, str(_pkg_dir / "io_tts.py")
    )
    _tts_mod = importlib.util.module_from_spec(_tts_spec)
    sys.modules[_tts_mod_name] = _tts_mod
    _tts_spec.loader.exec_module(_tts_mod)
else:
    _tts_mod = sys.modules[_tts_mod_name]

_stt_mod_name = "helios_io_stt"
if _stt_mod_name not in sys.modules:
    _stt_spec = importlib.util.spec_from_file_location(
        _stt_mod_name, str(_pkg_dir / "io_stt.py")
    )
    _stt_mod = importlib.util.module_from_spec(_stt_spec)
    sys.modules[_stt_mod_name] = _stt_mod
    _stt_spec.loader.exec_module(_stt_mod)
else:
    _stt_mod = sys.modules[_stt_mod_name]

_vision_mod_name = "helios_io_vision"
if _vision_mod_name not in sys.modules:
    _vision_spec = importlib.util.spec_from_file_location(
        _vision_mod_name, str(_pkg_dir / "io_vision.py")
    )
    _vision_mod = importlib.util.module_from_spec(_vision_spec)
    sys.modules[_vision_mod_name] = _vision_mod
    _vision_spec.loader.exec_module(_vision_mod)
else:
    _vision_mod = sys.modules[_vision_mod_name]

ConversationExchange = _ch_mod.ConversationExchange
ConversationHistoryManager = _ch_mod.ConversationHistoryManager
ResponsePipeline = _rp_mod.ResponsePipeline
ICRITemperatureMapper = _it_mod.ICRITemperatureMapper
BehaviorStatus = _limb_mod.BehaviorStatus
BehaviorCommand = _limb_mod.BehaviorCommand
BehaviorExecutor = _limb_mod.BehaviorExecutor
LimbDecisionBridge = _ldb_mod.LimbDecisionBridge
TTSModule = _tts_mod.TTSModule
STTModule = _stt_mod.STTModule
VisionModule = _vision_mod.VisionModule
