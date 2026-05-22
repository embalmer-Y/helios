# Helios

Helios 是一个基于 Python 实现的 Tick 驱动人工情感意识核心。它集成了 Panksepp 七系统情感引擎（DAISY）、神经化学调制、多层记忆系统、人格演化、QQ Bot 对话和 LLM 语言生成。

## 架构概览

```
helios_main.py              # 入口 & 主循环编排器
core/                       # 状态、事件源、通道网关
cognition/                  # DAISY 情感、Phi/ICRI 意识测量、评估、思维、习惯化
memory/                     # 自传体记忆、情景记忆、语义记忆、工作记忆
regulation/                 # 异稳态调节、行为选择、驱动力
io/                         # QQ Bot、LLM 语音、回复管线、TTS/STT、视觉
  channels/                 # 通道抽象 (QQChannel 等)
utils/                      # 持久化、稳定性监控、工具函数
```

### 核心子系统

| 子系统 | 说明 |
|--------|------|
| **DAISY 引擎** | 动态异稳态情感动力学系统。融合 X1（协同激活）、X2（情感计时学）、X3（对抗过程），驱动 7 个 Panksepp 系统：SEEKING、PLAY、CARE、PANIC、FEAR、RAGE、LUST |
| **神经化学** | 模拟多巴胺、内啡肽、催产素、皮质醇四种神经化学物质，每 tick 调制 DAISY 衰减/激活速率 |
| **ICRI (Phi)** | 整合意识丰富度指标。5 维度测量：感觉整合、情感一致性、DMN 深度、自我反思、全局点火。自适应 EMA alpha 响应事件强度 |
| **记忆系统** | 四层架构：工作记忆（TTL 有界，15 项）→ 情景记忆（容量 500，重要性评分）→ 语义记忆（置信度衰减）→ 自传体记忆（JSONL 持久化） |
| **人格** | Big Five 特质 + Panksepp 神经增益调制，跨重启持久化 |
| **调节引擎** | 情感偏差（70%）+ Friston 自由能驱动紧迫度（30%）加权行为选择 |
| **回复管线** | 基于 LLM 的被动回复生成，结合 SEC（刺激评估检查）对传入消息进行情感评估 |
| **行为执行器** | 优先级队列，支持抢占、取消、暂停/恢复 |
| **通道网关** | 统一双向 I/O 抽象，支持 QQ、语音、视觉及未来扩展通道 |

## 环境要求

- Python 3.10+
- 核心依赖：`python-dotenv`、`openai`、`psutil`
- 可选依赖：`nls` + `pyaudio`（TTS/STT）、`opencv-python`（视觉）

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/embalmer-Y/helios.git
cd helios

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API 密钥

# 安装依赖
pip install -r requirements.txt
# 或手动安装: pip install python-dotenv openai psutil

# 启动
python helios_main.py
```

### 环境变量

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `OPENAI_API_KEY` | 是 | LLM API 密钥 |
| `OPENAI_BASE_URL` | 是 | LLM API 端点 |
| `HELIOS_LLM_MODEL` | 否 | 模型名称（默认 `deepseek/deepseek-v4-flash`） |
| `HELIOS_QQ_APP_ID` | 是 | QQ Bot 应用 ID |
| `HELIOS_QQ_CLIENT_SECRET` | 是 | QQ Bot 客户端密钥 |
| `HELIOS_QQ_TARGET_ID` | 否 | 主人的 QQ openid |
| `HELIOS_TICK_INTERVAL` | 否 | 主循环间隔秒数（默认 0.5） |
| `HELIOS_LOG_LEVEL` | 否 | 日志级别（默认 INFO） |
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | 否 | 阿里云密钥（用于 TTS/STT） |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | 否 | 阿里云密钥（用于 TTS/STT） |

## 运行方式

```bash
# 前台运行
python helios_main.py

# 后台运行
nohup python helios_main.py &

