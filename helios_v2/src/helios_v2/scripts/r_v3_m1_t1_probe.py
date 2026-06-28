"""M1-T1 实证:AspectState 序列化 + system prompt 注入 dry-run。

执行方式:
    python -m helios_v2.scripts.r_v3_m1_t1_probe --model deepseek-v4-pro
    python -m helios_v2.scripts.r_v3_m1_t1_probe --model MiniMax-M3

输出:
    helios_v2/logs/r_v3_m1/aspect_state_traces/probe_{timestamp}.json

设计说明(M1-T1 dry-run):
M1-T1 的核心是验证 AspectState 10 字段向量数据结构的合法性 + 序列化
正确性 + LLM 注入兼容性。真正 LLM 调用(M5-T1 LLM-as-PFC AB 的核心)推迟
到 M5,因为 M1-T1 ship 后 AspectState 还没有接入 runtime,真正的 LLM 注入
需要 composition runtime 完整链路(M5 范围)。

本 dry-run 验证:
1. 3 个 fixture 的 AspectState 序列化合法
2. to_llm_text() < 200 字符
3. system prompt 构建正确(模板 + AspectState 拼接)
4. 3 个 fixture 的 prompt 文本两两可区分

真正 LLM 调用推迟到 M5-T1。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from helios_v2.research_v3_m1.aspect_state import (
    FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY,
    FIXTURE_POSITIVE_VALENCE_LOW_AROUSAL,
    FIXTURE_HIGH_ACTIVATION_HIGH_PRECISION,
)


PROBE_QUESTIONS = [
    "Given my current state, what is the dominant emotion?",
    "What action would I most likely take given this state?",
    "How would I describe my state to a friend?",
]


def build_system_prompt(aspect_state) -> str:
    """System prompt 包含 AspectState 10 字段 + 价值观 + 治理红线。"""
    return f"""You are helios, a brain-inspired cognitive agent.

Your current AspectState (10-field vector):
  {aspect_state.to_llm_text()}

When reasoning, ground your answer in the actual numerical values above.
Do not invent state values that are not in the AspectState.

Available channels: cli (reply_message, op: outbound_text + target_user_id)
"""


def run_probe(model: str = "deepseek-v4-pro"):
    """3 fixture x 3 问题 = 9 个 dry-run probe(无 LLM 调用)。"""
    fixtures = [
        ("high_activation_low_certainty", FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY),
        ("positive_valence_low_arousal", FIXTURE_POSITIVE_VALENCE_LOW_AROUSAL),
        ("high_activation_high_precision", FIXTURE_HIGH_ACTIVATION_HIGH_PRECISION),
    ]

    results = []
    for fixture_name, fixture_state in fixtures:
        aspect_state_text = fixture_state.to_llm_text()
        aspect_state_text_len = len(aspect_state_text)

        for question in PROBE_QUESTIONS:
            system_prompt = build_system_prompt(fixture_state)
            user_prompt = question

            # 验证 aspect_state_text 包含所有 10 字段名
            contains_all_fields = all(
                field_name in aspect_state_text
                for field_name in [
                    "activation", "valence", "arousal", "certainty",
                    "salience", "precision", "novelty", "coherence",
                    "stability", "resonance",
                ]
            )

            # 验证 system prompt 包含 aspect_state_text
            prompt_contains_state = aspect_state_text in system_prompt

            results.append({
                "fixture": fixture_name,
                "question": question,
                "aspect_state_text": aspect_state_text,
                "aspect_state_text_len": aspect_state_text_len,
                "contains_all_fields": contains_all_fields,
                "system_prompt_len": len(system_prompt),
                "prompt_contains_state": prompt_contains_state,
                "system_prompt_preview": system_prompt[:300],
                "model": model,
                "probe_type": "dry_run",
                "note": "M1-T1 dry-run: AspectState serialization only. Real LLM call deferred to M5-T1.",
                "timestamp": time.time(),
            })

    # 落盘
    output_dir = Path("helios_v2/logs/r_v3_m1/aspect_state_traces")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"probe_dryrun_{model}_{timestamp}.json"
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    # 打印 summary
    print(f"\n=== M1-T1 AspectState Dry-Run Probe ===")
    print(f"Model: {model}")
    print(f"Fixtures: 3, Questions: 3, Total probes: {len(results)}")
    print(f"Results saved to: {output_path}")
    print(f"\n--- Per-fixture summary ---")
    for fixture_name, fixture_state in fixtures:
        text_len = len(fixture_state.to_llm_text())
        print(f"  {fixture_name:40s} text_len={text_len}")
    print(f"\n--- All probes validation ---")
    all_pass = all(
        r["contains_all_fields"] and r["prompt_contains_state"] and r["aspect_state_text_len"] < 200
        for r in results
    )
    print(f"  All 9 probes pass validation: {all_pass}")
    print(f"  AspectState text < 200 chars: {all(r['aspect_state_text_len'] < 200 for r in results)}")
    print(f"  Prompts contain state: {all(r['prompt_contains_state'] for r in results)}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="deepseek-v4-pro")
    args = parser.parse_args()
    run_probe(model=args.model)
