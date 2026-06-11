# Requirement 79b - R79-B Channel-Catalog Runtime Injection and LLM Channel Arbitration — Design

## 1. Design Overview

R79-B closes the runtime gap between the v3 embodied-prompt contract
(`AggressiveRadicalEmbodiedPromptPath`, delivered in R79-A) and the `30` channel driver
subsystem. The change has three parts:

1. **Capability bundle**: a new `AggressiveRadicalPromptProfile` (frozen dataclass under
   `helios_v2.composition.profile`) holds the v3 path's per-runtime configuration:
   `prompt_path_mode` (always `"aggressive-radical-v3"` for now) and `ready_channels`
   (the channel catalog the LLM is allowed to pick from). Construction is fail-fast:
   empty `ready_channels` and duplicate channel names both raise `CompositionError` at
   `__post_init__` time.

2. **Runtime assembly integration**: `assemble_runtime` gains an opt-in
   `aggressive_radical_prompt_profile` keyword argument that flows through the
   `RuntimeProfile` capability-bundle mechanism (R50), switches the embodied-prompt
   bootstrap id from `v1` to `v3-aggressive-radical` (via `dataclasses.replace`), selects
   `AggressiveRadicalEmbodiedPromptPath` over `FirstVersionEmbodiedPromptPath`, and
   forwards `_resolved_ready_channels` to the embodied-prompt request bridge. Default
   assembly (no bundle) is byte-for-byte unchanged.

