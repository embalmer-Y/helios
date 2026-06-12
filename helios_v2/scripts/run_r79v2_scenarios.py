"""R79 v2 probe driver — first-person natural mind schema.

Reads the 7 scenario user messages from r79_v2/inputs/ and the new system prompt,
runs the helios-v2 run_llm_prompt_probe.py against each one with --response-format-json
and --save-json, and stores logs/reports under r79_v2/.

This is a pure prompt-level experiment. It does NOT modify the helios runtime.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path("/root/project/helios")
SCRIPT_DIR = ROOT / "helios_v2" / "scripts"
PROBE = SCRIPT_DIR / "run_llm_prompt_probe.py"
ENV_FILE = ROOT / ".env"

V2_ROOT = ROOT / "logs" / "prompt_probe_scenarios" / "r79_v2"
INPUTS = V2_ROOT / "inputs"
OUTPUTS = V2_ROOT / "outputs"
REPORTS = V2_ROOT / "reports"
for d in (OUTPUTS, REPORTS):
    d.mkdir(parents=True, exist_ok=True)

# Load .env into os.environ (probe does not auto-load)
import importlib.util
spec = importlib.util.spec_from_file_location("run_llm_smoke", SCRIPT_DIR / "run_llm_smoke.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore
mod._load_dotenv(ENV_FILE, override=False)

# Pull scenario list
manifest = json.loads((V2_ROOT / "scenarios_manifest_v2.json").read_text(encoding="utf-8"))
scenarios = manifest["scenarios"]
system_prompt = (INPUTS / "00_system_v2.txt").read_text(encoding="utf-8")

print(f"=== R79 v2 probe — first-person natural mind ===")
print(f"system: inputs/00_system_v2.txt ({len(system_prompt)} chars)")
print(f"scenarios: {len(scenarios)}")
print(f"model: {os.environ.get('HELIOS_LLM_MODEL', 'unset')}")
print(f"base_url: {os.environ.get('OPENAI_BASE_URL', 'unset')}")
print()

results = []
for s in scenarios:
    sid = s["id"]
    user_path = INPUTS / f"{sid}_user_v2.txt"
    out_log = OUTPUTS / f"{sid}_output.log"
    rep_path = REPORTS / f"{sid}.json"

    if not user_path.exists():
        print(f"!! {sid} user file missing, skip")
        continue

    cmd = [
        "helios_v2/.venv/bin/python",
        str(PROBE.relative_to(ROOT)),
        "--system-prompt", system_prompt,
        "--user-prompt-file", str(user_path.relative_to(ROOT)),
        "--response-format-json",
        "--save-json", str(rep_path.relative_to(ROOT)),
        "--temperature", "0.7",
        "--max-tokens", "500",
        "--timeout", "60",
    ]
    print(f"=== running {sid} ({s['label']}) ===")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy(),
        )
        elapsed = time.time() - t0
        out_log.write_text(
            f"=== STDOUT ===\n{proc.stdout}\n\n=== STDERR ===\n{proc.stderr}\n\n=== EXITCODE ===\n{proc.returncode}\n",
            encoding="utf-8",
        )
        passed_marker = "[PASS]" if "[PASS]" in proc.stdout else "[FAIL]" if "[FAIL]" in proc.stdout else "??"
        print(f"  -> {out_log.name} (exit={proc.returncode}, {passed_marker}, {elapsed:.1f}s)")
        results.append({"id": sid, "exit": proc.returncode, "passed": passed_marker, "elapsed": elapsed})
    except subprocess.TimeoutExpired:
        out_log.write_text(f"=== TIMEOUT after 120s ===\n", encoding="utf-8")
        print(f"  -> {out_log.name} (TIMEOUT)")
        results.append({"id": sid, "exit": -1, "passed": "TIMEOUT", "elapsed": 120.0})

print()
print("=== summary ===")
for r in results:
    print(f"  {r['id']:35s} | exit={r['exit']:3d} | {r['passed']:8s} | {r['elapsed']:.1f}s")

# Save run summary
(V2_ROOT / "run_summary_v2.json").write_text(
    json.dumps({"results": results, "scenarios": len(scenarios), "model": os.environ.get("HELIOS_LLM_MODEL")}, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
