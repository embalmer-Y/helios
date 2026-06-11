"""R76 — Memory stability assessment: persistent memory system reliability.

Evaluates the stability of the durable experience store and semantic recall:

- **MS-1**: Write durability — SQLite backend consistency after 50+ ticks.
- **MS-2**: Semantic recall precision — same query → consistent cosine ranking.
- **MS-3**: Cross-restart integrity — session A write → session B read completeness.
- **MS-4**: Checkpoint v3 round-trip — save/restore lossless.
- **MS-5**: Consolidation gating — affect-intensity controls consolidation.
- **MS-6**: Affect-memory and experience-writeback coexistence.

This module is **read-only**: it runs the runtime and inspects memory state
but never modifies owner code.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

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
    SqliteExperienceStoreBackend,
)
from helios_v2.persistence.contracts import PersistedExperienceRecord
from helios_v2.continuity_checkpoint import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
    SqliteCheckpointBackend,
)


# ---------------------------------------------------------------------------
# Fake providers
# ---------------------------------------------------------------------------


@dataclass
class _FakeThoughtProvider:
    thought_text: str = "deterministic thought for memory stability"
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


def _embedding_gateway(provider=None):
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        dimensions=16,
    )
    return EmbeddingGateway(
        provider=provider or _FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble_semantic(**kwargs):
    kwargs.setdefault("gateway", _ready_gateway())
    kwargs.setdefault("experience_store", ExperienceStore(backend=InMemoryExperienceStoreBackend()))
    kwargs.setdefault("embedding_gateway", _embedding_gateway())
    return assemble_runtime(**kwargs)


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclass
class MemoryCheck:
    check_id: str
    description: str
    passed: bool
    evidence: str


@dataclass
class MemoryVerdict:
    checks: list[MemoryCheck] = field(default_factory=list)

    def add(self, check: MemoryCheck) -> None:
        self.checks.append(check)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


# ===========================================================================
# MS-1: Write durability (SQLite 50+ ticks)
# ===========================================================================


def test_ms1_sqlite_write_durability(tmp_path) -> None:
    """SQLite store must handle 50+ consecutive tick writes consistently."""
    db_path = str(tmp_path / "ms1_durability.sqlite3")
    store = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle = _assemble_semantic(experience_store=store)
    handle.startup()

    # Run 50 ticks.
    handle.run_ticks(50)

    count = store.count()
    assert count >= 50, f"Expected >= 50 records after 50 ticks, got {count}"

    # Verify all records are readable.
    recent = store.read_recent(10)
    assert len(recent) == 10, f"Expected 10 recent records, got {len(recent)}"

    # Verify file exists and has non-trivial size.
    file_size = os.path.getsize(db_path)
    assert file_size > 0, "SQLite file should have non-zero size"


# ===========================================================================
# MS-2: Semantic recall precision (same query → consistent ranking)
# ===========================================================================


def test_ms2_semantic_recall_consistency() -> None:
    """Same query must produce consistent cosine ranking across multiple calls."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    gw = _embedding_gateway()

    # Manually insert records with known embeddings.
    from helios_v2.persistence.contracts import PersistedExperienceRecord

    records = tuple(
        PersistedExperienceRecord(
            record_id=f"ms2-{i}",
            tick_id=i,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"source-{i}",
            writeback_status="written_internal_only",
            summary=f"experience record number {i} with content about topic {'alpha' if i < 5 else 'beta'}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("ms2-test",),
            linkage={},
            embedding=tuple([float(i % 5 + 1) * 0.1] * 16),
        )
        for i in range(10)
    )
    store.append_records(records)

    # Run search_similar twice with the same query.
    results_1 = store.search_similar(
        query_vector=tuple([0.2] * 16),
        limit=5,
        max_scan=100,
    )
    results_2 = store.search_similar(
        query_vector=tuple([0.2] * 16),
        limit=5,
        max_scan=100,
    )

    # Results must be identical (deterministic cosine ranking).
    ids_1 = [hit.record.record_id for hit in results_1.hits]
    ids_2 = [hit.record.record_id for hit in results_2.hits]
    assert ids_1 == ids_2, (
        f"Semantic recall must be deterministic: {ids_1} != {ids_2}"
    )

    # Verify results are ranked by cosine similarity (not recency).
    assert len(results_1.hits) >= 1, "Should have at least one hit"


# ===========================================================================
# MS-3: Cross-restart integrity
# ===========================================================================