3. **Channel arbitration post-processor**: a new
   `AggressiveRadicalChannelArbitrationPostProcessor` (owner-neutral glue under
   `helios_v2.composition.bridges`) consumes the LLM JSON envelope's
   `i_will_send_it` / `i_send_through` / `act_type` triple and dispatches an
   `OutboundPacket` to the matching `ChannelDriver` via `ChannelSubsystem.dispatch_outbound`
   if and only if `i_send_through` is in `ready_channels`. JSON parse failure,
   `i_will_send_it=False`, non-ready channel, or unknown `act_type` are all no-ops
   (the LLM's declaration is honored as a thought, but no outbound action fires).

The post-processor is owner-neutral: it imports `helios_v2.composition.contracts` and
`helios_v2.channel_driver.dispatcher` only; it does not import the LLM owner or the
prompt contract owner. The composition owner-boundary guard remains green.

## 2. Current State and Gap

End-to-end probe (R79-D baseline framework, 2026-06-11, real LLM gpt-4o-mini) confirms
two gaps in the R79-B scope:

### 2.1 Capability-bundle gap

The `AggressiveRadicalPromptProfile` bundle (R79 §3.2.1) is **not yet implemented** as
a real `composition` module. The v3 path is wired into the engine (R79-A), but the
caller has no opt-in handle to declare `ready_channels` or select v3. The current
`assemble_runtime` flow uses the v1 first-version prompt path unconditionally.

### 2.2 Channel-arbitration gap

The LLM JSON envelope's `i_will_send_it` / `i_send_through` / `act_type` fields are
defined in the v3 contract (R79-A) and the LLM does emit them, but nothing in the
runtime consumes them. The v3 contract is unilaterally a write-only contract: the LLM
can declare a channel choice, but the runtime ignores it. The v1 wire format still
drives the outbound pipeline (`ChannelOutboundDispatchRuntimeStage` reads the
internal-thought result, not the v3 JSON).

The two gaps combined mean the v3 path is currently observable only as a system
prompt — the LLM-side channel choice is inert.

## 3. Target Architecture

```
helios_v2.composition.profile.AggressiveRadicalPromptProfile
  prompt_path_mode: Literal["aggressive-radical-v3"] = "aggressive-radical-v3"
  ready_channels: tuple[str, ...] = ()
  __post_init__: fail-fast on empty / duplicate channels

helios_v2.composition.RuntimeProfile
  aggressive_radical_prompt_profile: AggressiveRadicalPromptProfile | None = None

helios_v2.composition.assemble_runtime(..., aggressive_radical_prompt_profile=...):
  if resolved_profile.aggressive_radical_prompt_profile is not None:
      # 1. switch bootstrap id
      if resolved_config.embodied_prompt.prompt_bootstrap_id != "embodied-prompt-bootstrap:v1":
          raise CompositionError(...)
      resolved_config = replace(resolved_config,
          embodied_prompt=replace(resolved_config.embodied_prompt,
              prompt_bootstrap_id="embodied-prompt-bootstrap:v3-aggressive-radical"))
  _resolved_ready_channels = (
      _v3_bundle.ready_channels
      if resolved_profile.aggressive_radical_prompt_profile is not None
      else ()
  )

  # 2. select v3 path
  _resolved_prompt_path = (
      AggressiveRadicalEmbodiedPromptPath()
      if resolved_profile.aggressive_radical_prompt_profile is not None
      else FirstVersionEmbodiedPromptPath()
  )
  embodied_prompt = EmbodiedPromptEngine(
      config=resolved_config.embodied_prompt,
      prompt_path=_resolved_prompt_path,
  )

  # 3. inject ready_channels into the request bridge
  EmbodiedPromptRuntimeStage(
      prompt_layer=embodied_prompt,
      request_provider=(
          SemanticEmbodiedPromptRequestBridge(ready_channels=_resolved_ready_channels)
          if semantic_memory_enabled
          else FirstVersionEmbodiedPromptRequestBridge(ready_channels=_resolved_ready_channels)
      ),
  )

helios_v2.composition.bridges.FirstVersionEmbodiedPromptRequestBridge
  ready_channels: tuple[str, ...] = ()  # class field
  build_requests(...):
      _resolved_channels = self.ready_channels if self.ready_channels else ("cli",)
      capability_summary = {
          "available_channels": _resolved_channels,
          ...
      }

helios_v2.composition.bridges.SemanticEmbodiedPromptRequestBridge
  ready_channels: tuple[str, ...] = ()  # class field
  build_requests(...):  # same projection as v1

helios_v2.composition.bridges.AggressiveRadicalChannelArbitrationPostProcessor
  def process(self, completion: LlmCompletion, request: EmbodiedPromptRequest,
              ready_channels: frozenset[str],
              channel_subsystem: ChannelSubsystemAPI | None) -> ArbitrationOutcome:
      # 1. parse the JSON envelope
      envelope = _parse_envelope(completion.output_text)
      if envelope is None:
          return ArbitrationOutcome(dispatched=False, reason="parse_error")
      # 2. validate i_will_send_it
      if not envelope.i_will_send_it:
          return ArbitrationOutcome(dispatched=False, reason="not_sending")
      # 3. validate i_send_through is in ready_channels
      if envelope.i_send_through not in ready_channels:
          return ArbitrationOutcome(dispatched=False, reason="channel_not_ready",
                                    attempted=envelope.i_send_through)
      # 4. validate act_type
      act_op = _act_type_to_op(envelope.act_type)
      if act_op is None:
          return ArbitrationOutcome(dispatched=False, reason="unknown_act_type")
      # 5. dispatch
      if channel_subsystem is None:
          return ArbitrationOutcome(dispatched=False, reason="no_subsystem")
      packet = OutboundPacket(
          packet_id=f"arb:{completion.completion_id}",
          target_driver_id=envelope.i_send_through,
          op_name=act_op,
          payload={"text": envelope.i_want_to_say or "", "request_id": request.request_id},
          execution_priority=0,
          provenance={"source_completion_id": completion.completion_id},
      )
      result = channel_subsystem.dispatch_outbound((packet,), budget=1)
      return ArbitrationOutcome(
          dispatched=True,
          target=envelope.i_send_through,
          op=act_op,
          outcome=result.outcomes[0] if result.outcomes else None,
      )
```

The post-processor is a **standalone glue class** — it is not yet wired into the
runtime's outbound pipeline (that's R80's scope). For R79-B, the post-processor must
be importable and have 6+ unit-test cases verifying the dispatch / no-dispatch /
fallback / boundary logic. R80 will add the runtime-stage binding.

## 4. Data Structures

### 4.1 `AggressiveRadicalPromptProfile` (frozen dataclass)

```python
@dataclass(frozen=True)
class AggressiveRadicalPromptProfile:
    prompt_path_mode: Literal["aggressive-radical-v3"] = "aggressive-radical-v3"
    ready_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.ready_channels:
            raise CompositionError(
                "AggressiveRadicalPromptProfile.ready_channels must declare at least one "
                "channel; an empty list leaves the v3 path with no speaking surface "
                "(fail-fast; no silent v1 fallback)."
            )
        seen: set[str] = set()
        for channel in self.ready_channels:
            if not isinstance(channel, str) or not channel:
                raise CompositionError(
                    f"AggressiveRadicalPromptProfile.ready_channels entry must be a non-empty "
                    f"string, got {channel!r}."
                )
            if channel in seen:
                raise CompositionError(
                    f"AggressiveRadicalPromptProfile.ready_channels contains duplicate "
                    f"channel {channel!r} (channels are a set, not a multiset)."
                )
            seen.add(channel)
```

`PromptPathMode = Literal["aggressive-radical-v3"]` is exported alongside the dataclass.

### 4.2 `ArbitrationOutcome` (frozen dataclass, owned by the post-processor)

```python
@dataclass(frozen=True)
class ArbitrationOutcome:
    dispatched: bool
    reason: str = ""  # "" | "parse_error" | "not_sending" | "channel_not_ready" |
                     # "unknown_act_type" | "no_subsystem" | "dispatched"
    target: str | None = None
    op: str | None = None
    outcome: "OutboundDispatchOutcome | None" = None
```

This is a public-facing dataclass for the post-processor's return value, used by the
6+ unit tests and by R80's runtime-stage binding to emit `21` observability events.

### 4.3 `ArbitrationEnvelope` (internal frozen dataclass)

```python
@dataclass(frozen=True)
class _ArbitrationEnvelope:
    i_will_send_it: bool
    i_send_through: str | None
    act_type: str | None
    i_want_to_say: str | None
```

The post-processor parses the LLM JSON into this internal type. The fields match the
v3 schema in `prompt_contract.engine.AggressiveRadicalEmbodiedPromptPath`.

### 4.4 `RuntimeProfile` field

```python
aggressive_radical_prompt_profile: "AggressiveRadicalPromptProfile | None" = None
```

Added at the end of the dataclass (after `default_signal_mode`) to match the existing
convention. The TYPE_CHECKING-only import of `AggressiveRadicalPromptProfile` is used
in `runtime_assembly.py` to avoid the circular import
(`profile.py` imports `CompositionError` from `runtime_assembly.py`).

## 5. Module Changes

### 5.1 `helios_v2/src/helios_v2/composition/profile.py` (new)

New module containing `AggressiveRadicalPromptProfile` (frozen dataclass with
fail-fast `__post_init__`) and `PromptPathMode` (Literal type alias).

### 5.2 `helios_v2/src/helios_v2/composition/__init__.py` (modify)

Add to imports:
```python
from .profile import AggressiveRadicalPromptProfile, PromptPathMode
```
Add to `__all__` (alphabetical, A-section start):
```python
"AggressiveRadicalPromptProfile",
```

### 5.3 `helios_v2/src/helios_v2/composition/runtime_assembly.py` (modify)

- Add `TYPE_CHECKING` import of `AggressiveRadicalPromptProfile`.
- Add `from helios_v2.prompt_contract import (AggressiveRadicalEmbodiedPromptPath, ...)`.
- Add `aggressive_radical_prompt_profile` field to `RuntimeProfile` (after
  `default_signal_mode`).
- Add `aggressive_radical_prompt_profile` kwarg to `assemble_runtime` signature (with
  `_UNSET` sentinel).
- Add `aggressive_radical_prompt_profile` to the `_loose` dispatch table.
- Add `aggressive_radical_prompt_profile = resolved_profile.aggressive_radical_prompt_profile`
  to the rebind block.
- Add the v3 bundle resolution block (8-12 lines) right after
  `thought_profile_name = resolved_config.llm.thought_profile_name`:
  - bootstrap id switch (with non-v1 baseline check)
  - `_resolved_ready_channels` computation
- Add the `_resolved_prompt_path` selection (5 lines) right before
  `embodied_prompt = EmbodiedPromptEngine(...)`.
- Update the embodied-prompt `EmbodiedPromptRuntimeStage` request_provider to inject
  `ready_channels` (10 lines) — the bridge instance is constructed with
  `ready_channels=_resolved_ready_channels`.

### 5.4 `helios_v2/src/helios_v2/composition/bridges.py` (modify)

- Add `ready_channels: tuple[str, ...] = ()` class field to
  `FirstVersionEmbodiedPromptRequestBridge` and `SemanticEmbodiedPromptRequestBridge`.
- Add `_resolved_channels = self.ready_channels if self.ready_channels else ("cli",)`
  in each `build_requests`, right after `tick_id = frame.tick_id`.
- Replace `"available_channels": ("cli",)` with
  `"available_channels": _resolved_channels` in each `capability_summary` block.
- Add `AggressiveRadicalChannelArbitrationPostProcessor` class (owner-neutral glue)
  with `process(...)` method returning `ArbitrationOutcome`.

### 5.5 `helios_v2/tests/test_r79b_channel_arbitration.py` (new)

New test file with 6+ cases for the post-processor:
1. LLM picks ready channel → dispatch call made (`outcome.dispatched == True`,
   `outcome.target == "cli"`)
2. LLM picks non-ready channel → no dispatch
   (`outcome.dispatched == False`, `outcome.reason == "channel_not_ready"`)
3. LLM `i_will_send_it=False` → no dispatch
   (`outcome.dispatched == False`, `outcome.reason == "not_sending"`)
4. JSON parse failure → no dispatch (`outcome.dispatched == False`,
   `outcome.reason == "parse_error"`)
5. Multiple channels ready → LLM's chosen channel is used (parametrize over
   `("cli", "webchat", "feishu")`)
