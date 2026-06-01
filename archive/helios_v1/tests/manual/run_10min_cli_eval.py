"""Run the default CLI brain-like evaluation scaffold and write JSON/Markdown reports."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helios_main import Helios, HeliosConfig
from helios_evaluation import (
    CliBrainLikeEvaluationHarness,
    EvaluationReport,
    EvaluationScenario,
    build_default_20min_mixed_cli_scenario,
    build_r09_focused_6min_cli_scenario,
)


def _build_scenario(name: str) -> EvaluationScenario:
    normalized = str(name or "standard_20min").strip().lower()
    if normalized == "r09_focus_6min":
        return build_r09_focused_6min_cli_scenario()
    return build_default_20min_mixed_cli_scenario()


def _build_base_config() -> HeliosConfig:
    cfg = HeliosConfig()
    cfg.CLI_ENABLED = True
    cfg.CLI_USER_ID = cfg.CLI_USER_ID or "evaluation_operator"
    cfg.CLI_SESSION_NAME = cfg.CLI_SESSION_NAME or "evaluation_session"
    return cfg


def _cleanup_helios(helios: Helios) -> None:
    gateway = getattr(helios, "_channel_gateway", None)
    if gateway is not None and hasattr(gateway, "disconnect_all"):
        gateway.disconnect_all()
    for handler in list(helios.log.handlers):
        handler.close()
        helios.log.removeHandler(handler)


def _labelled_report_prefix(base_prefix: Path, label: str) -> Path:
    return base_prefix.parent / f"{base_prefix.name}_{label}"


def _run_live_report(
    *,
    cfg: HeliosConfig,
    scenario: EvaluationScenario,
    duration_seconds: int,
    sample_interval_seconds: float,
    report_prefix: Path,
    heartbeat: Callable[[str], None],
) -> tuple[EvaluationReport, Path, Path]:
    helios = Helios(cfg)
    try:
        harness = CliBrainLikeEvaluationHarness(scenario=scenario)
        report = harness.run_live(
            helios,
            duration_seconds=duration_seconds,
            sample_interval_seconds=sample_interval_seconds,
            heartbeat=heartbeat,
        )
        json_path, md_path = harness.write_report(report, report_prefix)
        return report, json_path, md_path
    finally:
        _cleanup_helios(helios)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the default CLI brain-like evaluation scaffold")
    parser.add_argument("--duration", type=int, default=1200, help="Wall-clock duration in seconds")
    parser.add_argument("--sample-interval", type=float, default=15.0, help="Sampling interval in seconds")
    parser.add_argument(
        "--scenario",
        type=str,
        default="standard_20min",
        help="Scenario preset: standard_20min or r09_focus_6min",
    )
    parser.add_argument(
        "--report-prefix",
        type=str,
        default="tests/reports/cli_brain_like_eval_20min",
        help="Output path prefix for JSON/Markdown reports",
    )
    parser.add_argument("--compare-left", type=str, default="", help="Existing JSON report path for the left comparison side")
    parser.add_argument("--compare-right", type=str, default="", help="Existing JSON report path for the right comparison side")
    parser.add_argument("--compare-left-label", type=str, default="sec_normal", help="Label for the left comparison side")
    parser.add_argument("--compare-right-label", type=str, default="sec_fallback", help="Label for the right comparison side")
    parser.add_argument(
        "--fresh-sec-compare",
        action="store_true",
        help="Run two fresh live evaluations sequentially: current SEC config vs forced SEC fallback, then emit paired reports plus comparison artifact.",
    )
    parser.add_argument("--fresh-left-label", type=str, default="sec_normal_live", help="Label for the fresh left run")
    parser.add_argument("--fresh-right-label", type=str, default="sec_fallback_live", help="Label for the fresh right run")
    args = parser.parse_args()
    scenario = _build_scenario(args.scenario)

    if args.compare_left and args.compare_right:
        harness = CliBrainLikeEvaluationHarness()
        left_report = harness.load_report(Path(args.compare_left))
        right_report = harness.load_report(Path(args.compare_right))
        comparison = harness.compare_reports(
            left_report,
            right_report,
            left_label=args.compare_left_label,
            right_label=args.compare_right_label,
        )
        json_path, md_path = harness.write_comparison_report(comparison, Path(args.report_prefix))
        print(
            {
                "comparison_json": str(json_path),
                "comparison_markdown": str(md_path),
                "total_score_delta": comparison.total_score_delta,
                "sec_fallback_delta": comparison.sec_fallback_delta,
            }
        )
        return 0

    if args.fresh_sec_compare:
        harness = CliBrainLikeEvaluationHarness()
        base_cfg = _build_base_config()
        duration_seconds = max(args.duration, 1)
        sample_interval_seconds = max(args.sample_interval, 1.0)
        base_prefix = Path(args.report_prefix)
        left_prefix = _labelled_report_prefix(base_prefix, args.fresh_left_label)
        right_prefix = _labelled_report_prefix(base_prefix, args.fresh_right_label)

        left_cfg = copy.deepcopy(base_cfg)
        left_cfg.CLI_SESSION_NAME = f"{base_cfg.CLI_SESSION_NAME}_{args.fresh_left_label}"
        left_report, left_json_path, left_md_path = _run_live_report(
            cfg=left_cfg,
            scenario=scenario,
            duration_seconds=duration_seconds,
            sample_interval_seconds=sample_interval_seconds,
            report_prefix=left_prefix,
            heartbeat=print,
        )

        right_cfg = copy.deepcopy(base_cfg)
        right_cfg.CLI_SESSION_NAME = f"{base_cfg.CLI_SESSION_NAME}_{args.fresh_right_label}"
        right_cfg.LLM_API_KEY = ""
        right_report, right_json_path, right_md_path = _run_live_report(
            cfg=right_cfg,
            scenario=scenario,
            duration_seconds=duration_seconds,
            sample_interval_seconds=sample_interval_seconds,
            report_prefix=right_prefix,
            heartbeat=print,
        )

        comparison = harness.compare_reports(
            left_report,
            right_report,
            left_label=args.fresh_left_label,
            right_label=args.fresh_right_label,
        )
        comparison_json_path, comparison_md_path = harness.write_comparison_report(comparison, Path(args.report_prefix))
        print(
            {
                "left_json_report": str(left_json_path),
                "left_markdown_report": str(left_md_path),
                "right_json_report": str(right_json_path),
                "right_markdown_report": str(right_md_path),
                "comparison_json": str(comparison_json_path),
                "comparison_markdown": str(comparison_md_path),
                "left_total_score": left_report.total_score_0_to_1,
                "right_total_score": right_report.total_score_0_to_1,
                "total_score_delta": comparison.total_score_delta,
                "sec_fallback_delta": comparison.sec_fallback_delta,
            }
        )
        return 0

    cfg = _build_base_config()
    report, json_path, md_path = _run_live_report(
        cfg=cfg,
        scenario=scenario,
        duration_seconds=max(args.duration if args.duration != 1200 or args.scenario == "standard_20min" else scenario.duration_seconds, 1),
        sample_interval_seconds=max(args.sample_interval if args.sample_interval != 15.0 or args.scenario == "standard_20min" else scenario.sample_interval_seconds, 1.0),
        report_prefix=Path(args.report_prefix),
        heartbeat=print,
    )
    print({"json_report": str(json_path), "markdown_report": str(md_path), "total_score": report.total_score_0_to_1})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())