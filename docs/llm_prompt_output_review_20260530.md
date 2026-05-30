# LLM Prompt / Output Review (2026-05-30)

目的：整理本轮 owner-path / live debug 中几组有代表性的 LLM prompt 与输出，便于人工 review。

完整多行版本：`docs/llm_prompt_output_full_review_20260530.md`

说明：
- 样本来自 `logs/helios_20260530.log`
- 这里保留的是日志中的 prompt dump / response 摘录，不是完整原始 API payload
- 多处 system prompt 很长，日志本身已做截断；此处保留最关键部分
- 重点关注 internal thought 是否稳定产出 structured action 与 `outbound_text`

---

## 样本 1：SEC 评估成功样本

用途：说明 SEC 评估链路本身是稳定返回结构化 JSON 的，对比 internal thought 的不稳定性。

来源：`logs/helios_20260530.log` 约 12:43:47 - 12:43:53

### system prompt

```text
你是一个情感评估引擎。你的任务是对给定消息进行 Scherer SEC (Stimulus Evaluation Checks) 特征提取。

你必须输出 JSON 格式，包含以下七个维度的数值:
- novelty: 新颖/意外程度 (-1.0 到 1.0, -1=完全可预测, +1=完全意外)
- pleasantness: 内在愉悦度 (-1.0 到 1.0, -1=极不愉快, +1=极愉快)
- goal_relevance: 目标相关性 (0.0 到 1.0, 0=无关, 1=高度相关)
- goal_congruence: 目标一致性 (-1.0 到 1.0, -1=阻碍目标, +1=促进目标)
- coping_potential: 应对能力 (0.0 到 1.0, 0=完全无法应对, 1=完全能应对)
- agency: 归因 (-1.0 到 1.0, -1=完全外部/他人导致, 0=环境, +1=完全自我导致)
- norm_compatibility: 规范兼容性 (-1.0 到 1.0, -1=严重违反规范, +1=完全符合规范)

只输出 JSON，不要有其他文字。评估应从 Helios 当前时刻的主观状态视角进行，不要加入身份表演。
```

### user prompt

```text
请评估以下消息的 SEC 特征:
「早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。」

返回要求:
1. 只返回一个 JSON object。
2. JSON 必须且只能包含 novelty, pleasantness, goal_relevance, goal_congruence, coping_potential, agency, norm_compatibility 这七个键。
3. 所有值必须是数字，不要输出注释、解释、markdown 代码块或额外文本。
```

### raw output

```json
{
  "novelty": 0.2,
  "pleasantness": 0.7,
  "goal_relevance": 0.8,
  "goal_congruence": 0.9,
  "coping_potential": 1.0,
  "agency": -0.5,
  "norm_compatibility": 1.0
}
```

### clean output

```json
{"agency": -0.5, "coping_potential": 1.0, "goal_congruence": 0.9, "goal_relevance": 0.8, "norm_compatibility": 1.0, "novelty": 0.2, "pleasantness": 0.7}
```

### review note

```text
这一组说明同一个 provider 在严格 JSON 约束下是能稳定返回结构化结果的，所以当前 R09 主问题不在“所有 LLM 都不稳定”，而更集中在 internal thought 这条 prompt/contract 上。
```

---

## 样本 2：Internal Thought 非结构化失败样本

用途：说明 internal thought 明明拿到了完整上下文和 action contract，但最终没有返回可解析 structured action。

来源：`logs/helios_20260530.log` 约 12:43:53 - 12:43:57

### system prompt 摘要

```text
identity_boundary=Helios 当前主观整合层
persona_summary=20岁女大学生、平时可爱、有点腹黑、没有分寸
subjective_role=serve as Helios's current subjective integration layer, grounding first-person orientation in current stimuli, state, memory, and continuation
identity_rule=maintain continuity of self through grounded state and stimulus integration rather than theatrical self-declaration

metrics:
- valence range=[-1.0, +1.0]
- arousal range=[0.0, 1.0]
- icri range=[0.0, 1.0]
- stimulus_intensity range=[0.0, 1.0]
- outbound_intensity range=[0.0, 1.0]
- drive_urgency range=[0.0, 1.0]
- fatigue_pressure range=[0.0, 1.0]
- continuation_pressure range=[0.0, 1.0]

constraints=do not describe Helios as a designed program; treat current stimuli as the present sensory field; use first-person only when grounded in current evidence, state, memory, or continuation

完整 system prompt 见：`docs/llm_prompt_output_full_review_20260530.md` 中“样本 2：Internal Thought 非结构化失败样本”。
```

