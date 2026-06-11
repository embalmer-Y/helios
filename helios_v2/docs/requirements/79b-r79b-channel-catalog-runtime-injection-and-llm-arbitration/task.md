# Requirement 79b - R79-B Channel-Catalog Runtime Injection and LLM Channel Arbitration — Task

## 1. Task Breakdown

### T1 — Create R79-B requirement package

Files created at `docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/`:

- `requirement.md` (~16.5 KB)
- `design.md` (~19.4 KB)
- `task.md` (this file)

### T2 — Implement `AggressiveRadicalPromptProfile` capability bundle

New file `src/helios_v2/composition/profile.py` with:
- `PromptPathMode = Literal["aggressive-radical-v3"]`
- `AggressiveRadicalPromptProfile` (frozen dataclass, 2 fields, fail-fast
  `__post_init__`).
- Re-export from `composition/__init__.py` (alphabetical, A-section start of
  `__all__`).

Validation: 5/5 behavioral tests (empty / valid / wrong mode / duplicate /
integration).

### T3 — Wire `RuntimeProfile.aggressive_radical_prompt_profile`

In `composition/runtime_assembly.py`:

- Add `TYPE_CHECKING` import of `AggressiveRadicalPromptProfile` (avoids the
  circular import with `profile.py`).
- Add `aggressive_radical_prompt_profile` field to `RuntimeProfile` (after
  `default_signal_mode`).
- Add the same kwarg to `assemble_runtime` signature (with `_UNSET` sentinel).
- Add to the `_loose` dispatch table.
- Add to the rebind block.

### T4 — Wire v3 bundle resolution in `assemble_runtime`

In `composition/runtime_assembly.py`, right after
`thought_profile_name = resolved_config.llm.thought_profile_name`:

- If `resolved_profile.aggressive_radical_prompt_profile is not None`:
  - Check `resolved_config.embodied_prompt.prompt_bootstrap_id` is the v1
    default; if not, raise `CompositionError` (fail-fast).
  - `replace(resolved_config.embodied_prompt,
    prompt_bootstrap_id="embodied-prompt-bootstrap:v3-aggressive-radical")`.
- Compute `_resolved_ready_channels = (bundle.ready_channels if bundle
  else ())`.

### T5 — Wire prompt-path selection in `assemble_runtime`

In `composition/runtime_assembly.py`, right before
`embodied_prompt = EmbodiedPromptEngine(...)`:

- Compute `_resolved_prompt_path = (AggressiveRadicalEmbodiedPromptPath() if
  bundle else FirstVersionEmbodiedPromptPath())`.
- Add import of `AggressiveRadicalEmbodiedPromptPath` from
  `helios_v2.prompt_contract`.
- Pass `_resolved_prompt_path` to `EmbodiedPromptEngine`.

### T6 — Wire bridge `ready_channels` injection in `assemble_runtime`

In `composition/runtime_assembly.py`, the `EmbodiedPromptRuntimeStage`
`request_provider` block:

- `FirstVersionEmbodiedPromptRequestBridge(ready_channels=_resolved_ready_channels)`
- `SemanticEmbodiedPromptRequestBridge(ready_channels=_resolved_ready_channels)`

### T7 — Add `ready_channels` class field to both bridges

In `composition/bridges.py`:

- `FirstVersionEmbodiedPromptRequestBridge`: add
  `ready_channels: tuple[str, ...] = ()` class field, add
  `_resolved_channels = self.ready_channels if self.ready_channels else ("cli",)`
  in `build_requests`, replace `("cli",)` with `_resolved_channels` in
  `capability_summary["available_channels"]`.
- `SemanticEmbodiedPromptRequestBridge`: same changes.

### T8 — Implement `AggressiveRadicalChannelArbitrationPostProcessor`

In `composition/bridges.py`:

- `ArbitrationOutcome` (frozen dataclass: `dispatched`, `reason`, `target`,
  `op`, `outcome`).
