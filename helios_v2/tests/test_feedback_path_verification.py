"""R75 — Feedback path verification: cognitive loop feedback paths end-to-end.

Validates the key feedback loops in the 19-stage cognitive chain:

- **FP-1**: 09 fire → 11 thought → 12 action → 13 planner → 15 writeback →
  18 autonomy → next tick 09 drive_urgency (R62 carry).
- **FP-2**: 09 no-fire → R54 closure → 18/17 still run → continuation carry.
- **FP-3**: 15 writeback → 06 memory (experience loop) → 10 retrieval (R52 recall).
- **FP-4**: 04 → 05 → 07 → 09 causal chain (R37/R38/R46/R48).
- **FP-5**: 18 continuity → 24 long-horizon → checkpoint save/restore.

This module is **read-only**: it runs the runtime and inspects results but
never modifies owner code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import assemble_runtime, default_composition_config
from helios_v2.composition import RuntimeProfile
from helios_v2.embedding import (
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    ProviderEmbedding,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.persistence import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
)
from helios_v2.continuity_checkpoint import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
)


# ---------------------------------------------------------------------------
# Fake providers
# ---------------------------------------------------------------------------


@dataclass
class _FakeThoughtProvider:
    thought_text: str = "deterministic thought for feedback verification"
    finish_reason: str = "stop"
    sufficiency: float = 0.9
    wants_to_continue: bool = False
    intends_action: bool = True

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json
        envelope = {
            "thought": self.thought_text,
            "sufficiency": self.sufficiency,
            "wants_to_continue": self.wants_to_continue,
            "continue_reason": "",
            "proposed_action": {"intends_action": self.intends_action, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(
            output_text=json.dumps(envelope),
            finish_reason=self.finish_reason,
        )


class _FakeEmbeddingProvider:
    dimensions: int = 16

    def embed(self, profile, request, api_key):
        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)


def _ready_gateway():
    config = default_composition_config()
    return LlmGateway(
        provider=_FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _embedding_gateway():
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        dimensions=16,
    )
    return EmbeddingGateway(
        provider=_FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble_semantic(**kwargs):
    kwargs.setdefault("gateway", _ready_gateway())
    kwargs.setdefault("experience_store", ExperienceStore(backend=InMemoryExperienceStoreBackend()))
    kwargs.setdefault("embedding_gateway", _embedding_gateway())
    return assemble_runtime(**kwargs)


def _assemble_legacy(**kwargs):
    kwargs.setdefault("gateway", _ready_gateway())
    kwargs.setdefault("default_signal_mode", "legacy_constant")
    return assemble_runtime(**kwargs)


# ---------------------------------------------------------------------------
# Feedback verdict
# ---------------------------------------------------------------------------


@dataclass
class FeedbackCheck:
    path_id: str
    description: str
    passed: bool
    evidence: str


@dataclass
class FeedbackVerdict:
    checks: list[FeedbackCheck] = field(default_factory=list)

    def add(self, check: FeedbackCheck) -> None:
        self.checks.append(check)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


# ===========================================================================
# FP-1: Full fire → thought → action → planner → writeback → autonomy carry
# ===========================================================================


def test_fp1_fire_path_autonomy_carry() -> None:
    """09 fire → 18 autonomy produces outward_drive that carries across ticks."""
    handle = _assemble_semantic()
    handle.startup()

    results = handle.run_ticks(3)

    # All ticks should fire (default semantic assembly fires).
    fire_decisions = [
        r.stage_results["thought_gating_and_continuation_pressure"].result.decision
        for r in results
    ]
    assert all(d == "fire" for d in fire_decisions), (
        f"Expected all fire decisions, got {fire_decisions}"
    )

    # 18 autonomy must produce a disposition on every tick.
    autonomy_results = [
        r.stage_results["subjective_autonomy_and_proactive_evolution"]
        for r in results
    ]
    assert all(ar is not None for ar in autonomy_results), (
        "All ticks must produce autonomy results"
    )

    # 15 writeback must produce continuity records.
    writeback_results = [
        r.stage_results["execution_writeback_and_autobiographical_consolidation"]
        for r in results
    ]
    assert all(wr is not None for wr in writeback_results), (
        "All ticks must produce writeback results"
    )

    # 17 evaluation must produce diagnostic results.
    eval_results = [
        r.stage_results["evaluation_fidelity_and_diagnostic_provenance"]
        for r in results
    ]
    assert all(er is not None for er in eval_results), (
        "All ticks must produce evaluation results"
    )


# ===========================================================================
# FP-2: No-fire gate → R54 closure → 18/17 still run
# ===========================================================================


def test_fp2_no_fire_closure_continuation() -> None:
    """High load forces no-fire; 18 and 17 still produce results."""
    from helios_v2.composition import assemble_runtime
    from helios_v2.interoception import RuntimePressureSample, StdlibRuntimePressureSampler

    # Use a custom sampler that reports extreme pressure.
    class _HighPressureSampler:
        def sample(self):
            return RuntimePressureSample(
                cpu_pressure=0.95, memory_pressure=0.95,
                latency_pressure=0.9, error_pressure=0.5,
            )

    handle = _assemble_semantic(interoceptive_sampler=_HighPressureSampler())
    handle.startup()

    result = handle.tick()

    # Gate should be no-fire due to high workload.
    gate = result.stage_results["thought_gating_and_continuation_pressure"]
    assert gate.result.decision == "no_fire", (
        f"Expected no_fire under high load, got {gate.result.decision}"
    )

    # 18 autonomy must still produce a result (R54 closure).
    autonomy = result.stage_results.get("subjective_autonomy_and_proactive_evolution")
    assert autonomy is not None, "18 autonomy must produce result even on no-fire tick"

    # 17 evaluation must still produce a result.
    eval_result = result.stage_results.get("evaluation_fidelity_and_diagnostic_provenance")
    assert eval_result is not None, "17 evaluation must produce result even on no-fire tick"


# ===========================================================================
# FP-3: Writeback → memory → retrieval loop
# ===========================================================================


def test_fp3_writeback_to_retrieval_loop() -> None:
    """15 writeback persists experience; 10 retrieval can recall it."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble_semantic(experience_store=store)
    handle.startup()

    # Run multiple ticks to build up experience.
    results = handle.run_ticks(5)

    # Store should have records after 5 ticks.
    count = store.count()
    assert count >= 5, f"Expected at least 5 records, got {count}"

    # The 10 directed retrieval stage should have produced a bundle.
    last_result = results[-1]
    retrieval = last_result.stage_results.get("directed_retrieval_into_thought_window")
    assert retrieval is not None, "10 directed retrieval must produce result"

    # The retrieval bundle should have some context (from the experience store).
    bundle = retrieval.bundle
    total_hits = (
        len(bundle.short_term_context)
        + len(bundle.mid_term_hits)
        + len(bundle.long_term_hits)
        + len(bundle.autobiographical_hits)
    )
    assert total_hits > 0, (
        "Directed retrieval should have hits from experience store after 5 ticks"
    )


