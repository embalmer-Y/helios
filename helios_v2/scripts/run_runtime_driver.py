"""Thin driver entry point for the Helios v2 runnable runtime.

This script constructs the runtime through the composition owner, attaches a JSON-line
observability sink, runs a bounded number of ticks, and writes the resulting event stream.

It is a thin entry point only. It contains no owner policy, no bridge logic, and no
assembly logic; all of that lives in `helios_v2.composition`. It runs a bounded, explicitly
specified number of ticks and then stops; it never starts an unbounded background loop.

LLM requirement: by default the assembled runtime is LLM-backed (the internal-thought owner
sources content from the `25` gateway). A real run therefore requires a statically-ready
bound LLM profile (the profile's api-key environment variable must be set), or startup fails
fast through the dependency gate. This driver reads `os.environ`; it does not auto-load
`.env`. For an offline run with no LLM, pass `--deterministic` to assemble the deterministic
thought path and omit the LLM critical dependency.

Examples:

    python helios_v2/scripts/run_runtime_driver.py --ticks 3
    python helios_v2/scripts/run_runtime_driver.py --ticks 5 --out logs/runtime_events.jsonl
    python helios_v2/scripts/run_runtime_driver.py --ticks 3 --deterministic
"""

from __future__ import annotations

import argparse
import sys
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
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Assemble the deterministic internal-thought path and omit the LLM critical "
        "dependency, for offline runs. Explicit opt-in; never a hidden fallback.",
    )
    parser.add_argument(
        "--channel-cli",
        action="store_true",
        help="Assemble the opt-in channel-bound runtime with a local CLI driver. Each tick "
        "reads one line from real stdin (a reader adapter) and writes Helios replies to "
        "stdout; observability events route to --out or stderr to avoid mixing. Local only, "
        "no network.",
    )
    return parser.parse_args(argv)


def _run(args: argparse.Namespace, stream: TextIO) -> int:
    if args.ticks <= 0:
        raise SystemExit("--ticks must be a positive integer")
    recorder = RuntimeObservabilityRecorder(
        sinks=(JsonLineStreamLogSink(stream=stream),),
        minimum_severity=args.min_severity,
    )
    if args.channel_cli:
        return _run_channel_cli(args, recorder)
    handle = assemble_runtime(recorder=recorder, deterministic_thought=args.deterministic)
    handle.startup()
    results = handle.run_ticks(args.ticks)
    return len(results)


def _run_channel_cli(args: argparse.Namespace, recorder: RuntimeObservabilityRecorder) -> int:
    """Owner: composition driver (channel-bound local run).

    Assemble the channel-bound runtime with a CLI driver whose output sink writes to real
    stdout, and feed one real stdin line into the driver per tick before ticking. This is the
    only place real stdio is touched, through an injected sink and an explicit read loop;
    owners never call `print`. Local only; no network.
    """

    def _cli_sink(rendered: str) -> None:
        sys.stdout.write(rendered + "\n")
        sys.stdout.flush()

    handle = assemble_runtime(
        recorder=recorder,
        deterministic_thought=args.deterministic,
        channel_cli=True,
        cli_output_sink=_cli_sink,
    )
    handle.startup()
    driver = handle.channel_subsystem._drivers["cli"]
    for _ in range(args.ticks):
        line = sys.stdin.readline()
        if line == "":
            break
        driver.submit_line(line.rstrip("\n"))
        handle.tick()
    return args.ticks


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
        # For a channel-cli local run, stdout carries the conversation, so observability
        # events go to stderr to avoid mixing the two streams.
        event_stream = sys.stderr if args.channel_cli else sys.stdout
        _run(args, event_stream)
        return 0
    out_path = Path(args.out)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as stream:
        _run(args, stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
