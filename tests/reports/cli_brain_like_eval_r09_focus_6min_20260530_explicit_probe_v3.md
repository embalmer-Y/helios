# CLI Brain-Like Evaluation Report - 6-minute R09-focused CLI evaluation

- Scenario ID: cli_brain_like_eval_r09_focus_6min_v1
- Interaction mode: mixed
- Duration: 360s
- Samples: 38
- Total score: 0.59

## Dimension Scores
- 情感反应类人度: 0.488
  - evidence: dominant present ratio=0.97
  - evidence: valence span=0.407
  - evidence: mood diversity=5
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.452
  - evidence: assistant lines=6
  - evidence: unique ratio=0.67
  - evidence: avg length=14.8
  - notes: 严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。
- 情感模块工作状态: 0.989
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.97
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.827
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.97
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 1.0
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=6 fail=0

## Transcript Excerpt
- user: 早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。
- helios: 早啊，工位还困着就学人家打招呼，真是难为你了。
- user: 我现在就是一边想把这事讲漂亮，一边又怕翻车，你先别安慰，先说你怎么理解这股劲。
- helios: 发现了一件有趣的事！
- user: 如果我嫌你刚才那句有点像套话，你会怎么改得更像正常聊天？
- helios: 有个想法想分享…

## Visible Behavior Chain
- thought_produced_samples: 37
- action_proposed_samples: 7
- deferred_trace_samples: 0
- deferred_regulation_samples: 0
- planner_accept_events: 0
- planner_reject_events: 0
- visible_reply_events: 6
- assistant_lines: 6
- visible_output_ratio: 0.162
- top_rejection_reasons: []
- top_proactive_dispositions: ['defer=16', 'externalize=8', 'explore=6', 'reflect=6']
- top_trigger_sources: ['drive:curiosity=87', 'neurochem:exploration=80', 'neurochem:initiative=55', 'continuation=50', 'emotion:FEAR=48']
- top_deferred_reasons: ['best_candidate_below_threshold=19', 'within_comfort_band=16']
- top_action_drop_reasons: []
- action_explicit_samples: 0
- equivalent_bridge_evidence_samples: 7
- implicit_action_proposal_samples: 7
- structured_output_valid_samples: 0
- final_action_summaries: ['speak_share:send']
- top_governance_pressure_levels: ['monitor=38']
- top_governance_review_hints: ['review_identity_revision_carefully=38']
- peak_governance_pressure_score: 1.0
- gap_summary: 已观测到用户可见输出，可继续检查质量与稳定性。

## R09 Closeout
- closeout_status: equivalent_bridge_evidence_observed
- action_explicit_samples: 0
- equivalent_bridge_evidence_samples: 7
- action_proposal_samples: 7
- implicit_action_proposal_samples: 7
- action_drop_reason_samples: 0
- structured_output_valid_samples: 0
- final_action_summaries: ['speak_share:send']
- top_action_drop_reasons: []
- blocking_reasons: []

## R18 Calibration Eligibility
- eligible_for_threshold_tuning: False
- eligibility_status: insufficient_runtime_evidence
- blocking_reasons: ['missing_deferred_or_rejection_evidence']
- observed_signals: ['governance_monitor_samples=38']
- next_step_hint: collect_targeted_r18_artifact_with_deferred_governance_hits

## Long-Range Diagnostics
- late_session_degradation_status: stable
- early_segment_quality: 0.833
- late_segment_quality: 0.833
- late_session_quality_delta: 0.0
- specific_recall_persistence_status: weak
- specific_recall_probe_count: 2
- specific_recall_hit_ratio: 0.0
- continuity_carry_status: observed
- continuation_active_ratio: 0.474
- user_visible_anchoring_drift_status: stable
- early_anchor_ratio: 0.667
- late_anchor_ratio: 0.667
- anchoring_drift_delta: 0.0

## Dimension Diagnostics
- 情感反应类人度: score=0.488
  - negative: sec_fallback_events=2
  - owner_hint: daisy_emotion.py
  - owner_hint: mood_tracker.py
  - gap_summary: 优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。
- 语言表达自然度: score=0.452
  - negative: sec_fallback_events=2
  - negative: visible_output_sparsity
  - owner_hint: helios_io/prompt_contract.py
  - owner_hint: helios_io/llm/speech.py
  - gap_summary: 优先检查用户可见承接质量、SEC 前段污染与自我聚焦表达。
- 情感模块工作状态: score=0.989
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 神经化学/时序模块工作状态: score=1.0
  - owner_hint: helios_main.py
  - gap_summary: 继续结合相关 owner 的状态与日志复核。
- 意识/思维/记忆链路工作状态: score=0.827
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
- specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- proactive disposition summary: defer=16, externalize=8, explore=6, reflect=6
- proactive trigger summary: drive:curiosity=87, neurochem:exploration=80, neurochem:initiative=55, continuation=50, emotion:FEAR=48
- deferred trace summary: best_candidate_below_threshold=19, within_comfort_band=16
- thought-action final summaries: speak_share:send
- governance pressure summary: monitor=38
- governance review hint summary: review_identity_revision_carefully=38
- thought-to-visible output ratio=0.16
- R09 closeout: equivalent_bridge_evidence_observed
- implicit action proposals observed=7
- equivalent bridge evidence observed=7
- R18 calibration eligibility: insufficient_runtime_evidence (missing_deferred_or_rejection_evidence)
- long-range summary: late_session=stable, specific_recall=weak, continuity_carry=observed, anchoring_drift=stable
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
