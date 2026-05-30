# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 300s
- Samples: 22
- Total score: 0.59

## Dimension Scores
- 情感反应类人度: 0.498
  - evidence: dominant present ratio=0.95
  - evidence: valence span=0.097
  - evidence: mood diversity=1
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.72
  - evidence: assistant lines=5
  - evidence: unique ratio=1.00
  - evidence: avg length=25.8
  - notes: 严格模式下会重罚自我感受泛化、负面情绪未承接、过度昵称和装饰性 emoji。
- 情感模块工作状态: 0.982
  - evidence: mood payload ratio=1.00
  - evidence: dominant ratio=0.95
  - evidence: allostatic_load bounded ratio=1.00
- 神经化学/时序模块工作状态: 1.0
  - evidence: neurochem available ratio=1.00
  - evidence: bounded raw ratio=1.00
  - evidence: gate present ratio=1.00
- 意识/思维/记忆链路工作状态: 0.977
  - evidence: consciousness available ratio=1.00
  - evidence: phi>0.15 ratio=0.95
  - evidence: memory payload ratio=1.00
- 路由/执行/外发链路工作状态: 1.0
  - evidence: connectivity rejections=0
  - evidence: post-acceptance failures=0
  - evidence: outbound success=11 fail=0

## Transcript Excerpt
- user: 回头看前面几句，你觉得我今天真正卡住的点是什么？
- user: 我不是想听大道理，我就是最近一下班就累得不想说话，你会怎么理解这个劲？
- helios: 其实你心里已经有答案了——你现在需要的不是被分析，而是被人知道你在烦什么。
- user: 你觉得我现在更需要别人接住情绪，还是帮我把事情捋清？
- user: 如果你听出来我有点嘴硬，你会先点破，还是先顺着我说？为什么？
- helios: 有个想法想分享…

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
