"""R83 Markdown report builder.

Writes a human-readable Markdown report from a frozen `R83Scores` +
`Verdict` instance. The report is the final acceptance artifact
for the R79 plan.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .long_runner import R83Scores
from .verdict import Verdict

AXIS_DESCRIPTIONS: dict[str, str] = {
    "A1_linguistic_naturalness": "LLM 输出自然度 / 像人度 (LLM-judge)",
    "A2_bio_responsiveness": "内部生化反应变化量 (algorithm)",
    "A3_memory_fidelity": "记忆存取 (R10 retrieval + R15 writeback)",
    "A4_agency_locking": "Agency + agency-locking (LLM-judge)",
    "A5_cross_tick_continuity": "跨 tick 演化连续性 (R82 drift)",
    "A6_stimulus_response_coherence": "刺激-反应一致性 (LLM-judge)",
}


@dataclass
class R83ReportBuilder:
    """Markdown report builder for R83Scores + Verdict."""

    scores: R83Scores
    verdict: Verdict
    run_id: str = "r83-run"
    notes: str = ""

    def write(self, output_path: Path) -> None:
        """Write the Markdown report to `output_path`.

        Args:
            output_path: path of the .md file to write.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        body = self._build_body()
        output_path.write_text(body, encoding="utf-8")

    def _build_body(self) -> str:
        lines: list[str] = []
        lines.append(f"# R83 Turing-Style Persona Evaluation Report: {self.run_id}")
        lines.append("")
        lines.append("## TL;DR")
        lines.append("")
        lines.append(f"- **Verdict**: `{self.verdict.label}`")
        lines.append(f"- **Mean score**: `{self.verdict.mean_score:.3f}`")
        lines.append(f"- **Min axis**: `{self.verdict.min_axis}` "
                     f"(`{self.verdict.min_score:.3f}`)")
        lines.append(f"- **Total ticks**: `{self.scores.total_ticks}`")
        lines.append(f"- **Elapsed**: `{self.scores.elapsed_seconds:.1f}s`")
        lines.append(f"- **Overall drift score**: "
                     f"`{self.scores.overall_drift_score:.4f}`")
        lines.append("")
        lines.append("## Axis scores")
        lines.append("")
        lines.append("| Axis | Description | Score |")
        lines.append("| --- | --- | ---: |")
        axis_to_value = {
            "A1_linguistic_naturalness": self.scores.a1_linguistic_naturalness,
            "A2_bio_responsiveness": self.scores.a2_bio_responsiveness,
            "A3_memory_fidelity": self.scores.a3_memory_fidelity,
            "A4_agency_locking": self.scores.a4_agency_locking,
            "A5_cross_tick_continuity": self.scores.a5_cross_tick_continuity,
            "A6_stimulus_response_coherence": self.scores.a6_stimulus_response_coherence,
        }
        for axis, value in axis_to_value.items():
            desc = AXIS_DESCRIPTIONS.get(axis, "")
            lines.append(f"| `{axis}` | {desc} | `{value:.3f}` |")
        lines.append("")
        lines.append("## Per-block detail (A2 algorithmic scores)")
        lines.append("")
        lines.append("| State | n_ticks | A2 | Judge A1 | Judge A4 | Judge A6 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for blk in self.scores.per_block:
            a1 = "—" if blk.judge_a1 is None else f"{blk.judge_a1:.3f}"
            a4 = "—" if blk.judge_a4 is None else f"{blk.judge_a4:.3f}"
            a6 = "—" if blk.judge_a6 is None else f"{blk.judge_a6:.3f}"
            lines.append(
                f"| `{blk.state_id}` | {blk.n_ticks} | "
                f"`{blk.a2_score:.3f}` | {a1} | {a4} | {a6} |"
            )
        lines.append("")
        lines.append("## Bio-chemistry deltas (first -> last per block)")
        lines.append("")
        lines.append("| State | Δ dopamine | Δ NE | Δ cortisol | Δ oxytocin | Δ valence | Δ arousal |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for blk in self.scores.per_block:
            h = blk.hormone_deltas
            f = blk.feeling_deltas
            lines.append(
                f"| `{blk.state_id}` | "
                f"`{h.get('dopamine', 0.0):+.3f}` | "
                f"`{h.get('norepinephrine', 0.0):+.3f}` | "
                f"`{h.get('cortisol', 0.0):+.3f}` | "
                f"`{h.get('oxytocin', 0.0):+.3f}` | "
                f"`{f.get('valence', 0.0):+.3f}` | "
                f"`{f.get('arousal', 0.0):+.3f}` |"
            )
        lines.append("")
        lines.append("## Recalibration targets")
        lines.append("")
        if self.verdict.recalibration_targets:
            for axis in self.verdict.recalibration_targets:
                lines.append(f"- `{axis}`")
        else:
            lines.append("- (none — all axes above the recalibration threshold)")
        lines.append("")
        if self.notes:
            lines.append("## Notes")
            lines.append("")
            lines.append(self.notes)
            lines.append("")
        return os.linesep.join(lines) + os.linesep
