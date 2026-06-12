# 人类记忆系统综述 - 计算模型层

> **来源**：Modern Hopfield Networks (Ramsauer 2020), Kanerva SDM (1988, 1993), Memory Networks (Weston 2014), Neural Turing Machines (Graves 2014), Differentiable Neural Computer (Graves 2016), RETRO (Borgeaud 2021), Memorizing Transformers (Wu 2022), RAG (Lewis 2020), Compressive Transformer (Rae 2020), MemGPT (Packer 2023), MemoryBank (Zhong 2024), A-MEM (Weng 2025)

## 1. 经典计算模型

### 1.1 Hopfield Network (Hopfield 1982)
- **机制**：全连接二值网络，记忆是能量极小点
- **容量**：~0.14N (N=神经元数) — 极小
- **检索**：异步更新收敛到最近记忆
- **问题**：容量小、易受伪记忆干扰

### 1.2 Modern Hopfield Networks (Ramsauer 2020 "Hopfield Networks is All You Need")
- **关键洞察**：把 Hopfield 网络的能量函数改成 log-sum-exp → 变成 attention 公式
- **容量**：**指数级** (与 hidden dim 有关)
- **检索**：相当于 transformer attention
- **含义**：**Transformer 本身就是一种现代 Hopfield 网络**
- **意义**：为基于 attention 的 memory 提供了理论基础

### 1.3 Kanerva SDM (Sparse Distributed Memory, Kanerva 1988)
- **机制**：高维空间中的稀疏访问点
- **容量**：N! / (N-k)! (k=激活数)
- **特性**：Hamming 距离 → 内容寻址；天然支持联想
- **应用**：Pentium 处理器 cache 启发 (Tezarr 1990)

### 1.4 Memory Networks (Weston 2014, Sukhbaatar 2015 "End-To-End Memory Networks")
- **结构**：4 模块 (I: input / G: generalize / O: output / R: response)
- **机制**：显式 memory slots + attention over slots
- **应用**：QA、对话

### 1.5 Neural Turing Machine (Graves 2014) / DNC (Graves 2016)
- **结构**：神经网络 + 外部 memory matrix
- **读写头**：content-based + location-based
- **机制**：可微分读写，类似操作系统分页
- **应用**：算法学习、图推理

## 2. Transformer 时代的记忆扩展

### 2.1 朴素扩展 = 增大 context window
- **早期**：512 tokens (BERT), 1024 (GPT-2), 2048 (GPT-3)
- **当前**：128K (GPT-4), 200K (Claude), 1M (Gemini 1.5)
- **根本限制**：
  - 平方复杂度 O(N²) — 100K context 要 10T ops
  - "Lost-in-the-Middle" 现象 (Liu 2023) — 中间信息被忽略
  - **不能持久化**（每次 session 重建）

### 2.2 RETRO (DeepMind 2021, Borgeaud)
- **结构**：base LM + retrieval encoder + 跨注意力
- **机制**：每 N 个 token 检索一次，跨注意力融合
- **结果**：7.5B 模型 + RETRO 匹敌 25B 模型
- **关键**：**检索嵌入到架构里**，不是外挂
- **对 Helios 启发**：R10 + LLM 应该是深度耦合，不是简单的"查表后塞 context"

### 2.3 Memorizing Transformers (Wu 2022)
- **结构**：在 self-attention 里加 kNN lookup
- **机制**：self-attention 注意力分两部分 = (1) context tokens (2) 检索到的外部 past kv-pairs
- **结果**：12K context 实际表现像 65K
- **对 Helios 启发**：**R10 检索结果应该是"额外 attention head"**，而不是"塞进 system prompt"**

### 2.4 RAG (Lewis 2020)
- **结构**：retriever + generator，分两阶段
- **机制**：query → embed → top-k → 塞进 prompt → 生成
- **优势**：简单、模块化
- **劣势**：**检索与生成解耦**（生成器不能反过来影响检索）
- **Helios 当前 ≈ RAG**

### 2.5 Compressive Transformer (Rae 2020)
- **结构**：把过去 context 压缩成粗粒度记忆
- **机制**：旧 context 用更少 tokens 表示
- **结果**：可处理比训练长 4-7 倍的序列
- **对 Helios 启发**：**work memory 应该压缩**，而不是全量塞 LLM

