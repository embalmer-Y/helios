"""Property-based tests for autobiographical memory compression.

# Feature: helios-architecture-enhancement
# Property 36: Memory Compression Trigger Condition
# Property 37: Compression Reduces Active Store Preserving Archive

**Validates: Requirements 34.1, 34.3**
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import floats, integers, sampled_from


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from memory import AutobiographicalStore, MemoryCompressor


def _create_unique_store_dir(tmp_path):
    store_dir = tmp_path / f"compression_{uuid.uuid4().hex}"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _record(store, timestamp: float, dominant: str, phi: float, narrative: str):
    moment = store.record(
        panksepp={dominant: 0.7},
        valence=0.4 if dominant in {"SEEKING", "CARE", "PLAY"} else -0.4,
        arousal=0.5,
        dominant=dominant,
        phi=phi,
        narrative=narrative,
    )
    moment.timestamp = timestamp
    return moment


class TestProperty36MemoryCompressionTriggerCondition:
    """Property 36: old dense days become compressible."""

    @given(
        n_moments=integers(min_value=101, max_value=150),
        age_days=integers(min_value=8, max_value=60),
        dominant=sampled_from(["SEEKING", "CARE", "PLAY", "FEAR", "PANIC"]),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_find_compressible_days_includes_old_dense_day(self, n_moments: int, age_days: int, dominant: str, tmp_path):
        store_dir = _create_unique_store_dir(tmp_path)
        path = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(path, auto_flush=False)
        compressor = MemoryCompressor(store)

        base = time.time() - age_days * 86400
        for index in range(n_moments):
            _record(store, base + index, dominant, 0.2, f"moment-{index}")

        compressible = compressor.find_compressible_days()
        date_string = store._date_string(base)

        assert (date_string, n_moments) in compressible


class TestProperty37CompressionPreservesArchive:
    """Property 37: compression shrinks the active view but not the raw archive."""

    @given(
        n_moments=integers(min_value=101, max_value=140),
        phi_base=floats(min_value=0.05, max_value=0.8, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=60000)
    def test_execute_compression_reduces_active_store_preserving_archive(self, n_moments: int, phi_base: float, tmp_path):
        store_dir = _create_unique_store_dir(tmp_path)
        path = Path(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(str(path), auto_flush=False)
        compressor = MemoryCompressor(store)

        base = time.time() - 12 * 86400
        dominants = ["FEAR", "CARE", "PLAY"]
        for index in range(n_moments):
            dominant = dominants[index % len(dominants)]
            phi = min(1.0, phi_base + (index / max(n_moments, 1)) * 0.1)
            _record(store, base + index, dominant, phi, f"event-{index}")

        store.flush()
        lines_before = _count_lines(path)
        active_before = len(store.moments)

        stats = compressor.execute_compression()

        assert stats["days_compressed"] == 1
        assert stats["moments_compressed"] == n_moments
        assert stats["summaries_produced"] == 1
        assert len(store.moments) < active_before
        assert len(store.moments) == 1
        assert _count_lines(path) == lines_before
