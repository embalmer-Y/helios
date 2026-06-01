# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live
- Right: sec_fallback_live
- Scenario match: True
- Total score delta (sec_fallback_live - sec_normal_live): 0.126
- SEC fallback delta (sec_fallback_live - sec_normal_live): 27
- Visible output ratio delta (sec_fallback_live - sec_normal_live): 0.333

## Long-Range Deltas
- late_session_degradation: {'left_status': 'unknown', 'right_status': 'stable', 'quality_delta_change': 0.0}
- specific_recall_persistence: {'left_status': 'unknown', 'right_status': 'weak', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'unknown', 'right_status': 'missing', 'continuation_active_ratio_delta': 0.5}
- user_visible_anchoring_drift: {'left_status': 'unknown', 'right_status': 'stable', 'anchoring_drift_delta_change': 0.0}

## Root Cause Summary
- sec_fallback_live 的 SEC fallback 比 sec_normal_live 多 27 次，优先怀疑 appraisal 前段污染。
- late-session quality 状态从 unknown 变为 stable。
- specific recall 状态从 unknown 变为 weak。
- continuity carry 状态从 unknown 变为 missing。
- anchoring drift 状态从 unknown 变为 stable。

## Dimension Deltas
- 情感反应类人度: 0.183 -> 0.348 (delta=0.165)
  - right_negative: sec_fallback_events=28
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.165，右侧新增负向因素 sec_fallback_events=28
- 情感模块工作状态: 0.6 -> 0.9 (delta=0.3)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.300，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.47 -> 0.545 (delta=0.075)
  - right_negative: thought_action_gap
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.075，右侧新增负向因素 thought_action_gap
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.15 -> 0.5 (delta=0.35)
  - right_negative: sec_fallback_events=28
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.350，右侧新增负向因素 sec_fallback_events=28
- 路由/执行/外发链路工作状态: 0.68 -> 0.8 (delta=0.12)
  - right_negative: visible_output_missing_after_action_proposal
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.120，右侧新增负向因素 visible_output_missing_after_action_proposal

## Warning Delta
- added_in_right: continuity_carry_missing: continuation 信号存在，但后段缺少可见延续。, specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。, thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。
- shared: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。
