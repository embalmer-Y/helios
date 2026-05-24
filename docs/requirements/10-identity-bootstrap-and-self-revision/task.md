# Requirement 10 - Identity Bootstrap and Self-Revision

## 1. Task Breakdown

### T10-1 定义 identity store 与 revision record
1. 定义持久化结构。
2. 区分普通运行配置与身份核心配置。
3. 增加最小测试样例。

### T10-2 实现 bootstrap 流程
1. 明确首启检测。
2. 完成 identity seed 注入。
3. 写入 initialized 标记。

### T10-3 实现 post-bootstrap lock
1. 阻止后续普通配置覆盖核心身份。
2. 补充错误与 observability。
3. 清理旧直接覆写路径。

### T10-4 接入 self-revision governance
1. 让 thought result 可输出 self-revision proposal。
2. 新增治理校验与审计流程。
3. 写入 revision history。

### T10-5 更新 prompt identity contract 与测试
1. 让 prompt 只从 identity store + governance 后状态生成。
2. 清除旧不合规 identity 文案。
3. 补齐启动与重启测试。

## 2. Dependencies

1. 依赖 R07 的 thought result owner。
2. 与 memory seed、personality state 和 prompt contract 强耦合。

## 3. Files and Modules

1. `personality.py`
2. `personality_contract.py`
3. `memory/seed_memory_importer.py`
4. `helios_main.py`
5. `cognition/thinking_integration.py`
6. future identity governance module
7. `tests/`
8. `data/`

## 4. Implementation Order

1. T10-1
2. T10-2
3. T10-3
4. T10-4
5. T10-5

## 5. Validation Plan

1. 首轮验证 identity store。
2. 第二轮验证 bootstrap idempotence。
3. 第三轮验证 post-bootstrap lock。
4. 第四轮验证 self-revision governance。

## 6. Completion Criteria

1. 首启 bootstrap 已正式化。
2. bootstrap 后用户无法直接改写 identity。
3. self-revision proposal 已受控落地。
4. revision history 与审计完成。
