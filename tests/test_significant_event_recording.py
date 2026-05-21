"""Test significant event recording to Episodic Memory (Task 10.4)

Validates Requirement 13.2:
  WHEN a significant emotional event occurs (Phi exceeds 0.3 or absolute
  valence exceeds 0.5), THE Helios SHALL record the event into Episodic
  memory via Memory_System.

  No recording SHALL occur when phi <= 0.3 AND |valence| <= 0.5.
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory_system import MemorySystem


# ═══════════════════════════════════════════════════
# Direct MemorySystem recording tests
# ═══════════════════════════════════════════════════


def test_record_when_phi_exceeds_threshold():
    """Events with phi > 0.3 should be recorded regardless of valence."""
    ms = MemorySystem()
    assert len(ms.episodic.items) == 0

    ms.remember(
        summary="High phi event",
        valence=0.1,  # low valence — below 0.5
        arousal=0.3,
        phi=0.5,      # above threshold
    )

    assert len(ms.episodic.items) == 1
    item = ms.episodic.items[0]
    assert item.phi == 0.5
    assert item.valence == 0.1
    assert item.arousal == 0.3
    assert item.emotional_tag != ""
    assert item.timestamp > 0
    print("✓ Event recorded when phi > 0.3")


def test_record_when_valence_exceeds_positive_threshold():
    """Events with valence > 0.5 should be recorded regardless of phi."""
    ms = MemorySystem()

    ms.remember(
        summary="Positive valence event",
        valence=0.7,   # above |0.5| threshold
        arousal=0.4,
        phi=0.1,       # below phi threshold
    )

    assert len(ms.episodic.items) == 1
    item = ms.episodic.items[0]
    assert item.valence == 0.7
    assert item.phi == 0.1
    print("✓ Event recorded when valence > 0.5")


def test_record_when_valence_exceeds_negative_threshold():
    """Events with valence < -0.5 should be recorded (|valence| > 0.5)."""
    ms = MemorySystem()

    ms.remember(
        summary="Negative valence event",
        valence=-0.8,  # |valence| > 0.5
        arousal=0.6,
        phi=0.2,       # below phi threshold
    )

    assert len(ms.episodic.items) == 1
    item = ms.episodic.items[0]
    assert item.valence == -0.8
    print("✓ Event recorded when |valence| > 0.5 (negative)")


def test_memory_item_contains_required_fields():
    """Recorded MemoryItem must include emotional_tag, valence, arousal, phi, timestamp."""
    ms = MemorySystem()

    ms.remember(
        summary="Complete event",
        valence=0.6,
        arousal=0.7,
        phi=0.4,
    )

    item = ms.episodic.items[0]
    # All required fields per task description
    assert hasattr(item, 'emotional_tag') and item.emotional_tag != ""
    assert hasattr(item, 'valence') and item.valence == 0.6
    assert hasattr(item, 'arousal') and item.arousal == 0.7
    assert hasattr(item, 'phi') and item.phi == 0.4
    assert hasattr(item, 'timestamp') and item.timestamp > 0
    print("✓ MemoryItem contains emotional_tag, valence, arousal, phi, timestamp")


# ═══════════════════════════════════════════════════
# Helios._record_significant_event integration tests
# ═══════════════════════════════════════════════════


def test_helios_has_record_significant_event_method():
    """Helios class must have the _record_significant_event helper."""
    from helios_main import Helios
    assert hasattr(Helios, '_record_significant_event'), (
        "Helios should have _record_significant_event method"
    )
    print("✓ Helios._record_significant_event method exists")


def test_record_significant_event_records_above_phi_threshold():
    """_record_significant_event should record when phi > 0.3."""
    from helios_main import Helios, HeliosConfig

    class FakeHelios:
        """Minimal stand-in with just the memory system."""
        def __init__(self):
            self.memory_system = MemorySystem()

    fake = FakeHelios()
    # Bind the method to our fake instance
    method = Helios._record_significant_event.__get__(fake, FakeHelios)

    method(phi=0.5, valence=0.1, arousal=0.3, dominant="SEEKING", events={"SEEKING": 0.5})

    assert len(fake.memory_system.episodic.items) == 1
    item = fake.memory_system.episodic.items[0]
    assert item.phi == 0.5
    assert item.valence == 0.1
    assert item.arousal == 0.3
    print("✓ _record_significant_event records when phi > 0.3")


def test_record_significant_event_records_above_valence_threshold():
    """_record_significant_event should record when |valence| > 0.5."""
    from helios_main import Helios, HeliosConfig

    class FakeHelios:
        def __init__(self):
            self.memory_system = MemorySystem()

    fake = FakeHelios()
    method = Helios._record_significant_event.__get__(fake, FakeHelios)

    # Positive valence above threshold
    method(phi=0.1, valence=0.7, arousal=0.5, dominant="CARE", events={})
    assert len(fake.memory_system.episodic.items) == 1

    # Negative valence above threshold
    method(phi=0.2, valence=-0.6, arousal=0.4, dominant="PANIC", events={"PANIC": 0.3})
    assert len(fake.memory_system.episodic.items) == 2
    print("✓ _record_significant_event records when |valence| > 0.5")


def test_record_significant_event_no_record_below_thresholds():
    """_record_significant_event should NOT record when phi <= 0.3 AND |valence| <= 0.5."""
    from helios_main import Helios, HeliosConfig

    class FakeHelios:
        def __init__(self):
            self.memory_system = MemorySystem()

    fake = FakeHelios()
    method = Helios._record_significant_event.__get__(fake, FakeHelios)

    # Both below threshold
    method(phi=0.2, valence=0.3, arousal=0.2, dominant="SEEKING", events={})
    method(phi=0.3, valence=0.5, arousal=0.1, dominant="CARE", events={})  # boundary: NOT above
    method(phi=0.1, valence=-0.4, arousal=0.5, dominant="FEAR", events={})
    method(phi=0.0, valence=0.0, arousal=0.0, dominant="", events={})

    assert len(fake.memory_system.episodic.items) == 0, (
        f"Expected 0 recordings but got {len(fake.memory_system.episodic.items)} "
        f"when both phi <= 0.3 and |valence| <= 0.5"
    )
    print("✓ No recording when phi ≤ 0.3 AND |valence| ≤ 0.5")


def test_record_significant_event_boundary_phi():
    """Boundary: phi = 0.3 exactly should NOT record (> 0.3 is the threshold)."""
    from helios_main import Helios, HeliosConfig

    class FakeHelios:
        def __init__(self):
            self.memory_system = MemorySystem()

    fake = FakeHelios()
    method = Helios._record_significant_event.__get__(fake, FakeHelios)

    method(phi=0.3, valence=0.0, arousal=0.0, dominant="", events={})
    assert len(fake.memory_system.episodic.items) == 0
    print("✓ Boundary: phi = 0.3 exactly does NOT trigger recording")


def test_record_significant_event_boundary_valence():
    """Boundary: |valence| = 0.5 exactly should NOT record (> 0.5 is the threshold)."""
    from helios_main import Helios, HeliosConfig

    class FakeHelios:
        def __init__(self):
            self.memory_system = MemorySystem()

    fake = FakeHelios()
    method = Helios._record_significant_event.__get__(fake, FakeHelios)

    method(phi=0.2, valence=0.5, arousal=0.0, dominant="", events={})
    method(phi=0.2, valence=-0.5, arousal=0.0, dominant="", events={})
    assert len(fake.memory_system.episodic.items) == 0
    print("✓ Boundary: |valence| = 0.5 exactly does NOT trigger recording")


def test_tick_calls_record_significant_event():
    """Verify that _tick() calls _record_significant_event."""
    from helios_main import Helios
    source = inspect.getsource(Helios._tick)

    assert "_record_significant_event" in source, (
        "_tick() should call self._record_significant_event()"
    )
    print("✓ _tick() calls _record_significant_event")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Significant Event Recording (Task 10.4)")
    print("=" * 60)

    test_record_when_phi_exceeds_threshold()
    test_record_when_valence_exceeds_positive_threshold()
    test_record_when_valence_exceeds_negative_threshold()
    test_memory_item_contains_required_fields()
    test_helios_has_record_significant_event_method()
    test_record_significant_event_records_above_phi_threshold()
    test_record_significant_event_records_above_valence_threshold()
    test_record_significant_event_no_record_below_thresholds()
    test_record_significant_event_boundary_phi()
    test_record_significant_event_boundary_valence()
    test_tick_calls_record_significant_event()

    print("\n" + "=" * 60)
    print("✅ All significant event recording tests passed!")
    print("=" * 60)
