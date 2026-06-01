"""Long-running stability monitoring utilities for Helios."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover - optional runtime dependency
    psutil = None


logger = logging.getLogger("helios.stability")


def _emit_warning(message: str, *args) -> None:
    logger.warning(message, *args)
    logging.getLogger().warning(message, *args)


class StabilityMonitor:
    """Tracks process memory usage, uptime, and log growth."""

    RSS_LIMIT_MB = 100.0
    LOG_SIZE_LIMIT_MB = 100.0

    def __init__(self, process_pid: Optional[int] = None, start_time: Optional[float] = None):
        self._pid = process_pid or os.getpid()
        self._start_time = start_time if start_time is not None else time.time()

    @property
    def uptime_hours(self) -> float:
        return max(0.0, (time.time() - self._start_time) / 3600.0)

    @property
    def rss_mb(self) -> float:
        """Return current process RSS in megabytes when available."""
        if psutil is None:
            return 0.0

        try:
            process = psutil.Process(self._pid)
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def check_memory(self) -> bool:
        """Return True while RSS stays within the configured limit."""
        rss = self.rss_mb
        if rss > self.RSS_LIMIT_MB:
            _emit_warning(
                "RSS %.1fMB exceeds limit %.1fMB",
                rss,
                self.RSS_LIMIT_MB,
            )
            return False
        return True

    def check_log_rotation(self, log_path: str) -> bool:
        """Return True while the log file remains under the rotation threshold."""
        try:
            size_mb = os.path.getsize(log_path) / (1024 * 1024)
        except OSError:
            return True

        if size_mb > self.LOG_SIZE_LIMIT_MB:
            _emit_warning(
                "Log file %.1fMB exceeds rotation limit %.1fMB: %s",
                size_mb,
                self.LOG_SIZE_LIMIT_MB,
                log_path,
            )
            return False
        return True