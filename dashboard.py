"""
Backward-compatibility stub — real implementation moved to utils/dashboard.py

All public APIs are re-exported here so existing imports continue to work:
    from dashboard import DashboardServer, ...
"""
# Re-export everything from the new location
from utils.dashboard import *  # noqa: F401, F403
