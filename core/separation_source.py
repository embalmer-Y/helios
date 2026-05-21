"""SeparationAnxietySource — computes PANIC triggers from elapsed separation time.

Implements the EventSource interface to generate PANIC system triggers
based on how long since last contact with the user. Uses an exponential
saturation curve that activates only after a threshold is crossed.
"""

import math
from typing import Dict, List

from core.event_source import EventSource
from core.helios_state import HeliosState


class SeparationAnxietySource(EventSource):
    """Computes PANIC triggers from elapsed time since last contact.

    Formula: anxiety = min(1.0, 1 - e^(-0.4 * separation_hours))
    Only emits a PANIC trigger when the computed anxiety exceeds 0.2.
    Does not produce any messages.
    """

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Compute PANIC trigger intensity from separation hours.

        Args:
            state: Current tick state containing separation_hours field.

        Returns:
            {"PANIC": anxiety} when anxiety > 0.2, otherwise empty dict.
        """
        sep_hours = state.separation_hours
        anxiety = min(1.0, 1 - math.exp(-0.4 * sep_hours))
        if anxiety > 0.2:
            return {"PANIC": anxiety}
        return {}

    def get_messages(self) -> List[dict]:
        """Return empty list — separation anxiety does not produce messages."""
        return []
