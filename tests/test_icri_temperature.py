"""Unit tests for ICRITemperatureMapper."""

import sys
import importlib.util
from pathlib import Path

# Load the module directly to avoid 'io' stdlib conflict
_pkg_dir = Path(__file__).parent.parent / "io"
_mod_name = "helios_io_icri_temperature"
if _mod_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _mod_name, str(_pkg_dir / "icri_temperature.py")
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_mod_name] = _mod
    _spec.loader.exec_module(_mod)
else:
    _mod = sys.modules[_mod_name]

ICRITemperatureMapper = _mod.ICRITemperatureMapper


class TestMapTemperature:
    """Tests for ICRITemperatureMapper.map_temperature()."""

    def test_below_010_returns_03(self):
        """ICRI < 0.10 should produce temperature 0.3."""
        assert ICRITemperatureMapper.map_temperature(0.0) == 0.3
        assert ICRITemperatureMapper.map_temperature(0.05) == 0.3
        assert ICRITemperatureMapper.map_temperature(0.099) == 0.3

    def test_010_to_025_returns_05(self):
        """ICRI in [0.10, 0.25) should produce temperature 0.5."""
        assert ICRITemperatureMapper.map_temperature(0.10) == 0.5
        assert ICRITemperatureMapper.map_temperature(0.15) == 0.5
        assert ICRITemperatureMapper.map_temperature(0.249) == 0.5

    def test_025_to_045_returns_075(self):
        """ICRI in [0.25, 0.45) should produce temperature 0.75."""
        assert ICRITemperatureMapper.map_temperature(0.25) == 0.75
        assert ICRITemperatureMapper.map_temperature(0.35) == 0.75
        assert ICRITemperatureMapper.map_temperature(0.449) == 0.75

    def test_045_to_065_returns_10(self):
        """ICRI in [0.45, 0.65) should produce temperature 1.0."""
        assert ICRITemperatureMapper.map_temperature(0.45) == 1.0
        assert ICRITemperatureMapper.map_temperature(0.55) == 1.0
        assert ICRITemperatureMapper.map_temperature(0.649) == 1.0

    def test_065_and_above_returns_13(self):
        """ICRI >= 0.65 should produce temperature 1.3."""
        assert ICRITemperatureMapper.map_temperature(0.65) == 1.3
        assert ICRITemperatureMapper.map_temperature(0.8) == 1.3
        assert ICRITemperatureMapper.map_temperature(1.0) == 1.3

    def test_boundary_values(self):
        """Test exact boundary values between tiers."""
        assert ICRITemperatureMapper.map_temperature(0.10) == 0.5
        assert ICRITemperatureMapper.map_temperature(0.25) == 0.75
        assert ICRITemperatureMapper.map_temperature(0.45) == 1.0
        assert ICRITemperatureMapper.map_temperature(0.65) == 1.3

    def test_monotonically_non_decreasing(self):
        """Temperature should never decrease as ICRI increases."""
        values = [i / 100.0 for i in range(101)]
        temps = [ICRITemperatureMapper.map_temperature(v) for v in values]
        for i in range(len(temps) - 1):
            assert temps[i] <= temps[i + 1], (
                f"Monotonicity violated: temp({values[i]})={temps[i]} > "
                f"temp({values[i+1]})={temps[i+1]}"
            )


class TestGetStyleLabel:
    """Tests for ICRITemperatureMapper.get_style_label()."""

    def test_below_010_mechanical(self):
        assert ICRITemperatureMapper.get_style_label(0.0) == "mechanical_brief"
        assert ICRITemperatureMapper.get_style_label(0.05) == "mechanical_brief"

    def test_010_to_025_warm(self):
        assert ICRITemperatureMapper.get_style_label(0.10) == "warm_moderate"
        assert ICRITemperatureMapper.get_style_label(0.20) == "warm_moderate"

    def test_025_to_045_creative(self):
        assert ICRITemperatureMapper.get_style_label(0.25) == "creative"
        assert ICRITemperatureMapper.get_style_label(0.35) == "creative"

    def test_045_to_065_highly_creative(self):
        assert ICRITemperatureMapper.get_style_label(0.45) == "highly_creative"
        assert ICRITemperatureMapper.get_style_label(0.55) == "highly_creative"

    def test_065_and_above_wild(self):
        assert ICRITemperatureMapper.get_style_label(0.65) == "wild_associative"
        assert ICRITemperatureMapper.get_style_label(1.0) == "wild_associative"

    def test_style_label_matches_temperature_tier(self):
        """Style labels should correspond to the same tier boundaries as temperature."""
        test_cases = [
            (0.05, "mechanical_brief", 0.3),
            (0.15, "warm_moderate", 0.5),
            (0.35, "creative", 0.75),
            (0.55, "highly_creative", 1.0),
            (0.75, "wild_associative", 1.3),
        ]
        for icri, expected_label, expected_temp in test_cases:
            assert ICRITemperatureMapper.get_style_label(icri) == expected_label
            assert ICRITemperatureMapper.map_temperature(icri) == expected_temp
