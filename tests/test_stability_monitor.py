"""Tests for long-running stability monitoring."""

import logging
import sys
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.stability_monitor import StabilityMonitor


class TestStabilityMonitor:
    def test_uptime_hours_tracks_elapsed_time(self):
        monitor = StabilityMonitor(start_time=1000.0)

        with mock.patch("utils.stability_monitor.time.time", return_value=4600.0):
            assert monitor.uptime_hours == 1.0

    def test_check_memory_returns_false_above_limit(self, caplog):
        monitor = StabilityMonitor()

        with mock.patch.object(StabilityMonitor, "rss_mb", new_callable=mock.PropertyMock, return_value=120.0):
            with caplog.at_level(logging.WARNING, logger="helios.stability"):
                assert monitor.check_memory() is False

        assert any("exceeds limit" in record.message for record in caplog.records)

    def test_check_log_rotation_returns_false_above_limit(self, caplog):
        monitor = StabilityMonitor()

        with mock.patch("utils.stability_monitor.os.path.getsize", return_value=150 * 1024 * 1024):
            with caplog.at_level(logging.WARNING, logger="helios.stability"):
                assert monitor.check_log_rotation("helios.log") is False

        assert any("rotation limit" in record.message for record in caplog.records)


class TestHeliosStabilityIntegration:
    def test_get_state_includes_stability_metrics(self):
        import helios_main

        helios = helios_main.Helios()
        state = helios.get_state()

        assert "rss_mb" in state
        assert "uptime_hours" in state

    def test_tick_writes_stability_metrics_into_runtime_state(self):
        import helios_main

        helios = helios_main.Helios()
        with mock.patch.object(type(helios.stability_monitor), "rss_mb", new_callable=mock.PropertyMock, return_value=42.5), \
             mock.patch.object(type(helios.stability_monitor), "uptime_hours", new_callable=mock.PropertyMock, return_value=3.25):
            helios._tick_once()

        assert helios.last_rss_mb == 42.5
        assert helios.last_uptime_hours == 3.25