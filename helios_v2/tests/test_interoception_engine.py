from __future__ import annotations

import builtins
from dataclasses import dataclass

import pytest

from helios_v2.interoception import (
    RuntimeInteroceptiveSource,
    RuntimePressureSample,
    RuntimePressureSampler,
    StdlibRuntimePressureSampler,
)
from helios_v2.sensory import SensoryIngress
from helios_v2.feeling import validate_internal_body_signal


@dataclass
class FakeRuntimePressureSampler(RuntimePressureSampler):
    sample_value: RuntimePressureSample

    def sample(self) -> RuntimePressureSample:
        return self.sample_value


def _sample(cpu=0.5, memory=0.4, latency=0.0, error=0.0) -> RuntimePressureSample:
    return RuntimePressureSample(
        cpu_pressure=cpu,
        memory_pressure=memory,
        latency_pressure=latency,
        error_pressure=error,
    )


def test_source_emits_one_interoceptive_signal_per_channel() -> None:
    source = RuntimeInteroceptiveSource(sampler=FakeRuntimePressureSampler(_sample()))
    signals = source.emit_raw_signals()

    assert len(signals) == 4
    channels = {s.metadata["pressure_channel"] for s in signals}
    assert channels == {"cpu", "memory", "latency", "error"}
    for s in signals:
        assert s.signal_type == "interoceptive"
        assert s.source_name == "interoception"
        assert s.signal_id
        assert s.content  # non-empty bounded projection
        assert 0.0 <= s.metadata["pressure_value"] <= 1.0


def test_source_projection_is_deterministic_for_fixed_sample() -> None:
    source = RuntimeInteroceptiveSource(sampler=FakeRuntimePressureSampler(_sample(cpu=0.7, memory=0.3)))
    first = source.emit_raw_signals()
    second = source.emit_raw_signals()
    assert tuple((s.signal_id, s.content) for s in first) == tuple((s.signal_id, s.content) for s in second)
    cpu_signal = next(s for s in first if s.metadata["pressure_channel"] == "cpu")
    assert cpu_signal.metadata["pressure_value"] == 0.7


def test_source_name_is_stable() -> None:
    source = RuntimeInteroceptiveSource(sampler=FakeRuntimePressureSampler(_sample()))
    assert source.source_name == "interoception"


def test_emitted_signals_normalize_to_valid_internal_body_signals() -> None:
    # Run the emitted RawSignals through real sensory ingress; the resulting stimuli must be
    # modality="interoceptive" and pass the 05 owner's internal-body-signal validation.
    ingress = SensoryIngress()
    ingress.register_source(RuntimeInteroceptiveSource(sampler=FakeRuntimePressureSampler(_sample())))
    batch = ingress.collect_stimuli()

    interoceptive = [s for s in batch.stimuli if s.modality == "interoceptive"]
    assert len(interoceptive) == 4
    for stimulus in interoceptive:
        # Must not raise: these are valid internal body signals for the 05 feeling stage.
        validate_internal_body_signal(stimulus)


def test_stdlib_sampler_returns_bounded_sample_without_psutil(monkeypatch) -> None:
    # Force the lazy `import psutil` to fail, so the sampler exercises its stdlib/default fallback
    # and must still return a fully bounded sample without raising.
    real_import = builtins.__import__

    def _no_psutil(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("psutil unavailable in test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_psutil)

    sampler = StdlibRuntimePressureSampler()
    sample = sampler.sample()
    for value in (
        sample.cpu_pressure,
        sample.memory_pressure,
        sample.latency_pressure,
        sample.error_pressure,
    ):
        assert 0.0 <= value <= 1.0


def test_stdlib_sampler_unavailable_facts_use_defined_default(monkeypatch) -> None:
    # With psutil unavailable AND no load average (simulate non-Unix), cpu/memory fall back to the
    # documented neutral default rather than raising.
    real_import = builtins.__import__

    def _no_psutil(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("psutil unavailable in test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_psutil)

    import os

    def _no_loadavg():
        raise OSError("no load average on this platform")

    monkeypatch.setattr(os, "getloadavg", _no_loadavg, raising=False)

    sampler = StdlibRuntimePressureSampler(unknown_default=0.0)
    sample = sampler.sample()
    assert sample.cpu_pressure == 0.0
    assert sample.memory_pressure == 0.0


def test_source_propagates_outright_sampler_exception() -> None:
    @dataclass
    class RaisingSampler(RuntimePressureSampler):
        def sample(self) -> RuntimePressureSample:
            raise RuntimeError("sampler boom")

    source = RuntimeInteroceptiveSource(sampler=RaisingSampler())
    with pytest.raises(RuntimeError, match="sampler boom"):
        source.emit_raw_signals()
