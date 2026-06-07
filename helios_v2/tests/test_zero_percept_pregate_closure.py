"""R65: zero-percept pre-gate closure — focused tests.

Validates that a zero-percept tick (empty 02 batch) short-circuits the pre-gate
06/07/08 chain via `activated=False` inactive results and closes through the 09
gate no-fire path, while ticks with any percept (default placeholder, real
external, or interoceptive-only) behave identically to pre-R65.
"""

from __future__ import annotations

from helios_v2.composition import (
    CANONICAL_STAGE_ORDER,
    RuntimeHandle,
    SequenceExternalSignalSource,
    assemble_runtime,
    default_composition_config,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion

from dataclasses import dataclass, field


@dataclass
class _FakeThoughtProvider:
    """Deterministic provider double; never touches the network."""

    thought_text: str = "deterministic llm thought for the current cycle"
    finish_reason: str = "stop"
    sufficiency: float = 0.9
    wants_to_continue: bool = False
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        self.calls.append(profile.profile_name)
        envelope = {
            "thought": self.thought_text,
            "sufficiency": self.sufficiency,
            "wants_to_continue": self.wants_to_continue,
            "continue_reason": "",
            "proposed_action": {"intends_action": True, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason=self.finish_reason)


def _ready_gateway() -> LlmGateway:
    config = default_composition_config()
    return LlmGateway(
        provider=_FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble(**kwargs) -> RuntimeHandle:
    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway()
    return assemble_runtime(**kwargs)


def _external_batch(signal_id: str, content: str):
    from helios_v2.sensory import RawSignal

    return (
        RawSignal(
            signal_id=signal_id,
            source_name="external",
            signal_type="text",
            content=content,
        ),
    )


# ---------------------------------------------------------------------------
# 1. Zero-percept tick → 06/07/08 all activated=False
# ---------------------------------------------------------------------------
def test_zero_percept_tick_skips_memory_workspace_consciousness() -> None:
    """An empty external source with no interoceptive sampler produces a genuinely
    empty 02 batch. The pre-gate 06/07/08 stages all return activated=False."""
    source = SequenceExternalSignalSource(batches=())
    handle = _assemble(external_signal_source=source)
    handle.startup()

    result = handle.tick()

    memory_result = result.stage_results["memory_affect_and_replay"]
    workspace_result = result.stage_results["workspace_competition_and_working_state"]
    conscious_result = result.stage_results["reportable_conscious_content"]

    assert memory_result.activated is False
    assert memory_result.state.memory_items == ()
    assert memory_result.state.replay_candidates == ()

    assert workspace_result.activated is False
    assert workspace_result.candidate_set.candidates == ()
    assert workspace_result.working_state.retained_candidate_ids == ()

    assert conscious_result.activated is False
    assert conscious_result.state.commit_status == "no_commit"
    assert conscious_result.state.no_commit_reason == "context_not_reportable"


# ---------------------------------------------------------------------------
# 2. Zero-percept tick closes through gate no-fire
# ---------------------------------------------------------------------------
def test_zero_percept_tick_closes_through_gate_no_fire() -> None:
    """A zero-percept tick reaches 09 gate, which decides no_fire, and the tick
    produces all 19 canonical stage results without raising."""
    source = SequenceExternalSignalSource(batches=())
    handle = _assemble(external_signal_source=source)
    handle.startup()

    result = handle.tick()

    gate_result = result.stage_results["thought_gating_and_continuation_pressure"]
    assert gate_result.result.decision == "no_fire"
    assert gate_result.result.no_fire_reason == "conscious_content_not_eligible"
    assert gate_result.signal_snapshot.global_activation_level == 0.0
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


# ---------------------------------------------------------------------------
# 3. Default assembly unchanged (placeholder percept → all pre-gate activate)
# ---------------------------------------------------------------------------
def test_default_assembly_unchanged() -> None:
    """The default assembly (FirstVersionSensorySource placeholder "hello runtime")
    produces a non-empty 02 batch, so all pre-gate stages activate as before."""
    handle = _assemble()
    handle.startup()

    result = handle.tick()

    memory_result = result.stage_results["memory_affect_and_replay"]
    workspace_result = result.stage_results["workspace_competition_and_working_state"]
    conscious_result = result.stage_results["reportable_conscious_content"]

    assert memory_result.activated is True
    assert len(memory_result.state.memory_items) > 0
    assert workspace_result.activated is True
    assert conscious_result.activated is True

    gate_result = result.stage_results["thought_gating_and_continuation_pressure"]
    assert gate_result.result.decision == "fire"
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


# ---------------------------------------------------------------------------
# 4. Semantic assembly with real percept unchanged
# ---------------------------------------------------------------------------
def test_semantic_assembly_with_real_percept_unchanged() -> None:
    """A semantic assembly with a real external stimulus activates all pre-gate stages."""
    from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
    from helios_v2.embedding import EmbeddingGateway, EmbeddingProfileRegistry, EmbeddingProfile

    source = SequenceExternalSignalSource(
        batches=(_external_batch("e1", "a real external observation"),)
    )
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    gateway = EmbeddingGateway(
        provider=_FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )
    handle = _assemble(
        external_signal_source=source,
        experience_store=store,
        embedding_gateway=gateway,
    )
    handle.startup()

    result = handle.tick()

    memory_result = result.stage_results["memory_affect_and_replay"]
    workspace_result = result.stage_results["workspace_competition_and_working_state"]
    conscious_result = result.stage_results["reportable_conscious_content"]

    assert memory_result.activated is True
    assert workspace_result.activated is True
    assert conscious_result.activated is True


# ---------------------------------------------------------------------------
# 5. Source exhaustion → subsequent ticks go inactive
# ---------------------------------------------------------------------------
def test_empty_external_source_exhaustion_still_fires() -> None:
    """After the source's batches are exhausted, subsequent ticks have empty 02 batches
    and the pre-gate inactive path activates. The first tick (with content) fires normally."""
    source = SequenceExternalSignalSource(
        batches=(_external_batch("e1", "only one batch"),)
    )
    handle = _assemble(external_signal_source=source)
    handle.startup()

    first = handle.tick()
    second = handle.tick()

    # First tick: real percept → all pre-gate stages activate
    assert first.stage_results["memory_affect_and_replay"].activated is True
    assert first.stage_results["thought_gating_and_continuation_pressure"].result.decision == "fire"

    # Second tick: exhausted source → empty 02 batch → inactive pre-gate → no_fire
    assert second.stage_results["memory_affect_and_replay"].activated is False
    assert second.stage_results["thought_gating_and_continuation_pressure"].result.decision == "no_fire"
    assert tuple(second.stage_results.keys()) == CANONICAL_STAGE_ORDER


# ---------------------------------------------------------------------------
# 6. Interoceptive-only tick still forms memory
# ---------------------------------------------------------------------------
def test_interoceptive_only_tick_still_forms_memory() -> None:
    """A tick with only interoceptive stimuli (no external) still has a non-empty 02 batch,
    so memory formation, workspace competition, and consciousness commitment all proceed."""

    class _BodySampler:
        def sample(self):
            from helios_v2.interoception import RuntimePressureSample

            return RuntimePressureSample(
                cpu_pressure=0.3, memory_pressure=0.2,
                latency_pressure=0.0, error_pressure=0.0,
            )

    handle = _assemble(interoceptive_sampler=_BodySampler())
    handle.startup()

    result = handle.tick()

    memory_result = result.stage_results["memory_affect_and_replay"]
    workspace_result = result.stage_results["workspace_competition_and_working_state"]
    conscious_result = result.stage_results["reportable_conscious_content"]

    assert memory_result.activated is True
    assert len(memory_result.state.memory_items) > 0
    assert workspace_result.activated is True
    assert conscious_result.activated is True
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@dataclass
class _FakeEmbeddingProvider:
    """Deterministic, network-free embedding provider for tests."""

    dimensions: int = 16

    def embed(self, profile, request, api_key):
        from helios_v2.embedding import ProviderEmbedding

        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[ord(char) % self.dimensions] += 0.01 * (index + 1)
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)
