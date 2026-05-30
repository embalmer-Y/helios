# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live_20260530_baseline
- Right: r09_closeout_single_live_20260530
- Scenario match: True
- Total score delta (r09_closeout_single_live_20260530 - sec_normal_live_20260530_baseline): 0.0
- SEC fallback delta (r09_closeout_single_live_20260530 - sec_normal_live_20260530_baseline): 4
- Visible output ratio delta (r09_closeout_single_live_20260530 - sec_normal_live_20260530_baseline): 0.0

## R18 Calibration Delta
- left_status: unknown
- right_status: insufficient_runtime_evidence
- left_eligible: False
- right_eligible: False
- eligibility_changed: False

## Long-Range Deltas
- late_session_degradation: {'left_status': 'stable', 'right_status': 'stable', 'quality_delta_change': -0.25}
- specific_recall_persistence: {'left_status': 'weak', 'right_status': 'weak', 'hit_ratio_delta': 0.333}
- continuity_carry: {'left_status': 'observed', 'right_status': 'observed', 'continuation_active_ratio_delta': 0.073}
- user_visible_anchoring_drift: {'left_status': 'stable', 'right_status': 'drifting', 'anchoring_drift_delta_change': -0.5}

## Root Cause Summary
- r09_closeout_single_live_20260530 的 SEC fallback 比 sec_normal_live_20260530_baseline 多 4 次，优先怀疑 appraisal 前段污染。
- anchoring drift 状态从 stable 变为 drifting。
- 显著下降维度: 意识/思维/记忆链路工作状态。

## Dimension Deltas
- 情感反应类人度: 0.55 -> 0.641 (delta=0.091)
  - right_negative: sec_fallback_events=6
  - comparison_summary: r09_closeout_single_live_20260530 相比 sec_normal_live_20260530_baseline 下降 -0.091，右侧新增负向因素 sec_fallback_events=6
- 情感模块工作状态: 0.995 -> 0.995 (delta=0.0)
  - comparison_summary: r09_closeout_single_live_20260530 相比 sec_normal_live_20260530_baseline 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.684 -> 0.564 (delta=-0.12)
  - right_negative: thought_action_gap
  - right_negative: visible_output_sparsity
  - comparison_summary: r09_closeout_single_live_20260530 相比 sec_normal_live_20260530_baseline 下降 0.120，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: r09_closeout_single_live_20260530 相比 sec_normal_live_20260530_baseline 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.476 -> 0.669 (delta=0.193)
  - right_negative: sec_fallback_events=6
  - right_negative: visible_output_sparsity
  - comparison_summary: r09_closeout_single_live_20260530 相比 sec_normal_live_20260530_baseline 下降 -0.193，右侧新增负向因素 sec_fallback_events=6
- 路由/执行/外发链路工作状态: 0.8 -> 0.8 (delta=0.0)
  - right_negative: visible_output_missing_after_action_proposal
  - comparison_summary: r09_closeout_single_live_20260530 相比 sec_normal_live_20260530_baseline 下降 0.000，右侧新增负向因素 none

## Warning Delta
- added_in_right: anchoring_drift: 对话后段逐渐脱离用户锚点，开始泛化。
- shared: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。, specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。, thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。, visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。
