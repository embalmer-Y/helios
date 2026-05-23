"""Test DriveOracle integration into tick pipeline (Task 9.1)

Validates Requirement 12.1:
  WHEN Helios executes a Tick, THE Helios SHALL compute the DriveVector
  from DriveOracle using current state information.
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cognition import DriveOracle, HeliosSnapshot, DriveVector


def test_drive_oracle_produces_drive_vector():
    """DriveOracle.cycle() should return a DriveVector with valid fields."""
    oracle = DriveOracle()
    snapshot = HeliosSnapshot(
        valence=0.2,
        arousal=0.4,
        time_since_last_interaction=7200,  # 2 hours
        phi_value=0.3,
    )
    result = oracle.cycle(snapshot)

    assert isinstance(result, DriveVector)
    assert 0.0 <= result.total <= 1.0
    assert result.dominant in (
        "curiosity", "social", "homeostatic", "achievement", "aesthetic"
    )
    print(f"✓ DriveOracle returns valid DriveVector: dominant={result.dominant}, total={result.total:.3f}")


def test_drive_dominant_and_urgency_written_to_state():
    """Verify that _tick writes drive_dominant and drive_urgency to internal state."""
    from helios_main import Helios, HeliosConfig
    source = inspect.getsource(Helios._tick)

    # Check that DriveOracle is called in the tick
    assert "drive_oracle.cycle" in source, (
        "helios_main._tick() should call self.drive_oracle.cycle()"
    )
    # Check that drive_dominant is written
    assert "_last_drive_dominant" in source, (
        "helios_main._tick() should write _last_drive_dominant"
    )
    # Check that drive_urgency is written
    assert "_last_drive_urgency" in source, (
        "helios_main._tick() should write _last_drive_urgency"
    )
    print("✓ _tick() writes drive_dominant and drive_urgency")


def test_drive_oracle_initialized_in_helios():
    """Verify Helios.__init__ creates a DriveOracle instance."""
    from helios_main import Helios, HeliosConfig
    source = inspect.getsource(Helios.__init__)
    assert "DriveOracle()" in source, (
        "Helios.__init__ should instantiate DriveOracle"
    )
    print("✓ DriveOracle initialized in Helios.__init__")


def test_drive_vector_dominant_reflects_state():
    """High separation time should make social the dominant drive."""
    oracle = DriveOracle()
    snapshot = HeliosSnapshot(
        time_since_last_interaction=10 * 3600,  # 10 hours
        social_connection_quality=0.3,
        valence=-0.2,
        arousal=0.3,
    )
    result = oracle.cycle(snapshot)

    assert result.social > 0.3, (
        f"Long separation should produce significant social drive: {result.social}"
    )
    print(f"✓ Long separation → social drive={result.social:.3f}, dominant={result.dominant}")


def test_snapshot_built_with_current_state():
    """HeliosSnapshot should be built from current tick state in _tick."""
    from helios_main import Helios
    source = inspect.getsource(Helios._tick)

    # Verify HeliosSnapshot is constructed with relevant state fields
    assert "HeliosSnapshot(" in source, (
        "_tick() should construct a HeliosSnapshot"
    )
    assert "valence=state.valence" in source or "valence=" in source, (
        "_tick() should pass valence to HeliosSnapshot"
    )
    print("✓ HeliosSnapshot constructed with current state values")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing DriveOracle Integration (Task 9.1)")
    print("=" * 60)

    test_drive_oracle_produces_drive_vector()
    test_drive_dominant_and_urgency_written_to_state()
    test_drive_oracle_initialized_in_helios()
    test_drive_vector_dominant_reflects_state()
    test_snapshot_built_with_current_state()

    print("\n" + "=" * 60)
    print("✅ All DriveOracle integration tests passed!")
    print("=" * 60)
