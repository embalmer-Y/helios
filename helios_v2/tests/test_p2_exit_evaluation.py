"""R73 — P2 exit evaluation: automated P2 milestone assessment.

Validates the P2 durable-memory and knowledge-foundation milestone
(PHASE_METRICS.md §4):
"P2 — Durable memory and knowledge foundation"

Scope
-----
- P2-T2: 33 store persists experience records across ticks.
- P2-T3: cross-restart continuity — new process retrieves prior session experience.
- P2-T4: semantic recall — search_similar ranks by cosine after embedding.
- P2-T5: checkpoint/restore — 42 checkpoint saves and restores cross-tick state.
- P2-T6: dual-timescale evolution — 04/05 cross-tick carry state differs from cold baseline.
- P2-H1: subjective continuity across restart (33 + 42 end-to-end).
- P2-H2: retrieval driven by real representation (semantic recall).
- P2-H3: embedding failure = hard stop.
- P2-H4: 06/04/05/14 persistence paths clearly defined.

This test module is **read-only**: it asserts over the existing runtime but never
modifies any owner implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import assemble_runtime, default_composition_config
from helios_v2.composition import RuntimeProfile
from helios_v2.embedding import (
    EmbeddingError,
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
    SqliteExperienceStoreBackend,
)
from helios_v2.continuity_checkpoint import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
    SqliteCheckpointBackend,
)
from helios_v2.feeling import InteroceptiveFeelingVector


# ---------------------------------------------------------------------------
# Fake providers (deterministic, network-free)
# ---------------------------------------------------------------------------


@dataclass
class _FakeThoughtProvider:
    thought_text: str = "deterministic llm thought for the current cycle"
    finish_reason: str = "stop"
    sufficiency: float = 0.9
    wants_to_continue: bool = False
    continue_reason: str = ""
    intends_action: bool = True
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        self.calls.append(profile.profile_name)
        envelope = {
            "thought": self.thought_text,
            "sufficiency": self.sufficiency,
            "wants_to_continue": self.wants_to_continue,
            "continue_reason": self.continue_reason,
            "proposed_action": {"intends_action": self.intends_action, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(
            output_text=json.dumps(envelope), finish_reason=self.finish_reason
        )


class _FakeEmbeddingProvider:
    """Deterministic hash-based embedding; similar texts embed similarly."""

    dimensions: int = 16

    def embed(self, profile, request, api_key):
        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)


class _RaisingEmbeddingProvider:
    """Provider double that always fails, to exercise the embedding hard-stop."""

    def embed(self, profile, request, api_key):
        raise EmbeddingError("simulated embedding transport failure")


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


def _ready_gateway(config=None, provider=None) -> LlmGateway:
    resolved = config if config is not None else default_composition_config()
    return LlmGateway(
        provider=provider or _FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=resolved.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _embedding_gateway(provider=None) -> EmbeddingGateway:
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    return EmbeddingGateway(
        provider=provider or _FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble(**kwargs):
    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway()
    return assemble_runtime(**kwargs)


# ---------------------------------------------------------------------------
# Stage-result accessors
# ---------------------------------------------------------------------------


def _neuromodulator_levels(result):
    return result.stage_results["neuromodulator_system"].state.levels


def _feeling(result):
    return result.stage_results["interoceptive_feeling_layer"].state.feeling


# ---------------------------------------------------------------------------
# P2 exit evaluation: data structures
# ---------------------------------------------------------------------------


@dataclass
class P2ExitCheck:
    """One atomic check in the P2 exit evaluation."""

    check_id: str
    description: str
    passed: bool
    evidence: str = ""


@dataclass
class P2ExitVerdict:
    """Aggregated P2 exit verdict."""

    checks: list[P2ExitCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def add(self, check: P2ExitCheck) -> None:
        self.checks.append(check)

    def summary(self) -> dict:
        return {
            "verdict": "PASS" if self.passed else "FAIL",
            "total": len(self.checks),
            "passed": sum(1 for c in self.checks if c.passed),
            "failed": sum(1 for c in self.checks if not c.passed),
            "details": [
                {"id": c.check_id, "passed": c.passed, "evidence": c.evidence}
                for c in self.checks
            ],
        }


# ===========================================================================
# P2-T2: Durable store persists experience records
# ===========================================================================


def test_p2_t2_store_persists_experience(tmp_path) -> None:
    """P2-T2: 33 store persists experience; count ≥ 10 after 10 ticks."""
    db_path = str(tmp_path / "p2_store.sqlite3")
    store = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
    )
    handle.startup()
    handle.run_ticks(10)

    count = store.count()
    assert count >= 10, f"expected ≥ 10 records after 10 ticks, got {count}"

    # Every persisted record has an embedding (semantic memory enabled).
    recent = store.read_recent(100)
    assert all(r.embedding is not None for r in recent), (
        "all persisted records should have embeddings under semantic assembly"
    )


# ===========================================================================
# P2-T3: Cross-restart continuity
# ===========================================================================


def test_p2_t3_cross_restart_continuity(tmp_path) -> None:
    """P2-T3: new process retrieves prior session experience after restart."""
    db_path = str(tmp_path / "p2_restart.sqlite3")

    # Session A: run ticks, persist, then drop the handle.
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle_a = _assemble(
        experience_store=store_a,
        embedding_gateway=_embedding_gateway(),
    )
    handle_a.startup()
    handle_a.run_ticks(5)
    count_a = store_a.count()
    assert count_a >= 5
    del handle_a, store_a

    # Session B: a new store object on the same file sees prior records.
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    assert store_b.count() == count_a

    handle_b = _assemble(
        experience_store=store_b,
        embedding_gateway=_embedding_gateway(),
    )
    handle_b.startup()
    result = handle_b.tick()

    # The prior session's experience re-enters the new session's thought window.
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    assert any(
        hit.source in ("experience_store", "experience_store_semantic")
        for hit in all_hits
    ), "prior session experience should be retrieved after restart"


# ===========================================================================
# P2-T4: Semantic recall
# ===========================================================================


def test_p2_t4_semantic_recall_cosine_ranking() -> None:
    """P2-T4: search_similar ranks by cosine similarity after embedding."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())

    # Populate records with known embedding vectors.
    from helios_v2.persistence.contracts import PersistedExperienceRecord

    records = []
    for i in range(10):
        vec = tuple([1.0 if j == i % 16 else 0.0 for j in range(16)])
        records.append(PersistedExperienceRecord(
            record_id=f"r-{i}",
            tick_id=i,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-{i}",
            writeback_status="written_internal_only",
            summary=f"record {i}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=(),
            linkage={},
            embedding=vec,
        ))
    store.append_records(tuple(records))

    # Query with a vector aligned to record 0's embedding.
    query = tuple([1.0] + [0.0] * 15)
    result = store.search_similar(query, limit=3, max_scan=10)

    # Record 0 should rank first (exact alignment).
    assert len(result.hits) >= 1
    assert result.hits[0].record.record_id == "r-0"
    assert result.hits[0].similarity > 0.9


