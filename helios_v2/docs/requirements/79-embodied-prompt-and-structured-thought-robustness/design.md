# Requirement 79 - Owner-Grounded Embodied Prompt and Structured-Thought Robustness

## 1. Design Overview

R79 adds a v3 embodied-prompt path that renders a first-person embodied contract from real owner
state (identity from `14`, attention field from `07`/`08`, ready channels from channel-state), and
makes `11`'s structured-thought parsing robust to a reasoning model's `<think>` block and markdown
code fence with a sufficient token budget. Both are opt-in (default-off); the v1 path and default
assembly are unchanged. The change is split across two owners — `16` (prompt) and `11` (thought) —
and is wired by composition with owner-neutral projections.

## 2. Current State and Gap

1. `16`: `FirstVersionEmbodiedPromptPath` builds six layers and renders identity from
   `identity_boundary_summary["identity_boundary"]`, which is a composition constant ("identity
   revision remains proposal-only and governance-validated"), not a first-person self-model. The
   schema uses framework field names indirectly through downstream consumers. There is no
   focused/peripheral/filtered attention field and no ready-channel distinction.
2. Composition `SemanticEmbodiedPromptRequestBridge` (R70) projects stimulus/state/retrieval from
   real stage results, but `capability_summary` and `identity_boundary_summary` are still
   composition constants.
3. `14` publishes `identity_state_snapshot` (`AppliedIdentityState` / `GovernanceCarryState`), and
   R68 already carries it across ticks — but `14` runs after `16` in the tick, so v3 must render
   identity from the prior-tick carried snapshot.
4. `11`: `_parse_structured_thought` does a bare `json.loads(output_text)`. A reasoning model emits
   a `<think>` block and/or a ```json``` fence, so parsing fails and falls to
   `insufficient_generation`; the thought profile `max_tokens` (default 800) is too small for a
   reasoning model and truncates (`finish_reason: length`).

## 3. Target Architecture

### 3.1 `16` v3 owner-grounded embodied prompt path

A new owner-private `OwnerGroundedEmbodiedPromptPath` implements the existing `EmbodiedPromptPath`
protocol (sibling to `FirstVersionEmbodiedPromptPath`, v1 untouched). It requires
`EmbodiedPromptConfig.prompt_bootstrap_id == "embodied-prompt-bootstrap:v3"` and raises
`PromptContractError` otherwise. It emits these layers:

1. `identity_grounding` — rendered verbatim from the injected prior-tick identity self-summary
   (owner-sourced from `14`); never a hardcoded "you are a person / not an AI" literal.
2. `present_field` — the focused stimulus text.
3. `attention_breakdown` — focused / peripheral / filtered tiers from the injected attention field.
4. `embodied_state` — affect/continuation text (as v1, real `04`/`05`/`09` via R70).
5. `ready_channels` — the injected ready-channel list.
6. `response_schema` — the 11 natural-language field names plus the four cross-field hard rules.
7. `anti_theatrical` — the upgraded grounding rule: first-person only when state-supported; null
   when unsupported; never self-describe as AI/model/runtime/role.

The `response_schema` field names are: `what_i_feel`, `what_i_think`, `i_want_to_say`,
`i_will_send_it`, `i_send_through`, `i_want_to_act`, `act_type`, `remember_this`,
`remember_because`, `i_want_to_think_more`, `think_more_about`. Hard rules: `i_will_send_it` only
if `i_want_to_say` non-null; `i_send_through` only if `i_will_send_it` and only a ready channel;
`remember_because` only if `remember_this`; `think_more_about` only if `i_want_to_think_more`.
`final_authorities` keeps `("planner", "channel", "identity_governance")`.

### 3.2 `11` structured-thought parsing robustness

A new owner-private helper `_extract_structured_json(text) -> str` runs before `json.loads`:

1. Remove a `<think>...</think>` reasoning block (and a dangling unterminated `<think>` tail).
2. Strip a markdown code fence (```` ```json ```` / ```` ``` ````).
3. Return the substring from the first `{` to the matching last `}`; if none, return `""`.

`_parse_structured_thought` calls it first, then parses. An empty/unparseable result raises
`StructuredThoughtParseError` (existing path → `insufficient_generation`). A bare-JSON completion
is byte-for-byte unchanged (extraction is identity on clean JSON).

### 3.3 Token budget

The thought `LlmProfile.max_tokens` is raised (default-config value) to a budget large enough to
hold a reasoning model's `<think>` plus the JSON envelope (target `2048`). This is a config value,
not a contract change. A `length`-truncated completion with no extractable JSON object remains an
explicit non-success result.

### 3.4 Composition wiring (opt-in)

`RuntimeProfile` gains `embodied_prompt_mode: str = "v3"` (`"v3"` default, or `"v1"` legacy escape hatch). When `"v3"` (default):

1. `EmbodiedPromptEngine` is built with `OwnerGroundedEmbodiedPromptPath` and bootstrap id `v3`.
2. The prompt-request bridge fills additive keys: `identity_boundary_summary["identity_self_summary"]`
   from the prior-tick `14` `identity_state_snapshot` (via the existing R68 carry seam, projected
   owner-neutrally), `stimulus_summary["attention_field"]` (focused/peripheral/filtered) from the
   `07`/`08` stage results, and `capability_summary["ready_channels"]` from real channel-state
   (falling back to `available_channels` when no channel subsystem is bound).
3. The thought profile is bound with the larger `max_tokens`.

When `"v1"` (the explicit legacy escape hatch) the v1 path is used.

## 4. Data Structures

All additive; no top-level contract field is added or removed.

1. `EmbodiedPromptRequest.identity_boundary_summary` gains key `identity_self_summary: str`
   (consumed by v3 only).
2. `EmbodiedPromptRequest.stimulus_summary` gains key `attention_field: Mapping` with
   `focused: str`, `peripheral: tuple[str, ...]`, `filtered: tuple[str, ...]` (v3 only).
3. `EmbodiedPromptRequest.capability_summary` gains key `ready_channels: tuple[str, ...]` (v3 only).
4. `RuntimeProfile.embodied_prompt_mode: str = "v1"` (composition).
5. No change to `EmbodiedPromptContract`, `LlmRequest`, `LlmCompletion`, or the `11` result
   contracts.

## 5. Module Changes

1. `prompt_contract/engine.py` — add `OwnerGroundedEmbodiedPromptPath`; add the v3 bootstrap-id
   guard; v1 path unchanged.
2. `prompt_contract/__init__.py` — export `OwnerGroundedEmbodiedPromptPath`.
3. `internal_thought/engine.py` — add `_extract_structured_json`; call it in
   `_parse_structured_thought`.
4. `composition/runtime_assembly.py` (`RuntimeProfile` + `assemble_runtime`) — add the
   `embodied_prompt_mode` field + validation, the `assemble_runtime` parameter, and the v3
   engine/path/bridge wiring. (Note: `RuntimeProfile` lives in `runtime_assembly.py`, not a
   separate `profile.py`.)
5. `composition/bridges.py` — extend the embodied-prompt request bridge to fill the three additive
   keys under v3; add owner-neutral projections `_attention_field_from_frame`,
   `_ready_channels_from_frame`, `_identity_self_summary_from_carry`.
6. `composition/runtime_assembly.py` — under `embodied_prompt_mode == "v3"`, build the engine with
   the v3 path + v3 bootstrap id, wire the larger thought `max_tokens`, and pass the identity carry
   into the request bridge.
7. Docs: `index.md`, `OWNER_GUIDE.*`, `PROGRESS_FLOW.*`, `ARCHITECTURE_BOUNDARIES.md`.

## 6. Migration Plan

1. v3 is the default `embodied_prompt_mode`; `"v1"` is an explicit legacy escape hatch. Tests that
   asserted v1 prompt behavior under the default assembly are migrated (pinned to
   `embodied_prompt_mode="v1"` or updated to the v3 contract), mirroring the R69 semantic-default
   migration.
2. Parsing robustness is unconditionally active in `11` because it is identity-preserving on clean
   JSON (existing bare-JSON tests stay green); no flag needed for it.
3. The token-budget bump applies to the thought profile in the default config; verify it does not
   regress existing LLM tests (they inject a fake provider and ignore max_tokens).
4. Later (P4) wires real channel arbitration onto the v3 `i_send_through` decision; out of scope.

## 7. Failure Modes and Constraints

1. v3 with a non-v3 bootstrap id → `PromptContractError` (fail-fast).
2. v3 with a missing `identity_self_summary` / `attention_field` / `ready_channels` key →
   `PromptContractError` (fail-fast; the bridge must fill them under v3).
3. `_extract_structured_json` returns `""` → `StructuredThoughtParseError` →
   `insufficient_generation`; never fabricates JSON.
4. Hardcoding identity in the prompt path is forbidden; identity text comes only from the injected
   summary.
5. Owner-boundary guard and ad-hoc-logging guard stay green; no new logging mechanism.

## 8. Observability and Logging

No new logging mechanism. The v3 contract and the `11` result flow through existing `21`/`17`/`23`
surfaces unchanged. The v3 layers are additional `PromptContractLayer` values the existing
observability already captures.

## 9. Validation Strategy

1. Unit: `OwnerGroundedEmbodiedPromptPath` renders the seven layers; identity layer equals the
   injected summary (change the summary → layer changes); no hardcoded identity literal in the
   module (guard-style assertion).
2. Unit: bootstrap-id guard raises on non-v3.
3. Unit: `_extract_structured_json` on (a) clean JSON, (b) `<think>...</think>` + JSON,
   (c) ```json``` fenced JSON, (d) `<think>` + fence + JSON, (e) no JSON → `""`.
4. Unit: `_parse_structured_thought` parses cases (a)-(d) and raises on (e); a `length`-truncated
   no-JSON completion → `insufficient_generation`.
5. Regression: default (`v1`) assembly byte-for-byte unchanged; existing prompt/thought tests green.
6. Composition: `assemble_runtime(..., embodied_prompt_mode="v3")` builds and runs one tick; the
   prompt request carries the three additive keys from real state.
7. Opt-in real-LLM smoke (not in CI): v3 path + reasoning model → parseable structured thought.
8. Guards: owner-boundary + ad-hoc-logging green; full network-free suite green.
