# V2.1 卡死诊断

> 2026-05-20 · 22h 存活但仅 21min 产出

## 症状

```
PID 61380: 存活 22h03min, 状态 S (sleeping), wchan=do_sys
日志: 462 行, 最后修改 01:32 (21min 后停止)
最后输出: cycle 352-362 之间的 LLM 调用
心跳: 最后一次 00:20, 之后无任何输出
```

## 数据画像 (21min)

| 指标 | V2.1 |
|------|------|
| LLM 调用 | 118 次 (0 失败) |
| Φ 范围 | **0.08 → 0.55** (比 V1 的 0.50-0.53 好) |
| Φ 峰值 | 0.55 (despair_crash 事件) |
| JSON 回退 | 27% |
| 事件追踪 | ~15 种事件 |

## 最可能根因

### 假说 1: LLM API 调用挂死 (概率 70%)
- `client.chat.completions.create(timeout=40)` — timeout 可能不生效
- 底层 httpx/requests 在 TCP 层面卡死
- 心跳最后一次在 LLM 调用后 `time.sleep()` 中

### 假说 2: 子循环死锁 (概率 20%)
- `emotion_engine.cycle()` 或 `thinking_mgr.generate_thoughts()` 
- 可能在某个内部循环中不退出

### 假说 3: Python GIL / 信号处理 (概率 10%)
- SIGINT handler 或其他信号导致主线程挂起

## 修复方案

1. **LLM 调用加超时 wrapper**: `concurrent.futures.ThreadPoolExecutor(timeout=45)`
2. **主循环心跳警卫**: 每 100 次迭代检查 `time.time() > last_output + 120`
3. **添加 watchdog 线程**: 独立监控主循环活跃度
4. **减少单次 sleep 时间**: 0.3s 代替 2-5s, 用迭代次数控制速率
