"""Unit tests for StatePersistence utility."""

import json
import logging
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from utils.persistence import StatePersistence
from personality import PersonalityProfile
from allostasis import AllostaticRegulator


@pytest.fixture
def tmp_data_dir():
    """Create a temporary data directory for each test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def persistence(tmp_data_dir):
    """Create a StatePersistence instance with a temp directory."""
    return StatePersistence(tmp_data_dir)


# ------------------------------------------------------------------
# Personality tests
# ------------------------------------------------------------------


class TestPersonalitySaveLoad:
    def test_round_trip_preserves_traits(self, persistence):
        pp = PersonalityProfile(openness=1.3, neuroticism=0.8, extraversion=1.1)
        persistence.save_personality(pp)
        loaded = persistence.load_personality()

        assert loaded is not None
        assert abs(loaded["traits"]["openness"] - 1.3) < 0.001
        assert abs(loaded["traits"]["neuroticism"] - 0.8) < 0.001
        assert abs(loaded["traits"]["extraversion"] - 1.1) < 0.001

    def test_round_trip_preserves_neuro_gains(self, persistence):
        pp = PersonalityProfile(openness=1.5)
        persistence.save_personality(pp)
        loaded = persistence.load_personality()

        assert loaded is not None
        assert "neuro_gains" in loaded
        assert "SEEKING" in loaded["neuro_gains"]

    def test_round_trip_preserves_emotion_cycles(self, persistence):
        pp = PersonalityProfile()
        pp.total_emotion_cycles = 42
        persistence.save_personality(pp)
        loaded = persistence.load_personality()

        assert loaded is not None
        assert loaded["total_emotion_cycles"] == 42

    def test_missing_file_returns_none(self, persistence):
        result = persistence.load_personality()
        assert result is None

    def test_corrupted_json_returns_none(self, persistence, tmp_data_dir, caplog):
        filepath = os.path.join(tmp_data_dir, "personality.json")
        with open(filepath, "w") as f:
            f.write("not valid json {{{")

        with caplog.at_level(logging.WARNING):
            result = persistence.load_personality()
        assert result is None
        assert any("corrupted" in r.message.lower() or "jsondecodeerror" in r.message.lower()
                   for r in caplog.records)

    def test_invalid_structure_returns_none(self, persistence, tmp_data_dir, caplog):
        filepath = os.path.join(tmp_data_dir, "personality.json")
        with open(filepath, "w") as f:
            json.dump({"version": 1, "timestamp": 0.0}, f)

        with caplog.at_level(logging.WARNING):
            result = persistence.load_personality()
        assert result is None

    def test_missing_trait_key_returns_none(self, persistence, tmp_data_dir, caplog):
        filepath = os.path.join(tmp_data_dir, "personality.json")
        with open(filepath, "w") as f:
            json.dump({
                "version": 1,
                "traits": {"openness": 1.0}  # Missing other traits
            }, f)

        with caplog.at_level(logging.WARNING):
            result = persistence.load_personality()
        assert result is None

    def test_version_field_present(self, persistence):
        pp = PersonalityProfile()
        persistence.save_personality(pp)
        loaded = persistence.load_personality()

        assert loaded is not None
        assert loaded["version"] == 1

    def test_timestamp_field_present(self, persistence):
        pp = PersonalityProfile()
        persistence.save_personality(pp)
        loaded = persistence.load_personality()

        assert loaded is not None
        assert "timestamp" in loaded
        assert loaded["timestamp"] > 0


# ------------------------------------------------------------------
# Allostasis tests
# ------------------------------------------------------------------


class TestAllostasisSaveLoad:
    def test_round_trip_preserves_setpoints(self, persistence):
        ar = AllostaticRegulator()
        # Run a few updates to get non-default setpoints
        ar.update({"SEEKING": 0.5, "FEAR": 0.3, "PLAY": 0.2,
                   "CARE": 0.1, "PANIC": 0.1, "RAGE": 0.1, "LUST": 0.1})
        persistence.save_allostasis(ar)
        loaded = persistence.load_allostasis()

        assert loaded is not None
        assert "setpoints" in loaded
        assert "SEEKING" in loaded["setpoints"]
        assert isinstance(loaded["setpoints"]["SEEKING"], float)

    def test_round_trip_preserves_load_level(self, persistence):
        ar = AllostaticRegulator()
        persistence.save_allostasis(ar)
        loaded = persistence.load_allostasis()

        assert loaded is not None
        assert "allostatic_load" in loaded
        assert isinstance(loaded["allostatic_load"], float)

    def test_round_trip_preserves_fatigue_status(self, persistence):
        ar = AllostaticRegulator()
        persistence.save_allostasis(ar)
        loaded = persistence.load_allostasis()

        assert loaded is not None
        assert "is_fatigued" in loaded
        assert isinstance(loaded["is_fatigued"], bool)

    def test_missing_file_returns_none(self, persistence):
        result = persistence.load_allostasis()
        assert result is None

    def test_corrupted_json_returns_none(self, persistence, tmp_data_dir, caplog):
        filepath = os.path.join(tmp_data_dir, "allostasis.json")
        with open(filepath, "w") as f:
            f.write("{invalid json content")

        with caplog.at_level(logging.WARNING):
            result = persistence.load_allostasis()
        assert result is None

    def test_invalid_structure_returns_none(self, persistence, tmp_data_dir, caplog):
        filepath = os.path.join(tmp_data_dir, "allostasis.json")
        with open(filepath, "w") as f:
            json.dump({"version": 1}, f)  # Missing allostatic_load and setpoints

        with caplog.at_level(logging.WARNING):
            result = persistence.load_allostasis()
        assert result is None

    def test_setpoints_not_dict_returns_none(self, persistence, tmp_data_dir, caplog):
        filepath = os.path.join(tmp_data_dir, "allostasis.json")
        with open(filepath, "w") as f:
            json.dump({
                "version": 1,
                "allostatic_load": 0.1,
                "setpoints": "not a dict"
            }, f)

        with caplog.at_level(logging.WARNING):
            result = persistence.load_allostasis()
        assert result is None

    def test_version_field_present(self, persistence):
        ar = AllostaticRegulator()
        persistence.save_allostasis(ar)
        loaded = persistence.load_allostasis()

        assert loaded is not None
        assert loaded["version"] == 1


# ------------------------------------------------------------------
# Atomic write tests
# ------------------------------------------------------------------


class TestAtomicWrite:
    def test_file_is_complete_after_save(self, persistence, tmp_data_dir):
        """Verify the written file is valid JSON (not partial)."""
        pp = PersonalityProfile()
        persistence.save_personality(pp)

        filepath = os.path.join(tmp_data_dir, "personality.json")
        with open(filepath, "r") as f:
            data = json.load(f)
        assert data["version"] == 1

    def test_no_temp_files_left_after_save(self, persistence, tmp_data_dir):
        """Verify no .tmp files remain after successful save."""
        pp = PersonalityProfile()
        persistence.save_personality(pp)

        files = os.listdir(tmp_data_dir)
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    def test_overwrite_preserves_atomicity(self, persistence, tmp_data_dir):
        """Verify that overwriting an existing file produces valid JSON."""
        pp1 = PersonalityProfile(openness=1.0)
        persistence.save_personality(pp1)

        pp2 = PersonalityProfile(openness=1.5)
        persistence.save_personality(pp2)

        loaded = persistence.load_personality()
        assert loaded is not None
        assert abs(loaded["traits"]["openness"] - 1.5) < 0.001


# ------------------------------------------------------------------
# Round-trip identity tests (Task 1.5: save then load returns identical data)
# ------------------------------------------------------------------


class TestRoundTripIdentity:
    """Validates: Requirements 2.3, 3.3 — save/load round-trips preserve all data."""

    def test_personality_round_trip_all_fields_identical(self, persistence):
        """Save then load returns data identical to what was saved."""
        pp = PersonalityProfile(
            openness=1.3, neuroticism=0.8, extraversion=1.1,
            agreeableness=0.9, conscientiousness=1.2
        )
        pp.total_emotion_cycles = 100

        persistence.save_personality(pp)
        loaded = persistence.load_personality()

        assert loaded is not None
        # All Big Five traits must match exactly
        assert abs(loaded["traits"]["openness"] - 1.3) < 1e-9
        assert abs(loaded["traits"]["neuroticism"] - 0.8) < 1e-9
        assert abs(loaded["traits"]["extraversion"] - 1.1) < 1e-9
        assert abs(loaded["traits"]["agreeableness"] - 0.9) < 1e-9
        assert abs(loaded["traits"]["conscientiousness"] - 1.2) < 1e-9
        # Neuro gains preserved
        assert loaded["neuro_gains"] == pp.neuro_gains
        # Evolution metadata preserved
        assert loaded["total_emotion_cycles"] == 100
        assert loaded["version"] == 1

    def test_allostasis_round_trip_all_fields_identical(self, persistence):
        """Save then load returns data identical to what was saved."""
        ar = AllostaticRegulator()
        # Drive some state changes
        for _ in range(5):
            ar.update({"SEEKING": 0.6, "FEAR": 0.4, "PLAY": 0.3,
                       "CARE": 0.2, "PANIC": 0.15, "RAGE": 0.1, "LUST": 0.05})

        persistence.save_allostasis(ar)
        loaded = persistence.load_allostasis()

        assert loaded is not None
        # Load level must match
        assert abs(loaded["allostatic_load"] - round(ar.get_load_level(), 6)) < 1e-9
        # Setpoints must match for all systems
        for sys_name, state in ar.states.items():
            assert sys_name in loaded["setpoints"]
            assert abs(loaded["setpoints"][sys_name] - round(state.setpoint, 6)) < 1e-9
        # Fatigue status preserved
        assert loaded["is_fatigued"] == ar.is_fatigued()
        assert loaded["version"] == 1

    def test_personality_save_load_save_load_stable(self, persistence):
        """Double round-trip: save→load→save→load produces same result."""
        pp = PersonalityProfile(openness=1.4, neuroticism=0.7)
        pp.total_emotion_cycles = 55

        persistence.save_personality(pp)
        loaded1 = persistence.load_personality()

        # Create a second profile with same values and save again
        pp2 = PersonalityProfile(openness=1.4, neuroticism=0.7)
        pp2.total_emotion_cycles = 55
        persistence.save_personality(pp2)
        loaded2 = persistence.load_personality()

        # Both loads should produce equivalent data
        assert loaded1["traits"] == loaded2["traits"]
        assert loaded1["neuro_gains"] == loaded2["neuro_gains"]
        assert loaded1["total_emotion_cycles"] == loaded2["total_emotion_cycles"]


# ------------------------------------------------------------------
# Corrupted file warning tests (Task 1.5: corrupted file returns None with warning)
# ------------------------------------------------------------------


class TestCorruptedFileWarning:
    """Validates: Requirements 2.3, 3.3 — corrupted files log WARNING and return None."""

    def test_personality_corrupted_logs_warning_level(self, persistence, tmp_data_dir, caplog):
        """Corrupted personality file logs at WARNING level (Req 2.3)."""
        filepath = os.path.join(tmp_data_dir, "personality.json")
        with open(filepath, "w") as f:
            f.write("<<<corrupted binary garbage>>>")

        with caplog.at_level(logging.DEBUG):
            result = persistence.load_personality()

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0, "Expected a WARNING log for corrupted file"

    def test_allostasis_corrupted_logs_warning_level(self, persistence, tmp_data_dir, caplog):
        """Corrupted allostasis file logs at WARNING level (Req 3.3)."""
        filepath = os.path.join(tmp_data_dir, "allostasis.json")
        with open(filepath, "w") as f:
            f.write("{{{{not valid json at all}}}}")

        with caplog.at_level(logging.DEBUG):
            result = persistence.load_allostasis()

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0, "Expected a WARNING log for corrupted file"

    def test_personality_truncated_json_logs_warning(self, persistence, tmp_data_dir, caplog):
        """Truncated JSON (simulating crash during write) logs WARNING."""
        filepath = os.path.join(tmp_data_dir, "personality.json")
        with open(filepath, "w") as f:
            f.write('{"version": 1, "traits": {"openness": 1.0, "neuroticism"')

        with caplog.at_level(logging.DEBUG):
            result = persistence.load_personality()

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0

    def test_allostasis_empty_file_logs_warning(self, persistence, tmp_data_dir, caplog):
        """Empty file logs WARNING (JSONDecodeError on empty content)."""
        filepath = os.path.join(tmp_data_dir, "allostasis.json")
        with open(filepath, "w") as f:
            f.write("")

        with caplog.at_level(logging.DEBUG):
            result = persistence.load_allostasis()

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0


# ------------------------------------------------------------------
# Missing file silent tests (Task 1.5: missing file returns None silently)
# ------------------------------------------------------------------


class TestMissingFileSilent:
    """Validates: Requirements 2.3, 3.3 — missing files return None without any warning."""

    def test_personality_missing_no_warning(self, persistence, caplog):
        """Missing personality file returns None with NO warning logged."""
        with caplog.at_level(logging.DEBUG):
            result = persistence.load_personality()

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0, (
            f"Expected no warnings for missing file, got: "
            f"{[r.message for r in warning_records]}"
        )

    def test_allostasis_missing_no_warning(self, persistence, caplog):
        """Missing allostasis file returns None with NO warning logged."""
        with caplog.at_level(logging.DEBUG):
            result = persistence.load_allostasis()

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 0, (
            f"Expected no warnings for missing file, got: "
            f"{[r.message for r in warning_records]}"
        )

    def test_personality_missing_no_log_output(self, persistence, caplog):
        """Missing personality file produces no log records at WARNING or above."""
        with caplog.at_level(logging.WARNING):
            result = persistence.load_personality()

        assert result is None
        assert len(caplog.records) == 0

    def test_allostasis_missing_no_log_output(self, persistence, caplog):
        """Missing allostasis file produces no log records at WARNING or above."""
        with caplog.at_level(logging.WARNING):
            result = persistence.load_allostasis()

        assert result is None
        assert len(caplog.records) == 0


# ------------------------------------------------------------------
# Data directory creation tests
# ------------------------------------------------------------------


class TestDataDirectory:
    def test_creates_data_dir_on_init(self):
        tmp = tempfile.mkdtemp()
        nested = os.path.join(tmp, "nested", "data")
        try:
            StatePersistence(nested)
            assert os.path.isdir(nested)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_handles_existing_dir(self, tmp_data_dir):
        """Should not raise if directory already exists."""
        sp = StatePersistence(tmp_data_dir)
        assert sp is not None
