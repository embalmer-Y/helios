from __future__ import annotations

import pytest

from helios_v2.temporal import TemporalError, TemporalPacingSample


def test_temporal_pacing_sample_accepts_unit_interval() -> None:
    sample = TemporalPacingSample(temporal_signal=0.0, dmn_available=True)
    assert sample.temporal_signal == 0.0
    assert sample.dmn_available is True
    sample_high = TemporalPacingSample(temporal_signal=1.0, dmn_available=False)
    assert sample_high.temporal_signal == 1.0
    assert sample_high.dmn_available is False


def test_temporal_pacing_sample_rejects_out_of_range() -> None:
    with pytest.raises(TemporalError, match="temporal_signal"):
        TemporalPacingSample(temporal_signal=1.5, dmn_available=True)
    with pytest.raises(TemporalError, match="temporal_signal"):
        TemporalPacingSample(temporal_signal=-0.1, dmn_available=True)
