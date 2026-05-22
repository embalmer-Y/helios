"""
io/icri_temperature.py — ICRI-to-LLM Temperature Mapping

Maps the Integrated Consciousness Richness Index (ICRI) to LLM generation
temperature using a 5-tier schedule. Low consciousness produces mechanical,
brief outputs; high consciousness produces wild, associative outputs.
"""


class ICRITemperatureMapper:
    """
    Maps ICRI level to LLM temperature using a 5-tier schedule.
    Low consciousness → mechanical speech; high consciousness → creative speech.

    The mapping is monotonically non-decreasing with ICRI:
        ICRI < 0.10        → 0.3  (mechanical_brief)
        ICRI in [0.10, 0.25) → 0.5  (warm_moderate)
        ICRI in [0.25, 0.45) → 0.75 (creative)
        ICRI in [0.45, 0.65) → 1.0  (highly_creative)
        ICRI >= 0.65        → 1.3  (wild_associative)
    """

    # (icri_threshold, temperature) — checked in descending order
    TIERS = [
        (0.65, 1.3),   # Wild associative
        (0.45, 1.0),   # Highly creative
        (0.25, 0.75),  # Creative
        (0.10, 0.5),   # Warm moderate
        (0.00, 0.3),   # Mechanical brief
    ]

    @staticmethod
    def map_temperature(icri: float) -> float:
        """Return LLM temperature for current ICRI level.

        Args:
            icri: The current ICRI value, expected in [0, 1] range.

        Returns:
            LLM temperature value from the 5-tier mapping.
        """
        for threshold, temp in ICRITemperatureMapper.TIERS:
            if icri >= threshold:
                return temp
        return 0.3  # Fallback (should not reach)

    @staticmethod
    def get_style_label(icri: float) -> str:
        """Return human-readable style label for dashboard display.

        Args:
            icri: The current ICRI value, expected in [0, 1] range.

        Returns:
            A string label describing the speech style at this ICRI level.
        """
        if icri >= 0.65:
            return "wild_associative"
        elif icri >= 0.45:
            return "highly_creative"
        elif icri >= 0.25:
            return "creative"
        elif icri >= 0.10:
            return "warm_moderate"
        else:
            return "mechanical_brief"
