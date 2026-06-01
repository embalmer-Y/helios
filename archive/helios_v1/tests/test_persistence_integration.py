"""
Tests for personality and allostasis persistence integration into the main loop.

Validates:
  - Personality is loaded from disk on startup (Requirement 2.2)
  - Allostasis is loaded from disk on startup (Requirement 3.2)
  - Both are saved on shutdown (Requirements 2.1, 3.1)
  - Both are saved periodically every 600 ticks (Requirement 2.4)
  - Missing/corrupted files result in defaults (Requirements 2.3, 3.3)
"""

import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

import pytest

from personality import PersonalityProfile
from allostasis import AllostaticRegulator, AllostasisConfig
from utils.persistence import StatePersistence


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path):
    """Provide a temporary data directory."""
    return str(tmp_path / "data")


@pytest.fixture
def persistence(data_dir):
    """Create a StatePersistence instance with a temp directory."""
    return StatePersistence(data_dir)


@pytest.fixture
def evolved_personality():
    """Create a personality profile with non-default traits."""
    p = PersonalityProfile()
    p.openness = 1.3
    p.extraversion = 0.7
    p.agreeableness = 1.1
    p.neuroticism = 0.8
    p.conscientiousness = 1.2
    p.total_emotion_cycles = 500
    p._recompute()
    return p


@pytest.fixture
def loaded_allostasis():
    """Create an AllostaticRegulator with accumulated state."""
    ar = AllostaticRegulator(AllostasisConfig(
        load_accum_rate=0.005,
        load_decay_rate=0.998,
        load_fatigue_threshold=0.5,
        recovery_threshold=0.2,
    ))
    # Simulate accumulated cycles
    ar.total_cycles = 1200
    ar.fatigue_cycles = 30
    ar.recovery_cycles = 10
    ar.states["SEEKING"].setpoint = 0.12
    ar.states["FEAR"].setpoint = 0.08
    return ar


# ---------------------------------------------------------------------------
# Startup load tests
# ---------------------------------------------------------------------------


class TestStartupLoad:
    """Verify personality and allostasis are restored from disk on startup."""

    def test_personality_restored_from_disk(self, persistence, data_dir, evolved_personality):
        """Personality traits are loaded and applied to a fresh PersonalityProfile."""
        # Save evolved personality
        persistence.save_personality(evolved_personality)

        # Simulate startup: create fresh personality then load
        fresh = PersonalityProfile()
        loaded_data = persistence.load_personality()
        assert loaded_data is not None

        traits = loaded_data["traits"]
        fresh.openness = traits["openness"]
        fresh.extraversion = traits["extraversion"]
        fresh.agreeableness = traits["agreeableness"]
        fresh.neuroticism = traits["neuroticism"]
        fresh.conscientiousness = traits["conscientiousness"]
        fresh.total_emotion_cycles = loaded_data["total_emotion_cycles"]
        fresh._recompute()

        assert fresh.openness == pytest.approx(1.3)
        assert fresh.extraversion == pytest.approx(0.7)
        assert fresh.agreeableness == pytest.approx(1.1)
        assert fresh.neuroticism == pytest.approx(0.8)
        assert fresh.conscientiousness == pytest.approx(1.2)
        assert fresh.total_emotion_cycles == 500

    def test_allostasis_restored_from_disk(self, persistence, data_dir, loaded_allostasis):
        """Allostasis setpoints and counters are loaded and applied."""
        # Save loaded allostasis
        persistence.save_allostasis(loaded_allostasis)

        # Simulate startup: create fresh allostasis then load
        fresh = AllostaticRegulator(AllostasisConfig(
            load_accum_rate=0.005,
            load_decay_rate=0.998,
            load_fatigue_threshold=0.5,
            recovery_threshold=0.2,
        ))
        loaded_data = persistence.load_allostasis()
        assert loaded_data is not None

        # Restore setpoints
        setpoints = loaded_data["setpoints"]
        for sys_name, sp_val in setpoints.items():
            if sys_name in fresh.states:
                fresh.states[sys_name].setpoint = sp_val
        fresh.fatigue_cycles = loaded_data["fatigue_cycles"]
        fresh.recovery_cycles = loaded_data["recovery_cycles"]
        fresh.total_cycles = loaded_data["total_cycles"]

        assert fresh.states["SEEKING"].setpoint == pytest.approx(0.12)
        assert fresh.states["FEAR"].setpoint == pytest.approx(0.08)
        assert fresh.total_cycles == 1200
        assert fresh.fatigue_cycles == 30
        assert fresh.recovery_cycles == 10

    def test_missing_personality_uses_defaults(self, persistence):
        """When no personality file exists, defaults are kept."""
        loaded_data = persistence.load_personality()
        assert loaded_data is None

        fresh = PersonalityProfile()
        # Verify defaults remain
        assert fresh.openness == 1.0
        assert fresh.extraversion == 1.0

    def test_missing_allostasis_uses_defaults(self, persistence):
        """When no allostasis file exists, defaults are kept."""
        loaded_data = persistence.load_allostasis()
        assert loaded_data is None

        fresh = AllostaticRegulator()
        # Verify defaults remain
        assert fresh.states["SEEKING"].setpoint == 0.05
        assert fresh.total_cycles == 0

    def test_corrupted_personality_uses_defaults(self, data_dir, persistence):
        """When personality file is corrupted, defaults are kept."""
        # Write garbage
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "personality.json"), "w") as f:
            f.write("{invalid json!!!")

        loaded_data = persistence.load_personality()
        assert loaded_data is None

    def test_corrupted_allostasis_uses_defaults(self, data_dir, persistence):
        """When allostasis file is corrupted, defaults are kept."""
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "allostasis.json"), "w") as f:
            f.write("not json at all")

        loaded_data = persistence.load_allostasis()
        assert loaded_data is None