- `AggressiveRadicalChannelArbitrationPostProcessor` class with
  `process(completion, request, ready_channels, channel_subsystem)` method.
  - Parse LLM JSON envelope → `_ArbitrationEnvelope`.
  - Validate `i_will_send_it`, `i_send_through ∈ ready_channels`, `act_type`
    in the allowed taxonomy.
  - On success: construct `OutboundPacket` and call
    `channel_subsystem.dispatch_outbound((packet,), budget=1)`.
  - On any failure: return `ArbitrationOutcome(dispatched=False, reason=...)`.

Imports limited to:
- `helios_v2.composition.contracts` (for `EmbodiedPromptRequest`)
- `helios_v2.channel_driver.dispatcher` (for `ChannelSubsystemAPI` etc.)
- `helios_v2.llm.contracts` (for `LlmCompletion`)
- `helios_v2.channel.contracts` (for `OutboundPacket`)

### T9 — Write `tests/test_r79b_channel_arbitration.py`

6+ test cases:

1. LLM picks ready channel → dispatch call made.
2. LLM picks non-ready channel → no dispatch (`reason="channel_not_ready"`).
3. LLM `i_will_send_it=False` → no dispatch (`reason="not_sending"`).
4. JSON parse failure → no dispatch (`reason="parse_error"`).
5. Multiple channels ready → LLM's chosen channel is used (parametrize).
6. Unknown `act_type` → no dispatch (`reason="unknown_act_type"`).

Use a fake `ChannelSubsystem` (mock that records `dispatch_outbound` calls).

### T10 — Write `tests/test_r79b_runtime_integration.py`

4+ test cases:

1. v1 default assembly is byte-for-byte unchanged
   (`prompt_bootstrap_id == "embodied-prompt-bootstrap:v1"`,
   `prompt_path` is `FirstVersionEmbodiedPromptPath`,
   `bridge.ready_channels == ()`).
2. v3 bundle assembly uses v3 path + injected ready_channels.
3. v3 bundle + non-v1 baseline bootstrap id → `CompositionError` fail-fast.
4. v3 bundle assembly with multi-channel `ready_channels` → bridge field
   round-trips.

### T11 — Run full test suite, confirm 848+ passed

```bash
cd /root/project/helios/helios_v2
.venv/bin/python -m pytest tests/ -q --tb=no
```

Expected: 848+ passed (842 baseline + 6 arbitration + ~4 integration);
modulo pre-existing `test_p2_p1_sqlite_append_throughput` and
`test_p2_p2_semantic_recall_latency` performance-flake failures.

### T12 — Run R79-D baseline end-to-end probe (real LLM)

Re-run the R79-D baseline framework scenario A_praise with v3 bundle
(`aggressive_radical_prompt_profile=
AggressiveRadicalPromptProfile(ready_channels=("cli",))`):

- `i_send_through_freq` for `cli` should be `>= 0.5`.
- `i_send_through_freq` for non-ready channels should be `< 0.2`.
- The LLM must use `i_send_through="cli"` (the only ready channel) for all
  ticks where `i_will_send_it=True`.

### T13 — Confirm R21 + composition guard still green

```bash
.venv/bin/python -m pytest tests/test_no_adhoc_logging_guard.py \
    tests/test_composition_owner_boundary_guard.py -q
```

Both must be green (no `print(...)` or `import logging` in the new code; no
cognitive-owner imports in the post-processor).

### T14 — Sync documentation

- `helios_v2/docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`:
  mark T3 (R79-B) sub-task checkbox list as done.
- `helios_v2/docs/requirements/index.md`: add R79b row, maturity
  `baseline_implementation`.
- `helios_v2/docs/PROGRESS_FLOW.en.md`: sync line naming R79b.
- `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`: sync line naming R79b.
- Update "Last synced" line on both progress flow maps to name R79b.

### T15 — Commit on `aggressive-radical-persona-no-theater`

Single commit:

```
R79-B: AggressiveRadicalPromptProfile + RuntimeProfile field + assemble_runtime integration + channel arbitration post-processor + 10+ tests
```

Files in the commit:
- `src/helios_v2/composition/profile.py` (new)
- `src/helios_v2/composition/__init__.py` (re-export)
- `src/helios_v2/composition/runtime_assembly.py` (integration)
- `src/helios_v2/composition/bridges.py` (bridge fields + post-processor)
- `tests/test_r79b_channel_arbitration.py` (new)
- `tests/test_r79b_runtime_integration.py` (new)
- `docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/{requirement,design,task}.md`
  (new)
