from __future__ import annotations

from helios_v2.temporal import RestStateTemporalSource


def test_dmn_available_tracks_rest_vs_external_task() -> None:
    source = RestStateTemporalSource()
    # Rest (no external stimulus) -> DMN engaged.
    assert source.sample(external_stimulus_present=False).dmn_available is True
    # External task present -> DMN suppressed.
    assert source.sample(external_stimulus_present=True).dmn_available is False


def test_temporal_signal_accumulates_across_no_fire_ticks() -> None:
    source = RestStateTemporalSource(per_tick_increment=0.2, max_signal=1.0)
    # Cold start: no accumulated rest.
    assert source.sample(False).temporal_signal == 0.0
    # Each no-fire tick advances the elapsed-rest accumulation.
    source.observe_tick(fired=False)
    s1 = source.sample(False).temporal_signal
    source.observe_tick(fired=False)
    s2 = source.sample(False).temporal_signal
    source.observe_tick(fired=False)
    s3 = source.sample(False).temporal_signal
    assert s1 == 0.2
    assert s2 == 0.4
    assert s3 == 0.6
    assert s1 < s2 < s3


def test_temporal_signal_resets_after_a_fire() -> None:
    source = RestStateTemporalSource(per_tick_increment=0.2)
    for _ in range(3):
        source.observe_tick(fired=False)
    assert source.sample(False).temporal_signal > 0.0
    source.observe_tick(fired=True)
    # The tick after a fire, the accumulated rest is reset.
    assert source.sample(False).temporal_signal == 0.0


def test_temporal_signal_is_clamped_at_max() -> None:
    source = RestStateTemporalSource(per_tick_increment=0.2, max_signal=1.0)
    for _ in range(20):
        source.observe_tick(fired=False)
    assert source.sample(False).temporal_signal == 1.0


def test_temporal_source_is_deterministic_for_fixed_sequence() -> None:
    def run() -> list[float]:
        source = RestStateTemporalSource()
        out: list[float] = []
        for fired in (False, False, True, False, False):
            out.append(source.sample(False).temporal_signal)
            source.observe_tick(fired=fired)
        return out

    assert run() == run()


def test_seed_ticks_since_last_fire_resumes_accumulation() -> None:
    source = RestStateTemporalSource(per_tick_increment=0.2)
    source.seed_ticks_since_last_fire(3)
    assert source.sample(False).temporal_signal == 0.6
    # Negative seed clamps to 0 (no fabricated negative history).
    source.seed_ticks_since_last_fire(-5)
    assert source.sample(False).temporal_signal == 0.0
