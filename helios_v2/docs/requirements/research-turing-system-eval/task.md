# Task — Helios v2 System-Level Turing Evaluation

## T1 (this file) — requirement + design + task 三件套 ✅
- [x] requirement.md: 10 axes, 1000+ ticks, dual-track judge, anti-theatrical aggregation
- [x] design.md: architecture, 10-block stimuli corpus, 10-axis rubric, implementation files
- [x] task.md: this checklist

## T2 — 小黑 评审 ground truth rubric + approve (阻塞 T3)
- [ ] 10 axes scoring criteria (D1-D10) approved by 小黑
- [ ] Stimuli corpus (10 blocks × 6-8 scenarios) reviewed by 小黑
- [ ] Spot-check sampling strategy confirmed (10% of 72 scenarios = ~7-8)
- [ ] Anti-theatrical aggregation thresholds approved (pass=0.8, dim=0.6, collapse=0.3)

## T3 — 1000+ tick 真实 LLM 系统级跑
- [ ] stimuli.jsonl generator: 10 blocks × 6-8 scenarios × ~13 sub-ticks = 1000+ stimuli
- [ ] system runner: drives helios_v2 with R85 4L memory + R97/R98 + R-PROTO-LEARN 5 algo
        + P5-A.2 RealRPE + 17 owner learners (Tier 1-4), captures full TickRecord per tick
- [ ] checkpoint every 50 ticks (可恢复)
- [ ] LLM call retry 3× + skip on fail
- [ ] 8h hard limit safety: emit `partial:True` if reached
- [ ] 整库 regression sanity check (no source code change so should be no-op)

## T4 — 10-axis evaluation
- [ ] INTERNAL axes (D2, D3, D4, D5, D8, D10) auto-score from runtime provenance
- [ ] BEHAVIOR axes (D1, D6, D7, D9) LLM-judge + scoring criteria matching design.md
- [ ] Anti-theatrical aggregation: 0.8 pass line + both-dim ≥0.6 + any-axis-collapse <0.3
- [ ] Provenance strings required for every axis
- [ ] Verdict emitted to verdict.json

## T5 — 小黑 10% spot-check review
- [ ] 7-8 sampled scenarios reviewed by 小黑
- [ ] Final human_override scores locked
- [ ] Final aggregate recomputed with overrides

## T6 — result.md report
- [ ] 10-axis per-axis score + provenance + human override
- [ ] Anti-theatrical aggregation result
- [ ] Verdict + 解读
- [ ] Improvement priorities (per-axis < 0.6 → what to fix in next iteration)
- [ ] Reproducibility note: stimuli.jsonl SHA-256 + verdict.json SHA-256

## T7 — 整库 regression check
- [ ] tests/ -q should still pass (no source code change; only scripts + data)
- [ ] r_proto_learn tests should still pass (no source code change)

## T8 — commit + push
- [ ] git add scripts/ + data/ + docs/
- [ ] git commit "research(turing-system-eval): 1000+ tick 10-axis evaluation"
- [ ] git push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
- [ ] 铁律: 调研分支永不 merge main

## T9 — 完整报告给小黑
- [ ] 全部 10 轴分数 + TuringVerdict
- [ ] 改进优先级 (P5-B / P5-C / P5-D 等下一步建议)
- [ ] 调试用 raw trace 路径 (小黑白可以抽样审)