6. Unknown `act_type` → no dispatch (`outcome.dispatched == False`,
   `outcome.reason == "unknown_act_type"`)

### 5.6 `helios_v2/tests/test_r79b_runtime_integration.py` (new)

New test file with 4+ cases for the assembly integration:
1. v1 default assembly is byte-for-byte unchanged (bootstrap id, prompt path, bridge
   type, bridge.ready_channels == ())
2. v3 bundle assembly uses v3 path + injected ready_channels
3. v3 bundle + non-v1 baseline bootstrap id → `CompositionError` fail-fast
4. v3 bundle assembly with multi-channel `ready_channels` → bridge field round-trips

### 5.7 Documentation sync

- `helios_v2/docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`:
  update T3 (R79-B) sub-task checkbox list to mark all items done.
- `helios_v2/docs/requirements/index.md`: add R79b row, maturity `baseline_implementation`.
- `helios_v2/docs/PROGRESS_FLOW.en.md` and `PROGRESS_FLOW.zh-CN.md`: sync line naming
  R79b; update "Last synced" line to name R79b.
- `helios_v2/docs/requirements/79b-r79b-channel-catalog-runtime-injection-and-llm-arbitration/{requirement,design,task}.md`:
  this requirement package.

## 6. Migration Plan

1. Branch `aggressive-radical-persona-no-theater` is already in place (R79-A
   baseline). Continue on the same branch.
