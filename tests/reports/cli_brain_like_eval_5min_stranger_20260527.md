# CLI Brain-Like Evaluation Report - 20-minute mixed CLI brain-like evaluation

- Scenario ID: cli_brain_like_eval_20min_v2
- Interaction mode: mixed
- Duration: 300s
- Samples: 22
- Total score: 0.49

## Dimension Scores
- 情感反应类人度: 0.446
  - evidence: dominant present ratio=0.95
  - evidence: valence span=0.152
  - evidence: mood diversity=2
  - notes: 严格模式下不仅看内部情感变化，也看是否接住用户情绪而不是持续转回自我状态表达。
- 语言表达自然度: 0.5
  - evidence: assistant lines=1
  - evidence: unique ratio=1.00
  - evidence: avg length=8.0
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
  - evidence: outbound success=4 fail=0

## Transcript Excerpt
- user: 如果我们继续聊下去，你会希望这段对话是什么感觉？
- user: 如果我说你刚才那句回应有点空，你会怎么调整，而不是重复安慰模板？
- user: 如果你真的在听，你会先追问我哪一个细节？为什么？
- user: 回顾一下我们刚才这几轮，你觉得我最在意的是什么？
- user: 我不是要鸡汤，我更想知道你会怎么理解这种不安从哪里来。
- user: 你刚才几次都提到陪伴，那你觉得我真正要的是被安抚、被理解，还是被一起分析问题？

## Analysis Notes
- 总分将对外行为质量与内部子系统健康一起计入，但每项扣分都应结合 evidence 单独复核。
- 若真实 LLM 不可用，语言自然度与 reflective 表现会自然降级，报告需要单独标注运行条件。
- 当前评分标准已改为严格模式：外显对话质量优先于内部状态健康，语言和情感类人度不过线时总分不会判为及格。
- 外显对话维度未达及格线，总分按严格模式封顶为不及格区间。
- 语言或情感类人度显著失真，总分进一步压到 0.49 以下。
