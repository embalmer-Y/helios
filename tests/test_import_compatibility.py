"""Compatibility guards for Phase 4 package restructuring.

These tests codify the import surface that must remain stable while source
files are reorganized into domain packages.
"""

from __future__ import annotations

import sys
import importlib.util
import pytest
from importlib import import_module
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent))


def test_legacy_root_module_imports_are_removed():
    removed_legacy_modules = [
        "appraisal",
        "autobiographical",
        "conation",
        "drives",
        "emotional_memory",
        "helios_utils",
        "memory_system",
        "emotions",
        "phi",
        "thinking",
    ]

    for module_name in removed_legacy_modules:
        with pytest.raises(ModuleNotFoundError):
            import_module(module_name)


def test_root_package_does_not_export_removed_legacy_limb_symbols():
    helios_pkg = import_module("helios")

    for symbol_name in ["Limb", "HeliosBody", "ActionIntent", "SafetyRule"]:
        assert not hasattr(helios_pkg, symbol_name)


def test_root_package_re_exports_daisy_compat_emotion_symbols():
    helios_pkg = import_module("helios")

    assert hasattr(helios_pkg, "PankseppEmotionEngine")
    assert hasattr(helios_pkg, "AffectState")
    assert not hasattr(helios_pkg, "PrimaryEmotionSystem")


def test_core_package_re_exports_gateway_abstractions():
    core = import_module("core")

    for symbol_name in [
        "ChannelGateway",
        "InputChannel",
        "OutputChannel",
        "BidirectionalChannel",
        "ChannelMessage",
        "HeliosState",
        "TickGuard",
    ]:
        assert hasattr(core, symbol_name)


def test_memory_package_re_exports_primary_memory_interfaces():
    memory_pkg = import_module("memory")

    for symbol_name in [
        "AutobiographicalStore",
        "MemorySystem",
        "MemoryItem",
        "WorkingMemory",
        "EpisodicMemory",
        "SemanticMemory",
        "EmotionalEpisodicMemory",
    ]:
        assert hasattr(memory_pkg, symbol_name)


def test_cognition_package_re_exports_primary_interfaces():
    cognition_pkg = import_module("cognition")

    for symbol_name in [
        "UnifiedPhi",
        "ConsciousnessMoment",
        "DriveOracle",
        "DriveVector",
        "HeliosSnapshot",
        "AppraisalEngine",
        "SECFeatures",
        "appraise_event",
        "ThinkingManager",
        "MemoryReplayEngine",
    ]:
        assert hasattr(cognition_pkg, symbol_name)


def test_regulation_package_re_exports_primary_interfaces():
    regulation_pkg = import_module("regulation")

    for symbol_name in [
        "RegulationEngine",
        "RegulationMemory",
        "ActionCandidate",
        "ConationEngine",
        "Intent",
        "IntentType",
    ]:
        assert hasattr(regulation_pkg, symbol_name)


def test_utils_package_re_exports_primary_interfaces():
    utils_pkg = import_module("utils")

    for symbol_name in [
        "StatePersistence",
        "clamp",
        "safe_div",
        "lerp",
        "sigmoid",
        "exp_decay",
    ]:
        assert hasattr(utils_pkg, symbol_name)


def test_io_channel_package_exports_multimodal_channels():
    channels = import_module("helios_io.channels")

    for symbol_name in ["QQChannel", "TTSChannel", "STTChannel", "VisionChannel"]:
        assert hasattr(channels, symbol_name)