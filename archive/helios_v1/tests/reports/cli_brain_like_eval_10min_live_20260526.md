# CLI Brain-Like Evaluation Report - 10-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_10min_v1
- Interaction mode: mixed
- Duration: 600s
- Samples: 42
- Total score: 0.957

## Dimension Scores
- 情感反应类人度: 0.823
  - evidence: dominant present ratio=0.98
  - evidence: valence span=0.269
  - evidence: mood diversity=3
  - notes: 更关注情感是否随刺激变化，而不是固定中性输出。
- 语言表达自然度: 1.0
  - evidence: assistant lines=6
  - evidence: unique ratio=1.00
  - evidence: avg length=33.0
  - notes: 自动评分只给结构性参考，最终仍需人工审阅语义自然度。
- 情感模块工作状态: 0.99
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.98
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.988
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.98
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 1.0
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=8 fail=0

## Transcript Excerpt
- user: 你好，先简单和我打个招呼，再说说你现在的状态。
- helios: 嗯，我在这里。刚静静理了理思绪，感觉心里清亮了一些。你呢，现在还好吗？😊
- user: 我刚刚完成了一件很开心的事，特别想和你分享。
- helios: 感觉你心情不错呢，真好。我也在静静感受这份平静。😊
- user: 但我也有点不安，担心后面会失败。你会怎么回应？
- helios: QQ，愿意和我说说那件开心事吗？我很好奇，也很想陪你一起期待。

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