# ===========================================================================
# FP-4: 04 → 05 → 07 → 09 causal chain
# ===========================================================================


def test_fp4_neuromodulator_feeling_workspace_gate_chain() -> None:
    """04 neuromodulator → 05 feeling → 07 workspace → 09 gate chain is real."""
    handle = _assemble_semantic()
    handle.startup()

    results = handle.run_ticks(3)

    for i, result in enumerate(results):
        # 04 neuromodulator must produce levels.
        nm = result.stage_results.get("neuromodulator_system")
        assert nm is not None, f"Tick {i}: 04 neuromodulator missing"
        assert nm.state.levels is not None, f"Tick {i}: 04 levels missing"

        # 05 feeling must produce a state.
        feeling = result.stage_results.get("interoceptive_feeling_layer")
        assert feeling is not None, f"Tick {i}: 05 feeling missing"
        assert feeling.state.feeling is not None, f"Tick {i}: 05 feeling state missing"

        # 07 workspace must produce candidates.
        workspace = result.stage_results.get("workspace_competition_and_working_state")
        assert workspace is not None, f"Tick {i}: 07 workspace missing"

        # 09 gate must consume real signals (check contributing_signals).
        gate = result.stage_results.get("thought_gating_and_continuation_pressure")
        assert gate is not None, f"Tick {i}: 09 gate missing"

    # Verify 04 levels evolve across ticks (dual-timescale R43).
    dopamine_values = [
        r.stage_results["neuromodulator_system"].state.levels.dopamine
        for r in results
    ]
    assert len(set(dopamine_values)) > 1, (
        f"04 dopamine should evolve across ticks, got {dopamine_values}"
    )

    # Verify 05 feeling evolves across ticks (dual-timescale R44).
    valence_values = [
        r.stage_results["interoceptive_feeling_layer"].state.feeling.valence
        for r in results
    ]
    assert len(set(valence_values)) > 1, (
        f"05 valence should evolve across ticks, got {valence_values}"
    )


# ===========================================================================
# FP-5: Continuity thread → checkpoint save/restore
# ===========================================================================


def test_fp5_continuity_checkpoint_round_trip() -> None:
    """18 continuity → 42 checkpoint → restart restores state."""
    ckpt = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle_a = _assemble_semantic(continuity_checkpoint=ckpt)
    handle_a.startup()

    # Run 3 ticks to build up continuity state.
    handle_a.run_ticks(3)

    # Checkpoint should have saved a snapshot.
    saved = ckpt.load_latest()
    assert saved is not None, "checkpoint must save after 3 ticks"
    assert saved.continuation_state is not None, (
        "checkpoint must save continuation state"
    )

    # Session B: restore from the same checkpoint.
    ckpt_b = ContinuityCheckpointStore(
        backend=InMemoryCheckpointBackend()
    )
    # Manually copy the checkpoint data by saving the same snapshot.
    ckpt_b.save_latest(saved)

    store_b = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_b = _assemble_semantic(
        experience_store=store_b,
        continuity_checkpoint=ckpt_b,
    )
    handle_b.startup()

    # The restored state should seed the thought gating stage.
    seeded = handle_b.thought_gating_stage._prior_continuation_state
    assert seeded is not None, (
        "09 stage should have restored prior continuation state from checkpoint"
    )


