"""R77 — Long-term stability prerequisites: operational readiness assessment.

Evaluates six long-term stability properties:

- **LT-1**: Resource boundedness — 20 ticks, memory + store growth controlled.
- **LT-2**: State isolation — independent handles share no mutable state.
- **LT-3**: Checkpoint corruption recovery — corrupted file → fail-fast.
- **LT-4**: Embedding failure isolation — raising provider → hard stop.
- **LT-5**: Zero-percept and high-load closure — R65/R54 paths complete.
- **LT-6**: Owner boundary non-regression — composition guard patterns hold.

This module is **read-only**: it exercises the runtime but never modifies owner code.
"""

from __future__ import annotations

import os
import re
import tracemalloc
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
    thought_text: str = "deterministic thought for stability prerequisites"
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


class _RaisingEmbeddingProvider:
    """Embedding provider that always raises — for LT-4 isolation test."""
    dimensions: int = 16

    def embed(self, profile, request, api_key):
        raise RuntimeError("embedding provider failure (LT-4 test)")


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
class StabilityCheck:
    check_id: str
    description: str
    passed: bool
    evidence: str


@dataclass
class StabilityVerdict:
    checks: list[StabilityCheck] = field(default_factory=list)

    def add(self, check: StabilityCheck) -> None:
        self.checks.append(check)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


# ===========================================================================
# LT-1: Resource boundedness (20 ticks)
# ===========================================================================


def test_lt1_resource_boundedness() -> None:
    """20 ticks must not consume excessive memory; store growth must be bounded."""
    handle = _assemble_semantic()
    handle.startup()

    tracemalloc.start()
    handle.run_ticks(20)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    store_count = handle.experience_store.count()

    assert peak_mb < 500, f"Peak memory {peak_mb:.1f} MB exceeds 500 MB threshold"
    # Store writes ~2 records per tick (writeback + affect); allow up to 50.
    assert store_count <= 50, f"Store has {store_count} records after 20 ticks (expected ≤ 50)"
    assert store_count >= 1, f"Store has 0 records after 20 ticks"


# ===========================================================================
# LT-2: State isolation (2 independent handles)
# ===========================================================================


def test_lt2_state_isolation() -> None:
    """Two independent handles must not share mutable state."""
    store_a = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store_b = ExperienceStore(backend=InMemoryExperienceStoreBackend())

    handle_a = _assemble_semantic(experience_store=store_a)
    handle_b = _assemble_semantic(experience_store=store_b)
    handle_a.startup()
    handle_b.startup()

    handle_a.run_ticks(5)
    count_a = store_a.count()

    handle_b.run_ticks(3)
    count_b = store_b.count()

    # Each store should only contain its own handle's records.
    assert count_a >= 1, "Handle A's store is empty after 5 ticks"
    assert count_b >= 1, "Handle B's store is empty after 3 ticks"

    # Store A should not have grown when handle B ran.
    count_a_after_b = store_a.count()
    assert count_a_after_b == count_a, (
        f"Store A grew from {count_a} to {count_a_after_b} when handle B ran — state leakage"
    )


# ===========================================================================
# LT-3: Checkpoint corruption recovery
# ===========================================================================


def test_lt3_checkpoint_corruption(tmp_path) -> None:
    """Corrupted checkpoint file must raise, not silently degrade."""
    db_path = str(tmp_path / "corrupt_ckpt.sqlite3")

    # Write corrupted data to the checkpoint database file.
    Path(db_path).write_bytes(b"\x00\x01\x02CORRUPTED_CHECKPOINT_DATA\xff\xfe")

    backend = SqliteCheckpointBackend(db_path=db_path)
    store = ContinuityCheckpointStore(backend=backend)

    # Loading a corrupted checkpoint must raise, not return None silently.
    with pytest.raises(Exception):
        store.load_latest()


# ===========================================================================
# LT-4: Embedding failure isolation
# ===========================================================================


def test_lt4_embedding_failure_isolation() -> None:
    """Raising embedding provider must cause hard-stop, no silent fallback."""
    raising_gw = _embedding_gateway(provider=_RaisingEmbeddingProvider())
    handle = _assemble_semantic(embedding_gateway=raising_gw)
    handle.startup()

    # Running a tick should raise when the embedding provider fails.
    with pytest.raises(Exception):
        handle.run_ticks(1)


# ===========================================================================
# LT-5: Zero-percept and high-load closure
# ===========================================================================


def test_lt5_zero_percept_and_high_load_closure() -> None:
    """Zero-percept and high-load ticks must complete without error."""
    # Zero-percept: no external stimulus source registered.
    config = default_composition_config()
    handle_zero = _assemble_semantic()
    handle_zero.startup()
    # A tick with no external signal source should complete via R65 path.
    results_zero = handle_zero.run_ticks(1)
    assert len(results_zero) == 1, "Zero-percept tick did not complete"

    # High-load: assemble with a pressure sampler that produces high pressure.
    from helios_v2.interoception import RuntimePressureSample

    high_sample = RuntimePressureSample(
        cpu_pressure=0.95,
        memory_pressure=0.95,
        latency_pressure=0.90,
        error_pressure=0.50,
    )

    class _HighPressureSampler:
        def sample(self):
            return high_sample

    handle_load = _assemble_semantic(interoceptive_sampler=_HighPressureSampler())
    handle_load.startup()
    results_load = handle_load.run_ticks(1)
    assert len(results_load) == 1, "High-load tick did not complete"

    # Verify 18 and 17 still ran under high load.
    result = results_load[0]
    stage_keys = set(result.stage_results.keys())
    assert "subjective_autonomy_and_proactive_evolution" in stage_keys, (
        "18 autonomy did not run under high load"
    )
    assert "evaluation_fidelity_and_diagnostic_provenance" in stage_keys, (
        "17 evaluation did not run under high load"
    )