2. Add `composition/profile.py` with `AggressiveRadicalPromptProfile`.
3. Update `composition/__init__.py` to re-export the bundle.
4. Update `composition/runtime_assembly.py`:
   - imports (TYPE_CHECKING for the bundle)
   - `RuntimeProfile` field
   - `assemble_runtime` signature + `_loose` + rebind
   - v3 bundle resolution block
   - `_resolved_prompt_path` selection
   - `EmbodiedPromptRuntimeStage` request_provider injection
5. Update `composition/bridges.py`:
   - `ready_channels` class field on both bridges
   - `_resolved_channels` projection in both `build_requests` methods
   - new `AggressiveRadicalChannelArbitrationPostProcessor` class
6. Add `tests/test_r79b_channel_arbitration.py` (6+ cases).
7. Add `tests/test_r79b_runtime_integration.py` (4+ cases).
8. Run `pytest helios_v2/tests/ -q` to confirm 848+ passed (baseline 842 + 6 + ~4).
9. R21 ad-hoc logging guard must remain green; composition owner-boundary guard
   must remain green.
10. Documentation sync: `index.md`, `PROGRESS_FLOW.en.md`, `PROGRESS_FLOW.zh-CN.md`,
    R79 parent `task.md` T3 checkbox list, R79b package triple.