### 2.6 MemGPT (Packer 2023, "Virtual Context Management")
- **结构**：LLM 操作系统化
- **机制**：
  - main context (= RAM) — 当前 LLM 看得到
  - external context (= disk) — 检索得到
  - LLM 自己调用 `recall()` / `archival_memory_search()` / `write_to_memory()`
  - 工具调用决定什么时候把什么搬出/搬入 main context
- **关键**：**LLM 主动管理自己的记忆**
- **对 Helios 启发**：**Helios 应该是"LLM 操作系统"**——R10/R15 都是 LLM 主动调用的工具

### 2.7 MemoryBank (Zhong 2024, 清华)
- **结构**：long-term memory + 短期 + 反思机制
- **机制**：
  - 短期 → 长期：Ebbinghaus 遗忘曲线 + 重要性权重
  - 长期 → 短期：检索时根据 context 调整权重
  - **AI 主动反思**：每 N 轮 LLM 自动"回顾" → 提炼 insights
- **对 Helios 启发**：**遗忘曲线 + 反思机制**是双线方案的具体化

### 2.8 A-MEM (Agentic Memory, Weng 2025)
- **结构**：每条记忆有动态生成的结构化 notes (tags, context, keywords)
- **机制**：
  - 新记忆进来时，LLM 生成结构化 notes
  - 检索时用 notes 做 cross-link
  - **Zettelkasten 风格**：每条记忆主动创建链接
- **对 Helios 启发**：**记忆应该有"自描述"层**（不只是 raw text）

## 3. 关键计算机制总结

| 模型 | 关键机制 | 对应人脑 | Helios 现状 |
|---|---|---|---|
| Hopfield / Attention | 内容寻址 | 海马索引 | ✅ LLM attention |
| Kanerva SDM | 稀疏高维 | 神经稀疏编码 | 部分（embedding）|
| Memory Net | 显式 slots + attention | 工作记忆 | ⚠️ R79-D framework |
| NTM/DNC | 读写头 | 海马写入/读取 | ⚠️ R10/R15 有，但弱 |
| RETRO | 嵌入架构 | 海马-皮层 | ❌ 当前是外挂 |
| Memorizing Transformer | 检索当 attention | 联合编码 | ❌ 缺失 |
| RAG | 检索 → prompt | 海马-皮层 (粗糙版) | ✅ 当前 R10 |
| Compressive Transformer | 压缩旧 context | 工作记忆压缩 | ❌ 缺失 |
| MemGPT | LLM 主动管理记忆 | 元认知 | ❌ 缺失 |
| MemoryBank | 遗忘曲线 + 反思 | 衰减 + DMN | ❌ 缺失 |
| A-MEM | 动态自描述 | 突触标记 | ❌ 缺失 |

## 4. 关键启示

### 4.1 Helios 是"无 OS 的 RAG"

当前 = LLM + 外部 store + 简单 RAG 检索
- **没有 working memory 管理**（LLM context 是黑盒）
- **没有遗忘机制**（store 永远增长）
- **没有反思机制**（LLM 不会主动回顾）

### 4.2 MemGPT 是最接近的方向

LLM 把 memory 当 OS，自己管理 main / external context。
- **Helios 应该引入 LLM 工具调用**（recall/archival_search/write_note）
- **但当前 v3 prompt 没暴露这些工具**（LLM 不知道有这些 API）

### 4.3 MemoryBank 给出"遗忘 + 反思"配方

- 短期 → 长期：遗忘曲线 + 重要性
- 长期 → 短期：context 调制权重
- **AI 主动反思**：周期性回顾提炼

### 4.4 A-MEM 给出"自描述"配方

- 记忆有结构化 notes（tags/context/keywords）
- 新记忆进来时主动 cross-link
- **Helios 当前记忆是 raw 文本 + embedding**——没有中间层

## 5. 关键设计原则（综合）

1. **多时间尺度**：短期/中期/长期/自传体 4 层（不是 1 层 store）
2. **衰减与重塑**：时间维度的动态变化（不是写进去就不变）
3. **LLM 主动管理**：记忆是 LLM 的工具，不是 LLM 的"输出参数"
4. **结构化与自描述**：每条记忆有"自描述"（不只是 raw 文本）
5. **反思与巩固**：周期性后台任务（不是每次 tick 同步处理）
6. **检索-生成深度耦合**：不只是塞 prompt，是 attention 级别融合
