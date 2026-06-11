"""R79-D CLI.

Usage:
  python -m helios_v2.tests.r79d list
  python -m helios_v2.tests.r79d run --scenario A_praise
  python -m helios_v2.tests.r79d run --all
  python -m helios_v2.tests.r79d run --all --noop
  python -m helios_v2.tests.r79d report --output <dir>
  python -m helios_v2.tests.r79d diff --baseline <dir1> --current <dir2>
  python -m helios_v2.tests.r79d assertions
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import _io

ROOT = Path("/root/project/helios")
DEFAULT_OUTPUT = ROOT / "logs" / "prompt_probe_scenarios" / "r79d"


def _load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" not in line: continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def cmd_list(args):
    from .scenarios import load_all
    scenarios = load_all()
    _io.write_line(f"Available scenarios ({len(scenarios)}):")
    for sid, s in scenarios.items():
        _io.write_line(f"  - {sid}: {s.description} (n_ticks={len(s.stimulus_script)}, n_assertions={len(s.assertions)}, repeat={s.repeat})")
    return 0


def cmd_run(args):
    from .framework import ExperimentConfig, run_experiment
    from .scenarios import load_all
    from .reports import aggregate_report

    _load_env()
    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = load_all()

    if args.scenario:
        if args.scenario not in scenarios:
            _io.write_line(f"Unknown scenario: {args.scenario}")
            _io.write_line(f"Available: {list(scenarios.keys())}")
            return 1
        scen = scenarios[args.scenario]
        cfg = ExperimentConfig(scenario=scen, output_dir=output_dir, use_real_llm=not args.noop, force=args.force)
        run_experiment(cfg)
    elif args.all:
        for sid, scen in scenarios.items():
            cfg = ExperimentConfig(scenario=scen, output_dir=output_dir, use_real_llm=not args.noop, force=args.force)
            run_experiment(cfg)
    else:
        _io.write_line("Specify --scenario <id> or --all")
        return 1

    agg = aggregate_report(output_dir, baseline_name=Path(output_dir).name)
    _io.write_line("")
    _io.write_line(f"Aggregate report: {agg}")
    return 0


def cmd_report(args):
    from .reports import aggregate_report
    out = aggregate_report(Path(args.output), baseline_name=Path(args.output).name)
    _io.write_line(f"wrote {out}")
    return 0


def cmd_diff(args):
    from .reports import diff_report
    out = diff_report(Path(args.baseline), Path(args.current))
    _io.write_line(f"wrote {out}")
    return 0


def cmd_assertions(args):
    from .assertions import list_assertions
    _io.write_line("Available assertions:")
    for name in list_assertions():
        _io.write_line(f"  - {name}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="R79-D baseline experiment runner")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="List available scenarios")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="Run scenarios")
    p_run.add_argument("--scenario", help="Scenario id to run")
    p_run.add_argument("--all", action="store_true", help="Run all scenarios")
    p_run.add_argument("--output", help="Output directory")
    p_run.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    p_run.add_argument("--noop", action="store_true", help="Use noop LLM (no real calls)")
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report", help="Generate aggregate report")
    p_report.add_argument("--output", required=True)
    p_report.set_defaults(func=cmd_report)

    p_diff = sub.add_parser("diff", help="Diff two output directories")
    p_diff.add_argument("--baseline", required=True)
    p_diff.add_argument("--current", required=True)
    p_diff.set_defaults(func=cmd_diff)

    p_assertions = sub.add_parser("assertions", help="List available assertion functions")
    p_assertions.set_defaults(func=cmd_assertions)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
