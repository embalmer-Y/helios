"""R79 T7: opt-in real-LLM assembly-level smoke (not part of the network-free suite).

Assembles the DEFAULT runtime (embodied_prompt_mode="v3" + the production OpenAI-compatible
gateway built from the config's thought profile) against the real LLM configured in `.env`,
runs a few ticks, and reports whether the v3 owner-grounded embodied prompt plus the `11`
structured-thought parsing robustness let a reasoning model's output close end to end as a
`completed` thought (rather than degrading to `insufficient_generation` because of a `<think>`
block / code fence).

Run:
    python helios_v2/scripts/r79_t7_smoke.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        print(f"[r79-t7] .env not found at {env_path}; aborting", flush=True)
        sys.exit(2)
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _ensure_src_on_path() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(src))


def main() -> int:
    _load_env()
    _ensure_src_on_path()

    from helios_v2.composition.runtime_assembly import assemble_runtime

    model = os.environ.get("HELIOS_LLM_MODEL", "<default>")
    print(f"[r79-t7] assembling DEFAULT runtime (v3) against real model={model}", flush=True)

    handle = assemble_runtime()  # default embodied_prompt_mode="v3" + production gateway
    handle.startup()

    max_ticks = 4
    fired_completed = False
    for tick_index in range(1, max_ticks + 1):
        result = handle.tick()
        prompt_stage = result.stage_results.get("embodied_subjective_prompt_and_action_autonomy")
        thought_stage = result.stage_results.get("internal_thought_loop_owner")

        v3_layers: set[str] = set()
        if prompt_stage is not None and getattr(prompt_stage, "contracts", None):
            v3_layers = {
                layer.layer_name
                for contract in prompt_stage.contracts
                for layer in contract.layers
            }
        is_v3 = {"identity_grounding", "attention_breakdown", "ready_channels"} <= v3_layers

        status = getattr(getattr(thought_stage, "result", None), "execution_status", None)
        activated = getattr(thought_stage, "activated", None)
        thought = getattr(getattr(thought_stage, "result", None), "thought", None)
        llm_used = getattr(thought, "llm_used", None) if thought is not None else None
        content = (thought.content[:160] if thought is not None and thought.content else "")

        print(
            f"[r79-t7] tick {tick_index}: prompt_is_v3={is_v3} "
            f"thought_activated={activated} execution_status={status} llm_used={llm_used}",
            flush=True,
        )
        if content:
            print(f"           thought: {content}", flush=True)

        if activated and status == "completed":
            fired_completed = True
            print(
                "[r79-t7] PASS: a fired tick parsed the real reasoning-model output into a "
                "completed v3 thought (think/fence robustness worked end to end).",
                flush=True,
            )
            break

    if not fired_completed:
        print(
            "[r79-t7] No fired+completed tick within the budget. If every tick was no-fire, "
            "inject a salient external_signal_source; if a fired tick was insufficient_generation, "
            "inspect the completion (parsing robustness regression).",
            flush=True,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
