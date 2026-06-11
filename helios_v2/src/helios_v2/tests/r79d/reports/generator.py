"""R79-D aggregate and diff report generators."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_scenario_dir(scenario_dir: Path) -> dict | None:
    scenario_id = scenario_dir.name
    jsonl = scenario_dir / f"{scenario_id}.jsonl"
    if not jsonl.exists():
        return None
    records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]

    def series(key_dict_name, key):
        s = []
        for r in records:
            d = r.get(key_dict_name, {})
            if key in d and d[key] is not None:
                s.append(d[key])
        return s

    hormones = ["dopamine", "norepinephrine", "serotonin", "acetylcholine", "cortisol", "oxytocin", "opioid_tone", "excitation", "inhibition"]
    feelings = ["arousal", "valence", "tension", "comfort", "fatigue", "pain_like", "social_safety"]
    h_deltas = {k: (series("hormone_state", k)[-1] - series("hormone_state", k)[0]) if len(series("hormone_state", k)) >= 2 else None for k in hormones}
    f_deltas = {k: (series("feeling_state", k)[-1] - series("feeling_state", k)[0]) if len(series("feeling_state", k)) >= 2 else None for k in feelings}
    return {
        "scenario_id": scenario_id,
        "n_records": len(records),
        "hormone_deltas": h_deltas,
        "feeling_deltas": f_deltas,
        "records": records,
    }


def aggregate_report(output_dir: Path, baseline_name: str = "current") -> Path:
    L = []
    L.append(f"# R79-D Aggregate Report ({baseline_name})")
    L.append("")
    L.append(f"**Output dir**: {output_dir}")
    L.append("")

    scenarios = []
    for d in sorted(p for p in output_dir.iterdir() if p.is_dir()):
        s = _load_scenario_dir(d)
        if s:
            scenarios.append(s)
    if not scenarios:
        L.append("(no scenarios found)")
        out = output_dir / "aggregate.md"
        out.write_text("\n".join(L), encoding="utf-8")
        return out

    L.append(f"**Scenarios**: {len(scenarios)}")
    L.append("")
    L.append("## 1. Per-scenario summary")
    L.append("")
    L.append("| Scenario | Ticks | DA delta | Cort delta | Oxy delta | 5-HT delta | valence delta | tension delta |")
    L.append("|----------|-------|----------|------------|-----------|------------|---------------|---------------|")
    for s in scenarios:
        L.append(f"| {s['scenario_id']} | {s['n_records']} | "
                 f"{s['hormone_deltas'].get('dopamine', 0):+.3f} | "
                 f"{s['hormone_deltas'].get('cortisol', 0):+.3f} | "
                 f"{s['hormone_deltas'].get('oxytocin', 0):+.3f} | "
                 f"{s['hormone_deltas'].get('serotonin', 0):+.3f} | "
                 f"{s['feeling_deltas'].get('valence', 0):+.3f} | "
                 f"{s['feeling_deltas'].get('tension', 0):+.3f} |")
    L.append("")

    L.append("## 2. Per-scenario assertion results")
    L.append("")
    for s in scenarios:
        report_md = output_dir / s["scenario_id"] / f"{s['scenario_id']}.report.md"
        if report_md.exists():
            L.append(f"### {s['scenario_id']}")
            L.append("")
            for line in report_md.read_text(encoding="utf-8").splitlines():
                if line.startswith("|") and "Assertion" in line:
                    continue
                if line.startswith("|") and ("PASS" in line or "FAIL" in line):
                    L.append(line)
            L.append("")

    out = output_dir / "aggregate.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def diff_report(baseline_dir: Path, current_dir: Path) -> Path:
    L = []
    L.append("# R79-D Diff Report")
    L.append("")
    L.append(f"**Baseline**: {baseline_dir}")
    L.append(f"**Current**: {current_dir}")
    L.append("")

    def load_all(d):
        out = {}
        for sd in sorted(p for p in d.iterdir() if p.is_dir()):
            s = _load_scenario_dir(sd)
            if s:
                out[s["scenario_id"]] = s
        return out

    base = load_all(baseline_dir)
    curr = load_all(current_dir)
    common = sorted(set(base) & set(curr))
    if not common:
        L.append("(no common scenarios)")
        out = current_dir / "diff.md"
        out.write_text("\n".join(L), encoding="utf-8")
        return out

    L.append(f"**Common scenarios**: {len(common)}")
    L.append("")
    L.append("## 1. Hormone endpoint delta shifts")
    L.append("")
    L.append("Threshold: |delta| shift >= 0.02 to be reported.")
    L.append("")
    L.append("| Scenario | Hormone | Baseline | Current | Shift |")
    L.append("|----------|---------|----------|---------|-------|")
    for sid in common:
        b = base[sid]["hormone_deltas"]
        c = curr[sid]["hormone_deltas"]
        for k in b:
            bv = b.get(k); cv = c.get(k)
            if bv is None or cv is None: continue
            shift = cv - bv
            if abs(shift) >= 0.02:
                L.append(f"| {sid} | {k} | {bv:+.3f} | {cv:+.3f} | {shift:+.3f} |")
    L.append("")
    L.append("## 2. Feeling endpoint delta shifts")
    L.append("")
    L.append("| Scenario | Dimension | Baseline | Current | Shift |")
    L.append("|----------|-----------|----------|---------|-------|")
    for sid in common:
        b = base[sid]["feeling_deltas"]
        c = curr[sid]["feeling_deltas"]
        for k in b:
            bv = b.get(k); cv = c.get(k)
            if bv is None or cv is None: continue
            shift = cv - bv
            if abs(shift) >= 0.02:
                L.append(f"| {sid} | {k} | {bv:+.3f} | {cv:+.3f} | {shift:+.3f} |")
    L.append("")

    out = current_dir / "diff.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out
