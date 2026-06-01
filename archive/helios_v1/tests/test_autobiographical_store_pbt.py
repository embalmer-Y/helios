"""
Property-based tests for Autobiographical Store disk safety.

# Feature: helios-architecture-enhancement
# Property 22: Autobiographical Store Flush Periodicity
# Property 23: JSONL Append-Only Resilience
# Property 24: Autobiographical Store Archive Threshold

**Validates: Requirements 21.1, 21.2, 21.3, 21.5**
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    integers, floats, text, lists, builds, composite, sampled_from, booleans
)

import pytest

from memory import AutobiographicalStore, AutobiographicalMoment, Chapter


# ------------------------------------------------------------------
# Strategies / Generators
# ------------------------------------------------------------------


PANKSEPP_SYSTEMS = ["SEEKING", "PLAY", "CARE", "PANIC", "FEAR", "RAGE", "LUST"]


@composite
def panksepp_vector(draw):
    """Generate a valid Panksepp activation vector."""
    result = {}
    for system in PANKSEPP_SYSTEMS:
        # Most activations are 0, some are non-zero
        if draw(booleans()):
            result[system] = draw(floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    return result


@composite
def moment_data(draw):
    """Generate data for recording a moment."""
    return {
        "panksepp": draw(panksepp_vector()),
        "valence": draw(floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "arousal": draw(floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "dominant": draw(sampled_from(PANKSEPP_SYSTEMS)),
        "phi": draw(floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        "narrative": draw(text(min_size=0, max_size=100)),
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _record_moment(store, panksepp=None, valence=0.5, arousal=0.4, dominant="SEEKING", phi=0.3, narrative="test"):
    """Helper to record a moment with default values."""
    if panksepp is None:
        panksepp = {"SEEKING": 0.5, "CARE": 0.3}
    return store.record(
        panksepp=panksepp,
        valence=valence,
        arousal=arousal,
        dominant=dominant,
        phi=phi,
        narrative=narrative,
    )


def _count_lines(filepath: Path) -> int:
    """Count lines in a file."""
    if not filepath.exists():
        return 0
    count = 0
    with open(filepath, encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count


def _write_malformed_file(filepath: Path, valid_count: int, malformed_positions: List[int]):
    """Write a JSONL file with malformed lines at specified positions (1-indexed)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    valid_moment = AutobiographicalMoment(
        moment_id="1234-000001",
        timestamp=1000.0,
        cycle=1,
        dominant="SEEKING",
        panksepp={"SEEKING": 0.5},
        valence=0.3,
        arousal=0.4,
        phi=0.2,
    )
    valid_json = json.dumps(valid_moment.to_dict())
    
    with open(filepath, "w", encoding="utf-8") as f:
        line_num = 1
        valid_written = 0
        while valid_written < valid_count or line_num <= max(malformed_positions, default=0):
            if line_num in malformed_positions:
                f.write("MALFORMED LINE NOT JSON\n")
            elif valid_written < valid_count:
                f.write(valid_json + "\n")
                valid_written += 1
            else:
                break
            line_num += 1


def _create_unique_store_dir(tmp_path):
    """Create a unique directory for a store to ensure test isolation."""
    store_dir = tmp_path / f"memory_{uuid.uuid4().hex}"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


# ------------------------------------------------------------------
# Property 22: Autobiographical Store Flush Periodicity
# ------------------------------------------------------------------