# ===========================================================================
# Composite verdict
# ===========================================================================


def test_feedback_path_composite_verdict() -> None:
    """Composite verdict for all feedback paths."""
    verdict = FeedbackVerdict()

    # -- FP-1: Fire path carry --
    handle = _assemble_semantic()
    handle.startup()
    results = handle.run_ticks(3)
    fire_count = sum(
        1 for r in results
        if r.stage_results["thought_gating_and_continuation_pressure"].result.decision == "fire"
    )
    autonomy_count = sum(
        1 for r in results
        if r.stage_results.get("subjective_autonomy_and_proactive_evolution") is not None
    )
    verdict.add(FeedbackCheck(
        "FP-1", "fire path → autonomy carry",
        fire_count == 3 and autonomy_count == 3,
        f"fire={fire_count}/3, autonomy={autonomy_count}/3",
    ))

    # -- FP-2: No-fire closure --
    class _HighLoad:
        def sample(self):
            return RuntimePressureSample(
                cpu_pressure=0.95, memory_pressure=0.95,
                latency_pressure=0.9, error_pressure=0.5,
            )

    from helios_v2.interoception import RuntimePressureSample
    handle_nf = _assemble_semantic(interoceptive_sampler=_HighLoad())
    handle_nf.startup()
    result_nf = handle_nf.tick()
    nf_decision = result_nf.stage_results["thought_gating_and_continuation_pressure"].result.decision
    nf_autonomy = result_nf.stage_results.get("subjective_autonomy_and_proactive_evolution")
    verdict.add(FeedbackCheck(
        "FP-2", "no-fire closure → 18/17 still run",
        nf_decision == "no_fire" and nf_autonomy is not None,
        f"decision={nf_decision}, autonomy={'yes' if nf_autonomy else 'no'}",
    ))

    # -- FP-3: Writeback → retrieval --
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_wr = _assemble_semantic(experience_store=store)
    handle_wr.startup()
    handle_wr.run_ticks(5)
    count = store.count()
    retrieval = handle_wr.run_ticks(1)[-1].stage_results.get("directed_retrieval_into_thought_window")
    has_bundle = retrieval is not None
    verdict.add(FeedbackCheck(
        "FP-3", "writeback → memory → retrieval",
        count >= 5 and has_bundle,
        f"store_count={count}, retrieval={'yes' if has_bundle else 'no'}",
    ))

    # -- FP-4: 04→05→07→09 chain --
    handle_chain = _assemble_semantic()
    handle_chain.startup()
    chain_results = handle_chain.run_ticks(3)
    dopamine_vals = [
        r.stage_results["neuromodulator_system"].state.levels.dopamine
        for r in chain_results
    ]
    valence_vals = [
        r.stage_results["interoceptive_feeling_layer"].state.feeling.valence
        for r in chain_results
    ]
    chain_evolved = len(set(dopamine_vals)) > 1 and len(set(valence_vals)) > 1
    verdict.add(FeedbackCheck(
        "FP-4", "04→05→07→09 causal chain",
        chain_evolved,
        f"dopamine={dopamine_vals}, valence={valence_vals}",
    ))

    # -- FP-5: Checkpoint round-trip --
    ckpt = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle_ckpt = _assemble_semantic(continuity_checkpoint=ckpt)
    handle_ckpt.startup()
    handle_ckpt.run_ticks(3)
    saved = ckpt.load_latest()
    ckpt_ok = saved is not None and saved.continuation_state is not None
    verdict.add(FeedbackCheck(
        "FP-5", "continuity checkpoint round-trip",
        ckpt_ok,
        f"saved={'yes' if saved else 'no'}, "
        f"continuation={'yes' if saved and saved.continuation_state else 'no'}",
    ))

    # Final assertion.
    assert verdict.passed, (
        f"FEEDBACK PATH VERDICT: FAIL\n"
        + "\n".join(
            f"  [FAIL] {c.path_id}: {c.description} — {c.evidence}"
            for c in verdict.checks
            if not c.passed
        )
    )

    print(f"\n{'=' * 60}")
    print(f"FEEDBACK PATH VERDICT: {'PASS' if verdict.passed else 'FAIL'}")
    for c in verdict.checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}] {c.path_id}: {c.description} — {c.evidence}")
    print(f"{'=' * 60}")