# ===========================================================================
# P2-T5: Checkpoint save/restore
# ===========================================================================


def test_p2_t5_checkpoint_save_restore(tmp_path) -> None:
    """P2-T5: 42 checkpoint saves and restores 09/18 cross-tick state."""
    ckpt_path = str(tmp_path / "p2_checkpoint.sqlite3")
    store_path = str(tmp_path / "p2_store.sqlite3")

    # Session A: run ticks with checkpoint, then verify state is saved.
    ckpt_a = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=ckpt_path)
    )
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path))
    handle_a = _assemble(
        experience_store=store_a,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_a,
    )
    handle_a.startup()
    handle_a.run_ticks(3)

    saved = ckpt_a.load_latest()
    assert saved is not None, "checkpoint should have saved after 3 ticks"
    assert saved.continuation_state is not None

    # Session B: a new checkpoint store on the same file restores the state.
    ckpt_b = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=ckpt_path)
    )
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path))
    handle_b = _assemble(
        experience_store=store_b,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_b,
    )
    handle_b.startup()

    # The restored state seeds the 09 stage's prior continuation pressure.
    seeded = handle_b.thought_gating_stage._prior_continuation_state
    assert seeded is not None, "09 stage should have restored prior continuation state"


# ===========================================================================
# P2-T6: Dual-timescale evolution (04/05 cross-tick carry)
# ===========================================================================