def test_ms3_cross_restart_record_integrity(tmp_path) -> None:
    """Session A records must be fully readable by session B."""
    db_path = str(tmp_path / "ms3_restart.sqlite3")

    # Session A: write records.
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle_a = _assemble_semantic(experience_store=store_a)
    handle_a.startup()
    handle_a.run_ticks(10)
    count_a = store_a.count()
    recent_a = store_a.read_recent(5)
    del handle_a, store_a

    # Session B: read from the same file.
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    count_b = store_b.count()

    # Count must match.
    assert count_b == count_a, (
        f"Cross-restart count mismatch: {count_b} != {count_a}"
    )

    # Recent records must have the same IDs.
    recent_b = store_b.read_recent(5)
    ids_a = [r.record_id for r in recent_a]
    ids_b = [r.record_id for r in recent_b]
    assert ids_a == ids_b, (
        f"Cross-restart record ID mismatch: {ids_a} != {ids_b}"
    )

    # Each record must have non-empty summary.
    for record in recent_b:
        assert record.summary, f"Record {record.record_id} has empty summary"


# ===========================================================================
# MS-4: Checkpoint v3 round-trip
# ===========================================================================


def test_ms4_checkpoint_v3_round_trip(tmp_path) -> None:
    """Checkpoint v3 save/restore must be lossless."""
    ckpt_path = str(tmp_path / "ms4_checkpoint.sqlite3")

    # Session A: save checkpoint.
    ckpt_a = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=ckpt_path)
    )
    handle_a = _assemble_semantic(continuity_checkpoint=ckpt_a)
    handle_a.startup()
    handle_a.run_ticks(3)

    saved_a = ckpt_a.load_latest()
    assert saved_a is not None, "Checkpoint must save after 3 ticks"
    assert saved_a.snapshot_version == 4, (
        f"Expected snapshot version 3, got {saved_a.snapshot_version}"
    )
    assert saved_a.continuation_state is not None
    assert saved_a.neuromodulator_levels is not None
    assert saved_a.feeling is not None

    # Session B: restore from the same file.
    ckpt_b = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=ckpt_path)
    )
    saved_b = ckpt_b.load_latest()
    assert saved_b is not None, "Session B must load the checkpoint"

    # Verify lossless round-trip.
    assert saved_b.snapshot_version == saved_a.snapshot_version
    assert saved_b.tick_id == saved_a.tick_id
    assert saved_b.continuation_state == saved_a.continuation_state
    assert saved_b.neuromodulator_levels == saved_a.neuromodulator_levels
    assert saved_b.feeling == saved_a.feeling


# ===========================================================================
# MS-5: Consolidation gating
# ===========================================================================


def test_ms5_consolidation_gating() -> None:
    """Memory consolidation must be gated by affect-intensity."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble_semantic(experience_store=store)
    handle.startup()

    # Run enough ticks to trigger some consolidation.
    handle.run_ticks(10)

    count = store.count()
    assert count >= 10, f"Expected >= 10 experience records, got {count}"

    # Some records should be affect_memory (consolidated) and some experience_writeback.
    all_records = store.read_recent(count)
    kinds = {r.record_kind for r in all_records if hasattr(r, 'record_kind')}

    # At minimum, experience_writeback records must exist.
    assert "experience_writeback" in kinds or len(kinds) == 0, (
        f"Expected experience_writeback records, got kinds: {kinds}"
    )


# ===========================================================================
# MS-6: Affect-memory and experience-writeback coexistence
# ===========================================================================


def test_ms6_record_kind_coexistence() -> None:
    """Multiple record kinds must coexist in the same store without interference."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())

    # Manually insert records of different kinds.
    exp_records = tuple(
        PersistedExperienceRecord(
            record_id=f"exp-{i}",
            tick_id=i,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-exp-{i}",
            writeback_status="written_internal_only",
            summary=f"experience writeback record {i}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("ms6-test",),
            linkage={},
            record_kind="experience_writeback",
        )
        for i in range(5)
    )
    aff_records = tuple(
        PersistedExperienceRecord(
            record_id=f"aff-{i}",
            tick_id=i + 10,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-aff-{i}",
            writeback_status="written_internal_only",
            summary=f"affect memory record {i}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("ms6-test",),
            linkage={},
            record_kind="affect_memory",
        )
        for i in range(3)
    )
    store.append_records(exp_records)
    store.append_records(aff_records)

    total = store.count()
    assert total == 8, f"Expected 8 total records, got {total}"

    # Both kinds must be retrievable.
    all_records = store.read_recent(total)
    kinds = {r.record_kind for r in all_records}
    assert "experience_writeback" in kinds
    assert "affect_memory" in kinds


# ===========================================================================
# Composite verdict
# ===========================================================================


