"""R79-B verification: RuntimeProfile.aggressive_radical_prompt_profile integration with assemble_runtime.

Owner-neutral integration tests for the v3 capability-bundle → assemble_runtime wiring.
Asserts:
- v1 default assembly is byte-for-byte unchanged
- v3 bundle assembly activates the v3 path and injects ready_channels
- v3 bundle + non-v1 baseline bootstrap id → CompositionError fail-fast
- v3 bundle with multi-channel ready_channels round-trips through the bridge field
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path("/root/project/helios/helios_v2")
sys.path.insert(0, str(ROOT / "src"))

import pytest

from helios_v2.composition import assemble_runtime
from helios_v2.composition.profile import AggressiveRadicalPromptProfile
from helios_v2.composition.runtime_assembly import (
    CompositionError,
    RuntimeProfile,
    default_composition_config,
)
from helios_v2.llm import (
    LlmCompletion,
    LlmProfileReadiness,
    LlmReadinessReport,
    LlmUsage,
)
from helios_v2.prompt_contract import (
    AggressiveRadicalEmbodiedPromptPath,
    FirstVersionEmbodiedPromptPath,
)
from helios_v2.runtime.stages import EmbodiedPromptRuntimeStage
from helios_v2.sensory import RawSignal


# ----------------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------------


@dataclass
class _NoopGateway:
    """Minimal LLM gateway: static-readiness always green, complete returns stub envelope.

    Used so assemble_runtime can build the kernel + stages without trying to reach
    a real provider. The tests do not call handle.tick() — they only inspect the
    assembled stage wiring.
    """

    def check_static_readiness(self, profile_names):
        return LlmReadinessReport(
            report_id="r79b-integration-mock",
            checked_live=False,
            entries=tuple(
                LlmProfileReadiness(
                    profile_name=name,
                    exists=True,
                    static_ready=True,
                    live_ready=None,
                    detail="r79b mock ready",
                )
                for name in profile_names
            ),
        )

    def complete(self, request):  # pragma: no cover - tests do not tick
        body = json.dumps({
            "thought": "stub",
            "sufficiency": 0.8,
            "wants_to_continue": False,
            "continue_reason": "",
            "proposed_action": {"intends_action": False, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        })
        return LlmCompletion(
            completion_id=f"r79b:completion:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="r79b-mock",
            output_text=body,
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=0.0,
        )


def _find_embodied_prompt_stage(handle):
    """Walk the kernel's stage list to find the EmbodiedPromptRuntimeStage.

    The kernel's _stages is a private field, but the runtime deliberately
    exposes all stages through this single list and there is no public
    accessor for individual stages yet. The integration tests use the same
    private-field access that R70/R78 tests rely on.
    """

    for stage in handle.kernel._stages:  # noqa: SLF001
        if isinstance(stage, EmbodiedPromptRuntimeStage):
            return stage
    raise AssertionError(
        "EmbodiedPromptRuntimeStage not found in handle.kernel._stages"
    )


# ----------------------------------------------------------------------------
# T10 tests
# ----------------------------------------------------------------------------


def test_r79b_default_assembly_is_v1_unchanged():
    """Test 1: default assembly (no bundle) keeps v1 bootstrap id and v1 path.

    Asserts the R79-B §7 constraint: the v1 default is byte-for-byte unchanged.
    """
    handle = assemble_runtime(
        deterministic_thought=True,
        gateway=_NoopGateway(),
    )
    stage = _find_embodied_prompt_stage(handle)
    bootstrap_id = stage.prompt_layer.config.prompt_bootstrap_id
    assert bootstrap_id == "embodied-prompt-bootstrap:v1", (
        f"v1 default assembly must use 'embodied-prompt-bootstrap:v1', got {bootstrap_id!r}"
    )
    assert isinstance(stage.prompt_layer.prompt_path, FirstVersionEmbodiedPromptPath), (
        f"v1 default assembly must use FirstVersionEmbodiedPromptPath, got "
        f"{type(stage.prompt_layer.prompt_path).__name__}"
    )
    # FirstVersion bridge keeps ready_channels=() by default (no v3 bundle).
    assert stage.request_provider.ready_channels == (), (
        f"v1 default must have empty ready_channels on FirstVersion bridge, got "
        f"{stage.request_provider.ready_channels!r}"
    )


def test_r79b_v3_bundle_uses_v3_path_and_injects_ready_channels():
    """Test 2: v3 bundle → v3 bootstrap id + v3 path + ready_channels injected on bridge."""
    bundle = AggressiveRadicalPromptProfile(ready_channels=("cli", "webchat"))
    handle = assemble_runtime(
        deterministic_thought=True,
        gateway=_NoopGateway(),
        aggressive_radical_prompt_profile=bundle,
    )
    stage = _find_embodied_prompt_stage(handle)
    bootstrap_id = stage.prompt_layer.config.prompt_bootstrap_id
    assert bootstrap_id == "embodied-prompt-bootstrap:v3-aggressive-radical", (
        f"v3 bundle must switch bootstrap id to v3-aggressive-radical, got {bootstrap_id!r}"
    )
    assert isinstance(stage.prompt_layer.prompt_path, AggressiveRadicalEmbodiedPromptPath), (
        f"v3 bundle must use AggressiveRadicalEmbodiedPromptPath, got "
        f"{type(stage.prompt_layer.prompt_path).__name__}"
    )
    assert stage.request_provider.ready_channels == ("cli", "webchat"), (
        f"v3 bundle must inject ready_channels into FirstVersion bridge, got "
        f"{stage.request_provider.ready_channels!r}"
    )


def test_r79b_v3_bundle_with_non_v1_baseline_raises_composition_error():
    """Test 3: v3 bundle + non-v1 baseline bootstrap id → CompositionError (fail-fast)."""
    bundle = AggressiveRadicalPromptProfile(ready_channels=("cli",))
    # Pre-set a non-v1 baseline on the embodied-prompt config.
    config = default_composition_config()
    # Build a new config with a tampered bootstrap id. embodied_prompt is a frozen
    # dataclass, so we use dataclasses.replace.
    from dataclasses import replace as _replace
    tampered_config = _replace(
        config,
        embodied_prompt=_replace(
            config.embodied_prompt,
            prompt_bootstrap_id="embodied-prompt-bootstrap:v2-arousal",
        ),
    )
    with pytest.raises(CompositionError, match="embodied-prompt-bootstrap:v1"):
        assemble_runtime(
            deterministic_thought=True,
            gateway=_NoopGateway(),
            config=tampered_config,
            aggressive_radical_prompt_profile=bundle,
        )


def test_r79b_v3_bundle_multi_channel_ready_channels_round_trip():
    """Test 4: v3 bundle with 3-channel ready_channels round-trips through the bridge."""
    bundle = AggressiveRadicalPromptProfile(
        ready_channels=("cli", "webchat", "feishu")
    )
    handle = assemble_runtime(
        deterministic_thought=True,
        gateway=_NoopGateway(),
        aggressive_radical_prompt_profile=bundle,
    )
    stage = _find_embodied_prompt_stage(handle)
    assert stage.request_provider.ready_channels == ("cli", "webchat", "feishu")
    # The bundle survives the assembly rebind path.
    assert bundle.ready_channels == ("cli", "webchat", "feishu")


def test_r79b_profile_field_default_is_none():
    """Test 5: RuntimeProfile.aggressive_radical_prompt_profile defaults to None (v1 default)."""
    profile = RuntimeProfile()
    assert profile.aggressive_radical_prompt_profile is None


def test_r79b_profile_field_round_trips_bundle():
    """Test 6: RuntimeProfile.aggressive_radical_prompt_profile round-trips the bundle."""
    bundle = AggressiveRadicalPromptProfile(ready_channels=("cli",))
    profile = RuntimeProfile(aggressive_radical_prompt_profile=bundle)
    assert profile.aggressive_radical_prompt_profile is bundle
