# M1-T1: AspectState 向量实证(TASK + 验收)

> **任务**:M1-T1 ship 任务清单
> **完成时间**:2026-06-28

## 1. ship 任务清单

| Task ID | 任务 | 状态 |
|---|---|---|
| T1-1 | `helios_v2/src/helios_v2/research_v3_m1/__init__.py` | ✅ |
| T1-2 | `aspect_state.py` AspectState dataclass + 3 fixture + 3 is_* 方法 | ✅ |
| T1-3 | `projections.py` v2 owner 投影 | ✅ |
| T1-4 | `test_aspect_state.py` 10+ 单元测试 | ✅ |
| T1-5 | `test_projections.py` 6+ 投影测试 | ✅ |
| T1-6 | `r_v3_m1_t1_probe.py` 真实 LLM probe | ✅ |

## 2. 验收门

1. v2 baseline 100% passed
2. M1-T1 新增 ≥ 10 单元测试 100% passed
3. 3 fixture 在 AspectState 形式下两两可区分
4. 3 fixture 在 v1 标量形式下区分度 < 0.1
5. to_llm_text() < 200 字符
6. frozen 不可变
7. 真实 LLM probe 1 个跑通

## 3. 执行步骤(terminal 启用后)

```bash
cd d:\Software\project\helios
pytest helios_v2/tests/research_v3_m1/ -v
python -m helios_v2.scripts.r_v3_m1_t1_probe --model deepseek-v4-pro
git add helios_v2/src/helios_v2/research_v3_m1/ \
        helios_v2/tests/research_v3_m1/ \
        helios_v2/scripts/r_v3_m1_t1_probe.py \
        helios_v2/logs/r_v3_m1/ \
        helios_v2/docs/requirements/research-v3-m1-t1-aspect-state/
git commit -m "research(R-PROTO-LEARN.v3-m1-t1): ship AspectState 10+ field vector + v2 owner projections"
git push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
```