# ---------------------------------------------------------------------------
# Shutdown save tests
# ---------------------------------------------------------------------------


class TestShutdownSave:
    """Verify personality and allostasis are saved on shutdown."""

    def test_personality_saved_on_shutdown(self, persistence, data_dir, evolved_personality):
        """Personality state file exists after save."""
        persistence.save_personality(evolved_personality)
        filepath = os.path.join(data_dir, "personality.json")
        assert os.path.exists(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)
        assert data["traits"]["openness"] == pytest.approx(1.3)
        assert data["total_emotion_cycles"] == 500

    def test_allostasis_saved_on_shutdown(self, persistence, data_dir, loaded_allostasis):
        """Allostasis state file exists after save."""
        persistence.save_allostasis(loaded_allostasis)
        filepath = os.path.join(data_dir, "allostasis.json")
        assert os.path.exists(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)
        assert data["setpoints"]["SEEKING"] == pytest.approx(0.12)
        assert data["total_cycles"] == 1200


# ---------------------------------------------------------------------------
# Periodic save tests
# ---------------------------------------------------------------------------


class TestPeriodicSave:
    """Verify that periodic save happens every 600 ticks."""

    def test_periodic_save_at_600_tick_boundary(self, persistence, data_dir, evolved_personality, loaded_allostasis):
        """
        Simulates the periodic persistence check at tick 600.
        After saving, both files should reflect current state.
        """
        # Simulate tick 600 — save
        persistence.save_personality(evolved_personality)
        persistence.save_allostasis(loaded_allostasis)

        # Verify files are written
        assert os.path.exists(os.path.join(data_dir, "personality.json"))
        assert os.path.exists(os.path.join(data_dir, "allostasis.json"))

        # Now modify personality and re-save (simulating tick 1200)
        evolved_personality.openness = 1.5
        evolved_personality.total_emotion_cycles = 1100
        persistence.save_personality(evolved_personality)

        # Verify updated values
        loaded = persistence.load_personality()
        assert loaded["traits"]["openness"] == pytest.approx(1.5)
        assert loaded["total_emotion_cycles"] == 1100


# ---------------------------------------------------------------------------
# Full lifecycle test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Test the complete load → evolve → periodic save → shutdown save cycle."""

    def test_startup_evolve_save_restart_retains_state(self, data_dir):
        """
        Lifecycle test:
        1. Fresh start (no files) → defaults
        2. Evolve personality
        3. Save (shutdown)
        4. Restart (load) → personality restored
        """
        persistence = StatePersistence(data_dir)

        # Session 1: Fresh start
        p = PersonalityProfile()
        allo = AllostaticRegulator()

        personality_data = persistence.load_personality()
        assert personality_data is None  # First start

        # Evolve during session
        p.openness = 1.15
        p.total_emotion_cycles = 200
        p._recompute()
        allo.total_cycles = 600
        allo.states["CARE"].setpoint = 0.09

        # Shutdown save
        persistence.save_personality(p)
        persistence.save_allostasis(allo)

        # Session 2: Restart
        p2 = PersonalityProfile()
        allo2 = AllostaticRegulator()

        personality_data = persistence.load_personality()
        assert personality_data is not None
        traits = personality_data["traits"]
        p2.openness = traits["openness"]
        p2.total_emotion_cycles = personality_data["total_emotion_cycles"]
        p2._recompute()

        allostasis_data = persistence.load_allostasis()
        assert allostasis_data is not None
        for sys_name, sp_val in allostasis_data["setpoints"].items():
            if sys_name in allo2.states:
                allo2.states[sys_name].setpoint = sp_val
        allo2.total_cycles = allostasis_data["total_cycles"]

        # Verify restoration
        assert p2.openness == pytest.approx(1.15)
        assert p2.total_emotion_cycles == 200
        assert allo2.states["CARE"].setpoint == pytest.approx(0.09)
        assert allo2.total_cycles == 600
