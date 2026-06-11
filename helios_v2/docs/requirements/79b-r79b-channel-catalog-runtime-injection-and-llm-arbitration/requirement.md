# Requirement 79b - R79-B Channel-Catalog Runtime Injection and LLM Channel Arbitration

## 1. Background and Problem

R79-A (delivered) added the `AggressiveRadicalEmbodiedPromptPath` (v3) as a sibling to
`FirstVersionEmbodiedPromptPath` (v1). The v3 path renders a six-layer contract:
`present_field` / `embodied_state` / `attention_breakdown` / `channel_catalog` /
`response_schema` / `v3_system_prompt`. Layer 4 (`channel_catalog`) is supposed to
project the runtime's actual per-driver channel availability, but the underlying
`FirstVersionEmbodiedPromptRequestBridge` and `SemanticEmbodiedPromptRequestBridge` both
hardcode `available_channels: ("cli",)` — a static shim that ignores the `30` channel
driver subsystem's real `ChannelStateSnapshot`.

Additionally, the v3 prompt contract instructs the LLM to output JSON with
`i_will_send_it` + `i_send_through` + `act_type` fields so the LLM can request a
non-CLI channel (e.g. `webchat`, `feishu`) when it has a higher-attention
external-output obligation. The runtime has no consumer for that JSON: nothing
interprets `i_send_through` and dispatches to the corresponding `ChannelDriver`,
so the LLM's channel choice is dropped on the floor.

End-to-end probe (R79-D baseline framework, 2026-06-11) with a real LLM (gpt-4o-mini
via OpenAI-compatible) confirms the v3 system prompt is built and the LLM does produce
valid JSON, but the `i_send_through` field's value never reaches any channel driver —
the runtime's outbound pipeline still defaults to the legacy CLI dispatch path
(`ChannelOutboundDispatchRuntimeStage` reads the v1 wire format, not the v3 JSON).

This violates R79-B's intent (R79 §3.2 requirement 4: "A new post-processor interprets
the LLM JSON's `i_will_send_it` + `i_send_through` + `act_type` triple and dispatches
to the appropriate `ChannelDriver` if and only if the chosen channel is in the
`ready_channels` set. LLM output that names a non-ready channel is treated as
'internal-only'.").

The R79-B gap is therefore two-fold:

1. **Capability bundle / integration**: the v3 bundle's `ready_channels` tuple is
   not propagated to the embodied-prompt request bridge, so the v3 system prompt's
   `channel_catalog` layer is built from the v1 shim.
2. **LLM-side post-processing**: nothing consumes the LLM's `i_send_through`
   declaration. The v3 contract's outbound semantics are inert.

## 2. Goal

Complete the runtime-injection + arbitration half of R79-B so the v3 path is
end-to-end: the bundle's `ready_channels` is forwarded to the LLM-facing prompt
contract (replacing the v1 hardcoded shim), and the LLM's channel choice
(`i_send_through` in the v3 JSON) is consumed by a post-processor that dispatches to
the correct `ChannelDriver` if and only if the channel is in the bundle's
`ready_channels` snapshot. Channels not in the snapshot are treated as
"internal-only" (the LLM's declaration is honored as a thought, but no outbound
action fires). Default assembly (no v3 bundle) remains byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Capability bundle — `AggressiveRadicalPromptProfile`

1. The `22` composition root owner gains a frozen dataclass
   `AggressiveRadicalPromptProfile(prompt_path_mode: Literal["aggressive-radical-v3"] = "aggressive-radical-v3", ready_channels: tuple[str, ...] = ())`
   under `helios_v2.composition.profile`.
