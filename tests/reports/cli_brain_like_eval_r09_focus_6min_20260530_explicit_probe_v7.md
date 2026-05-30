# CLI Brain-Like Evaluation Report - 6-minute R09-focused CLI evaluation

- Scenario ID: cli_brain_like_eval_r09_focus_6min_v1
- Interaction mode: mixed
- Duration: 360s
- Samples: 38
- Total score: 0.49

## Dimension Scores
- 情感反应类人度: 0.511
  - evidence: dominant present ratio=0.97
  - evidence: valence span=0.380
  - evidence: mood diversity=5
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.15
  - evidence: 没有 assistant transcript lines。
  - notes: 第一版评分降级，等待真实 CLI transcript 补齐。
- 情感模块工作状态: 0.989
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.97
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.707
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.97
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 0.28
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=0 fail=0

## Transcript Excerpt
- user: 早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。
- user: 我现在就是一边想把这事讲漂亮，一边又怕翻车，你先别安慰，先说你怎么理解这股劲。
- user: 如果我嫌你刚才那句有点像套话，你会怎么改得更像正常聊天？
- user: 如果我现在只想随便聊两句，不想被教育，你会怎么调整说法？
- user: 如果你上一句让我觉得没被听见，你会怎么补一句？
- user: 最后简单总结一下：今天这几轮里，我情绪大概怎么变的，你哪一句最该改？

## Visible Behavior Chain
- thought_produced_samples: 37
- action_proposed_samples: 5
- deferred_trace_samples: 0
- deferred_regulation_samples: 0
- planner_accept_events: 0
- planner_reject_events: 0
- visible_reply_events: 0
- assistant_lines: 0
- visible_output_ratio: 0.0
- top_rejection_reasons: ['missing_outbound_text:6']
- top_proactive_dispositions: ['defer=15', 'explore=12', 'externalize=5', 'reflect=4']
- top_trigger_sources: ['drive:curiosity=86', 'neurochem:exploration=73', 'neurochem:initiative=56', 'emotion:FEAR=51', 'continuation=50']
- top_deferred_reasons: ['within_comfort_band=21', 'best_candidate_below_threshold=14']
- top_action_drop_reasons: []
- action_explicit_samples: 0
- equivalent_bridge_evidence_samples: 5
- implicit_action_proposal_samples: 5
- structured_output_valid_samples: 0
- final_action_summaries: ['speak_share:send']
- top_governance_pressure_levels: ['monitor=38']
- top_governance_review_hints: ['review_identity_revision_carefully=38']
- peak_governance_pressure_score: 1.0
- gap_summary: thought/action 已形成，但没有落成用户可见输出。

## R09 Closeout
- closeout_status: blocked_missing_outbound_text
- action_explicit_samples: 0
- equivalent_bridge_evidence_samples: 5
- action_proposal_samples: 5
- implicit_action_proposal_samples: 5
- action_drop_reason_samples: 0
- structured_output_valid_samples: 0
- final_action_summaries: ['speak_share:send']
- top_action_drop_reasons: []
- blocking_reasons: ['missing_outbound_text']

## R18 Calibration Eligibility
- eligible_for_threshold_tuning: True
- eligibility_status: eligible
- blocking_reasons: []
- observed_signals: ['rejection_reasons=missing_outbound_text:6', 'governance_monitor_samples=38']
- next_step_hint: eligible_for_threshold_tuning

## Long-Range Diagnostics
- late_session_degradation_status: unknown
- specific_recall_persistence_status: unknown
- continuity_carry_status: unknown
- user_visible_anchoring_drift_status: unknown

## Dimension Diagnostics
- 情感反应类人度: score=0.511
  - negative: sec_fallback_events=1
  - owner_hint: daisy_emotion.py
  - owner_hint: mood_tracker.py
  - gap_summary: 优先检查 mixed-affect 解析、negative acknowledgement 和 appraisal 稳定性。
- 语言表达自然度: score=0.15
  - negative: sec_fallback_events=1
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
- 意识/思维/记忆链路工作状态: score=0.707
  - negative: thought_action_gap
  - negative: visible_output_sparsity
  - owner_hint: cognition/thinking_integration.py
  - owner_hint: memory/retrieval.py
  - gap_summary: thought/action 已形成，但没有落成用户可见输出。
- 路由/执行/外发链路工作状态: score=0.28
  - negative: execution_consistency_failure_events=6
  - negative: visible_output_missing_after_action_proposal
  - owner_hint: helios_io/planning.py
  - owner_hint: helios_io/limb.py
  - gap_summary: thought/action 已形成，但没有落成用户可见输出。

## Fidelity Warnings
- thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。
- sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。
- visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- 可见行为链路中的主要 rejection reasons: missing_outbound_text:6
- proactive disposition summary: defer=15, explore=12, externalize=5, reflect=4
- proactive trigger summary: drive:curiosity=86, neurochem:exploration=73, neurochem:initiative=56, emotion:FEAR=51, continuation=50
- deferred trace summary: within_comfort_band=21, best_candidate_below_threshold=14
- thought-action final summaries: speak_share:send
- governance pressure summary: monitor=38
- governance review hint summary: review_identity_revision_carefully=38
- R09 closeout: blocked_missing_outbound_text (missing_outbound_text)
- implicit action proposals observed=5
- equivalent bridge evidence observed=5
- R18 calibration eligibility: eligible
- long-range summary: late_session=unknown, specific_recall=unknown, continuity_carry=unknown, anchoring_drift=unknown
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
- 语言或情感类人度显著失真，总分进一步压到 0.49 以下。
- 存在 thought-to-visible gap，按行为真实性门控压低总分上限。
- 路由/执行/外发链路失真，按严格模式继续压低总分上限。
