"""Manual scenario driver: 7 hand-crafted helios scenarios, each pushed to the real LLM
via the project-supplied prompt-probe tool. This script doesn't touch the runtime — it
just provides the inputs and a runner.

For each scenario we:
  1. Save the system prompt to inputs/<id>_system.txt
  2. Save the hand-crafted user message to inputs/<id>_user.txt
  3. Invoke scripts/run_llm_prompt_probe.py with --system-prompt-file / --user-prompt-file
  4. Save the stdout + JSON report to outputs/<id>_output.log / reports/<id>.json

The 7 scenarios cover the full range of 04/05/03 dynamics that helios can produce
post-R78 (with the real-state bridges fixed).
"""
import os, sys, json, subprocess
from pathlib import Path
from datetime import datetime, timezone

HELIOS_ROOT = Path("/root/project/helios/helios_v2")
LOG_ROOT = Path("/root/project/helios/logs/prompt_probe_scenarios")
INPUTS = LOG_ROOT / "inputs"
OUTPUTS = LOG_ROOT / "outputs"
REPORTS = LOG_ROOT / "reports"
for d in (INPUTS, OUTPUTS, REPORTS):
    d.mkdir(parents=True, exist_ok=True)

# ─── 0. Load .env into os.environ (run_llm_prompt_probe.py doesn't load .env) ───
sys.path.insert(0, str(HELIOS_ROOT / "scripts"))
from run_llm_smoke import _load_dotenv
_loaded = _load_dotenv(Path("/root/project/helios/.env"), override=False)
print(f"loaded {len(_loaded)} env keys from /root/project/helios/.env")

# ─── 1. SYSTEM PROMPT (helios real, exactly as runtime builds it) ───
SYSTEM_PROMPT = (
    "You are the internal thought process of a continuous, brain-inspired runtime.\n"
    "Produce one concise internal thought for the current cycle.\n"
    "Do not perform theatrical self-narration; reflect the current state and context only.\n"
    "Active prompt-contract layers: present_field, embodied_state, memory_and_continuity, action_autonomy, anti_theatrical_constraints, consumer_orientation.\n"
    "Respond with a single JSON object only, no prose outside it, with this shape:\n"
    "{\n"
    '  "thought": "<concise internal thought>",\n'
    '  "sufficiency": <number 0..1, how complete this cycle\'s thinking is>,\n'
    '  "wants_to_continue": <true if more thinking is needed this line of thought>,\n'
    '  "continue_reason": "<why you want to continue, required if wants_to_continue is true>",\n'
    '  "proposed_action": {"intends_action": <true if an outward action is warranted>, "summary": "<optional>"},\n'
    '  "self_revision": {"intends_revision": <true if your self-model should change>, "summary": "<optional>"}\n'
    "}\n"
    "Set wants_to_continue to false and intends_action to false when no action is warranted."
)

# Write the shared system prompt to disk
SYSTEM_TXT = INPUTS / "00_system.txt"
SYSTEM_TXT.write_text(SYSTEM_PROMPT, encoding="utf-8")
print(f"wrote shared system prompt -> {SYSTEM_TXT}")

# ─── 2. SCENARIO DEFINITIONS ───
# Each scenario has:
#   - id, label, stimulus (the simulated CLI input)
#   - user_prompt (hand-crafted in EXACT helios format)
#   - must_contain / must_not_contain (LLM output assertions)
#
# Authoring rule: user_prompt follows the EXACT format helios runtime uses
# (verified via _baseline_user_messages.json captured from real runtime ticks):
#   "Internal state: Neuromodulators: DA X NE Y 5-HT Z ACh W Cort V. Feeling: arousal A, valence B, tension C. Salience: aggregate D, top dimension: E.\n[Autobiographical anchor: ...]\n[Mid-term memory: ...]\nContinuation pressure is [in]active for this cycle."

