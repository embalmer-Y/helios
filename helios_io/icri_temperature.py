from __future__ import annotations


class ICRITemperatureMapper:
    """Static 5-tier mapping from ICRI to LLM temperature and style label."""

    @staticmethod
    def map_temperature(icri: float) -> float:
        if icri < 0.10:
            return 0.3
        if icri < 0.25:
            return 0.5
        if icri < 0.45:
            return 0.75
        if icri < 0.65:
            return 1.0
        return 1.3

    @staticmethod
    def get_style_label(icri: float) -> str:
        if icri < 0.10:
            return "mechanical"
        if icri < 0.25:
            return "reserved"
        if icri < 0.45:
            return "balanced"
        if icri < 0.65:
            return "expressive"
        return "expansive"