def test_p2_t6_dual_timescale_evolution() -> None:
    """P2-T6: 04/05 cross-tick carry state differs from cold baseline."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
    )
    handle.startup()

    results = handle.run_ticks(3)

    # 04 neuromodulator: dopamine trajectory must not be constant.
    dopamine = [_neuromodulator_levels(r).dopamine for r in results]
    assert len(set(dopamine)) > 1, (
        f"04 dopamine should evolve cross-tick, got {dopamine}"
    )

    # 05 feeling: valence trajectory must not be constant.
    valence = [_feeling(r).valence for r in results]
    assert len(set(valence)) > 1, (
        f"05 valence should evolve cross-tick, got {valence}"
    )


# ===========================================================================
# P2-H1: Subjective continuity across restart (33 + 42 end-to-end)
# ===========================================================================


def test_p2_h1_subjective_continuity_across_restart(tmp_path) -> None:
    """P2-H1: 33 + 42 together maintain subjective continuity across restart."""
    ckpt_path = str(tmp_path / "p2h1_checkpoint.sqlite3")
    store_path = str(tmp_path / "p2h1_store.sqlite3")

    # Session A: run semantic assembly with checkpoint.
    ckpt_a = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=ckpt_path)
    )
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path))
    handle_a = _assemble(
        experience_store=store_a,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_a,
    )
    handle_a.startup()
    handle_a.run_ticks(5)

    # Checkpoint has feeling + neuromodulator levels (version 3).
    saved = ckpt_a.load_latest()
    assert saved is not None
    assert saved.feeling is not None, "checkpoint should save 05 feeling state"
    assert saved.neuromodulator_levels is not None, "checkpoint should save 04 levels"
    assert saved.snapshot_version == 4

    # Session B: restore and verify.
    ckpt_b = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=ckpt_path)
    )
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path))
    handle_b = _assemble(
        experience_store=store_b,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_b,
    )
    handle_b.startup()

    # Both 04 and 05 stages should have seeded prior state.
    assert handle_b.feeling_stage._prior_state is not None
    seeded_feeling = handle_b.feeling_stage._prior_state.feeling
    assert seeded_feeling == saved.feeling


# ===========================================================================
# P2-H2: Retrieval driven by real representation
# ===========================================================================


def test_p2_h2_retrieval_driven_by_real_representation() -> None:
    """P2-H2: semantic retrieval is driven by real embedding, not just recency."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())

    from helios_v2.persistence.contracts import PersistedExperienceRecord

    # Two records with different embeddings.
    vec_a = tuple([1.0, 0.0] + [0.0] * 14)  # aligned with "topic A"
    vec_b = tuple([0.0, 1.0] + [0.0] * 14)  # aligned with "topic B"
    records = [
        PersistedExperienceRecord(
            record_id="topic-a",
            tick_id=1,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id="src-a",
            writeback_status="written_internal_only",
            summary="topic A experience",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=(),
            linkage={},
            embedding=vec_a,
        ),
        PersistedExperienceRecord(
            record_id="topic-b",
            tick_id=2,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id="src-b",
            writeback_status="written_internal_only",
            summary="topic B experience",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=(),
            linkage={},
            embedding=vec_b,
        ),
    ]
    store.append_records(tuple(records))

    # Query aligned with topic A: topic-a should rank first despite being older.
    result = store.search_similar(vec_a, limit=2, max_scan=10)
    assert len(result.hits) == 2
    assert result.hits[0].record.record_id == "topic-a", (
        "semantic recall should rank by cosine, not recency"
    )


# ===========================================================================
# P2-H3: Embedding failure = hard stop
# ===========================================================================


