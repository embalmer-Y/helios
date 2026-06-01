# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live
- Right: sec_fallback_live
- Scenario match: True
- Total score delta (sec_fallback_live - sec_normal_live): -0.09
- SEC fallback delta (sec_fallback_live - sec_normal_live): 37
- Visible output ratio delta (sec_fallback_live - sec_normal_live): 0.238

## Long-Range Deltas
- late_session_degradation: {'left_status': 'stable', 'right_status': 'stable', 'quality_delta_change': 0.05}
- specific_recall_persistence: {'left_status': 'weak', 'right_status': 'weak', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'observed', 'right_status': 'observed', 'continuation_active_ratio_delta': 0.272}
- user_visible_anchoring_drift: {'left_status': 'stable', 'right_status': 'stable', 'anchoring_drift_delta_change': 0.1}

## Root Cause Summary
- sec_fallback_live 的 SEC fallback 比 sec_normal_live 多 37 次，优先怀疑 appraisal 前段污染。
- 显著下降维度: 情感反应类人度, 语言表达自然度。

## Dimension Deltas
- 情感反应类人度: 0.52 -> 0.23 (delta=-0.29)
  - right_negative: sec_fallback_events=42
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.290，右侧新增负向因素 sec_fallback_events=42
- 情感模块工作状态: 0.982 -> 0.982 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.577 -> 0.647 (delta=0.07)
  - right_negative: thought_action_gap
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 -0.070，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.597 -> 0.256 (delta=-0.341)
  - right_negative: sec_fallback_events=42
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.341，右侧新增负向因素 sec_fallback_events=42
- 路由/执行/外发链路工作状态: 0.8 -> 0.8 (delta=0.0)
  - right_negative: visible_output_missing_after_action_proposal
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none

## Warning Delta
- removed_in_right: visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。
- shared: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。, specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。, thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。
