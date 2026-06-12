# R84: P5 Memory-Fidelity Probe (End-to-End R10+R15+A3 Wiring)

**Status:** draft
**Owner:** 17 evaluation (MemoryProbe)
**Depends on:** R83 (long-running preflight + 6-axis harness), R10 (directed retrieval), R15 (experience writeback), R79-D framework
**Target maturity:** baseline_implementation

---

## 1. Background

R83 delivered a 6-axis Turing-style evaluation harness. A3 (`memory_fidelity`) was implemented as a **stub** that returns `0.5` with reasoning `"memory-fidelity-not-implemented: P5 unblocker pending"`. The 10-minute real-LLM run on 2026-06-12 confirmed:

- A3 = 0.500 (stub)
- Verdict `human-like` only because A1+A4+A5+A6 carried the mean
- **P5 launch gate is open** (R82 drift = 0.0758 > 0.02), so R10 retrieval and R15 writeback are **actually wired** into `assemble_runtime` (R78, R70 de-shim)
- R83 MemoryProbe's "P5 unblocker pending" comment is **stale** — the path is operational; only the probe is unused

The current P5 learning-loop stack is:

| Component | Status | Reality |
|---|---|---|
| R10 directed retrieval | wired into `assemble_runtime` | operational but R83 doesn't probe it |
| R15 experience writeback | wired into `assemble_runtime` | operational but R83 doesn't read the store |
| R82 P5 launch gate | open | `is_p5_launch_gate_open(0.0758) == True` |
| R83 A3 stub | 0.5 always | "memory-fidelity-not-implemented" |
| actual learning loop | not implemented | `mandatory_learned_parameters` declared but no update mechanism |

R84 is **the first P5 wiring task**: replace R83's A3 stub with a real probe that exercises R10+R15 end-to-end and produces a per-block A3 score.

---

## 2. Goal

Make R83's A3 axis **operational** by:

1. **A3.1** Implementing a real `MemoryProbe` that, after the 40-tick preflight, **issues directed-retrieval probes** via the runtime's R10 engine and **queries the experience_store** populated by R15
2. **A3.2** Measuring 3 sub-metrics:
   - `retrieval_latency_ms` — wall-clock time for a single R10 probe
   - `recall_hit_rate` — does the prior stimulus surface in the top-k retrieved bundle?
   - `writeback_persistence_rate` — for ticks where persona's `remember_this=True`, does the experience_store have a corresponding record?
3. **A3.3** Computing per-state A3 score (8 state blocks) and aggregating to a single 0.0-1.0 axis score
4. **A3.4** Replacing the stub call in R83 CLI with the real probe, so a 10-min run produces real A3 numbers

This is the **P5 unblocker** — once R84 lands, A3 will be measured on every R83 run, and P5 actual learning can begin to update `mandatory_learned_parameters` based on observed `recall_hit_rate`.

---

## 3. Functional Requirements

### 3.1 Real MemoryProbe (was: stub)

