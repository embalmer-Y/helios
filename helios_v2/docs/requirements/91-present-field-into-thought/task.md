# Requirement 91 - Present-Field Into the Internal Thought Prompt — Tasks

## 1. Task Breakdown

### T1 — Contract additive field
- Add `PRESENT_FIELD_SUMMARY_MAX_CHARS` and `PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX` constants in
  `internal_thought/contracts.py`.
- Add `present_field_summary: str | None = None` to `InternalThoughtRequest`.
- Extend `__post_init__`: when set, must be non-blank; when over cap, deterministically truncate
  with the documented suffix.

### T2 — `11` engine renders the line when present
- In `LlmInternalThoughtPath._build_messages`, prepend `Present field: <summary>` to the user
  message when `request.present_field_summary` is non-None and non-empty. Keep all existing lines
  in the same order otherwise. The deterministic-fallback `FirstVersionInternalThoughtPath._render_content`
  prepends the same line to the synthesized content for parity.

### T3 — Composition projection (semantic only)
- Add a private helper `_present_field_summary_text(frame, temporal_source)` in
  `composition/bridges.py`:
  - read `frame.stage_results.get("reportable_conscious_content")`; if activated and
    `state.focal_content` is not None, project `focal: <focal_summary>` and append `tokens: a, b, c`
    when `salient_tokens` is non-empty (limit ≤ 8 tokens, joined by `, `).
  - else project `no focal content this cycle: <no_commit_reason or "inactive">` (honest absence).
  - if `temporal_source` is provided, append `; pacing: <temporal_signal>` (round to 4 decimals).
- Add an injected `temporal_source: object | None = None` field to
  `SemanticInternalThoughtRequestBridge` and assign the helper output to `present_field_summary`.
- `FirstVersionInternalThoughtRequestBridge` — leave unchanged (field stays default None).

### T4 — Wire temporal source in semantic assembly
- In `composition/runtime_assembly.py`, where the existing `temporal_source` is built for the
  semantic gate-signal bridge, also pass it to `SemanticInternalThoughtRequestBridge`.

### T5 — Tests (network-free)
- `tests/test_internal_thought_contracts_present_field.py` (new) — None default, non-blank rule,
  length cap + truncation suffix.
- `tests/test_internal_thought_engine_present_field.py` (new) — `_build_messages` adds the line iff
  set; None keeps the existing message byte-for-byte; deterministic-fallback path adds the line too.
- `tests/test_semantic_thought_request_bridge_present_field.py` (new) — focal-committed projection;
  no-commit honest absence; optional temporal pacing append; legacy bridge None.
- All under `helios_v2/tests/`. Reuse existing test helpers / fakes; no new test framework.

### T6 — Docs sync
- `requirements/index.md` — add row 91 with `baseline_implementation` maturity.
- `ROADMAP.zh-CN.md` §10 W1 R91 — mark delivered with the test count.
- `OWNER_GUIDE.*` / `PROGRESS_FLOW.*` — unchanged (additive, no owner color / chain / boundary
  change). Verify no stale sync markers; do NOT bump them in this commit.

### T7 — Local probe re-verification (no new probe runs unless prompt shape changes)
- The R91 probe set under `scripts/r91_probes/` already validates the prompt shape this
  requirement implements. If T2 changes the line shape from `Present field: focal: ... ; pacing: ...`,
  re-run the probe set per `requirement-authoring-standard.md` §8.2 and update the design.

## 2. Dependencies

1. Reads `08` published `ReportableConsciousContent` (already exists, no change).
2. Reads optional `helios_v2.temporal.TemporalSource.sample(...)` (already exists).
3. No `02`/`06`/`10`/embedding/LLM imports inside the bridge.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/internal_thought/contracts.py`
2. `helios_v2/src/helios_v2/internal_thought/engine.py`
3. `helios_v2/src/helios_v2/composition/bridges.py`
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
5. `helios_v2/tests/test_internal_thought_contracts_present_field.py` (new)
6. `helios_v2/tests/test_internal_thought_engine_present_field.py` (new)
7. `helios_v2/tests/test_semantic_thought_request_bridge_present_field.py` (new)
8. `helios_v2/docs/requirements/index.md`
9. `helios_v2/docs/ROADMAP.zh-CN.md`

## 4. Implementation Order

1. T1 — contract additive field + tests (T5 first slice).
2. T2 — `_build_messages` rendering + tests (T5 second slice).
3. T3 — bridge projection helper + bridge field + tests (T5 third slice).
4. T4 — assembly wiring; verify the chain end-to-end with a small offline run.
5. T5 — finalize tests; full network-free suite green.
6. T6 — docs sync.
7. T7 — re-run the probe set if prompt shape changed.

## 5. Validation Plan

1. First narrow check: `pytest helios_v2/tests/test_internal_thought_contracts_present_field.py
   helios_v2/tests/test_internal_thought_engine_present_field.py
   helios_v2/tests/test_semantic_thought_request_bridge_present_field.py -q`.
2. Regression: `pytest helios_v2/tests -q` (network-free) stays green; the prior 996/4 baseline
   becomes ≥ 996 + new R91 tests.
3. Manual: run `helios_v2/scripts/emotion_test_run.py --messages 6 --max-sleep 0.1` against the real
   LLM after R91 lands; confirm captured `--llm-log` JSONL shows the new `Present field:` line and
   the model engages content (the empirical fix the probe predicted).

## 6. Completion Criteria

1. `InternalThoughtRequest.present_field_summary` is an additive optional bounded field;
   default-None preserves all prior behavior.
2. Under the semantic-memory assembly, every fired tick whose `08` committed a focal item produces
   a request whose `present_field_summary` carries the real focal summary + tokens, plus pacing
   when wired; no-commit produces an honest absent marker.
3. The `11` LLM user message contains the `Present field:` line iff the field is set; with None it
   is byte-for-byte the pre-R91 form.
4. The full network-free suite is green; new tests cover contract, engine, and bridge paths.
5. `index.md` row 91 and ROADMAP §10 R91 delivered note are in place.
6. The R91 prompt shape the probe set validated is the one shipped (§9.1 of design.md).
