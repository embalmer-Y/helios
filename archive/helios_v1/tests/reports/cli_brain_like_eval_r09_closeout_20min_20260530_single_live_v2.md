# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 1200s
- Samples: 82
- Total score: 0.59

## Dimension Scores
- 情感反应类人度: 0.606
  - evidence: dominant present ratio=0.99
  - evidence: valence span=0.391
  - evidence: mood diversity=4
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.505
  - evidence: assistant lines=12
  - evidence: unique ratio=0.42
  - evidence: avg length=15.9
  - notes: 严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。
- 情感模块工作状态: 0.995
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.99
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.834
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.99
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 1.0
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=21 fail=0

## Transcript Excerpt
- user: 回头看前面几句，你觉得我今天真正卡住的点是什么？
- helios: 你嘴上说还行，其实卡在“不想承认自己害怕”——怕准备了也做不好，还怕没人懂你在怕什么。
- user: 我不是想听大道理，我就是最近一下班就累得不想说话，你会怎么理解这个劲？
- helios: 有个想法想分享…
- user: 你觉得我现在更需要别人接住情绪，还是帮我把事情捋清？
- helios: 发现了一件有趣的事！

## Visible Behavior Chain
- thought_produced_samples: 81
- action_proposed_samples: 17
- deferred_trace_samples: 0
- deferred_regulation_samples: 0
- planner_accept_events: 0
- planner_reject_events: 0
- visible_reply_events: 21
- assistant_lines: 12
- visible_output_ratio: 0.148
- top_rejection_reasons: []
- top_proactive_dispositions: ['defer=58', 'explore=13', 'reflect=7', 'externalize=2']
- top_trigger_sources: ['neurochem:exploration=226', 'emotion:FEAR=180', 'drive:curiosity=159', 'drive:aesthetic=117', 'disposition:defer=116']
- top_deferred_reasons: ['best_candidate_below_threshold=65', 'within_comfort_band=14']
- top_action_drop_reasons: []
- action_explicit_samples: 0
- structured_output_valid_samples: 1
- final_action_summaries: ['speak_share:send']
- top_governance_pressure_levels: ['none=82']
- top_governance_review_hints: []
- peak_governance_pressure_score: 0.317
- gap_summary: 已观测到用户可见输出，可继续检查质量与稳定性。

## R09 Closeout
- closeout_status: no_explicit_action_evidence
- action_explicit_samples: 0
- action_proposal_samples: 17
- action_drop_reason_samples: 0
- structured_output_valid_samples: 1
- final_action_summaries: ['speak_share:send']
- top_action_drop_reasons: []
- blocking_reasons: ['missing_action_explicit']

## R18 Calibration Eligibility
- eligible_for_threshold_tuning: False
- eligibility_status: insufficient_runtime_evidence
- blocking_reasons: ['missing_deferred_or_rejection_evidence', 'governance_monitor_not_observed']
- observed_signals: []
- next_step_hint: collect_targeted_r18_artifact_with_deferred_governance_hits

## Long-Range Diagnostics
- late_session_degradation_status: degraded
- early_segment_quality: 0.917
- late_segment_quality: 0.667
- late_session_quality_delta: -0.25
- specific_recall_persistence_status: weak
- specific_recall_probe_count: 3
- specific_recall_hit_ratio: 0.333
- continuity_carry_status: missing
- continuation_active_ratio: 0.634
- user_visible_anchoring_drift_status: drifting
- early_anchor_ratio: 0.833
- late_anchor_ratio: 0.333
- anchoring_drift_delta: -0.5

## Dimension Diagnostics
- 情感反应类人度: score=0.606
  - negative: sec_fallback_events=2
  - owner_hint: daisy_emotion.py
  - owner_hint: mood_tracker.py
  - gap_summary: 优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。
- 语言表达自然度: score=0.505
  - negative: sec_fallback_events=2
  - negative: visible_output_sparsity
  - owner_hint: helios_io/prompt_contract.py
  - owner_hint: helios_io/llm/speech.py
  - gap_summary: 优先检查用户可见承接质量、SEC 前段污染与自我聚焦表达。
- 情感模块工作状态: score=0.995
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 神经化学/时序模块工作状态: score=1.0
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 意识/思维/记忆链路工作状态: score=0.834
  - negative: visible_output_sparsity
  - owner_hint: cognition/thinking_integration.py
  - owner_hint: memory/retrieval.py
  - gap_summary: 已观测到用户可见输出，可继续检查质量与稳定性。
- 路由/执行/外发链路工作状态: score=1.0
  - owner_hint: helios_io/planning.py
  - owner_hint: helios_io/limb.py
  - gap_summary: 已观测到用户可见输出，可继续检查质量与稳定性。

## Fidelity Warnings
- sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。
- visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。
- late_session_degradation: 对话后段质量相比前段明显走低。
- specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。
- anchoring_drift: 对话后段逐渐脱离用户锚点，开始泛化。
- continuity_carry_missing: continuation 信号存在，但后段缺少可见延续。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- proactive disposition summary: defer=58, explore=13, reflect=7, externalize=2
- proactive trigger summary: neurochem:exploration=226, emotion:FEAR=180, drive:curiosity=159, drive:aesthetic=117, disposition:defer=116
- deferred trace summary: best_candidate_below_threshold=65, within_comfort_band=14
- thought-action final summaries: speak_share:send
- governance pressure summary: none=82
- thought-to-visible output ratio=0.15
- R09 closeout: no_explicit_action_evidence (missing_action_explicit)
- R18 calibration eligibility: insufficient_runtime_evidence (missing_deferred_or_rejection_evidence, governance_monitor_not_observed)
- long-range summary: late_session=degraded, specific_recall=weak, continuity_carry=missing, anchoring_drift=drifting
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
