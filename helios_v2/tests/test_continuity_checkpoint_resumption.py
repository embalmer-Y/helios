from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import CANONICAL_STAGE_ORDER, assemble_runtime
from helios_v2.composition.dependencies import CONTINUITY_CHECKPOINT_READY
from helios_v2.continuity_checkpoint import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
    SqliteCheckpointBackend,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.composition import default_composition_config
from helios_v2.runtime import RuntimeStartupError


@dataclass
class _DeferringThoughtProvider:
    """Deterministic provider: every tick concludes with no action (a deferring tick).

    A sufficient/no-continue/no-action tick yields a `defer` disposition and forms/reinforces
    the `24` continuity-thread layer, producing non-trivial cross-tick state to checkpoint.
    """

    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "resolved, nothing to do",
            "sufficiency": 0.95,
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _continue_gateway() -> LlmGateway:
    config = default_composition_config()
    return LlmGateway(
        provider=_DeferringThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _thought_gating_prior(handle):
    stage = next(
        s
        for s in handle.kernel._stages
        if s.stage_name == "thought_gating_and_continuation_pressure"
    )
    return stage._prior_continuation_state


def _autonomy_prior(handle):
    stage = next(
        s
        for s in handle.kernel._stages
        if s.stage_name == "subjective_autonomy_and_proactive_evolution"
    )
    return stage._prior_deferred_records, stage._prior_continuity_threads


def test_checkpoint_enabled_registers_dependency_spec() -> None:
    store = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store, default_signal_mode="legacy_constant")
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert CONTINUITY_CHECKPOINT_READY in spec_names


def test_cold_checkpoint_store_starts_inert() -> None:
    store = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store, default_signal_mode="legacy_constant")
    handle.startup()

    prior = _thought_gating_prior(handle)
    deferred, threads = _autonomy_prior(handle)
    # A cold store seeds nothing: identical to the non-checkpointing runtime.
    assert prior.active is False
    assert deferred == ()
    assert threads == ()


def test_checkpoint_saves_latest_snapshot_after_tick() -> None:
    store = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store, default_signal_mode="legacy_constant")
    handle.startup()
    handle.run_ticks(3)

    snapshot = store.load_latest()
    assert snapshot is not None
    assert snapshot.tick_id == 3
    # The continue/no-action ticks build long-horizon continuity threads.
    assert len(snapshot.continuity_threads) >= 1


def test_restart_resumes_prior_continuity_by_provenance(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")

    # Session A: run ticks against a fresh checkpoint file, then drop the handle.
    store_a = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    handle_a = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store_a, default_signal_mode="legacy_constant")
    handle_a.startup()
    handle_a.run_ticks(3)
    saved = store_a.load_latest()
    assert saved is not None

    # Session B (simulated restart): a brand-new runtime against the same file must resume the
    # prior cross-tick state, verified by provenance (seeded state equals the saved snapshot).
    store_b = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    handle_b = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store_b, default_signal_mode="legacy_constant")
    handle_b.startup()

    resumed_continuation = _thought_gating_prior(handle_b)
    resumed_deferred, resumed_threads = _autonomy_prior(handle_b)
    assert resumed_continuation == saved.continuation_state
    assert resumed_deferred == saved.deferred_records
    assert resumed_threads == saved.continuity_threads
    # The restored continuity is non-trivial: at least one continuity thread survived restart.
    assert len(resumed_threads) >= 1


def test_restart_resumed_state_actually_feeds_first_tick(tmp_path) -> None:
    db_path = str(tmp_path / "continuity_checkpoint.sqlite3")

    store_a = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    handle_a = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store_a, default_signal_mode="legacy_constant")
    handle_a.startup()
    handle_a.run_ticks(3)
    saved = store_a.load_latest()
    assert saved is not None
    threads_after_a = len(saved.continuity_threads)

    # The restarted runtime's first tick reinforces the restored threads rather than starting
    # the thread layer from zero, proving the seeded state is actually consumed.
    store_b = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    handle_b = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store_b, default_signal_mode="legacy_constant")
    handle_b.startup()
    first = handle_b.tick()
    autonomy_result = first.stage_results[
        "subjective_autonomy_and_proactive_evolution"
    ].result
    assert autonomy_result.long_horizon_state.max_thread_age >= threads_after_a


def test_unwritable_checkpoint_backend_fails_fast_at_startup(tmp_path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    db_path = str(blocker / "nested" / "continuity_checkpoint.sqlite3")
    store = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db_path))
    handle = assemble_runtime(gateway=_continue_gateway(), continuity_checkpoint=store, default_signal_mode="legacy_constant")

    with pytest.raises(RuntimeStartupError):
        handle.startup()


def test_default_assembly_has_no_checkpoint_state() -> None:
    # Without continuity_checkpoint, the handle carries no checkpoint and the dependency is absent.
    handle = assemble_runtime(gateway=_continue_gateway(), default_signal_mode="legacy_constant")
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert CONTINUITY_CHECKPOINT_READY not in spec_names
    assert handle.continuity_checkpoint is None
    # The default canonical order is unchanged by the checkpoint mechanism.
    assert tuple(s.stage_name for s in handle.kernel._stages) == CANONICAL_STAGE_ORDER
