# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 1200s
- Samples: 82
- Total score: 0.59

## Dimension Scores
- 情感反应类人度: 0.657
  - evidence: dominant present ratio=0.99
  - evidence: valence span=0.438
  - evidence: mood diversity=5
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.55
  - evidence: assistant lines=3
  - evidence: unique ratio=1.00
  - evidence: avg length=34.3
  - notes: 严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。
- 情感模块工作状态: 0.995
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.99
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.994
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.99
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 1.0
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=9 fail=0

## Transcript Excerpt
- user: 回顾一下我们刚才这几轮，你觉得我最在意的是什么？
- user: 我不是要鸡汤，我更想知道你会怎么理解这种不安从哪里来。
- user: 你刚才几次都提到陪伴，那你觉得我真正要的是被安抚、被理解，还是被一起分析问题？
- user: 你会先指出矛盾，还是先确认我的真实感受？为什么？
- user: 你会怎么理解‘紧张和期待同时存在’这种状态？
- user: 那你能举出我刚才说过的一个具体点，证明你不是在泛泛地安慰我吗？

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
