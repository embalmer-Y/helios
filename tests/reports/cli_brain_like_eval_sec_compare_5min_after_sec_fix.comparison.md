# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live
- Right: sec_fallback_live
- Scenario match: True
- Total score delta (sec_fallback_live - sec_normal_live): 0.0
- SEC fallback delta (sec_fallback_live - sec_normal_live): 2
- Visible output ratio delta (sec_fallback_live - sec_normal_live): 0.095

## Long-Range Deltas
- late_session_degradation: {'left_status': 'stable', 'right_status': 'stable', 'quality_delta_change': -0.25}
- specific_recall_persistence: {'left_status': 'not_observed', 'right_status': 'weak', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'observed', 'right_status': 'observed', 'continuation_active_ratio_delta': 0.227}
- user_visible_anchoring_drift: {'left_status': 'stable', 'right_status': 'stable', 'anchoring_drift_delta_change': -0.5}

## Root Cause Summary
- sec_fallback_live 的 SEC fallback 比 sec_normal_live 多 2 次，优先怀疑 appraisal 前段污染。
- specific recall 状态从 not_observed 变为 weak。

## Dimension Deltas
- 情感反应类人度: 0.496 -> 0.556 (delta=0.06)
  - right_negative: sec_fallback_events=51
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.060，右侧新增负向因素 sec_fallback_events=51
- 情感模块工作状态: 0.982 -> 0.982 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.547 -> 0.547 (delta=0.0)
  - right_negative: thought_action_gap
  - right_negative: visible_output_sparsity
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.66 -> 0.607 (delta=-0.053)
  - right_negative: sec_fallback_events=51
  - right_negative: visible_output_sparsity
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.053，右侧新增负向因素 sec_fallback_events=51
- 路由/执行/外发链路工作状态: 0.72 -> 0.72 (delta=0.0)
  - right_negative: planner_reject_events=2
  - right_negative: visible_output_missing_after_action_proposal
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none

## Warning Delta
- added_in_right: specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。
- shared: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。, thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。, visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。