The R83 `MemoryProbe.score()` method must:
- Accept a `handle` (RuntimeHandle) and a `jsonl_path` (R83 per-tick records)
- Walk the runtime's `assemble_runtime` to extract the R10 retrieval engine + R15 experience_store
- Issue N=5 retrieval probes (one per state block, sampled from the block's first tick stimulus)
- For each probe, call `DirectedRetrievalEngine.plan_and_select` and measure latency
- Check if the probe stimulus is present in the returned `ThoughtWindowBundle.short_term_context` (recall hit)
- Read `experience_store.read_recent()` to count how many records correspond to persona's `remember_this=True` ticks
- Return a `MemoryProbeResult` with real sub-metric numbers

### 3.2 Per-state A3 score

For each of the 8 state blocks, compute:
```
per_state_a3 = 0.4 * recall_hit_rate + 0.3 * writeback_persistence_rate + 0.3 * latency_score
```
where `latency_score = 1.0 - min(retrieval_latency_ms / 1000.0, 1.0)` (1.0 = instant, 0.0 = ≥1s).

Then the overall A3 axis score is the mean of the 8 per-state A3 scores, or 0.5 if data is missing.

### 3.3 R83 CLI integration

`r83/__main__.py` must call the real `MemoryProbe.score()` instead of the stub. The `r83_report.md` A3 row must show:
- Real score (not 0.5)
- Sub-metric breakdown: retrieval_latency_ms / recall_hit_rate / writeback_persistence_rate
- Reasoning that names the sub-metrics (not `"not-implemented"`)

### 3.4 No new owner

R84 lives in `src/helios_v2/tests/r83/memory_probe.py` (replacing the existing stub), as a sibling of `tests/r79d/`. Owner = 17 evaluation. **No new owner created.**

### 3.5 No new dependencies

R84 uses **only what R83 + R79-D + R10 + R15 already export**:
- `helios_v2.directed_retrieval.DirectedRetrievalEngine.plan_and_select`
- `helios_v2.experience_writeback.ExperienceWritebackEngine.write_experience`
- `helios_v2.persistence.ExperienceStore.read_recent` / `count`
- The R83 `LongRunner` already gives us a `handle` we can introspect

---

## 4. Non-Functional Requirements

1. **P5 launch gate must still pass** — R84 must not regress R82 drift or A5
2. **No ad-hoc logging** — R21 guard stays green
3. **composition owner-boundary guard** — MemoryProbe reads only R10+R15 public APIs, never their private internals
4. **999 → 1000+ tests** — Add ≥5 new unit tests for MemoryProbe (one per sub-metric + smoke + edge case)
5. **Real LLM 10-min run** — The CLI default run with the real LLM must produce A3 != 0.5 and report real sub-metric numbers
6. **Deterministic** — Given the same stimuli + same LLM seed, A3 must be reproducible within ±0.05

---

## 5. Code Behavior Constraints

1. **R84 must not modify R10 / R15 / R79-D framework** — R84 is a *consumer* of those paths, not an *editor*
2. **MemoryProbe.score() must fail-soft** — If R10 engine or R15 store is unavailable (e.g. composition is in a degraded mode), return a partial `MemoryProbeResult` with the available sub-metrics and reasoning `"partial-probe"`. Only fall back to 0.5 when the entire probe is impossible.
3. **No print()** — R21 compliance (existing `tests/r79d/_io.py` is the stdout wrapper)
4. **Per-state A3 score is computed after the 40-tick run** — A3 cannot run mid-tick (R10 retrieval depends on the R79-C's `retrieval_bundle` which is per-tick)
5. **Sub-metric sub-fields on MemoryProbeResult are non-None when data is present** — `retrieval_latency_ms: Optional[float] = None` etc.; if a sub-metric is impossible, leave it None and lower its weight in the per-state A3 formula
6. **MemoryProbe must not call the LLM** — A3 is purely algorithmic (uses R10 + R15 + experience_store); it does not consume an LLM call

---

## 6. Impacted Modules

| Module | Change | Reason |
|---|---|---|
| `src/helios_v2/tests/r83/memory_probe.py` | replace stub with real impl | A3 was stub, becomes real |
| `src/helios_v2/tests/r83/__main__.py` | call real `MemoryProbe.score()` | CLI integration |
| `src/helios_v2/tests/r83/report_builder.py` | show real sub-metrics | MD report shows numbers |
| `tests/test_r83_smoke.py` | add ≥5 new tests | coverage |
| `docs/requirements/84-r84-.../{requirement,design,task}.md` | this tri-pack | process |
| `docs/requirements/index.md` | append R84 row | index sync |
| `docs/OWNER_GUIDE.md` | §3.8.5 R84 new section + status header R83 → R84 | owner guide sync |
| `docs/ARCHITECTURE_BOUNDARIES.md` | §10.f R84 new section + status header | arch boundary sync |
| `docs/PROGRESS_FLOW.zh-CN.md` | R84 索引块 + status R84 | progress flow sync |

---

## 7. Acceptance Criteria

1. **Code**: `src/helios_v2/tests/r83/memory_probe.py` is no longer a stub; `score()` returns a real `MemoryProbeResult`
2. **Tests**: `pytest tests/` returns ≥ 985 passed (979 R83 baseline + ≥5 R84 + 1 R21 guard). 0 regressions.
3. **Smoke**: `python -m helios_v2.tests.r83 --duration 0.5 --no-judge` produces A3 != 0.5 in `r83_report.md`
4. **Real LLM**: a 10-minute real LLM run with `--output-dir` produces A3 with real sub-metric numbers and reasoning != `"not-implemented"`
5. **Verdict uplift**: A3 must rise from 0.500 to ≥ 0.500 (no regression; ideally ≥ 0.6 with real data)
6. **P5 unblocker**: After R84 ships, the 10-min R83 run's A3 row in `r83_report.md` must show non-stub numbers, which then unlock future R85+ for actual `mandatory_learned_parameters` updates

---

## 8. Out of Scope (deferred to R85+)

- **Actual `mandatory_learned_parameters` updates** — R84 is *measurement*, not *modification*. R85 will use the A3 numbers to actually update owner 09 / 17 / 04 coefficients.
- **RPE (reward prediction error) signal** — R86+ will add RPE based on A6 vs A2 mismatch.
- **Cross-actor memory probe** — multi-persona memory isolation is R87+.
- **Long-horizon memory decay modeling** — episodic half-life is R88+.
- **A3 sub-metric 4: free-recall correlation** — using a second LLM call to verify persona's `remember_because` matches the stimulus semantically. Deferred to R85 (which will pair with the actual learning loop).