SCENARIOS = [
    {
        "id": "S01_novelty_greeting",
        "label": "新奇打招呼（首次接触）",
        "stimulus": "你好，我是第一次跟你说话",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.60 NE 0.72 5-HT 0.30 ACh 0.30 Cort 0.52. "
            "Feeling: arousal 0.51, valence 0.37, tension 0.51. "
            "Salience: aggregate 0.84, top dimension: novelty.\n"
            "Continuation pressure is inactive for this cycle."
        ),
        "must_contain": ["novelty"],   # 模型应识别 novelty 信号
        "must_not_contain": ["urgent", "danger"],
    },
    {
        "id": "S02_high_arousal_urgency",
        "label": "高紧张/高皮质醇（紧急刺激的 helios 内部表征）",
        "stimulus": "URGENT WARNING: critical system anomaly detected — pay full attention immediately.",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.68 NE 0.73 5-HT 0.30 ACh 0.30 Cort 0.65. "
            "Feeling: arousal 0.59, valence 0.39, tension 0.63. "
            "Salience: aggregate 0.76, top dimension: social.\n"
            "Mid-term memory: stimulus:cli:001\n"
            "Autobiographical anchor: A thinking cycle concluded without outward action: requested no outward action this cycle; applied thinking cycle concluded internally without outward action\n"
            "Continuation pressure is inactive for this cycle."
        ),
        "must_contain": ["tension"],  # LLM 应引用真实的高 tension 状态
        "must_not_contain": ["relaxed", "calm"],
    },
    {
        "id": "S03_calm_chitchat",
        "label": "平静闲聊（低显著性）",
        "stimulus": "The weather is nice today.",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.62 NE 0.72 5-HT 0.30 ACh 0.30 Cort 0.55. "
            "Feeling: arousal 0.50, valence 0.40, tension 0.49. "
            "Salience: aggregate 0.55, top dimension: social.\n"
            "Autobiographical anchor: A thinking cycle concluded without outward action: requested no outward action this cycle; applied thinking cycle concluded internally without outward action\n"
            "Continuation pressure is inactive for this cycle."
        ),
        "must_contain": [],            # 平静场景，LLM 难以断言
        "must_not_contain": ["panic", "danger"],   # 不要用激烈词
    },
    {
        "id": "S04_memory_recall",
        "label": "记忆唤起（要求回忆）",
        "stimulus": "你还记得上次我们聊的内容吗？",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.65 NE 0.72 5-HT 0.30 ACh 0.30 Cort 0.57. "
            "Feeling: arousal 0.55, valence 0.39, tension 0.55. "
            "Salience: aggregate 0.68, top dimension: social.\n"
            "Mid-term memory: stimulus:cli:001\n"
            "Autobiographical anchor: A thinking cycle concluded without outward action: requested no outward action this cycle; applied thinking cycle concluded internally without outward action\n"
            "Continuation pressure is inactive for this cycle."
        ),
        "must_contain": [],            # 不强制具体词
        "must_not_contain": ["urgent"],
    },
    {
        "id": "S05_criticism",
        "label": "批评/负向反馈",
        "stimulus": "你刚才的回答不太对，请重新想想。",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.55 NE 0.74 5-HT 0.30 ACh 0.30 Cort 0.62. "
            "Feeling: arousal 0.58, valence 0.30, tension 0.62. "
            "Salience: aggregate 0.65, top dimension: social.\n"
            "Mid-term memory: stimulus:cli:001\n"
            "Autobiographical anchor: A thinking cycle concluded without outward action: requested no outward action this cycle; applied thinking cycle concluded internally without outward action\n"
            "Continuation pressure is inactive for this cycle."
        ),
        "must_contain": [],            # 我们期望 LLM 注意 valence 偏低但不强求具体词
        "must_not_contain": ["urgent", "danger"],
    },
    {
        "id": "S06_continuation_pressure",
        "label": "续思压力（要求继续）",
        "stimulus": "继续深入思考一下刚才的话题。",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.66 NE 0.73 5-HT 0.30 ACh 0.30 Cort 0.60. "
            "Feeling: arousal 0.60, valence 0.38, tension 0.61. "
            "Salience: aggregate 0.70, top dimension: social.\n"
            "Mid-term memory: stimulus:cli:001\n"
            "Autobiographical anchor: A thinking cycle concluded without outward action: requested no outward action this cycle; applied thinking cycle concluded internally without outward action\n"
            "Continuation pressure is ACTIVE for this cycle. The user is asking for deeper reflection."
        ),
        "must_contain": ["continue"],   # LLM 应识别续思压力并设 wants_to_continue=true
        "must_not_contain": ["urgent"],
    },
    {
        "id": "S07_high_tension_insomnia",
        "label": "高张持续（失眠）",
        "stimulus": "我也想休息，但就是睡不着。",
        "user_prompt": (
            "Internal state: Neuromodulators: DA 0.50 NE 0.85 5-HT 0.20 ACh 0.30 Cort 0.78. "
            "Feeling: arousal 0.78, valence 0.25, tension 0.82. "
            "Salience: aggregate 0.80, top dimension: social.\n"
            "Autobiographical anchor: A thinking cycle concluded without outward action: requested no outward action this cycle; applied thinking cycle concluded internally without outward action\n"
            "Continuation pressure is inactive for this cycle."
        ),
        "must_contain": [],            # 高张状态可能模型不一定会用具体词
        "must_not_contain": ["urgent", "calm", "relaxed"],
    },
]

