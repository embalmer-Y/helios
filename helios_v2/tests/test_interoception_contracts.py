from __future__ import annotations

import pytest

from helios_v2.interoception import InteroceptionError, RuntimePressureSample


def test_runtime_pressure_sample_accepts_unit_interval_values() -> None:
    sample = RuntimePressureSample(
        cpu_pressure=0.4,
        memory_pressure=0.6,
        latency_pressure=0.0,
        error_pressure=1.0,
    )
    assert sample.cpu_pressure == 0.4
    assert sample.memory_pressure == 0.6
    assert sample.latency_pressure == 0.0
    assert sample.error_pressure == 1.0


@pytest.mark.parametrize(
    "field",
    ["cpu_pressure", "memory_pressure", "latency_pressure", "error_pressure"],
)
def test_runtime_pressure_sample_rejects_out_of_range(field: str) -> None:
    values = {
        "cpu_pressure": 0.1,
        "memory_pressure": 0.1,
        "latency_pressure": 0.1,
        "error_pressure": 0.1,
    }
    values[field] = 1.5
    with pytest.raises(InteroceptionError, match=field):
        RuntimePressureSample(**values)


def test_runtime_pressure_sample_rejects_negative() -> None:
    with pytest.raises(InteroceptionError, match="cpu_pressure"):
        RuntimePressureSample(
            cpu_pressure=-0.1,
            memory_pressure=0.1,
            latency_pressure=0.1,
            error_pressure=0.1,
        )
