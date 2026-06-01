"""Tests for active-view autobiographical memory compression."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory import AutobiographicalStore, MemoryCompressor


def _record_moment(store, timestamp: float, dominant: str, phi: float, narrative: str):
    moment = store.record(
        panksepp={dominant: 0.8},
        valence=0.4 if dominant in {"CARE", "PLAY", "SEEKING"} else -0.4,
        arousal=0.5,
        dominant=dominant,
        phi=phi,
        narrative=narrative,
    )
    moment.timestamp = timestamp
    return moment


def _count_lines(path: Path) -> int:
    with open(path, encoding="utf-8") as handle:
        return sum(1 for _ in handle)


class TestMemoryCompression:
    def test_find_compressible_days_requires_old_dense_day(self, tmp_path):
        store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
        compressor = MemoryCompressor(store)
        old_timestamp = time.time() - 8 * 86400

        for index in range(101):
            _record_moment(store, old_timestamp + index, "SEEKING", 0.2, f"old-{index}")

        compressible = compressor.find_compressible_days()

        assert compressible == [(store._date_string(old_timestamp), 101)]

    def test_find_compressible_days_ignores_recent_day(self, tmp_path):
        store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
        compressor = MemoryCompressor(store)
        recent_timestamp = time.time() - 2 * 86400

        for index in range(120):
            _record_moment(store, recent_timestamp + index, "CARE", 0.3, f"recent-{index}")

        assert compressor.find_compressible_days() == []

    def test_execute_compression_reduces_active_store_but_preserves_raw_jsonl(self, tmp_path):
        path = tmp_path / "autobio.jsonl"
        store = AutobiographicalStore(str(path), auto_flush=False)
        compressor = MemoryCompressor(store)
        old_timestamp = time.time() - 9 * 86400

        for index in range(105):
            dominant = "FEAR" if index < 35 else "CARE" if index < 70 else "PLAY"
            _record_moment(store, old_timestamp + index, dominant, 0.2 + index / 1000.0, f"event-{index}")

        store.flush()
        raw_lines_before = _count_lines(path)
        active_count_before = len(store.moments)

        stats = compressor.execute_compression()

        assert stats == {"days_compressed": 1, "moments_compressed": 105, "summaries_produced": 1}
        assert _count_lines(path) == raw_lines_before
        assert len(store.moments) < active_count_before
        assert len(store.moments) == 1
        assert store.moments[0].moment_id.startswith("compressed-")
        assert "Compressed 105 autobiographical moments" in store.moments[0].narrative

    def test_execute_compression_logs_stats(self, tmp_path, caplog):
        path = tmp_path / "autobio.jsonl"
        store = AutobiographicalStore(str(path), auto_flush=False)
        compressor = MemoryCompressor(store)
        old_timestamp = time.time() - 10 * 86400

        for index in range(101):
            _record_moment(store, old_timestamp + index, "PANIC", 0.5, f"panic-{index}")

        with caplog.at_level("INFO"):
            compressor.execute_compression()

        assert any("Memory compression:" in record.message for record in caplog.records)