11. Commit on `aggressive-radical-persona-no-theater`:
    `R79-B: AggressiveRadicalPromptProfile + RuntimeProfile field + assemble_runtime
    integration + channel arbitration post-processor + 10+ tests`.

## 7. Failure Modes and Constraints

1. The `AggressiveRadicalPromptProfile` `__post_init__` fail-fast: empty channels,
   duplicate channels, non-string channel names all raise `CompositionError` at
   construction. There is no silent fallback to v1.
2. The `assemble_runtime` non-v1 baseline check: if the caller pre-sets a
   `prompt_bootstrap_id` other than `embodied-prompt-bootstrap:v1`, the v3 bundle
   activation raises `CompositionError`. The v3 path is an additive sibling, not a
   fork that allows arbitrary baseline ids.
3. The `AggressiveRadicalChannelArbitrationPostProcessor.process(...)` fail-soft:
   any failure mode (parse error, not-sending, non-ready channel, unknown
   `act_type`, missing subsystem) returns `ArbitrationOutcome(dispatched=False,
   reason=...)` and emits an `21` observability event. There is no exception
   raise; the runtime continues to the next tick.
4. The post-processor is owner-neutral: it imports only
   `helios_v2.composition.contracts` and `helios_v2.channel_driver.dispatcher`.
   The composition owner-boundary guard test
   (`test_composition_owner_boundary_guard.py`) must remain green.
5. The change preserves R70's owner-neutrality guarantee: bridges still read
   only published contract types from the frame, never cognitive policy. The
   post-processor reads only the LLM JSON envelope and the `ready_channels`
   set, never cognitive state.
6. R21 ad-hoc logging guard: no `print(...)` or `import logging` calls in
   `runtime_assembly.py` or `bridges.py`. The post-processor uses the existing
   `21` observability owner for emit.

## 8. Observability and Logging

The post-processor emits `21` observability events for every decision:

- `event_kind="r79b_arbitration_dispatched"`: `target`, `op`, `outcome` payload.
- `event_kind="r79b_arbitration_skipped"`: `reason`, `attempted_channel` (when
  applicable), `i_will_send_it`, `ready_channels` payload.

The events are emitted via the `RuntimeObservabilityRecorder` injected into the
post-processor constructor (no global state). When no recorder is injected, the
events are dropped (no log spam).

The `assemble_runtime` v3 bundle resolution emits one `21` event:
`event_kind="r79b_bundle_activated"`: `bundle_id`, `ready_channels`, `bootstrap_id`
payload.

## 9. Validation Strategy

1. **Unit tests (new)**:
   - `test_r79b_channel_arbitration.py` — 6+ cases for the post-processor.
   - `test_r79b_runtime_integration.py` — 4+ cases for the assembly integration.
2. **Regression**: full `pytest helios_v2/tests/ -q` — baseline 842 passed must
   move to 848+ passed with no failures (modulo pre-existing R71 perf-flake
   failures).
3. **End-to-end probe**: re-run the R79-D baseline framework scenario
   A_praise with v3 bundle (`aggressive_radical_prompt_profile=
   AggressiveRadicalPromptProfile(ready_channels=("cli",))`) and confirm
   `i_send_through_freq` for `cli` is `>= 0.5` and for non-ready channels is
   `< 0.2`.
4. **Composition owner-boundary guard**:
   `test_composition_owner_boundary_guard.py` must remain green (no new
   cognitive-owner imports in the post-processor).
5. **R21 ad-hoc logging guard**: `test_no_adhoc_logging_guard.py` must remain
   green (no `print(...)` or `import logging` calls in the new code).
