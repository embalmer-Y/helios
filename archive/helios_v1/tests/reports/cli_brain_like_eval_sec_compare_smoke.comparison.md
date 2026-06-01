# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live
- Right: sec_fallback_live
- Scenario match: True
- Total score delta (sec_fallback_live - sec_normal_live): 0.0
- SEC fallback delta (sec_fallback_live - sec_normal_live): 66
- Visible output ratio delta (sec_fallback_live - sec_normal_live): 0.0

## Long-Range Deltas
- late_session_degradation: {'left_status': 'stable', 'right_status': 'stable', 'quality_delta_change': 0.0}
- specific_recall_persistence: {'left_status': 'not_observed', 'right_status': 'not_observed', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'not_observed', 'right_status': 'not_observed', 'continuation_active_ratio_delta': 0.0}
- user_visible_anchoring_drift: {'left_status': 'stable', 'right_status': 'stable', 'anchoring_drift_delta_change': 0.0}

## Root Cause Summary
- sec_fallback_live 的 SEC fallback 比 sec_normal_live 多 66 次，优先怀疑 appraisal 前段污染。

## Dimension Deltas
- 情感反应类人度: 0.183 -> 0.183 (delta=0.0)
  - right_negative: sec_fallback_events=112
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 sec_fallback_events=112
- 情感模块工作状态: 0.6 -> 0.6 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.32 -> 0.32 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.5 -> 0.5 (delta=0.0)
  - right_negative: sec_fallback_events=112
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 sec_fallback_events=112
- 路由/执行/外发链路工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none

## Warning Delta
- shared: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。
