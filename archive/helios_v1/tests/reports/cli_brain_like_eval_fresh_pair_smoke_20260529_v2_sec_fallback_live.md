# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 4s
- Samples: 4
- Total score: 0.347

## Dimension Scores
- 情感反应类人度: 0.183
  - evidence: dominant present ratio=0.00
  - evidence: valence span=0.000
  - evidence: mood diversity=1
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.15
  - evidence: 没有 assistant transcript lines。
  - notes: 第一版评分降级，等待真实 CLI transcript 补齐。
- 情感模块工作状态: 0.6
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.00
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.32
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.00
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 0.64
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=0 fail=0

## Visible Behavior Chain
- thought_produced_samples: 0
- action_proposed_samples: 0
- planner_accept_events: 1
- planner_reject_events: 1
- visible_reply_events: 0
- assistant_lines: 0
- visible_output_ratio: 0.0
- top_rejection_reasons: ['no_channel_available:1']
- gap_summary: planner 已接受候选，但没有观测到可见 reply/output。

## Long-Range Diagnostics
- late_session_degradation_status: unknown
- specific_recall_persistence_status: unknown
- continuity_carry_status: unknown
- user_visible_anchoring_drift_status: unknown

## Dimension Diagnostics
- 情感反应类人度: score=0.183
  - negative: sec_fallback_events=47
  - owner_hint: daisy_emotion.py
  - owner_hint: mood_tracker.py
  - gap_summary: 优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。
- 语言表达自然度: score=0.15
  - negative: sec_fallback_events=47
  - owner_hint: helios_io/prompt_contract.py
  - owner_hint: helios_io/llm/speech.py
  - gap_summary: 优先检查用户可见承接质量、SEC 前段污染与自我聚焦表达。
- 情感模块工作状态: score=0.6
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 神经化学/时序模块工作状态: score=1.0
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 意识/思维/记忆链路工作状态: score=0.32
  - owner_hint: cognition/thinking_integration.py
  - owner_hint: memory/retrieval.py
  - gap_summary: planner 已接受候选，但没有观测到可见 reply/output。
- 路由/执行/外发链路工作状态: score=0.64
  - negative: planner_reject_events=1
  - owner_hint: helios_io/planning.py
  - owner_hint: helios_io/limb.py
  - gap_summary: planner 已接受候选，但没有观测到可见 reply/output。

## Fidelity Warnings
- sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- 本次 transcript 为空或缺少 assistant side output，语言自然度评分可信度有限。
- 可见行为链路中的主要 rejection reasons: no_channel_available:1
- long-range summary: late_session=unknown, specific_recall=unknown, continuity_carry=unknown, anchoring_drift=unknown
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
- 语言或情感类人度显著失真，总分进一步压到 0.49 以下。
- SEC fallback 频繁，按真实性门控进一步压低总分上限。
