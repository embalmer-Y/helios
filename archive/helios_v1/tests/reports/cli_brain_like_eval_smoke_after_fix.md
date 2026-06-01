# CLI Brain-Like Evaluation Report - 10-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_10min_v1
- Interaction mode: mixed
- Duration: 5s
- Samples: 4
- Total score: 0.453

## Dimension Scores
- 情感反应类人度: 0.067
  - evidence: dominant present ratio=0.00
  - evidence: valence span=0.000
  - evidence: mood diversity=1
  - notes: 更关注情感是否随刺激变化，而不是固定中性输出。
- 语言表达自然度: 0.15
  - evidence: 没有 assistant transcript lines。
  - notes: 第一版评分降级，等待真实 CLI transcript 补齐。
- 情感模块工作状态: 0.6
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.00
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.5
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.00
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 0.68
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=0 fail=0

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 本次 transcript 为空或缺少 assistant side output，语言自然度评分可信度有限。
