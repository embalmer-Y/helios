"""Thin driver entry point for the Helios v2 runnable runtime.

This script constructs the runtime through the composition owner, attaches a JSON-line
observability sink, runs a bounded number of ticks, and writes the resulting event stream.

It is a thin entry point only. It contains no owner policy, no bridge logic, and no
assembly logic; all of that lives in `helios_v2.composition`. It runs a bounded, explicitly
specified number of ticks and then stops; it never starts an unbounded background loop.

Examples:

    python helios_v2/scripts/run_runtime_driver.py --ticks 3
    python helios_v2/scripts/run_runtime_driver.py --ticks 5 --out logs/runtime_events.jsonl
"""

from __future__ import annotations

import argparse
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import TextIO

from helios_v2.composition import assemble_runtime
from helios_v2.observability import JsonLineStreamLogSink, RuntimeObservabilityRecorder


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Helios v2 runtime for a bounded number of ticks.")
    parser.add_argument(
        "--ticks",
        type=int,
        default=3,
        help="Positive number of ticks to run before stopping (default: 3).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional path to write the JSON-line event stream. Defaults to stdout.",
    )
    parser.add_argument(
        "--min-severity",
        type=str,
        default="debug",
        choices=("debug", "info", "notice", "warning", "error", "critical"),
        help="Minimum severity dispatched to the sink (default: debug).",
    )
    return parser.parse_args(argv)


def _run(args: argparse.Namespace, stream: TextIO) -> int:
    if args.ticks <= 0:
        raise SystemExit("--ticks must be a positive integer")
    recorder = RuntimeObservabilityRecorder(
        sinks=(JsonLineStreamLogSink(stream=stream),),
        minimum_severity=args.min_severity,
    )
    handle = assemble_runtime(recorder=recorder)
    handle.startup()
    results = handle.run_ticks(args.ticks)
    return len(results)


def main(argv: list[str] | None = None) -> int:
    """Owner: composition driver.

    Purpose:
        Assemble a runtime, run a bounded number of ticks, and emit the JSON-line stream.

    Inputs:
        `argv` - optional argument vector; defaults to `sys.argv[1:]`.

    Returns:
        Process exit code (0 on success).
    """

    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.out is None:
        _run(args, sys.stdout)
        return 0
    out_path = Path(args.out)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as stream:
        _run(args, stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