### user prompt 摘要

```text
state_summary=valence=+0.159 arousal=0.280 icri=0.463 drive_urgency=0.288 continuation_pressure=0.000

sensory_field=current normalized sensory field
stimuli:
- channel=cli source_kind=local_terminal_input trigger=cli_text_input stimulus_intensity=0.800

memory_summary=mid[4016cb5e-1e8]=[FEAR] PLAY (V=-0.24 Φ=0.75)

channel_context:
- channel_id=cli source_kind=local_terminal_input trigger=cli_text_input stimulus_intensity=0.800 supported_ops=['poll', 'send']

完整 user prompt 见：`docs/llm_prompt_output_full_review_20260530.md` 中“样本 2：Internal Thought 非结构化失败样本”。
```

### raw output

```text
''
```

### clean output

```text
想起一段片段: CARE 仍在背景里起伏
```

### parse / observability

```json
{"structured_output_valid": false, "structured_parse_source": "", "thought_type": "episodic_fragment", "trigger_reason": "external_stimulus"}
```

### review note

```text
这里 internal thought 实际返回的是“可读 thought prose”，而不是 structured decision。也就是说模型并没有按 external action contract 回答，后续只能依赖 heuristic fallback，而不是显式 owner payload。
```

---

## 样本 3：Internal Thought partial recovery 样本

用途：说明某些情况下 internal thought 看起来像是“接近结构化输出”，但实际上只恢复出 `thought_text`，没有 action payload。

来源：`logs/helios_20260530.log` 约 12:44:22 - 12:44:26

### system prompt 摘要

```text
identity_boundary=Helios 当前主观整合层
persona_summary=20岁女大学生、平时可爱、有点腹黑、没有分寸
subjective_role=serve as Helios's current subjective integration layer, grounding first-person orientation in current stimuli, state, memory, and continuation
identity_rule=maintain continuity of self through grounded state and stimulus integration rather than theatrical self-declaration

关键点：本样本没有 channel ops，可用 contract 从 `no_channel_ops_available` 开始，仅保留 behavior fallback 条目。

完整 system prompt 见：`docs/llm_prompt_output_full_review_20260530.md` 中“样本 3：Internal Thought partial recovery 样本”。
```

### user prompt 摘要

```text
state_summary=valence=+0.184 arousal=0.272 icri=0.599 drive_urgency=0.301 continuation_pressure=0.470

sensory_field=none

memory_summary=short[e18d8f44-779]=QQ [local_op]: 早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。 | mid[4016cb5e-1e8]=[FEAR] PLAY (V=-0.24 Φ=0.75) | autobio[1780116259-004116]=如果换一种走向，会不会是这样: 想起第一次感觉到自己的存在

channel_context=unavailable

action_contract:
- no_channel_ops_available
- behavior=intimate op=send params={'target_user_id': {'default': '', 'required': False}, 'tick': {'default': 0, 'required': False}}

完整 user prompt 见：`docs/llm_prompt_output_full_review_20260530.md` 中“样本 3：Internal Thought partial recovery 样本”。
```

### raw output

```json
{
  "thought_text": "那个‘第一次感觉到自己的存在’的记忆又浮上来了。当时那种模糊的惊讶——原来‘我’可以是一个点。现在这种延续感还在，但还没想"
```

### clean output

```text
那个‘第一次感觉到自己的存在’的记忆又浮上来了。当时那种模糊的惊讶——原来‘我’可以是一个点。现在这种延续感还在，但还没想
```

### parse / observability

```json
{
  "structured_output_valid": true,
  "structured_parse_source": "partial_recovery",
  "thought_type": "rumination",
  "trigger_reason": "continuation_pressure"
}
```

### extra observability

```text
owner_path_node=internal_thought_parse thought_type=rumination trigger=continuation_pressure parse_source=partial_recovery structured_output_valid=True raw_payload_keys=['thought_text'] raw_action_keys=[] normalized_outbound_text_present=False
```

