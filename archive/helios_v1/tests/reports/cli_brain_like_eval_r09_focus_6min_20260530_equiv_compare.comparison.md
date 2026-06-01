# CLI Brain-Like Evaluation Comparison - 6-minute R09-focused CLI evaluation

- Scenario ID: cli_brain_like_eval_r09_focus_6min_v1
- Left: r09_focus_prev
- Right: r09_focus_equiv
- Scenario match: True
- Total score delta (r09_focus_equiv - r09_focus_prev): -0.174
- SEC fallback delta (r09_focus_equiv - r09_focus_prev): 0
- Visible output ratio delta (r09_focus_equiv - r09_focus_prev): 0.0

## R18 Calibration Delta
- left_status: insufficient_runtime_evidence
- right_status: insufficient_runtime_evidence
- left_eligible: False
- right_eligible: False
- eligibility_changed: False

## Long-Range Deltas
- late_session_degradation: {'left_status': 'stable', 'right_status': 'stable', 'quality_delta_change': 0.5}
- specific_recall_persistence: {'left_status': 'weak', 'right_status': 'weak', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'observed', 'right_status': 'observed', 'continuation_active_ratio_delta': -0.106}
- user_visible_anchoring_drift: {'left_status': 'stable', 'right_status': 'stable', 'anchoring_drift_delta_change': 1.0}

## Root Cause Summary
- 显著下降维度: 语言表达自然度。

## Dimension Deltas
- 情感反应类人度: 0.625 -> 0.587 (delta=-0.038)
  - comparison_summary: r09_focus_equiv 相比 r09_focus_prev 下降 0.038，右侧新增负向因素 none
- 情感模块工作状态: 0.989 -> 0.989 (delta=0.0)
  - comparison_summary: r09_focus_equiv 相比 r09_focus_prev 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.887 -> 0.887 (delta=0.0)
  - right_negative: visible_output_sparsity
  - comparison_summary: r09_focus_equiv 相比 r09_focus_prev 下降 0.000，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: r09_focus_equiv 相比 r09_focus_prev 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.658 -> 0.525 (delta=-0.133)
  - right_negative: visible_output_sparsity
  - comparison_summary: r09_focus_equiv 相比 r09_focus_prev 下降 0.133，右侧新增负向因素 none
- 路由/执行/外发链路工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: r09_focus_equiv 相比 r09_focus_prev 下降 0.000，右侧新增负向因素 none

## Warning Delta
- shared: specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。, visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。
