"""Render all R91 probe reports under logs/prerun/r91_probes/ into a single human-readable report
for human evaluation. Reads each saved JSON report and emits the user prompt + raw model output for
inspection. Read-only; no LLM calls."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    in_dir = root / "logs" / "prerun" / "r91_probes"
    out_path = root / "logs" / "prerun" / "r91_probes" / "_RESULTS_OVERVIEW.md"
    if not in_dir.exists():
        print(f"missing dir: {in_dir}", file=sys.stderr)
        return 2

    chunks: list[str] = []
    chunks.append("# R91 prompt-probe results overview\n")
    chunks.append("Read-only render of every probe under `logs/prerun/r91_probes/` for human review.\n")
    for path in sorted(in_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        case = data["prompt_case"]
        for result in data["results"]:
            target = result["target"]
            exp = result["expectations"]
            status = "PASS" if exp["passed"] else "FAIL"
            chunks.append(f"## {path.stem} — {status} ({target['name']}, {result['elapsed_seconds']}s, finish={result['finish_reason']})\n")
            chunks.append("**must_contain**: " + json.dumps(case["must_contain"], ensure_ascii=False))
            chunks.append("**must_not_contain**: " + json.dumps(case["must_not_contain"], ensure_ascii=False))
            if exp["missing_must_contain"]:
                chunks.append("MISSING: " + json.dumps(exp["missing_must_contain"], ensure_ascii=False))
            if exp["matched_must_not_contain"]:
                chunks.append("FORBIDDEN HIT: " + json.dumps(exp["matched_must_not_contain"], ensure_ascii=False))
            chunks.append("\n### user prompt\n```\n" + case["user_prompt"] + "\n```\n")
            chunks.append("### model output (full)\n```\n" + result["output_text"] + "\n```\n")
    out_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
