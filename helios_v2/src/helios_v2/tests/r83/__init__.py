"""R83 Long-Running Preflight and Turing-Style Persona Evaluation.

This is the final acceptance gate of the R79 plan. R83 is a 10-minute
end-to-end audit harness that drives helios_v2 under CLI external input
and produces a 6-axis Turing-style report on whether the persona behaves
like a person.

R83 is a sibling of `helios_v2.tests.r79d`, not a child. Both share the
same framework primitives (`Scenario` / `TickRecord` / `ExperimentConfig`)
but R83 owns its own state-block / judge-probe / report-builder code.

Public surface:
    - `LongRunner` (long_runner.py) - the continuous-run harness
    - `JudgeProbe` (judge.py) - external LLM judge probe
    - `MemoryProbe` (memory_probe.py) - directed-retrieval probe
    - `R83ReportBuilder` (report_builder.py) - 6-axis Markdown report
    - `Verdict` (verdict.py) - overall pass/fail logic
    - `scenarios` (scenarios/) - 8-state stimulus catalog
    - `_io` (_io.py) - R21-compliant stdout wrapper

Version: 0.1.0 (2026-06-11, R83 T0)
"""
__version__ = "0.1.0"
