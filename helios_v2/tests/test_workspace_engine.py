from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector
from helios_v2.memory import MemoryReplayCandidate
from helios_v2.workspace import (
    WorkingStateRetentionPath,
    WorkingStateSnapshot,
    WorkspaceCandidate,
    WorkspaceCandidateSet,
    WorkspaceCompetitionConfig,
    WorkspaceCompetitionEngine,
    WorkspaceCompetitionError,
    WorkspaceCompetitionPath,
)


def _build_feeling(value: float = 0.5) -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=value,
        arousal=value,
        tension=value,
        comfort=value,
        fatigue=value,
        pain_like=value,
        social_safety=value,
    )


def _build_feeling_state() -> InteroceptiveFeelingState:
    return InteroceptiveFeelingState(
        state_id="interoceptive-feeling-state:001",
        source_neuromodulator_state_id="neuromodulator-state:001",
        feeling=_build_feeling(0.6),
        tick_id=9,
    )


def _build_replay_candidates() -> tuple[MemoryReplayCandidate, ...]:
    return (
        MemoryReplayCandidate(
            candidate_id="memory-candidate:forced",
            memory_id="memory:001",
            family="episodic",
            source_feeling_state_id="interoceptive-feeling-state:001",
            replay_reasons=("high_affect_intensity",),
            forced_consolidation=True,
            priority_hint=0.8,
        ),
        MemoryReplayCandidate(
            candidate_id="memory-candidate:normal",
            memory_id="memory:002",
            family="semantic",
            source_feeling_state_id="interoceptive-feeling-state:001",
            replay_reasons=("prediction_mismatch_or_surprise",),
            forced_consolidation=False,
            priority_hint=0.5,
        ),
    )


def _build_config() -> WorkspaceCompetitionConfig:
    return WorkspaceCompetitionConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        working_state_bootstrap_id="workspace-bootstrap:v1",
        mandatory_learned_parameters=(
            "competition_policy",
            "candidate_retention_policy",
            "working_state_update_policy",
        ),
    )


@dataclass
class CountingCompetitionPath(WorkspaceCompetitionPath):
    calls: int = 0

    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        self.calls += 1
        assert len(replay_candidates) == 2
        assert replay_candidates[0].forced_consolidation is True
        assert feeling_state.state_id == "interoceptive-feeling-state:001"
        assert config.working_state_bootstrap_id == "workspace-bootstrap:v1"
        assert tick_id == 13
        return WorkspaceCandidateSet(
            set_id="workspace-set:001",
            source_feeling_state_id=feeling_state.state_id,
            candidates=(
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:forced",
                    source_memory_candidate_id="memory-candidate:forced",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.8,
                    forced_consolidation=True,
                    workspace_score_hint=0.9,
                ),
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:normal",
                    source_memory_candidate_id="memory-candidate:normal",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.5,
                    forced_consolidation=False,
                    workspace_score_hint=0.6,
                ),
            ),
            tick_id=tick_id,
        )


@dataclass
class CountingRetentionPath(WorkingStateRetentionPath):
    calls: int = 0

    def retain_working_state(
        self,
        candidate_set: WorkspaceCandidateSet,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkingStateSnapshot:
        self.calls += 1
        assert candidate_set.set_id == "workspace-set:001"
        assert config.legal_max_score == 1.0
        assert tick_id == 13
        return WorkingStateSnapshot(
            state_id="working-state:001",
            source_candidate_set_id=candidate_set.set_id,
            retained_candidate_ids=("workspace-candidate:forced",),
            tick_id=tick_id,
        )


@dataclass
class UnavailableCompetitionPath(WorkspaceCompetitionPath):
    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        raise WorkspaceCompetitionError("Required workspace competition capability is unavailable")


@dataclass
class MissingForcedCandidatePath(WorkspaceCompetitionPath):
    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        return WorkspaceCandidateSet(
            set_id="workspace-set:bad",
            source_feeling_state_id=feeling_state.state_id,
            candidates=(
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:normal",
                    source_memory_candidate_id="memory-candidate:normal",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.5,
                    forced_consolidation=False,
                    workspace_score_hint=0.6,
                ),
            ),
            tick_id=tick_id,
        )


