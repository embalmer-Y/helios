"""Tick exception protection for the Helios main loop.

TickGuard wraps each tick execution with exception handling so that a single
module failure does not crash the entire process. It tracks consecutive errors
and transitions into a safe mode when failures become persistent.
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TickGuard:
    """Wraps tick execution with exception handling and safe mode management.

    When a tick raises an exception, the error is logged and the consecutive
    error counter increments. After exceeding a configurable threshold (default
    10), the guard enters safe mode where non-essential modules should be
    skipped. Safe mode exits automatically after a sustained run of successful
    ticks (default 100 consecutive successes).
    """

    def __init__(
        self,
        max_consecutive_errors: int = 10,
        safe_mode_recovery_ticks: int = 100,
    ):
        self._error_count: int = 0
        self._max_errors: int = max_consecutive_errors
        self._safe_mode: bool = False
        self._safe_mode_recovery_ticks: int = safe_mode_recovery_ticks
        self._success_count_in_safe_mode: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def execute(self, tick_fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Execute *tick_fn* with exception protection.

        On success the consecutive error counter resets to zero. If already in
        safe mode, consecutive successes are tracked and safe mode exits after
        the recovery threshold is reached.

        On failure the error counter increments, the exception is logged with
        full traceback, and safe mode is entered if the threshold is exceeded.
        """
        try:
            tick_fn(*args, **kwargs)
            # Success path
            self._error_count = 0
            if self._safe_mode:
                self._success_count_in_safe_mode += 1
                if self._success_count_in_safe_mode >= self._safe_mode_recovery_ticks:
                    logger.info(
                        "Safe mode recovery complete after %d consecutive successful ticks",
                        self._success_count_in_safe_mode,
                    )
                    self._safe_mode = False
                    self._success_count_in_safe_mode = 0
        except Exception as e:
            self._error_count += 1
            self._success_count_in_safe_mode = 0
            logger.error("Tick exception: %s", e, exc_info=True)
            if self._error_count > self._max_errors:
                if not self._safe_mode:
                    logger.critical(
                        "Consecutive errors (%d) exceeded threshold (%d), entering safe mode",
                        self._error_count,
                        self._max_errors,
                    )
                self._safe_mode = True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def in_safe_mode(self) -> bool:
        """Whether the guard is currently in safe mode."""
        return self._safe_mode

    @property
    def consecutive_errors(self) -> int:
        """Current count of consecutive tick errors."""
        return self._error_count
