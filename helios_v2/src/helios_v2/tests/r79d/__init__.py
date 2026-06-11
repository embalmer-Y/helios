"""R79-D baseline experiment framework.

Purpose
-------
A configuration-driven probe framework for helios_v2. Each "experiment" is a
JSON scenario + a set of assertions. The framework runs the scenario through
the helios runtime (real LLM, dry-run, or mock) and produces:
  - a per-tick JSONL event log
  - a markdown report with per-assertion PASS/FAIL

Design principles
-----------------
- Configurable: scenarios are plain JSON; no code changes needed to add a group.
- Extensible: assertions are registered in a registry; users can add new ones
  via @register_assertion decorator.
- Reproducible: each scenario has a stable id; output paths include the
  scenario id and timestamp; old outputs are not overwritten unless --force.
- Decoupled: the framework does NOT depend on any specific LLM gateway
  implementation. Pass any LlmGatewayAPI.

Owner: helios_v2/runtime / 28-owner architecture.
"""
from .framework import (
    Scenario,
    TickRecord,
    AssertionResult,
    ExperimentConfig,
    run_experiment,
    run_all,
)
from .assertions import register_assertion, list_assertions, BUILTIN_ASSERTIONS
from .scenarios import SCENARIOS, load_all

__all__ = [
    "Scenario",
    "TickRecord",
    "AssertionResult",
    "ExperimentConfig",
    "run_experiment",
    "run_all",
    "register_assertion",
    "list_assertions",
    "BUILTIN_ASSERTIONS",
    "SCENARIOS",
    "load_all",
]
