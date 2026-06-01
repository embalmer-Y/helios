# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live
- Right: sec_fallback_live
- Scenario match: True
- Total score delta (sec_fallback_live - sec_normal_live): -0.018
- SEC fallback delta (sec_fallback_live - sec_normal_live): 7
- Visible output ratio delta (sec_fallback_live - sec_normal_live): 0.0

## Long-Range Deltas
- late_session_degradation: {'left_status': 'unknown', 'right_status': 'unknown', 'quality_delta_change': 0.0}
- specific_recall_persistence: {'left_status': 'unknown', 'right_status': 'unknown', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'unknown', 'right_status': 'unknown', 'continuation_active_ratio_delta': 0.0}
- user_visible_anchoring_drift: {'left_status': 'unknown', 'right_status': 'unknown', 'anchoring_drift_delta_change': 0.0}

## Root Cause Summary
- sec_fallback_live 的 SEC fallback 比 sec_normal_live 多 7 次，优先怀疑 appraisal 前段污染。
- 显著下降维度: 意识/思维/记忆链路工作状态。

## Dimension Deltas
- 情感反应类人度: 0.183 -> 0.183 (delta=0.0)
  - right_negative: sec_fallback_events=7
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 sec_fallback_events=7
- 情感模块工作状态: 0.6 -> 0.6 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.5 -> 0.32 (delta=-0.18)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.180，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.15 -> 0.15 (delta=0.0)
  - right_negative: sec_fallback_events=7
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 sec_fallback_events=7
- 路由/执行/外发链路工作状态: 0.68 -> 0.68 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none

## Warning Delta
- added_in_right: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。