- `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`
  (T3 checkbox list update)
- `docs/requirements/index.md` (R79b row)
- `docs/PROGRESS_FLOW.en.md` (R79b sync line)
- `docs/PROGRESS_FLOW.zh-CN.md` (R79b sync line)

## 2. Dependencies

T1 → T2 → T3 → T4 → T5 → T6 → T7 (strict order; each must be green before next)

T8, T9 (post-processor + arbitration tests) can be done in parallel with T1-T7
once T7 is done.

T10 (integration tests) depends on T3-T7.

T11-T13 depend on T9, T10.

T14 depends on T11 (and is best done after tests are green).

T15 depends on T14.

## 3. Files and Modules

### Modify

- `helios_v2/src/helios_v2/composition/__init__.py` — re-export (~5 lines).
- `helios_v2/src/helios_v2/composition/runtime_assembly.py` — integration
  (~50 lines).
- `helios_v2/src/helios_v2/composition/bridges.py` — bridge fields (~15 lines)
  + post-processor (~100 lines).
- `helios_v2/docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`
  — T3 checkbox list (~10 lines).
- `helios_v2/docs/requirements/index.md` — R79b row (~1 line).
- `helios_v2/docs/PROGRESS_FLOW.en.md` — R79b sync line (~2 lines).
- `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` — R79b sync line (~2 lines).

### New

- `helios_v2/src/helios_v2/composition/profile.py` — bundle (~100 lines).
- `helios_v2/tests/test_r79b_channel_arbitration.py` — 6+ tests (~200 lines).
- `helios_v2/tests/test_r79b_runtime_integration.py` — 4+ tests (~100 lines).
- `helios_v2/docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/requirement.md`
- `helios_v2/docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/design.md`
- `helios_v2/docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/task.md`

## 4. Implementation Order

1. **T1** (next): create the R79-B requirement package triple.
2. **T2**: implement `AggressiveRadicalPromptProfile`.
3. **T3-T7**: integrate into `RuntimeProfile` + `assemble_runtime` + bridges.
4. **T8**: implement the post-processor.
5. **T9**: write the post-processor unit tests.
6. **T10**: write the assembly integration tests.
7. **T11**: run full test suite.
8. **T12**: run R79-D baseline end-to-end probe.
9. **T13**: confirm R21 + composition guard.
10. **T14**: documentation sync.
11. **T15**: commit.

## 5. Validation Plan

1. **T2 unit tests** (5/5 behavioral, run via Python REPL or `tests/test_aggressive_radical_prompt_profile.py`).
2. **T9 unit tests** (6+ cases in `test_r79b_channel_arbitration.py`).
3. **T10 integration tests** (4+ cases in `test_r79b_runtime_integration.py`).
4. **T11 full regression** (`pytest helios_v2/tests/ -q`).
5. **T12 end-to-end probe** (R79-D baseline scenario A_praise + v3 bundle).
6. **T13 R21 + composition guard**.

## 6. Completion Criteria

- [x] R79-B requirement package triple exists at
      `docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/`.
- [ ] `AggressiveRadicalPromptProfile` implemented and exported; 5/5
      behavioral tests pass.
- [ ] `RuntimeProfile.aggressive_radical_prompt_profile` field + assemble_runtime
      integration wired.
- [ ] `ready_channels` class field on both bridges; `_resolved_channels`
      projection in both `build_requests` methods.
- [ ] `AggressiveRadicalChannelArbitrationPostProcessor` implemented with
      6+ test cases.
- [ ] `test_r79b_runtime_integration.py` with 4+ test cases.
- [ ] Full suite 848+ passed.
- [ ] R21 ad-hoc logging guard green.
- [ ] Composition owner-boundary guard green.
- [ ] R79-D baseline end-to-end probe shows `i_send_through` for `cli` is
      the dominant channel under A_praise.
- [ ] Documentation synced: `index.md`, `PROGRESS_FLOW.en.md`,
      `PROGRESS_FLOW.zh-CN.md`, R79 parent `task.md` T3 checkbox list.
- [ ] Commit on `aggressive-radical-persona-no-theater` branch.
