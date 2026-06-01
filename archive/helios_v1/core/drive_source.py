"""InternalDriveSource — generates Panksepp triggers from drive urgency signals.

Implements the EventSource interface to translate the dominant drive's urgency
into corresponding Panksepp system triggers. Maps each of the five drives
(curiosity, social, homeostatic, achievement, aesthetic) to its underlying
Panksepp affective system based on Panksepp's taxonomy.

Drive-to-Panksepp mapping:
  curiosity   → SEEKING  (exploration / prediction error reduction)
  social      → PANIC    (separation distress / social bonding)
  homeostatic → FEAR     (physiological safety threat)
  achievement → SEEKING  (goal-directed appetitive behavior)
  aesthetic   → PLAY     (creative expression / playful engagement)
"""

from typing import Dict, List

from core.event_source import EventSource
from core.helios_state import HeliosState


# Mapping from drive names to their corresponding Panksepp systems.
DRIVE_TO_PANKSEPP: Dict[str, str] = {
    "curiosity": "SEEKING",
    "social": "PANIC",
    "homeostatic": "FEAR",
    "achievement": "SEEKING",
    "aesthetic": "PLAY",
}


class InternalDriveSource(EventSource):
    """Generates Panksepp triggers from DriveOracle urgency signals.

    Each tick, reads the dominant drive and its urgency from HeliosState
    and maps it to the corresponding Panksepp system trigger. Does not
    produce any messages.
    """

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Map dominant drive urgency to a Panksepp trigger.

        Args:
            state: Current tick state containing drive_dominant and
                drive_urgency fields.

        Returns:
            Dictionary with the mapped Panksepp system and the drive
            urgency as intensity. Empty dict if no dominant drive is set
            or urgency is zero.
        """
        drive_name = state.drive_dominant
        urgency = state.drive_urgency

        if not drive_name or urgency <= 0.0:
            return {}

        panksepp_system = DRIVE_TO_PANKSEPP.get(drive_name)
        if panksepp_system is None:
            return {}

        return {panksepp_system: urgency}

    def get_messages(self) -> List[dict]:
        """Return empty list — internal drives do not produce messages."""
        return []