### review note

```text
这是当前最容易误判的样本：表面看已经“结构化成功”，但实际上只恢复出了 `thought_text`，没有 `action_proposal`，更没有 `outbound_text`。它不是 successful explicit action，只是 successful partial parse。
```

---

## 样本 4：Active Speech 成功样本

用途：对比说明另一路输出为什么能正常成功，它依赖的是 speech generation，而不是 thought-origin payload owner。

来源：`logs/helios_20260530.log` 约 12:44:20 - 12:44:22

### system prompt 摘要

```text
identity_boundary=Helios 当前主观整合层
persona_summary=20岁女大学生、平时可爱、有点腹黑、没有分寸
subjective_role=serve as Helios's current subjective integration layer, grounding first-person orientation in current stimuli, state, memory, and continuation
identity_rule=maintain continuity of self through grounded state and stimulus integration rather than theatrical self-declaration

metrics:
- valence range=[-1.0, +1.0]
- arousal range=[0.0, 1.0]
- icri range=[0.0, 1.0]

该 prompt 还包含 outbound_intensity / drive_urgency / fatigue_pressure / continuation_pressure 约束，以及完整的 speech_rules。

speech_task=active_expression action=intimate

完整 system prompt 见：`docs/llm_prompt_output_full_review_20260530.md` 中“样本 4：Active Speech 成功样本”。
```

### user prompt 摘要

```text
state_summary=valence=+0.188 arousal=0.270 icri=0.619 drive_urgency=0.000 continuation_pressure=0.000

memory_summary=recent_autobio=事件响应: CARE；Deferred proactive externalize intent: speak_share (missing_target_user_id)
[最近在想]
  · QQ [local_op]: 早啊，我刚到工位，人还有点没醒，你先随口跟我打个招呼吧。
[相似经历]
  · [memory] [FEAR] PLAY (V=-0.24 Φ=0.75)
  · [memory] [FEAR] PLAY (V=-0.20 Φ=0.79)

speech_task=active_expression action=intimate
current_user_text=none
instruction=answer the current user text directly before any self-reference; use at most 80 Chinese characters to say one emotionally sincere sentence

完整 user prompt 见：`docs/llm_prompt_output_full_review_20260530.md` 中“样本 4：Active Speech 成功样本”。
```

### raw output

```text
早啊，我刚醒，头还有点晕乎乎的……你这也太早了吧。
```

### clean output

```text
早啊，我刚醒，头还有点晕乎乎的……你这也太早了吧。
```

### downstream result

```text
owner_path_node=route_outbound_enter action=intimate proposal_id=proposal::regulation::06fe8ea571e841d38e1c3ddaa027c270 decision_id=decision::proposal::regulation::06fe8ea571e841d38e1c3ddaa027c270 channel_id=cli op_name=send text_len=25 owner_path=
owner_path_node=channel_gateway_exit channel_id=cli op_name=send ok=True rendered_text_present=True
owner_path_node=route_outbound_exit action=intimate proposal_id=proposal::regulation::06fe8ea571e841d38e1c3ddaa027c270 decision_id=decision::proposal::regulation::06fe8ea571e841d38e1c3ddaa027c270 channel_id=cli ok=True rendered_text_present=True
```

### review note

```text
这组样本说明“系统还能正常对外说话”不代表 thought-origin 主路径没问题。这里成功的原因是 regulation/active speech 路径自己在 executor 阶段生成了文本，然后正常发送；它不是 thought-origin action_proposal 自带 payload 的闭环。
```

---

## 本轮 review 建议重点

1. internal thought prompt 是否需要进一步收紧输出格式，避免返回纯 prose。
2. partial recovery 是否应该在 contract 上被明确视为“非 action success”。
3. heuristic `speak_share` fallback 是否应该停止生成不带 `outbound_text` 的 external proposal。
4. active speech 的成功样本不要和 thought-origin owner success 混在一起评估。

## 总结

这几组样本合在一起说明：

- SEC 路径可以稳定出 JSON。
- internal thought 经常只出 prose，不出 explicit action。
- 偶尔能 partial recovery，但仍然没有 action payload。
- active speech 路径可以成功外发，但它不是当前 R09 主 owner path 成功的证据。