@dataclass
class WrongRetentionPath(WorkingStateRetentionPath):
    def retain_working_state(
        self,
        candidate_set: WorkspaceCandidateSet,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkingStateSnapshot:
        return WorkingStateSnapshot(
            state_id="working-state:bad",
            source_candidate_set_id=candidate_set.set_id,
            retained_candidate_ids=("workspace-candidate:missing",),
            tick_id=tick_id,
        )


@dataclass
class WrongForcedFlagPath(WorkspaceCompetitionPath):
    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        return WorkspaceCandidateSet(
            set_id="workspace-set:wrong-forced",
            source_feeling_state_id=feeling_state.state_id,
            candidates=(
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:forced",
                    source_memory_candidate_id="memory-candidate:forced",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.8,
                    forced_consolidation=False,
                    workspace_score_hint=0.9,
                ),
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:normal",
                    source_memory_candidate_id="memory-candidate:normal",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.5,
                    forced_consolidation=False,
                    workspace_score_hint=0.6,
                ),
            ),
            tick_id=tick_id,
        )


@dataclass
class DuplicateSourceCandidatePath(WorkspaceCompetitionPath):
    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        return WorkspaceCandidateSet(
            set_id="workspace-set:duplicate-source",
            source_feeling_state_id=feeling_state.state_id,
            candidates=(
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:forced-a",
                    source_memory_candidate_id="memory-candidate:forced",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.8,
                    forced_consolidation=True,
                    workspace_score_hint=0.9,
                ),
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:forced-b",
                    source_memory_candidate_id="memory-candidate:forced",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.75,
                    forced_consolidation=True,
                    workspace_score_hint=0.88,
                ),
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:normal",
                    source_memory_candidate_id="memory-candidate:normal",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.5,
                    forced_consolidation=False,
                    workspace_score_hint=0.6,
                ),
            ),
            tick_id=tick_id,
        )


@dataclass
class MismatchedReplayProvenancePath(WorkspaceCompetitionPath):
    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        return WorkspaceCandidateSet(
            set_id="workspace-set:mismatch",
            source_feeling_state_id=feeling_state.state_id,
            candidates=(
                WorkspaceCandidate(
                    candidate_id="workspace-candidate:forced",
                    source_memory_candidate_id="memory-candidate:forced",
                    source_feeling_state_id=feeling_state.state_id,
                    priority_hint=0.8,
                    forced_consolidation=True,
                    workspace_score_hint=0.9,
                ),
            ),
            tick_id=tick_id,
        )


def test_engine_rejects_malformed_feeling_state_before_competition_invocation() -> None:
    competition_path = CountingCompetitionPath()
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=competition_path,
        retention_path=CountingRetentionPath(),
    )

    @dataclass
    class MalformedFeelingState:
        state_id: str = ""
        source_neuromodulator_state_id: str = "neuromodulator-state:001"
        feeling: InteroceptiveFeelingVector = _build_feeling(0.6)
        tick_id: int | None = 9

    with pytest.raises(WorkspaceCompetitionError, match="non-empty state_id"):
        engine.compete(_build_replay_candidates(), MalformedFeelingState(), tick_id=13)  # type: ignore[arg-type]

    assert competition_path.calls == 0


def test_engine_rejects_replay_candidates_with_feeling_provenance_mismatch() -> None:
    mismatched_replay_candidates = (
        MemoryReplayCandidate(
            candidate_id="memory-candidate:forced",
            memory_id="memory:001",
            family="episodic",
            source_feeling_state_id="interoceptive-feeling-state:other",
            replay_reasons=("high_affect_intensity",),
            forced_consolidation=True,
            priority_hint=0.8,
        ),
    )
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=MismatchedReplayProvenancePath(),
        retention_path=CountingRetentionPath(),
    )

    with pytest.raises(WorkspaceCompetitionError, match="source feeling state provenance used for workspace competition"):
        engine.compete(mismatched_replay_candidates, _build_feeling_state(), tick_id=13)


def test_engine_competes_and_publishes_working_state_with_injected_collaborators() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=CountingCompetitionPath(),
        retention_path=CountingRetentionPath(),
    )

    candidate_set, working_state = engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)

    assert candidate_set.set_id == "workspace-set:001"
    assert len(candidate_set.candidates) == 2
    assert working_state.source_candidate_set_id == candidate_set.set_id
    assert working_state.retained_candidate_ids == ("workspace-candidate:forced",)


def test_engine_builds_request_and_publication_ops_from_valid_inputs() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=CountingCompetitionPath(),
        retention_path=CountingRetentionPath(),
    )
    candidate_set, working_state = engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)

    run_op = engine.build_run_competition_op(_build_replay_candidates(), _build_feeling_state())
    publish_set_op = engine.build_publish_candidate_set_op(candidate_set)
    publish_state_op = engine.build_publish_working_state_op(working_state)

    assert run_op.op_name == "run_workspace_competition"
    assert run_op.candidate_count == 2
    assert publish_set_op.op_name == "publish_workspace_candidate_set"
    assert publish_set_op.forced_candidate_count == 1
    assert publish_state_op.op_name == "publish_working_state_snapshot"
    assert publish_state_op.retained_candidate_count == 1