2. `ready_channels` must be a tuple of non-empty strings; an empty tuple
   is rejected at construction with `CompositionError` (fail-fast: "an empty
   list leaves the v3 path with no speaking surface (fail-fast; no silent v1
   fallback)").
3. Duplicate channel names are rejected at construction with
   `CompositionError` (fail-fast: channels are a set, not a multiset).
4. The bundle must be exported from `helios_v2.composition` (added to `__all__`
   in `composition/__init__.py`).

### 3.2 Runtime profile — `RuntimeProfile.aggressive_radical_prompt_profile`

1. `RuntimeProfile` gains a new optional field
   `aggressive_radical_prompt_profile: AggressiveRadicalPromptProfile | None = None`.
2. The `assemble_runtime` signature gains the same keyword argument with the
   `_UNSET` sentinel default; the `_loose` dispatch table and the rebind block
   must include the new field.
3. The TYPE_CHECKING-only import of `AggressiveRadicalPromptProfile` is used
   in `runtime_assembly.py` to avoid the circular import
   (`profile.py` imports `CompositionError` from `runtime_assembly.py`).
4. Default assembly (no v3 bundle) is byte-for-byte unchanged: `RuntimeProfile()`
   is the default runtime and `assemble_runtime()` produces the same handle as
   before R79-B.

### 3.3 v3 bundle resolution in `assemble_runtime`

1. When `resolved_profile.aggressive_radical_prompt_profile is not None`,
   `assemble_runtime` must switch the embodied-prompt bootstrap id from
   `embodied-prompt-bootstrap:v1` to
   `embodied-prompt-bootstrap:v3-aggressive-radical` via
   `dataclasses.replace(...)` on the resolved config.
2. If the resolved config's `embodied_prompt.prompt_bootstrap_id` is not the
   default v1 id (i.e. the caller pre-set a different baseline), the
   composition must raise `CompositionError` — the v3 path is an additive
   sibling, not a fork that allows arbitrary baseline ids.
3. A local `_resolved_ready_channels` tuple is computed once and forwarded to
   the embodied-prompt request bridge instance and (optionally) the channel
   arbitration post-processor.

### 3.4 Prompt-path selection

1. `assemble_runtime` selects `AggressiveRadicalEmbodiedPromptPath` (v3) when
   the bundle is active, otherwise `FirstVersionEmbodiedPromptPath` (v1) —
   the default.
2. The selected path is built once into a local `_resolved_prompt_path`
   variable and passed to `EmbodiedPromptEngine(prompt_path=...)`.
3. Default assembly (no v3 bundle) selects v1 path byte-for-byte unchanged.

### 3.5 Embodied-prompt request bridge — `ready_channels` injection

1. `FirstVersionEmbodiedPromptRequestBridge` and
   `SemanticEmbodiedPromptRequestBridge` each gain a class field
   `ready_channels: tuple[str, ...] = ()`.
2. In `build_requests`, the bridge computes
   `_resolved_channels = self.ready_channels if self.ready_channels else ("cli",)`
   once and projects it to `capability_summary["available_channels"]`.
3. When the v3 bundle is absent, `self.ready_channels` is `()` and the
   projection falls back to the hardcoded `("cli",)` shim — v1 default
   behavior is byte-for-byte unchanged.
4. When the v3 bundle is active with
   `ready_channels=("cli", "webchat", "feishu")`, the LLM-facing
   `capability_summary.available_channels` must reflect the full tuple
   (verified by source inspection and by the v3 path's rendered
   `v3_system_prompt` mentioning the channels).

### 3.6 Channel arbitration post-processor

1. A new `AggressiveRadicalChannelArbitrationPostProcessor` (owner-neutral
   glue in `helios_v2.composition.bridges`) consumes the LLM JSON envelope
   after it returns and dispatches to the correct `ChannelDriver` if and only
   if the chosen channel is in the bundle's `ready_channels` set.
2. Input: `LlmCompletion` (with `raw_text` containing the JSON envelope),
   `request` (the `EmbodiedPromptRequest` that produced the LLM call),
   `ready_channels: frozenset[str]`.
3. The post-processor parses the JSON envelope's
   `i_will_send_it` / `i_send_through` / `act_type` fields. If parsing fails
   (invalid JSON, missing keys, wrong types), the post-processor is a
   no-op: it logs an `21` observability event and returns.
4. Dispatch decision:
   - If `i_will_send_it is True` and `i_send_through in ready_channels`,
     the post-processor calls the appropriate `ChannelDriver` based on
     `act_type` and `i_send_through`.
   - If `i_will_send_it is False` or `i_send_through not in ready_channels`,
     the post-processor is a no-op for this tick (the LLM's declaration is
     honored as an internal thought; no outbound action fires).
5. The post-processor imports `helios_v2.composition.contracts` and
   `helios_v2.channel_driver.dispatcher` only; it does not import the LLM
   owner or the prompt contract owner — the composition
   owner-boundary guard remains green.
6. The post-processor is registered as a no-op stub until the next
   sub-task (R80) wires it into the runtime's outbound pipeline; for R79-B,
   it must be importable and have at least 6 unit-test cases verifying the
   dispatch / no-dispatch / fallback / boundary logic.

### 3.7 Observability and verification

1. The existing `21` observability owner and `R21` ad-hoc logging guard must
   continue to pass without modification — R79-B introduces no `print(...)`
   or `import logging` calls.
2. The composition owner-boundary guard test
   (`test_composition_owner_boundary_guard.py`) must remain green.
3. A new R79-B verification test must run at least 6 cases covering:
   - LLM picks ready channel → dispatch call made
   - LLM picks non-ready channel → no dispatch
   - LLM `i_will_send_it=False` → no dispatch
   - JSON parsing failure → no dispatch (fail-soft)
   - Multiple channels ready → LLM's chosen channel is used
   - `act_type` validation: unknown `act_type` → no dispatch

## 4. Non-Functional Requirements

1. **Performance**: zero per-tick cost change. The v1 default assembly is
   byte-for-byte unchanged; the v3 path adds one tuple-deref and one
   string-format call per tick (negligible vs the LLM call).
2. **Reliability**: the v3 bundle's `ready_channels` is fail-fast
   validated at construction; the `assemble_runtime` resolution raises
   `CompositionError` for any non-v1 baseline id when the bundle is active.
3. **Observability**: the new post-processor must emit `21` observability
   events for "dispatch" and "no-dispatch" decisions, with the LLM
   declaration, the bundle's `ready_channels` set, and the chosen channel
   in the event payload.
4. **Compatibility**: v1 default assembly (`assemble_runtime()` with no
   `aggressive_radical_prompt_profile`) is byte-for-byte unchanged:
   - `prompt_bootstrap_id == "embodied-prompt-bootstrap:v1"`
   - `prompt_path` is `FirstVersionEmbodiedPromptPath`
   - `bridge.ready_channels == ()` (the field exists but is empty)
   - `capability_summary["available_channels"] == ("cli",)`

## 5. Code Behavior Constraints

1. No new owner imports in `runtime_assembly.py` or `bridges.py` other
   than `AggressiveRadicalEmbodiedPromptPath` (already in
   `helios_v2.prompt_contract`) and `AggressiveRadicalPromptProfile` (under
   `TYPE_CHECKING` to avoid the circular import).
2. The post-processor is owner-neutral: it lives under
   `helios_v2.composition.bridges` and imports only
   `helios_v2.composition.contracts` and
   `helios_v2.channel_driver.dispatcher`. It must not import the LLM owner
   or the prompt contract owner.
3. The change preserves R70's owner-neutrality guarantee: bridges still
   read only published contract types from the frame, never cognitive
   policy. The post-processor reads only the LLM JSON envelope and the
   `ready_channels` set, never cognitive state.
4. The R21 ad-hoc logging guard is preserved: no `print(...)` or
   `import logging` calls are added in `runtime_assembly.py` or
   `bridges.py`.
5. The `RuntimeProfile` field is added at the end of the dataclass (after
   `default_signal_mode`) to match the existing convention.
6. All `replace(...)` calls in `assemble_runtime` use the already-imported
   `replace` from `dataclasses` (not `dataclasses.replace(...)`).

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/profile.py` — new module
   containing `AggressiveRadicalPromptProfile` (frozen dataclass with
   fail-fast `__post_init__`).
2. `helios_v2/src/helios_v2/composition/__init__.py` — re-export
   `AggressiveRadicalPromptProfile` (added to `__all__` in alphabetical
   order at the start of the A-section).
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — add
   `RuntimeProfile.aggressive_radical_prompt_profile` field; add
   `assemble_runtime` kwarg with `_UNSET` sentinel; add to the `_loose`
   dispatch table; add to the rebind block; add the v3 bundle resolution
   block (8-12 lines); add the `_resolved_prompt_path` selection (5
   lines); update the embodied-prompt `EmbodiedPromptRuntimeStage`
   request_provider to inject `ready_channels` (10 lines).
4. `helios_v2/src/helios_v2/composition/bridges.py` — add
   `ready_channels: tuple[str, ...] = ()` class field to
   `FirstVersionEmbodiedPromptRequestBridge` and
   `SemanticEmbodiedPromptRequestBridge`; add
   `_resolved_channels` projection in each `build_requests`; replace the
   `("cli",)` literal in each `capability_summary` block with
   `_resolved_channels`; add
   `AggressiveRadicalChannelArbitrationPostProcessor` (owner-neutral glue
   class).
5. `helios_v2/tests/test_r79b_channel_arbitration.py` — new test file
   with 6+ cases for the post-processor.
6. `helios_v2/tests/test_r79b_runtime_integration.py` — new test file
   with 4+ cases for the assembly integration (v1 default / v3 bundle /
   non-v1 baseline fail-fast / empty ready_channels).
7. `helios_v2/docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/{requirement,design,task}.md`
   — this requirement package.
8. `helios_v2/docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`
   — update T3 (R79-B) sub-task checkbox list (mark R79-B as
   `baseline_implementation`).
9. `helios_v2/docs/requirements/index.md` — add R79b row, maturity
   `baseline_implementation`.
10. `helios_v2/docs/PROGRESS_FLOW.en.md` and `PROGRESS_FLOW.zh-CN.md` —
    sync line naming R79b.

## 7. Acceptance Criteria

1. `helios_v2/src/helios_v2/composition/profile.py` exists and exports
   `AggressiveRadicalPromptProfile` with the 2 fields and the
   `__post_init__` fail-fast validations (empty channels, duplicate
   channels).
2. `helios_v2/src/helios_v2/composition/__init__.py` re-exports
   `AggressiveRadicalPromptProfile` (verifiable via `from helios_v2.composition import AggressiveRadicalPromptProfile`).
3. `assemble_runtime()` (default, no v3 bundle) produces a handle where
   the `EmbodiedPromptRuntimeStage`'s prompt layer has
   `prompt_bootstrap_id == "embodied-prompt-bootstrap:v1"` and the
   request provider is `FirstVersionEmbodiedPromptRequestBridge` (or
   `SemanticEmbodiedPromptRequestBridge` in semantic mode) with
   `ready_channels == ()`. v1 default assembly is byte-for-byte
   unchanged.
4. `assemble_runtime(aggressive_radical_prompt_profile=AggressiveRadicalPromptProfile(ready_channels=("cli", "webchat", "feishu")))`
   produces a handle where the prompt layer has
   `prompt_bootstrap_id == "embodied-prompt-bootstrap:v3-aggressive-radical"`,
   the prompt path is `AggressiveRadicalEmbodiedPromptPath`, and the
   request provider's `ready_channels` is `("cli", "webchat", "feishu")`.
5. `assemble_runtime(aggressive_radical_prompt_profile=..., config=<config with non-v1 prompt_bootstrap_id>)`
   raises `CompositionError` with a message naming the v1 baseline
   requirement (fail-fast).
6. The `AggressiveRadicalChannelArbitrationPostProcessor` is importable
   and the 6+ test cases in `test_r79b_channel_arbitration.py` are
   green: LLM picks ready channel → dispatch; LLM picks non-ready
   channel → no dispatch; `i_will_send_it=False` → no dispatch; JSON
   parse fail → no dispatch; multiple channels ready → LLM's choice
   used; unknown `act_type` → no dispatch.
7. The full test suite (`pytest helios_v2/tests/`) is green modulo
   pre-existing `test_p2_p1_sqlite_append_throughput` and
   `test_p2_p2_semantic_recall_latency` performance-flake failures
   (confirmed pre-existing by stash-and-rerun on the pre-R79-B commit
   `aafe756`). Baseline moves from 842 passed to 848+ passed
   (842 + 6 R79-B arbitration + ~4 R79-B integration).
8. R21 ad-hoc logging guard (`test_no_adhoc_logging_guard.py`) is
   green.
9. Composition owner-boundary guard
   (`test_composition_owner_boundary_guard.py`) is green.
10. End-to-end LLM probe (R79-D baseline framework scenario A_praise
    with v3 bundle) shows `i_send_through_freq > 0.5` for at least
    one ready channel and `i_send_through_freq < 0.2` for non-ready
    channels.
11. R79-B requirement package is created at
    `docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/`
    with `requirement.md`, `design.md`, `task.md`; `index.md`,
    `PROGRESS_FLOW.en.md`, and `PROGRESS_FLOW.zh-CN.md` are synced
    in the same change set; R79 parent package's `task.md` T3
    sub-task checkbox list is updated.