# ===========================================================================
# LT-6: Owner boundary non-regression
# ===========================================================================


def test_lt6_owner_boundary_non_regression() -> None:
    """Composition must not import cognitive policy from owner engines."""
    from helios_v2.composition import bridges as bridges_module
    import inspect

    source = inspect.getsource(bridges_module)

    # Guard 1: No neuromodulator sensitivity policy in composition.
    assert not re.search(
        r"neuromodulator_sensitivity_policy|NeuromodulatorSensitivityPolicy",
        source,
    ), "composition/bridges.py imports neuromodulator sensitivity policy"

    # Guard 2: No autonomy drive pressure computation in composition.
    assert not re.search(
        r"autonomy_drive_pressure|drive_pressure_score",
        source,
    ), "composition/bridges.py computes autonomy drive pressure"

    # Guard 3: No feeling coupling coefficients in composition.
    assert not re.search(
        r"feeling_coupling_coefficient|coupling_weight",
        source,
    ), "composition/bridges.py contains feeling coupling coefficients"


# ===========================================================================
# Composite verdict
# ===========================================================================


def test_stability_composite_verdict(tmp_path) -> None:
    """Composite verdict for long-term stability prerequisites."""
    verdict = StabilityVerdict()

    # LT-1: Resource boundedness
    handle = _assemble_semantic()
    handle.startup()
    tracemalloc.start()
    handle.run_ticks(20)
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak / (1024 * 1024)
    verdict.add(StabilityCheck(
        "LT-1", "resource boundedness (20 ticks)",
        peak_mb < 500,
        f"peak={peak_mb:.1f}MB",
    ))

    # LT-2: State isolation
    sa = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    sb = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    ha = _assemble_semantic(experience_store=sa)
    hb = _assemble_semantic(experience_store=sb)
    ha.startup(); hb.startup()
    ha.run_ticks(5); ca = sa.count()
    hb.run_ticks(3); ca2 = sa.count()
    verdict.add(StabilityCheck(
        "LT-2", "state isolation",
        ca2 == ca,
        f"a_before={ca}, a_after_b={ca2}",
    ))

    # LT-3: Checkpoint corruption
    db = str(tmp_path / "ckpt_corrupt.sqlite3")
    Path(db).write_bytes(b"\x00CORRUPT\xff")
    try:
        ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=db)).load_latest()
        verdict.add(StabilityCheck("LT-3", "checkpoint corruption", False, "no exception raised"))
    except Exception as exc:
        verdict.add(StabilityCheck("LT-3", "checkpoint corruption", True, f"raised {type(exc).__name__}"))

    # LT-4: Embedding failure
    rhandle = _assemble_semantic(embedding_gateway=_embedding_gateway(_RaisingEmbeddingProvider()))
    rhandle.startup()
    try:
        rhandle.run_ticks(1)
        verdict.add(StabilityCheck("LT-4", "embedding failure isolation", False, "no exception"))
    except Exception as exc:
        verdict.add(StabilityCheck("LT-4", "embedding failure isolation", True, f"raised {type(exc).__name__}"))

    # LT-5: Zero-percept closure
    hz = _assemble_semantic()
    hz.startup()
    try:
        rz = hz.run_ticks(1)
        verdict.add(StabilityCheck("LT-5", "zero-percept closure", len(rz) == 1, f"results={len(rz)}"))
    except Exception as exc:
        verdict.add(StabilityCheck("LT-5", "zero-percept closure", False, f"raised {type(exc).__name__}"))

    # LT-6: Owner boundary
    from helios_v2.composition import bridges as bm
    import inspect
    src = inspect.getsource(bm)
    violations = []
    if re.search(r"neuromodulator_sensitivity_policy", src):
        violations.append("neuromodulator_sensitivity_policy")
    if re.search(r"autonomy_drive_pressure", src):
        violations.append("autonomy_drive_pressure")
    if re.search(r"feeling_coupling_coefficient", src):
        violations.append("feeling_coupling_coefficient")
    verdict.add(StabilityCheck(
        "LT-6", "owner boundary non-regression",
        len(violations) == 0,
        f"violations={violations}" if violations else "clean",
    ))

    # Print verdict
    print("\n=== R77 Long-Term Stability Prerequisites ===")
    for c in verdict.checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}] {c.check_id}: {c.description} ({c.evidence})")
    print(f"  Overall: {'PASS' if verdict.passed else 'FAIL'}\n")

    assert verdict.passed, (
        f"Stability verdict failed: {[c.check_id for c in verdict.checks if not c.passed]}"
    )
