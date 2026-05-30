# CLI Brain-Like Evaluation Comparison - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Left: sec_normal_live
- Right: sec_fallback_live
- Scenario match: True
- Total score delta (sec_fallback_live - sec_normal_live): -0.09
- SEC fallback delta (sec_fallback_live - sec_normal_live): 40
- Visible output ratio delta (sec_fallback_live - sec_normal_live): -0.074

## Long-Range Deltas
- late_session_degradation: {'left_status': 'stable', 'right_status': 'degraded', 'quality_delta_change': -0.416}
- specific_recall_persistence: {'left_status': 'weak', 'right_status': 'weak', 'hit_ratio_delta': 0.0}
- continuity_carry: {'left_status': 'observed', 'right_status': 'missing', 'continuation_active_ratio_delta': 0.0}
- user_visible_anchoring_drift: {'left_status': 'stable', 'right_status': 'drifting', 'anchoring_drift_delta_change': -0.834}

## Root Cause Summary
- sec_fallback_live 的 SEC fallback 比 sec_normal_live 多 40 次，优先怀疑 appraisal 前段污染。
- sec_fallback_live 的 thought-to-visible ratio 下降 0.074，说明用户可见外化更稀疏。
- late-session quality 状态从 stable 变为 degraded。
- continuity carry 状态从 observed 变为 missing。
- anchoring drift 状态从 stable 变为 drifting。
- 显著下降维度: 情感反应类人度, 意识/思维/记忆链路工作状态。

## Dimension Deltas
- 情感反应类人度: 0.55 -> 0.324 (delta=-0.226)
  - right_negative: sec_fallback_events=42
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.226，右侧新增负向因素 sec_fallback_events=42
- 情感模块工作状态: 0.995 -> 0.995 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 意识/思维/记忆链路工作状态: 0.684 -> 0.564 (delta=-0.12)
  - right_negative: thought_action_gap
  - right_negative: visible_output_sparsity
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.120，右侧新增负向因素 none
- 神经化学/时序模块工作状态: 1.0 -> 1.0 (delta=0.0)
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none
- 语言表达自然度: 0.476 -> 0.42 (delta=-0.056)
  - right_negative: sec_fallback_events=42
  - right_negative: visible_output_sparsity
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.056，右侧新增负向因素 sec_fallback_events=42
- 路由/执行/外发链路工作状态: 0.8 -> 0.8 (delta=0.0)
  - right_negative: visible_output_missing_after_action_proposal
  - comparison_summary: sec_fallback_live 相比 sec_normal_live 下降 0.000，右侧新增负向因素 none

## Warning Delta
- added_in_right: anchoring_drift: 对话后段逐渐脱离用户锚点，开始泛化。, continuity_carry_missing: continuation 信号存在，但后段缺少可见延续。, late_session_degradation: 对话后段质量相比前段明显走低。
- shared: sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。, specific_recall_weak: 面对 recall probe 时缺少稳定的具体承接。, thought_action_gap: 存在 action proposal 痕迹，但没有用户可见 reply/output。, visible_output_sparsity: 有 thought 活动，但用户可见输出偏稀疏。