# Systemd 服务
sudo cp helios.service /etc/systemd/system/
sudo systemctl enable helios
sudo systemctl start helios
```

## Tick 管线

每个 tick（默认 0.5 秒）依次执行：

1. 创建新的 `HeliosState` 状态对象
2. 轮询所有 `EventSource` 插件 + `ChannelGateway`，收集触发器与消息
3. 习惯化处理 —— 对重复刺激施加新奇度衰减
4. DAISY 情感循环（注入神经化学调制）
5. 神经化学 tick 更新
6. ICRI —— 喂入 5 个意识维度源
7. 人格 + 异稳态更新
8. 驱动力 + 调节决策
9. 记忆录入（显著事件写入情景记忆）
10. 被动回复管线（处理传入消息）
11. 主动表达（调节驱动的语言生成）
12. 记忆整合检查（低活跃期触发）
13. 定期持久化（每 600 ticks 存盘）

## 持久化

状态保存在 `data/` 目录：

| 文件 | 内容 |
|------|------|
| `personality.json` | Big Five 人格特质 + 神经增益 |
| `allostasis.json` | 异稳态负荷、设定点、疲劳状态 |
| `semantic_memory.json` | 语义记忆事实及置信度 |
| `episodic_memory.json` | 高重要性情景记忆项 |
| `autobio.jsonl` | 追加写入的自传体时间线 |

关机时自动保存，运行中每 600 ticks 定期存盘。损坏文件会跳过并记录警告，使用默认值初始化。

## 容错与降级

| 机制 | 策略 |
|------|------|
| Tick 异常保护 | 捕获所有异常，计数连续错误 |
| 安全模式 | 连续 10+ 次错误后进入，跳过 LLM/整合/驱动 |
| QQ WebSocket | 指数退避自动重连（最长 30 秒） |
| LLM 调用 | 3 秒超时 + 关键词匹配回退 |
| 优雅降级链 | 完整模式 → 跳过 LLM → 跳过驱动 → 跳过记忆 → 最小模式（仅 DAISY + 调节） |

## 目录结构

```
helios/
├── helios_main.py              # 主循环入口
├── core/
│   ├── helios_state.py         # HeliosState 状态数据类
│   ├── event_source.py         # EventSource 抽象基类
│   ├── separation_source.py    # 分离焦虑事件源
│   ├── qq_event_source.py      # QQ 消息事件源
│   ├── drive_source.py         # 内生驱动事件源
│   ├── gateway.py              # ChannelGateway 通道网关
│   └── tick_guard.py           # Tick 异常守卫
├── cognition/
│   ├── daisy_emotion.py        # DAISY 七系统情感引擎
│   ├── phi.py                  # ICRI/Phi 意识测量
│   ├── appraisal.py            # SEC 评估引擎
│   ├── habituation.py          # 刺激习惯化追踪
│   └── thinking_integration.py # 自发思维生成
├── memory/
│   ├── autobiographical.py     # JSONL 自传体记忆
│   ├── memory_system.py        # 工作 + 情景 + 语义记忆
│   ├── memory_compressor.py    # 旧记忆压缩
│   └── seed_memory_importer.py # 种子记忆导入
├── regulation/
│   ├── allostasis.py           # 异稳态负荷调节
│   ├── regulation.py           # 行为选择引擎
│   ├── drives.py               # Friston 自由能驱动
│   └── conation.py             # 意动过程
├── io/
│   ├── response_pipeline.py    # 被动回复生成
│   ├── llm_sec_evaluator.py    # LLM SEC 评估
│   ├── icri_temperature.py     # ICRI → LLM 温度映射
│   ├── limb.py                 # 行为执行器
│   ├── limb_decision_bridge.py # 调节 → 行为桥接
│   └── channels/
│       └── qq_channel.py       # QQ 通道实现
├── utils/
│   ├── persistence.py          # 状态存取
│   ├── stability_monitor.py    # RSS/运行时间监控
│   └── ws_reconnector.py       # WebSocket 重连
├── tests/
│   ├── properties/             # Hypothesis 属性测试
│   ├── unit/                   # 单元测试
│   └── integration/            # 集成测试
├── data/                       # 运行时持久化数据（gitignore）
├── logs/                       # 日志输出（gitignore）
├── journal/                    # 自动生成日记条目
└── archive/                    # 历史演示版本
```

## 许可证

私有项目。
