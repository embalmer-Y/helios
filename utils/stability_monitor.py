"""utils/stability_monitor.py — Long-Running Stability Monitor

Monitors process memory usage (RSS), uptime, and log file rotation.
Designed for 24+ hour continuous operation.

Requirements: 33.1, 33.2, 33.5
"""

import os
import time
import logging

logger = logging.getLogger("helios.stability")


class StabilityMonitor:
    """Monitors process health for long-running operation.

    Checks RSS memory, tracks uptime, and verifies log rotation limits.
    """

    RSS_LIMIT_MB: float = 100.0
    LOG_SIZE_LIMIT_MB: float = 100.0

    def __init__(self):
        self._start_time = time.time()
        self._psutil_available = False
        self._process = None
        self._init_psutil()

    def _init_psutil(self):
        """Attempt to initialize psutil for memory monitoring."""
        try:
            import psutil
            self._process = psutil.Process(os.getpid())
            self._psutil_available = True
        except ImportError:
            logger.warning("psutil not available — memory monitoring disabled")

    @property
    def rss_mb(self) -> float:
        """Current process RSS memory usage in megabytes."""
        if not self._psutil_available or not self._process:
            return 0.0
        try:
            return self._process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    @property
    def uptime_hours(self) -> float:
        """Continuous operation time in hours."""
        return (time.time() - self._start_time) / 3600

    def check_memory(self) -> bool:
        """Check if RSS memory is within limits.

        Returns:
            True if memory is within limit, False if exceeding RSS_LIMIT_MB.
        """
        current = self.rss_mb
        if current > self.RSS_LIMIT_MB:
            logger.warning(
                f"RSS memory {current:.1f}MB exceeds limit {self.RSS_LIMIT_MB}MB"
            )
            return False
        return True

    def check_log_rotation(self, log_path: str) -> bool:
        """Check if a log file exceeds the size limit.

        Args:
            log_path: Path to the log file to check.

        Returns:
            True if log file is within limit, False if exceeding.
        """
        if not os.path.exists(log_path):
            return True
        try:
            size_mb = os.path.getsize(log_path) / (1024 * 1024)
            if size_mb > self.LOG_SIZE_LIMIT_MB:
                logger.warning(
                    f"Log file {log_path} is {size_mb:.1f}MB, "
                    f"exceeds limit {self.LOG_SIZE_LIMIT_MB}MB"
                )
                return False
            return True
        except OSError:
            return True
