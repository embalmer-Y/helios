"""Property-based tests for ICRI temperature mapping.

Property 29: ICRI-to-Temperature 5-Tier Mapping
"""

import sys
from pathlib import Path

from hypothesis import given, settings
from hypothesis.strategies import floats

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.icri_temperature import ICRITemperatureMapper


class TestICRITemperatureMapper:
    @given(
        a=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        b=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_mapping_is_monotonic_non_decreasing(self, a: float, b: float):
        lower = min(a, b)
        upper = max(a, b)
        assert ICRITemperatureMapper.map_temperature(lower) <= ICRITemperatureMapper.map_temperature(upper)

    def test_exact_tier_boundaries(self):
        assert ICRITemperatureMapper.map_temperature(0.0) == 0.3
        assert ICRITemperatureMapper.map_temperature(0.0999) == 0.3
        assert ICRITemperatureMapper.map_temperature(0.10) == 0.5
        assert ICRITemperatureMapper.map_temperature(0.2499) == 0.5
        assert ICRITemperatureMapper.map_temperature(0.25) == 0.75
        assert ICRITemperatureMapper.map_temperature(0.4499) == 0.75
        assert ICRITemperatureMapper.map_temperature(0.45) == 1.0
        assert ICRITemperatureMapper.map_temperature(0.6499) == 1.0
        assert ICRITemperatureMapper.map_temperature(0.65) == 1.3
        assert ICRITemperatureMapper.map_temperature(1.0) == 1.3