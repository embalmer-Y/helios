"""Bridge from regulation scores to behavior executor commands."""

from __future__ import annotations

import time
from typing import Any, Optional


class LimbDecisionBridge:
    PRIORITY_THRESHOLDS = [
        (0.8, 100),
        (0.6, 75),
        (0.4, 50),
        (0.2, 25),
        (0.0, 10),
    ]

    def __init__(self, executor):
        self._executor = executor

    def convert_and_enqueue(self, action: str, score: float, params: Optional[dict[str, Any]] = None):
        priority = self._score_to_priority(score)
        return self._executor.enqueue_named(
            name=f"{action}_{int(time.time() * 1000)}",
            action=action,
            priority=priority,
            params=params or {},
        )

    def _score_to_priority(self, score: float) -> int:
        for threshold, priority in self.PRIORITY_THRESHOLDS:
            if score >= threshold:
                return priority
        return 10