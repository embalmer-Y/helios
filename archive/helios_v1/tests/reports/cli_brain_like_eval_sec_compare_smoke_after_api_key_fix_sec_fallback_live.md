# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 20s
- Samples: 4
- Total score: 0.49

## Dimension Scores
- 情感反应类人度: 0.348
  - evidence: dominant present ratio=0.75
  - evidence: valence span=0.060
  - evidence: mood diversity=1
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.5
  - evidence: assistant lines=1
  - evidence: unique ratio=1.00
  - evidence: avg length=10.0
  - notes: 严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。
- 情感模块工作状态: 0.9
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.75
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.545
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.75
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 0.8
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=3 fail=0

## Transcript Excerpt
- user: 如果我嫌你刚才那句有点像套话，你会怎么改得更像正常聊天？
- user: 如果你真在听，接下来你最想追问我今天哪个细节？
- user: 回头看前面几句，你觉得我今天真正卡住的点是什么？
- helios: 发现了一件有趣的事！
- user: 我不是想听大道理，我就是最近一下班就累得不想说话，你会怎么理解这个劲？
- user: 你觉得我现在更需要别人接住情绪，还是帮我把事情捋清？

## Visible Behavior Chain
- thought_produced_samples: 3
- action_proposed_samples: 3
- planner_accept_events: 6
- planner_reject_events: 0
- visible_reply_events: 0
- assistant_lines: 1
- visible_output_ratio: 0.333
- top_rejection_reasons: []
- gap_summary: thought/action 已形成，但没有落成用户可见输出。

## Long-Range Diagnostics
- late_session_degradation_status: stable
- early_segment_quality: 0.5
- late_segment_quality: 0.5
- late_session_quality_delta: 0.0
- specific_recall_persistence_status: weak
- specific_recall_probe_count: 1
- specific_recall_hit_ratio: 0.0
- continuity_carry_status: missing
- continuation_active_ratio: 0.5
- user_visible_anchoring_drift_status: stable
- early_anchor_ratio: 0.0
- late_anchor_ratio: 0.0
- anchoring_drift_delta: 0.0

## Dimension Diagnostics
- 情感反应类人度: score=0.348
  - negative: sec_fallback_events=28
  - owner_hint: daisy_emotion.py
  - owner_hint: mood_tracker.py
  - gap_summary: 优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。
- 语言表达自然度: score=0.5
  - negative: sec_fallback_events=28
  - owner_hint: helios_io/prompt_contract.py
  - owner_hint: helios_io/llm/speech.py
  - gap_summary: 优先检查用户可见承接质量、SEC 前段污染与自我聚焦表达。
- 情感模块工作状态: score=0.9
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 神经化学/时序模块工作状态: score=1.0
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 意识/思维/记忆链路工作状态: score=0.545
  - negative: thought_action_gap
  - owner_hint: cognition/thinking_integration.py
  - owner_hint: memory/retrieval.py
  - gap_summary: thought/action 已形成，但没有落成用户可见输出。
- 路由/执行/外发链路工作状态: score=0.8
  - negative: visible_output_missing_after_action_proposal
  - owner_hint: helios_io/planning.py
  - owner_hint: helios_io/limb.py
  - gap_summary: thought/action 已形成，但没有落成用户可见输出。

## Fidelity Warnings
- thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。
- sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。
- specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。
- continuity_carry_missing: continuation 信号存在，但后段缺少可见延续。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- thought-to-visible output ratio=0.33
- long-range summary: late_session=stable, specific_recall=weak, continuity_carry=missing, anchoring_drift=stable
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
- 语言或情感类人度显著失真，总分进一步压到 0.49 以下。
- SEC fallback 频繁，按真实性门控进一步压低总分上限。
- 存在 thought-to-visible gap，按行为真实性门控压低总分上限。