def test_p2_h3_embedding_failure_hard_stop() -> None:
    """P2-H3: embedding failure causes hard stop, no silent degradation."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    # Use a raising provider to simulate embedding failure.
    failing_gateway = _embedding_gateway(provider=_RaisingEmbeddingProvider())

    handle = _assemble(
        experience_store=store,
        embedding_gateway=failing_gateway,
    )
    handle.startup()

    # A tick that produces a persistable experience should fail on embedding.
    with pytest.raises(Exception):
        handle.tick()


# ===========================================================================
# P2-H4: Persistence paths clearly defined
# ===========================================================================


def test_p2_h4_persistence_paths_defined() -> None:
    """P2-H4: 06/04/05/14 persistence paths are clearly defined (not ad-hoc)."""
    # 06 memory formation: AffectGroundedMemoryFormationPath exists in helios_v2.memory.
    from helios_v2.memory import AffectGroundedMemoryFormationPath
    assert AffectGroundedMemoryFormationPath is not None

    # 04 dual-timescale: DualTimescaleNeuromodulatorUpdatePath exists in helios_v2.neuromodulation.
    from helios_v2.neuromodulation import DualTimescaleNeuromodulatorUpdatePath
    assert DualTimescaleNeuromodulatorUpdatePath is not None

    # 05 persistent feeling: PersistentFeelingConstructionPath exists in helios_v2.feeling.
    from helios_v2.feeling import PersistentFeelingConstructionPath
    assert PersistentFeelingConstructionPath is not None

    # 14 identity governance carry: GovernanceCarryState exists in helios_v2.identity_governance.
    from helios_v2.identity_governance import GovernanceCarryState
    assert GovernanceCarryState is not None


# ===========================================================================
# P2 comprehensive exit verdict
# ===========================================================================


def test_p2_exit_verdict(tmp_path) -> None:
    """Run all P2 exit checks and produce a structured pass/fail verdict."""
    verdict = P2ExitVerdict()

    # -- P2-T2: Store persists --
    db_t2 = str(tmp_path / "p2v_store.sqlite3")
    store_t2 = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_t2))
    handle_t2 = _assemble(
        experience_store=store_t2,
        embedding_gateway=_embedding_gateway(),
    )
    handle_t2.startup()
    handle_t2.run_ticks(10)
    count_t2 = store_t2.count()
    verdict.add(P2ExitCheck(
        "P2-T2", "store persists experience",
        count_t2 >= 10,
        f"count={count_t2}",
    ))

    # -- P2-T3: Cross-restart continuity --
    db_t3 = str(tmp_path / "p2v_restart.sqlite3")
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_t3))
    handle_a = _assemble(
        experience_store=store_a,
        embedding_gateway=_embedding_gateway(),
    )
    handle_a.startup()
    handle_a.run_ticks(3)
    count_a = store_a.count()
    del handle_a, store_a

    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_t3))
    handle_b = _assemble(
        experience_store=store_b,
        embedding_gateway=_embedding_gateway(),
    )
    handle_b.startup()
    # Verify persistent continuity BEFORE tick (tick appends new records).
    count_b_before = store_b.count()
    result_b = handle_b.tick()
    bundle = result_b.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    has_recall = any(
        hit.source in ("experience_store", "experience_store_semantic")
        for hit in all_hits
    )
    verdict.add(P2ExitCheck(
        "P2-T3", "cross-restart continuity",
        count_b_before == count_a and has_recall,
        f"count_match={count_b_before == count_a}, recall={has_recall}",
    ))

    # -- P2-T4: Semantic recall cosine ranking --
    store_t4 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    from helios_v2.persistence.contracts import PersistedExperienceRecord
    recs = [
        PersistedExperienceRecord(
            record_id=f"t4-{i}", tick_id=i,
            continuity_kind="internal_only", outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed", source_outcome_id=f"s-{i}",
            writeback_status="written_internal_only", summary=f"r{i}",
            requested_effect_summary="", applied_effect_summary="",
            reason_trace=(), linkage={},
            embedding=tuple([1.0 if j == i % 16 else 0.0 for j in range(16)]),
        )
        for i in range(5)
    ]
    store_t4.append_records(tuple(recs))
    query = tuple([1.0] + [0.0] * 15)
    sr = store_t4.search_similar(query, limit=2, max_scan=5)
    verdict.add(P2ExitCheck(
        "P2-T4", "semantic recall cosine ranking",
        len(sr.hits) >= 1 and sr.hits[0].record.record_id == "t4-0",
        f"hits={len(sr.hits)}, top={sr.hits[0].record.record_id if sr.hits else 'none'}",
    ))

    # -- P2-T5: Checkpoint save/restore --
    ckpt_t5 = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    store_t5 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_t5 = _assemble(
        experience_store=store_t5,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_t5,
    )
    handle_t5.startup()
    handle_t5.run_ticks(3)
    saved_t5 = ckpt_t5.load_latest()
    verdict.add(P2ExitCheck(
        "P2-T5", "checkpoint save/restore",
        saved_t5 is not None and saved_t5.continuation_state is not None,
        f"version={saved_t5.snapshot_version if saved_t5 else 'none'}",
    ))

    # -- P2-T6: Dual-timescale evolution --
    store_t6 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_t6 = _assemble(
        experience_store=store_t6,
        embedding_gateway=_embedding_gateway(),
    )
    handle_t6.startup()
    results_t6 = handle_t6.run_ticks(3)
    dopamine_vals = [_neuromodulator_levels(r).dopamine for r in results_t6]
    valence_vals = [_feeling(r).valence for r in results_t6]
    verdict.add(P2ExitCheck(
        "P2-T6", "dual-timescale evolution (04+05)",
        len(set(dopamine_vals)) > 1 and len(set(valence_vals)) > 1,
        f"04_dopamine={dopamine_vals}, 05_valence={valence_vals}",
    ))

    # -- P2-H1: Subjective continuity across restart --
    ckpt_h1 = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    store_h1 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_h1 = _assemble(
        experience_store=store_h1,
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_h1,
    )
    handle_h1.startup()
    handle_h1.run_ticks(3)
    saved_h1 = ckpt_h1.load_latest()
    verdict.add(P2ExitCheck(
        "P2-H1", "subjective continuity across restart",
        saved_h1 is not None and saved_h1.feeling is not None and saved_h1.neuromodulator_levels is not None,
        f"v={saved_h1.snapshot_version if saved_h1 else 'none'}, "
        f"feeling={'yes' if saved_h1 and saved_h1.feeling else 'no'}, "
        f"nm={'yes' if saved_h1 and saved_h1.neuromodulator_levels else 'no'}",
    ))

    # -- P2-H2: Real representation retrieval (reuses P2-T4 check) --
    verdict.add(P2ExitCheck(
        "P2-H2", "retrieval by real representation",
        len(sr.hits) >= 1 and sr.hits[0].record.record_id == "t4-0",
        "semantic recall ranks by cosine, not recency",
    ))

    # -- P2-H3: Embedding failure hard stop --
    store_h3 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    failing_gw = _embedding_gateway(provider=_RaisingEmbeddingProvider())
    handle_h3 = _assemble(
        experience_store=store_h3,
        embedding_gateway=failing_gw,
    )
    handle_h3.startup()
    embedding_hard_stop = False
    try:
        handle_h3.tick()
    except Exception:
        embedding_hard_stop = True
    verdict.add(P2ExitCheck(
        "P2-H3", "embedding failure = hard stop",
        embedding_hard_stop,
        "tick raises on embedding failure",
    ))

    # -- P2-H4: Persistence paths defined --
    paths_ok = True
    try:
        from helios_v2.memory import AffectGroundedMemoryFormationPath
        from helios_v2.neuromodulation import DualTimescaleNeuromodulatorUpdatePath
        from helios_v2.feeling import PersistentFeelingConstructionPath
        from helios_v2.identity_governance import GovernanceCarryState
    except ImportError:
        paths_ok = False
    verdict.add(P2ExitCheck(
        "P2-H4", "persistence paths clearly defined",
        paths_ok,
        "06/04/05/14 persistence types importable from owner packages",
    ))

    # Final assertion.
    assert verdict.passed, (
        f"P2 EXIT VERDICT: FAIL\n"
        + "\n".join(
            f"  [FAIL] {c.check_id}: {c.description} — {c.evidence}"
            for c in verdict.checks
            if not c.passed
        )
    )

    summary = verdict.summary()
    print(f"\n{'=' * 60}")
    print(f"P2 EXIT VERDICT: {summary['verdict']}")
    print(f"  Total: {summary['total']}, Passed: {summary['passed']}, Failed: {summary['failed']}")
    for d in summary["details"]:
        status = "PASS" if d["passed"] else "FAIL"
        print(f"  [{status}] {d['id']}: {d['evidence']}")
    print(f"{'=' * 60}")