def test_engine_fails_explicitly_when_required_competition_capability_is_unavailable() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=UnavailableCompetitionPath(),
        retention_path=CountingRetentionPath(),
    )

    with pytest.raises(WorkspaceCompetitionError, match="competition capability is unavailable"):
        engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)


def test_engine_rejects_candidate_sets_that_drop_forced_consolidation_candidates() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=MissingForcedCandidatePath(),
        retention_path=CountingRetentionPath(),
    )

    with pytest.raises(WorkspaceCompetitionError, match="must be included in the published workspace candidate set"):
        engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)


def test_engine_rejects_working_state_that_retains_unknown_candidate_ids() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=CountingCompetitionPath(),
        retention_path=WrongRetentionPath(),
    )

    with pytest.raises(WorkspaceCompetitionError, match="retain only candidate ids published"):
        engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)


def test_engine_rejects_non_memory_candidate_inputs() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=CountingCompetitionPath(),
        retention_path=CountingRetentionPath(),
    )

    @dataclass
    class ForeignCandidate:
        candidate_id: str = "foreign:001"

    with pytest.raises(WorkspaceCompetitionError, match="only accepts explicit MemoryReplayCandidate"):
        engine.build_run_competition_op((ForeignCandidate(),), _build_feeling_state())  # type: ignore[arg-type]


def test_engine_rejects_workspace_candidates_that_do_not_preserve_forced_consolidation_flag() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=WrongForcedFlagPath(),
        retention_path=CountingRetentionPath(),
    )

    with pytest.raises(WorkspaceCompetitionError, match="must preserve the forced_consolidation flag"):
        engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)


def test_engine_rejects_duplicate_source_memory_candidate_ids_in_candidate_set() -> None:
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=DuplicateSourceCandidatePath(),
        retention_path=CountingRetentionPath(),
    )

    with pytest.raises(WorkspaceCompetitionError, match="must not publish duplicate source_memory_candidate_id"):
        engine.compete(_build_replay_candidates(), _build_feeling_state(), tick_id=13)


# --- R46: real salience-weighted competition + bounded attention retention (owner-owned) ---

from helios_v2.workspace import (  # noqa: E402
    BoundedAttentionRetentionPath,
    SalienceWeightedWorkspaceCompetitionPath,
)


def _feeling_state(arousal: float, tension: float = 0.3, pain: float = 0.0) -> InteroceptiveFeelingState:
    return InteroceptiveFeelingState(
        state_id="interoceptive-feeling-state:001",
        source_neuromodulator_state_id="neuromodulator-state:001",
        feeling=InteroceptiveFeelingVector(
            valence=0.5,
            arousal=arousal,
            tension=tension,
            comfort=0.5,
            fatigue=0.3,
            pain_like=pain,
            social_safety=0.5,
        ),
        tick_id=9,
    )


def _replay(candidate_id: str, priority: float, *, forced: bool = False) -> MemoryReplayCandidate:
    return MemoryReplayCandidate(
        candidate_id=candidate_id,
        memory_id=f"memory:{candidate_id}",
        family="episodic",
        source_feeling_state_id="interoceptive-feeling-state:001",
        replay_reasons=("high_affect_intensity",),
        forced_consolidation=forced,
        priority_hint=priority,
    )


def test_competition_score_increases_with_priority_hint() -> None:
    path = SalienceWeightedWorkspaceCompetitionPath()
    feeling = _feeling_state(arousal=0.4)
    candidates = (_replay("c-high", 0.9), _replay("c-low", 0.2))

    result = path.build_candidate_set(candidates, feeling, _build_config(), 7)

    by_source = {c.source_memory_candidate_id: c for c in result.candidates}
    assert by_source["c-high"].workspace_score_hint > by_source["c-low"].workspace_score_hint
    assert all(0.0 <= c.workspace_score_hint <= 1.0 for c in result.candidates)


def test_competition_score_increases_with_feeling_salience() -> None:
    path = SalienceWeightedWorkspaceCompetitionPath()
    candidates = (_replay("c", 0.5),)

    calm = path.build_candidate_set(candidates, _feeling_state(arousal=0.1, tension=0.1), _build_config(), 7)
    aroused = path.build_candidate_set(candidates, _feeling_state(arousal=0.9, tension=0.9), _build_config(), 7)

    assert aroused.candidates[0].workspace_score_hint > calm.candidates[0].workspace_score_hint