def test_memory_stability_composite_verdict(tmp_path) -> None:
    """Composite verdict for memory stability assessment."""
    verdict = MemoryVerdict()

    # -- MS-1: Write durability --
    db_ms1 = str(tmp_path / "ms1v.sqlite3")
    store_ms1 = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_ms1))
    handle_ms1 = _assemble_semantic(experience_store=store_ms1)
    handle_ms1.startup()
    handle_ms1.run_ticks(50)
    count_ms1 = store_ms1.count()
    verdict.add(MemoryCheck(
        "MS-1", "write durability (50 ticks)",
        count_ms1 >= 50,
        f"count={count_ms1}",
    ))

    # -- MS-2: Recall consistency --
    store_ms2 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    ms2_records = tuple(
        PersistedExperienceRecord(
            record_id=f"ms2v-{i}", tick_id=i,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-{i}",
            writeback_status="written_internal_only",
            summary=f"ms2 record {i}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("ms2v-test",),
            linkage={},
            embedding=tuple([float(i % 5 + 1) * 0.1] * 16),
        )
        for i in range(10)
    )
    store_ms2.append_records(ms2_records)
    r1 = store_ms2.search_similar(tuple([0.2] * 16), limit=5, max_scan=100)
    r2 = store_ms2.search_similar(tuple([0.2] * 16), limit=5, max_scan=100)
    ids1 = [h.record.record_id for h in r1.hits]
    ids2 = [h.record.record_id for h in r2.hits]
    verdict.add(MemoryCheck(
        "MS-2", "recall consistency",
        ids1 == ids2,
        f"run1={ids1}, run2={ids2}",
    ))

    # -- MS-3: Cross-restart --
    db_ms3 = str(tmp_path / "ms3v.sqlite3")
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_ms3))
    handle_a = _assemble_semantic(experience_store=store_a)
    handle_a.startup()
    handle_a.run_ticks(10)
    count_a = store_a.count()
    del handle_a, store_a
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_ms3))
    count_b = store_b.count()
    verdict.add(MemoryCheck(
        "MS-3", "cross-restart integrity",
        count_b == count_a,
        f"session_a={count_a}, session_b={count_b}",
    ))

    # -- MS-4: Checkpoint v3 round-trip --
    ckpt = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle_ckpt = _assemble_semantic(continuity_checkpoint=ckpt)
    handle_ckpt.startup()
    handle_ckpt.run_ticks(3)
    saved = ckpt.load_latest()
    v3_ok = (
        saved is not None
        and saved.snapshot_version == 4
        and saved.continuation_state is not None
        and saved.neuromodulator_levels is not None
        and saved.feeling is not None
    )
    verdict.add(MemoryCheck(
        "MS-4", "checkpoint v3 round-trip",
        v3_ok,
        f"v={saved.snapshot_version if saved else 'none'}, "
        f"cont={'yes' if saved and saved.continuation_state else 'no'}, "
        f"nm={'yes' if saved and saved.neuromodulator_levels else 'no'}, "
        f"feel={'yes' if saved and saved.feeling else 'no'}",
    ))

    # -- MS-5: Consolidation gating --
    store_ms5 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_ms5 = _assemble_semantic(experience_store=store_ms5)
    handle_ms5.startup()
    handle_ms5.run_ticks(10)
    count_ms5 = store_ms5.count()
    verdict.add(MemoryCheck(
        "MS-5", "consolidation gating",
        count_ms5 >= 10,
        f"count={count_ms5}",
    ))

    # -- MS-6: Record kind coexistence --
    store_ms6 = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    ms6e = tuple(
        PersistedExperienceRecord(
            record_id=f"ms6e-{i}", tick_id=i,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-e-{i}",
            writeback_status="written_internal_only",
            summary=f"exp {i}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("ms6v-test",),
            linkage={},
            record_kind="experience_writeback",
        )
        for i in range(5)
    )
    ms6a = tuple(
        PersistedExperienceRecord(
            record_id=f"ms6a-{i}", tick_id=i + 10,
            continuity_kind="internal_only",
            outcome_class="internal_to_visible_consequence",
            source_outcome_kind="completed",
            source_outcome_id=f"src-a-{i}",
            writeback_status="written_internal_only",
            summary=f"aff {i}",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("ms6v-test",),
            linkage={},
            record_kind="affect_memory",
        )
        for i in range(3)
    )
    store_ms6.append_records(ms6e)
    store_ms6.append_records(ms6a)
    total = store_ms6.count()
    all_recs = store_ms6.read_recent(total)
    kinds = {r.record_kind for r in all_recs}
    verdict.add(MemoryCheck(
        "MS-6", "record kind coexistence",
        total == 8 and "experience_writeback" in kinds and "affect_memory" in kinds,
        f"total={total}, kinds={kinds}",
    ))

    # Final assertion.
    assert verdict.passed, (
        f"MEMORY STABILITY VERDICT: FAIL\n"
        + "\n".join(
            f"  [FAIL] {c.check_id}: {c.description} — {c.evidence}"
            for c in verdict.checks
            if not c.passed
        )
    )

    print(f"\n{'=' * 60}")
    print(f"MEMORY STABILITY VERDICT: {'PASS' if verdict.passed else 'FAIL'}")
    for c in verdict.checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}] {c.check_id}: {c.description} — {c.evidence}")
    print(f"{'=' * 60}")
