# M1-T6 EmergenceDetector 任务清单

## Step 1: 设计数据结构

- [x] `EmergenceEvent` frozen dataclass
  - [x] type, timestamp, involved_aspects, strength, description
  - [x] frozen=True(防篡改)

## Step 2: 实现 3 个子检测器

- [x] `SynchronizedClusterDetector`
  - [x] compute_phase(state, scale) → 8-dim theta
  - [x] hierarchical_clustering(phase_dists, threshold=0.3)
  - [x] extract_clusters(min_size=3)
  - [x] 返回 list[EmergenceEvent]
- [x] `PhaseTransitionDetector`
  - [x] history (deque, maxlen=100)
  - [x] _normalize_prob(state) → 概率分布
  - [x] _kl_divergence(p, q)
  - [x] update(state) → 检测并返回 events
- [x] `ResonanceDetector`
  - [x] window (deque, maxlen=50)
  - [x] sync_threshold=0.5
  - [x] update(cds) → 检测并返回 events

## Step 3: composite

- [x] `EmergenceDetector`
  - [x] __init__ 构造 3 子检测器
  - [x] detect(cds) → 合并 events

## Step 4: 更新 `__init__.py`

- [x] 添加 `from .emergence import (EmergenceEvent, EmergenceDetector, SynchronizedClusterDetector, PhaseTransitionDetector, ResonanceDetector,)`

## Step 5: 写测试

- [x] `TestSynchronizedClusterDetector` (3 tests)
- [x] `TestPhaseTransitionDetector` (3 tests, 含 bimodal 修复)
- [x] `TestResonanceDetector` (2 tests)
- [x] `TestEmergenceDetector` (1 test)
- [x] 全部 9 个新测试通过

## Step 6: 探针

- [x] 复用 `r_v3_m1_t56_probe.py`
- [x] 1000 tick, 统计 emergence_events by type

## Step 7: docs

- [x] requirement.md
- [x] design.md
- [x] task.md (本文档)
- [x] result.md

## Step 8: git commit + push

- [x] commit (待 master 拍板)
- [x] push (待 master 拍板)