def test_competition_preserves_provenance_and_forced_flag_and_keeps_all_candidates() -> None:
    path = SalienceWeightedWorkspaceCompetitionPath()
    feeling = _feeling_state(arousal=0.5)
    candidates = (_replay("c-forced", 0.3, forced=True), _replay("c-normal", 0.9))

    result = path.build_candidate_set(candidates, feeling, _build_config(), 7)

    # Every replay candidate is still in the published set (the owner invariant).
    assert len(result.candidates) == 2
    by_source = {c.source_memory_candidate_id: c for c in result.candidates}
    assert by_source["c-forced"].forced_consolidation is True
    assert all(c.source_feeling_state_id == feeling.state_id for c in result.candidates)


def test_competition_is_deterministic() -> None:
    path = SalienceWeightedWorkspaceCompetitionPath()
    feeling = _feeling_state(arousal=0.6)
    candidates = (_replay("a", 0.7), _replay("b", 0.4))
    first = path.build_candidate_set(candidates, feeling, _build_config(), 7)
    second = path.build_candidate_set(candidates, feeling, _build_config(), 7)
    assert [c.workspace_score_hint for c in first.candidates] == [
        c.workspace_score_hint for c in second.candidates
    ]


def _candidate_set_with_scores(scores: dict[str, float]) -> WorkspaceCandidateSet:
    return WorkspaceCandidateSet(
        set_id="workspace-set:001",
        source_feeling_state_id="interoceptive-feeling-state:001",
        candidates=tuple(
            WorkspaceCandidate(
                candidate_id=cid,
                source_memory_candidate_id=f"memory-candidate:{cid}",
                source_feeling_state_id="interoceptive-feeling-state:001",
                priority_hint=0.5,
                forced_consolidation=False,
                workspace_score_hint=score,
            )
            for cid, score in scores.items()
        ),
        tick_id=9,
    )


def test_bounded_retention_keeps_only_top_k() -> None:
    path = BoundedAttentionRetentionPath(max_retained=2)
    candidate_set = _candidate_set_with_scores({"low": 0.2, "mid": 0.5, "high": 0.9})

    snapshot = path.retain_working_state(candidate_set, _build_config(), 9)

    assert len(snapshot.retained_candidate_ids) == 2
    assert set(snapshot.retained_candidate_ids) == {"high", "mid"}
    assert "low" not in snapshot.retained_candidate_ids


def test_bounded_retention_never_empty_for_non_empty_set() -> None:
    path = BoundedAttentionRetentionPath(max_retained=0)  # pathological config
    candidate_set = _candidate_set_with_scores({"only": 0.3})
    snapshot = path.retain_working_state(candidate_set, _build_config(), 9)
    assert snapshot.retained_candidate_ids == ("only",)


def test_bounded_retention_tie_break_is_deterministic() -> None:
    path = BoundedAttentionRetentionPath(max_retained=1)
    # Two equal scores: the lexicographically smaller candidate_id wins deterministically.
    candidate_set = _candidate_set_with_scores({"b-id": 0.5, "a-id": 0.5})
    snapshot = path.retain_working_state(candidate_set, _build_config(), 9)
    assert snapshot.retained_candidate_ids == ("a-id",)


def test_real_paths_pass_engine_invariants_with_forced_candidate_losing_attention() -> None:
    # A forced-consolidation candidate with a LOW priority loses the attention competition and is
    # excluded from the bounded working state, while remaining in the candidate set. This must
    # pass every engine invariant (forced stays in the SET; retained ids subset of the set).
    engine = WorkspaceCompetitionEngine(
        config=_build_config(),
        competition_path=SalienceWeightedWorkspaceCompetitionPath(),
        retention_path=BoundedAttentionRetentionPath(max_retained=1),
    )
    feeling = _feeling_state(arousal=0.3, tension=0.2)
    candidates = (
        _replay("c-forced-low", 0.1, forced=True),
        _replay("c-normal-high", 0.95),
    )

    candidate_set, working_state = engine.compete(candidates, feeling, tick_id=7)

    # Forced candidate is still in the published candidate set (consolidation membership).
    forced_in_set = any(
        c.source_memory_candidate_id == "c-forced-low" and c.forced_consolidation
        for c in candidate_set.candidates
    )
    assert forced_in_set
    # But the bounded attention focus held only the higher-salience normal candidate.
    assert len(working_state.retained_candidate_ids) == 1
    retained = candidate_set.candidates[
        [c.candidate_id for c in candidate_set.candidates].index(working_state.retained_candidate_ids[0])
    ]
    assert retained.source_memory_candidate_id == "c-normal-high"