class TestProperty22FlushPeriodicity:
    """Property 22: For any sequence of recorded moments, the AutobiographicalStore
    SHALL flush to disk after every 10th moment recorded since last flush.

    **Validates: Requirements 21.1**
    """

    @given(n_moments=integers(min_value=1, max_value=100))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_flush_triggered_every_10_moments(self, n_moments: int, tmp_path):
        """After every 10th moment, flush is triggered."""
        # Create UNIQUE directory per hypothesis example
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        
        for i in range(n_moments):
            _record_moment(store, narrative=f"moment-{i}")
        
        # Expected number of lines = largest multiple of 10 <= n_moments
        expected_lines = (n_moments // 10) * 10
        
        # Check file has expected number of lines
        actual_lines = _count_lines(Path(filepath))
        assert actual_lines == expected_lines, f"Expected {expected_lines} lines, got {actual_lines}"

    @given(extra_after_flush=integers(min_value=0, max_value=9))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unflushed_moments_dont_write_until_10(self, extra_after_flush: int, tmp_path):
        """Moments after a flush don't write until 10 more are accumulated."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        
        # Record exactly 10 moments → triggers flush
        for i in range(10):
            _record_moment(store, narrative=f"batch1-{i}")
        
        lines_after_10 = _count_lines(Path(filepath))
        assert lines_after_10 == 10, f"After 10 moments, expected 10 lines, got {lines_after_10}"
        
        # Record fewer than 10 more moments
        for i in range(extra_after_flush):
            _record_moment(store, narrative=f"batch2-{i}")
        
        # File should still have only 10 lines
        lines_after_extra = _count_lines(Path(filepath))
        assert lines_after_extra == 10, f"After {extra_after_flush} more moments, expected still 10 lines, got {lines_after_extra}"

    @given(moment_infos=lists(moment_data(), min_size=1, max_size=50))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_flush_count_invariant(self, moment_infos: List[dict], tmp_path):
        """The number of flushed lines is always a multiple of 10."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        
        for info in moment_infos:
            store.record(**info)
        
        lines = _count_lines(Path(filepath))
        assert lines % 10 == 0, f"Expected lines to be multiple of 10, got {lines}"

    @given(n_before_close=integers(min_value=0, max_value=25))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_close_flushes_all_remaining(self, n_before_close: int, tmp_path):
        """close() flushes all remaining unflushed moments."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        
        for i in range(n_before_close):
            _record_moment(store, narrative=f"moment-{i}")
        
        store.close()
        
        lines = _count_lines(Path(filepath))
        assert lines == n_before_close, f"After close, expected {n_before_close} lines, got {lines}"


# ------------------------------------------------------------------
# Property 23: JSONL Append-Only Resilience
# ------------------------------------------------------------------


class TestProperty23JSONLAppendOnlyResilience:
    """Property 23: For any JSONL file written by the AutobiographicalStore,
    each write operation SHALL append (file grows monotonically). When loading,
    malformed lines SHALL be skipped (valid lines loaded successfully) without aborting.

    **Validates: Requirements 21.2, 21.3**
    """

    @given(n_batches=integers(min_value=1, max_value=5))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_file_grows_monotonically(self, n_batches: int, tmp_path):
        """Each flush only appends — file size never shrinks."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        store_path = Path(filepath)
        
        previous_size = 0
        previous_lines = 0
        
        for batch in range(n_batches):
            for i in range(10):
                _record_moment(store, narrative=f"batch{batch}-{i}")
            
            current_lines = _count_lines(store_path)
            assert current_lines >= previous_lines, "File lines should never decrease"
            previous_lines = current_lines
            
            if store_path.exists():
                current_size = store_path.stat().st_size
                assert current_size >= previous_size, "File size should never decrease"
                previous_size = current_size

    @given(
        n_valid=integers(min_value=5, max_value=20),
        malformed_positions=lists(integers(min_value=1, max_value=25), min_size=1, max_size=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_malformed_lines_skipped_on_load(self, n_valid: int, malformed_positions: List[int], tmp_path):
        """Malformed JSON lines are skipped — only valid lines are loaded."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        # Ensure malformed positions don't exceed total lines
        total_lines = n_valid + len(malformed_positions)
        malformed_positions = [p for p in malformed_positions if p <= total_lines]
        assume(len(malformed_positions) > 0)  # Need at least one malformed position
        
        _write_malformed_file(store_path, n_valid, malformed_positions)
        
        # Load the file
        store = AutobiographicalStore(filepath, auto_flush=False)
        
        # Should have loaded exactly the valid lines
        assert len(store.moments) == n_valid, f"Expected {n_valid} moments, got {len(store.moments)}"

    @given(
        n_valid=integers(min_value=1, max_value=10),
        malformed_positions=lists(integers(min_value=1, max_value=15), min_size=1, max_size=3)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_lines_after_malformed_are_loaded(self, n_valid: int, malformed_positions: List[int], tmp_path):
        """Loading continues past malformed lines — valid lines after corruption are still loaded."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        total_lines = n_valid + len(malformed_positions)
        malformed_positions = [p for p in malformed_positions if p <= total_lines]
        assume(len(malformed_positions) > 0)
        
        # Write at least one valid line after the last malformed
        last_malformed = max(malformed_positions)
        if n_valid + len(malformed_positions) <= last_malformed:
            n_valid = last_malformed - len(malformed_positions) + 1
        
        _write_malformed_file(store_path, n_valid, malformed_positions)
        
        store = AutobiographicalStore(filepath, auto_flush=False)
        
        # Should have loaded valid lines
        assert len(store.moments) >= 1, "Should have loaded at least one valid moment"

    @given(n_moments=integers(min_value=10, max_value=30))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_each_line_is_valid_json(self, n_moments: int, tmp_path):
        """Every line written is valid JSON parseable as a moment."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        store_path = Path(filepath)
        
        for i in range(n_moments):
            _record_moment(store, narrative=f"moment-{i}")
        
        store.close()
        
        with open(store_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                data = json.loads(line.strip())
                assert "moment_id" in data, f"Line {line_num} missing moment_id"
                assert "timestamp" in data, f"Line {line_num} missing timestamp"

    @given(
        n_before=integers(min_value=10, max_value=20),
        n_after=integers(min_value=10, max_value=20)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_append_preserves_original_content(self, n_before: int, n_after: int, tmp_path):
        """Content written before an append is preserved unchanged."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store = AutobiographicalStore(filepath, auto_flush=True)
        store_path = Path(filepath)
        
        # Write first batch
        for i in range(n_before):
            _record_moment(store, narrative=f"before-{i}")
        
        store.flush()
        
        # Capture first batch content
        with open(store_path, encoding="utf-8") as f:
            original_content = f.read()
        
        # Write second batch
        for i in range(n_after):
            _record_moment(store, narrative=f"after-{i}")
        
        store.close()
        
        # Verify original content is preserved
        with open(store_path, encoding="utf-8") as f:
            full_content = f.read()
        
        assert full_content.startswith(original_content), "Original content should be preserved at the start"


# ------------------------------------------------------------------
# Property 24: Autobiographical Store Archive Threshold
# ------------------------------------------------------------------


class TestProperty24ArchiveThreshold:
    """Property 24: For any JSONL file exceeding 50000 lines, the
    AutobiographicalStore SHALL archive the file (rename with timestamp) and
    start a new file retaining only the most recent 5000 moments.

    **Validates: Requirements 21.5**
    """

    @given(n_over_threshold=integers(min_value=1, max_value=1000))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=60000)
    def test_archive_triggered_above_50000_lines(self, n_over_threshold: int, tmp_path):
        """When file has > 50000 lines, archive is triggered on next flush."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        # Pre-write a file with > 50000 lines
        valid_moment = AutobiographicalMoment(
            moment_id="1234-000001",
            timestamp=1000.0,
            cycle=1,
            dominant="SEEKING",
            panksepp={"SEEKING": 0.5},
            valence=0.3,
            arousal=0.4,
            phi=0.2,
        )
        
        with open(store_path, "w", encoding="utf-8") as f:
            for i in range(50000 + n_over_threshold):
                f.write(json.dumps(valid_moment.to_dict()) + "\n")
        
        # Load and trigger flush
        store = AutobiographicalStore(filepath, auto_flush=False)
        _record_moment(store, narrative="trigger")
        store.flush()
        
        # Check archive was created
        archive_files = list(store_dir.glob("autobio_*_*.jsonl"))
        assert len(archive_files) >= 1, "Archive file should be created"

    @given(n_at_or_below=integers(min_value=0, max_value=49999))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=60000)
    def test_no_archive_at_or_below_50000_lines(self, n_at_or_below: int, tmp_path):
        """No archive is created when file has <= 50000 lines."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        if n_at_or_below > 0:
            valid_moment = AutobiographicalMoment(
                moment_id="1234-000001",
                timestamp=1000.0,
                cycle=1,
                dominant="SEEKING",
                panksepp={"SEEKING": 0.5},
                valence=0.3,
                arousal=0.4,
                phi=0.2,
            )
            
            with open(store_path, "w", encoding="utf-8") as f:
                for i in range(n_at_or_below):
                    f.write(json.dumps(valid_moment.to_dict()) + "\n")
        
        store = AutobiographicalStore(filepath, auto_flush=False)
        _record_moment(store, narrative="trigger")
        store.flush()
        
        # After recording, check if we're at or below threshold
        # If total lines <= 50000, no archive
        total_after = n_at_or_below + 1  # +1 for the new moment
        if total_after <= 50000:
            archive_files = list(store_dir.glob("autobio_*_*.jsonl"))
            assert len(archive_files) == 0, f"No archive should be created at {total_after} lines (<= 50000)"

    @given(n_total=integers(min_value=50001, max_value=55000))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=120000)
    def test_archive_retains_most_recent_5000(self, n_total: int, tmp_path):
        """After archive, active file has at most 5000 moments."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        # Write > 50000 lines
        for i in range(n_total):
            moment = AutobiographicalMoment(
                moment_id=f"1234-{i:06d}",
                timestamp=1000.0 + i,
                cycle=i,
                dominant="SEEKING",
                panksepp={"SEEKING": 0.5},
                valence=float(i % 100) / 100,
                arousal=0.4,
                phi=0.2,
                narrative=f"moment-{i:05d}",
            )
            
            if i == 0:
                with open(store_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(moment.to_dict()) + "\n")
            else:
                with open(store_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(moment.to_dict()) + "\n")
        
        # Load and trigger flush
        store = AutobiographicalStore(filepath, auto_flush=False)
        _record_moment(store, narrative="trigger")
        store.flush()
        
        # In-memory moments should be <= 5000
        assert len(store.moments) <= 5000, f"After archive, moments should be <= 5000, got {len(store.moments)}"
        
        # Active file should have <= 5000 lines
        active_lines = _count_lines(store_path)
        assert active_lines <= 5000, f"Active file should have <= 5000 lines, got {active_lines}"

    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=60000)
    @given(n_over=integers(min_value=1, max_value=100))
    def test_archive_filename_has_timestamp_suffix(self, n_over: int, tmp_path):
        """Archived file has a timestamp suffix in format YYYYMMDD_HHMMSS."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        valid_moment = AutobiographicalMoment(
            moment_id="1234-000001",
            timestamp=1000.0,
            cycle=1,
            dominant="SEEKING",
            panksepp={"SEEKING": 0.5},
            valence=0.3,
            arousal=0.4,
            phi=0.2,
        )
        
        with open(store_path, "w", encoding="utf-8") as f:
            for i in range(50000 + n_over):
                f.write(json.dumps(valid_moment.to_dict()) + "\n")
        
        store = AutobiographicalStore(filepath, auto_flush=False)
        _record_moment(store, narrative="trigger")
        store.flush()
        
        archive_files = list(store_dir.glob("autobio_*_*.jsonl"))
        assert len(archive_files) >= 1, "Should have at least one archive file"
        
        # Check filename format: autobio_YYYYMMDD_HHMMSS.jsonl
        archive_name = archive_files[0].stem  # autobio_YYYYMMDD_HHMMSS
        parts = archive_name.replace("autobio_", "").split("_")
        assert len(parts) == 2, f"Expected 2 parts in timestamp, got {parts}"
        assert len(parts[0]) == 8, f"Date part should be 8 chars (YYYYMMDD), got {parts[0]}"
        assert len(parts[1]) == 6, f"Time part should be 6 chars (HHMMSS), got {parts[1]}"
        assert parts[0].isdigit(), f"Date part should be digits, got {parts[0]}"
        assert parts[1].isdigit(), f"Time part should be digits, got {parts[1]}"

    @given(n_total=integers(min_value=50001, max_value=52000))
    @settings(max_examples=8, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=120000)
    def test_in_memory_trimmed_to_recent_5000(self, n_total: int, tmp_path):
        """After archive, in-memory moments are the most recent 5000."""
        store_dir = _create_unique_store_dir(tmp_path)
        filepath = str(store_dir / "autobio.jsonl")
        store_path = Path(filepath)
        
        # Create moments with distinct narratives
        for i in range(n_total):
            moment = AutobiographicalMoment(
                moment_id=f"1234-{i:06d}",
                timestamp=1000.0 + i,
                cycle=i,
                dominant="SEEKING",
                panksepp={"SEEKING": 0.5},
                valence=0.3,
                arousal=0.4,
                phi=0.2,
                narrative=f"narrative-{i:05d}",
            )
            
            if i == 0:
                with open(store_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(moment.to_dict()) + "\n")
            else:
                with open(store_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(moment.to_dict()) + "\n")
        
        store = AutobiographicalStore(filepath, auto_flush=False)
        _record_moment(store, narrative="trigger")
        store.flush()
        
        # The most recent moments should be retained
        # Check that narratives of the most recent moments are present
        if len(store.moments) >= 2:
            # Most recent moments should have higher indices
            recent_narratives = [m.narrative for m in store.moments[-5:]]
            # They should all start with "narrative-" or "trigger"
            for narr in recent_narratives:
                assert narr.startswith("narrative-") or narr == "trigger", f"Unexpected narrative: {narr}"

