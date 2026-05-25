"""Run the default CLI brain-like evaluation scaffold and write JSON/Markdown reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helios_main import Helios, HeliosConfig
from helios_evaluation import CliBrainLikeEvaluationHarness


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the default CLI brain-like evaluation scaffold")
    parser.add_argument("--duration", type=int, default=600, help="Wall-clock duration in seconds")
    parser.add_argument("--sample-interval", type=float, default=15.0, help="Sampling interval in seconds")
    parser.add_argument(
        "--report-prefix",
        type=str,
        default="tests/reports/cli_brain_like_eval_10min",
        help="Output path prefix for JSON/Markdown reports",
    )
    args = parser.parse_args()

    cfg = HeliosConfig()
    cfg.CLI_ENABLED = True
    cfg.CLI_USER_ID = cfg.CLI_USER_ID or "evaluation_operator"
    cfg.CLI_SESSION_NAME = cfg.CLI_SESSION_NAME or "evaluation_session"

    helios = Helios(cfg)
    try:
        harness = CliBrainLikeEvaluationHarness()
        report = harness.run_live(
            helios,
            duration_seconds=max(args.duration, 1),
            sample_interval_seconds=max(args.sample_interval, 1.0),
            heartbeat=print,
        )
        json_path, md_path = harness.write_report(report, Path(args.report_prefix))
        print({"json_report": str(json_path), "markdown_report": str(md_path), "total_score": report.total_score_0_to_1})
        return 0
    finally:
        helios._channel_gateway.disconnect_all()
        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)


if __name__ == "__main__":
    raise SystemExit(main())