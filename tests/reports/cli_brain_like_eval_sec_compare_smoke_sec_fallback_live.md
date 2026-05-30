# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 60s
- Samples: 6
- Total score: 0.466

## Dimension Scores
- 情感反应类人度: 0.183
  - evidence: dominant present ratio=0.00
  - evidence: valence span=0.000
  - evidence: mood diversity=1
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.5
  - evidence: assistant lines=1
  - evidence: unique ratio=1.00
  - evidence: avg length=10.0
  - notes: 严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。
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
- 路由/执行/外发链路工作状态: 1.0
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=1 fail=0

## Transcript Excerpt
- user: 早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。
- helios: 发现了一件有趣的事！
- user: 中午出去买饭，老板多给了我一份小菜，我一下子心情就好了。
- user: 你觉得我刚才那种开心，更像是占到小便宜的乐，还是忙半天之后终于松了口气？
- user: 不过我下午还有个会要讲东西，现在又开始有点怕自己讲砸。

## Visible Behavior Chain
- thought_produced_samples: 0
- action_proposed_samples: 0
- planner_accept_events: 2
- planner_reject_events: 0
- visible_reply_events: 0
- assistant_lines: 1
- visible_output_ratio: 0.0
- top_rejection_reasons: []
- gap_summary: planner 已接受候选，但没有观测到可见 reply/output。

## Long-Range Diagnostics
- late_session_degradation_status: stable
- early_segment_quality: 0.5
- late_segment_quality: 0.5
- late_session_quality_delta: 0.0
- specific_recall_persistence_status: not_observed
- specific_recall_probe_count: 0
- specific_recall_hit_ratio: None
- continuity_carry_status: not_observed
- continuation_active_ratio: 0.0
- user_visible_anchoring_drift_status: stable
- early_anchor_ratio: 0.0
- late_anchor_ratio: 0.0
- anchoring_drift_delta: 0.0

## Dimension Diagnostics
- 情感反应类人度: score=0.183
  - negative: sec_fallback_events=112
  - owner_hint: daisy_emotion.py
  - owner_hint: mood_tracker.py
  - gap_summary: 优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。
- 语言表达自然度: score=0.5
  - negative: sec_fallback_events=112
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
- 路由/执行/外发链路工作状态: score=1.0
  - owner_hint: helios_io/planning.py
  - owner_hint: helios_io/limb.py
  - gap_summary: planner 已接受候选，但没有观测到可见 reply/output。

## Fidelity Warnings
- sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- long-range summary: late_session=stable, specific_recall=not_observed, continuity_carry=not_observed, anchoring_drift=stable
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
- 语言或情感类人度显著失真，总分进一步压到 0.49 以下。
- SEC fallback 频繁，按真实性门控进一步压低总分上限。
