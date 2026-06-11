"""R79-D scenarios package — each scenario is a JSON file in this directory."""
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parent
SCENARIOS: dict[str, "Scenario"] = {}


def discover_scenarios() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*.json"))


def load_all() -> dict[str, "Scenario"]:
    global SCENARIOS
    from ..framework import Scenario
    if SCENARIOS:
        return SCENARIOS
    for path in discover_scenarios():
        s = Scenario.from_json(path)
        SCENARIOS[s.id] = s
    return SCENARIOS


__all__ = ["SCENARIOS_DIR", "discover_scenarios", "load_all", "SCENARIOS"]