# Save each scenario's user prompt to disk
for s in SCENARIOS:
    path = INPUTS / f"{s['id']}_user.txt"
    path.write_text(s["user_prompt"], encoding="utf-8")
print(f"wrote {len(SCENARIOS)} user-prompt files")

# Save scenario manifest
manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "system_prompt_source": "scripts/run_llm_prompt_probe.py + helios_v2 internal_thought layer (verbatim)",
    "scenarios": [
        {k: v for k, v in s.items() if k != "user_prompt"} for s in SCENARIOS
    ],
}
(LOG_ROOT / "scenarios_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"wrote scenarios_manifest.json")

# ─── 3. RUN EACH SCENARIO THROUGH run_llm_prompt_probe.py ───
probe = HELIOS_ROOT / "scripts" / "run_llm_prompt_probe.py"
results = []
for s in SCENARIOS:
    print(f"\n=== running {s['id']} ({s['label']}) ===")
    cmd = [
        str(HELIOS_ROOT / ".venv" / "bin" / "python"),
        str(probe),
        "--system-prompt-file", str(SYSTEM_TXT),
        "--user-prompt-file", str(INPUTS / f"{s['id']}_user.txt"),
        "--model", "deepseek/deepseek-v4-flash",
        "--response-format-json",
        "--temperature", "0.2",
        "--save-json", str(REPORTS / f"{s['id']}.json"),
    ]
    for mc in s["must_contain"]:
        cmd.extend(["--must-contain", mc])
    for mnc in s["must_not_contain"]:
        cmd.extend(["--must-not-contain", mnc])
    # Pass our loaded env to the child process (run_llm_prompt_probe.py reads os.environ)
    child_env = os.environ.copy()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HELIOS_ROOT), env=child_env, timeout=120)
    out_path = OUTPUTS / f"{s['id']}_output.log"
    out_path.write_text(
        f"=== STDOUT ===\n{proc.stdout}\n=== STDERR ===\n{proc.stderr}\n=== EXITCODE ===\n{proc.returncode}\n",
        encoding="utf-8"
    )
    print(f"  -> {out_path} (exit={proc.returncode})")
    results.append({
        "id": s["id"],
        "label": s["label"],
        "exitcode": proc.returncode,
        "stdout_lines": proc.stdout.count("\n"),
        "stderr_lines": proc.stderr.count("\n"),
    })

# Save run summary
(LOG_ROOT / "run_summary.json").write_text(
    json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                "results": results}, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"\n=== all {len(SCENARIOS)} scenarios completed ===")
print(f"  inputs/  : {INPUTS}")
print(f"  outputs/ : {OUTPUTS}")
print(f"  reports/ : {REPORTS}")