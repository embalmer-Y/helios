"""
io/limb_decision_bridge.py — Bridge between RegulationEngine and BehaviorExecutor

Converts regulation scores into priority-ordered BehaviorCommands and enqueues
them in the BehaviorExecutor. This cleanly separates regulation decisions from
execution mechanics.

Requirements: 29.2
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LimbDecisionBridge:
    """
    Bridge between RegulationEngine scores and BehaviorExecutor commands.

    Converts regulation decisions (action + score) into executable behavior
    commands with appropriate priority levels, then enqueues them in the
    BehaviorExecutor for priority-ordered execution.

    Priority mapping (score → priority):
        score ≥ 0.8 → 100 (Critical)
        score ≥ 0.6 → 75  (High)
        score ≥ 0.4 → 50  (Normal)
        score ≥ 0.2 → 25  (Low)
        else         → 10  (Background)
    """

    # Priority mapping: urgency score threshold → priority level
    PRIORITY_THRESHOLDS = [
        (0.8, 100),  # Critical
        (0.6, 75),   # High
        (0.4, 50),   # Normal
        (0.2, 25),   # Low
        (0.0, 10),   # Background
    ]

    def __init__(self, executor):
        """
        Initialize the bridge with a BehaviorExecutor instance.

        Args:
            executor: A BehaviorExecutor instance to enqueue commands into.
        """
        self._executor = executor

    def convert_and_enqueue(self, action: str, score: float, params: Optional[dict] = None):
        """
        Convert a regulation score to a priority-ordered BehaviorCommand and enqueue it.

        Maps the regulation score to a priority level using the threshold table,
        then creates a uniquely-named BehaviorCommand and enqueues it in the
        BehaviorExecutor.

        Args:
            action: The action type selected by RegulationEngine (e.g., "speak", "browse").
            score: The regulation score in [0, 1] indicating urgency/importance.
            params: Optional parameters for the behavior action.
        """
        priority = self._score_to_priority(score)
        name = f"{action}_{int(time.time())}"
        logger.debug(
            f"Converting regulation action '{action}' (score={score:.3f}) "
            f"to behavior command with priority={priority}"
        )
        self._executor.enqueue(
            name=name,
            action=action,
            priority=priority,
            params=params or {},
        )

    def _score_to_priority(self, score: float) -> int:
        """
        Map a regulation score [0, 1] to a discrete priority level.

        Uses threshold-based mapping:
            score ≥ 0.8 → 100
            score ≥ 0.6 → 75
            score ≥ 0.4 → 50
            score ≥ 0.2 → 25
            else         → 10

        Args:
            score: The regulation score in [0, 1].

        Returns:
            Integer priority level (10, 25, 50, 75, or 100).
        """
        for threshold, priority in self.PRIORITY_THRESHOLDS:
            if score >= threshold:
                return priority
        return 10
