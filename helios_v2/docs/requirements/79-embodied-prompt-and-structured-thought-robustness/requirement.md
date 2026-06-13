# Requirement 79 - Owner-Grounded Embodied Prompt and Structured-Thought Robustness

## 1. Background and Problem

R70 shipped semantic bridges that project real `04`/`05`/`09`/`10` state into the embodied
prompt, and R27 added a structured `json_object` thought envelope that `11` parses into its
fired-cycle judgment. Two problems block this path from being both non-theatrical and stable.

1. The v1 prompt's anti-theatrical layer is a top-down rule, and its structured-thought schema
   leaks framework vocabulary (`sufficiency` / `continuation` / `action_proposal` /
   `self_revision_proposal`). The model reverse-engineers the schema and performs for it, and
   defaults to clinical third-person self-description because the prompt never frames a
   first-person embodied perspective.

2. The experimental branch proposed fixing this by hardcoding an identity assertion into the
   prompt ("You are a person. Not an AI, not a role, not a runtime."). That is an owner-boundary
   violation: the "who I am" belongs to the `14` identity-governance owner, and v1 already
   renders identity from an injected `identity_boundary_summary` rather than hardcoding it.
   Hardcoding it also risks fabricating a self-model the runtime has not yet earned (the
   self-awareness acceptance criterion FG-3 is not yet read-only reconstructable), which the
   architecture philosophy §3.3/§7.5 forbids.

A real LLM prompt probe (2026, MiniMax-M3, via `scripts/run_llm_prompt_probe.py`) of a proposed
owner-grounded embodied prompt (identity rendered from owner state, natural-language fields, a
focused/peripheral/filtered attention field, a ready-channel list, and an upgraded
"only-what-the-state-supports" anti-theatrical rule) confirmed the behavior is correct: the model
produced a grounded first-person response anchored to the injected body state (high tension, low
social-safety), never referred to itself as an AI/runtime/role, honored the single ready channel,
and obeyed the cross-field hard rules — without any hardcoded "you are a person" assertion.

The same probe, run twice, also exposed a separate, decisive defect that is not a prompt-wording
problem: a reasoning model emits a `<think>...</think>` block and a markdown ```json``` code fence
around the JSON, so `11`'s `_parse_structured_thought` (a bare `json.loads(output_text)`) fails to
parse and falls to `insufficient_generation`. Adding an explicit "output only raw JSON" prompt
instruction did not fix it (the `<think>` block is a model-architecture behavior the prompt cannot
suppress); worse, the reasoning text consumed the whole token budget and the response was
truncated (`finish_reason: length`) before any JSON was emitted. On a reasoning model the current
runtime thought path therefore cannot reliably parse structured cognition, which directly
threatens the P0–P3 stability and owner-computation gates (G0/G1).

## 2. Goal

Upgrade the `16` embodied-prompt path to an owner-grounded first-person embodied contract
(identity rendered from the `14` owner, natural-language fields, a real attention field, a real
ready-channel list, and an upgraded grounding-based anti-theatrical rule, with no hardcoded
identity assertion), and make `11`'s structured-thought parsing robust to a reasoning model's
`<think>` block and markdown code fence with a sufficient token budget and explicit fail-fast on
unparseable or truncated output, so real LLM cognition runs through the v3 path stably and without
theater while every embodied field remains traceable to real owner state.

## 3. Functional Requirements

### 3.1 Owner-grounded embodied prompt path (`16`)

1. The `16` prompt-contract owner must gain a v3 embodied-prompt path as a sibling to the v1
   `FirstVersionEmbodiedPromptPath`, implementing the existing `EmbodiedPromptPath` protocol; the
   v1 path must not be modified.
2. The v3 identity framing must be rendered from identity state supplied through the prompt
   request (sourced from the `14` identity-governance owner), not hardcoded in the prompt path.
   A hardcoded identity/subjectivity assertion (for example a literal "you are a person / not an
   AI") in the prompt path is forbidden.
3. The v3 response schema must use natural-language field names
   (`what_i_feel` / `what_i_think` / `i_want_to_say` / `i_will_send_it` / `i_send_through` /
   `i_want_to_act` / `act_type` / `remember_this` / `remember_because` / `i_want_to_think_more` /
   `think_more_about`); the v1 framework field names must not appear in the v3 schema.
4. The v3 prompt must render a focused/peripheral/filtered attention field from real `07`
   workspace/attention state, and a ready-channel list from real channel-state, through explicit
   request fields; it must not fabricate attention tiers or channels.
5. The v3 prompt must instruct first-person embodied expression that states only what the
   provided owner state supports, returns null when a field is unsupported, and never describes
   itself as an AI / model / runtime / role (the upgraded anti-theatrical rule).
6. The v3 schema must enforce the cross-field hard rules: `i_will_send_it` only if `i_want_to_say`
   is non-null; `i_send_through` only if `i_will_send_it` and only a ready channel;
   `remember_because` only if `remember_this`; `think_more_about` only if `i_want_to_think_more`.
7. The v3 path must keep `final_authorities` including `identity_governance`, `planner`, and
   `channel`; it must not claim execution, channel, or governance authority.

### 3.2 Structured-thought parsing robustness (`11`)

1. `11`'s structured-thought parse must robustly extract the JSON object before parsing: strip a
   leading/surrounding `<think>...</think>` reasoning block and a markdown code fence
   (```` ```json ```` / ```` ``` ````) when present, then parse the remaining JSON object. A
   model that emits a bare JSON object is unchanged.
2. The LLM request for thought must use a token budget large enough to hold a reasoning model's
   `<think>` content plus the JSON envelope, so a reasoning model does not truncate before the
   JSON (`finish_reason: length`).
3. After extraction, an absent or malformed JSON object must remain an explicit
   `insufficient_generation` result (the existing fail-fast behavior); the parser must never
   fabricate, guess, or silently coerce a structured envelope.
4. A `length`-truncated completion with no extractable JSON object must be an explicit
   non-success result, not a silent partial parse.
5. The prompt must still request a raw JSON object (the prompt-side instruction is retained
   because it helps non-reasoning models), but parsing robustness, not the prompt, is the
   authoritative guarantee.

### 3.3 Scope boundary

1. Real channel arbitration and outbound dispatch of the v3 decision (the experimental "R79-B")
   are out of scope here and deferred to P4; this requirement renders a ready-channel list and
   shapes the decision, but performs no real transport.
2. This requirement does not change `14` governance logic; it only consumes identity state the
   `14` owner already publishes (extending the prompt request seam if needed).

## 4. Non-Functional Requirements

1. Performance: the v3 path adds at most one extra string assembly per tick; the parse-time
   extraction is a bounded O(n) string operation; no new per-tick I/O.
2. Reliability: a reasoning model's `<think>`/fenced output parses correctly; a truncated or
   unparseable output is an explicit fail-fast non-success, never a silent or fabricated parse.
3. Observability and logging: no new logging mechanism; `21` remains the single logging
   mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: v3 is the default `embodied_prompt_mode` and `"v1"` is an explicit
   legacy escape hatch. Tests asserting v1 prompt behavior under the default assembly are migrated
   (pinned to `"v1"` or updated to the v3 contract), mirroring the R69 semantic-default migration.
   Parsing robustness is additive — a bare-JSON completion behaves exactly as before, so it needs
   no flag.

## 5. Code Behavior Constraints

1. Forbidden: hardcoding an identity or subjectivity assertion in the prompt path; identity
   framing must be rendered from owner-supplied state (`ARCHITECTURE_PHILOSOPHY` §3.3/§7.5).
2. Forbidden: the parser silently repairing, fabricating, or guessing a structured envelope;
   unparseable output after extraction is an explicit `insufficient_generation`.
3. Forbidden: the v3 prompt fabricating attention tiers, channels, feelings, memories, or facts
   not present in the injected owner state.
4. Boundary rule: identity belongs to `14`; the prompt path is a formatter; `11` owns the final
   judgment; the parser only extracts and validates, it does not judge.
5. The composition owner-boundary guard and the ad-hoc-logging guard must stay green.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/prompt_contract/engine.py` — the v3 owner-grounded embodied path.
2. `helios_v2/src/helios_v2/prompt_contract/contracts.py` — request/contract fields for the
   identity framing, attention field, and ready-channel list (additive).
3. `helios_v2/src/helios_v2/prompt_contract/__init__.py` — export the v3 path.
4. `helios_v2/src/helios_v2/internal_thought/engine.py` — robust JSON extraction in
   `_parse_structured_thought` and the thought-request token budget.
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` and `composition/bridges.py` — opt-in
   wiring of the v3 path, the identity-state render seam, and the attention/ready-channel
   projections (owner-neutral glue).
6. `helios_v2/tests/` — v3 path tests, parsing-robustness unit tests (fixed strings, network-free),
   default-assembly regression.
7. Docs: `requirements/index.md`, `OWNER_GUIDE.md`/`.zh-CN.md`, `PROGRESS_FLOW.en.md`/`.zh-CN.md`,
   `ARCHITECTURE_BOUNDARIES.md`.

## 7. Acceptance Criteria

1. The v3 path returns a layered embodied contract whose identity framing is rendered from the
   injected identity state: changing the injected identity state changes the rendered identity
   block, and no hardcoded "you are a person / not an AI" literal exists in the prompt path.
2. The v3 schema uses the natural-language field names and enforces the four cross-field hard
   rules; `i_send_through` is bounded to the ready-channel set.
3. Given a completion that wraps the JSON in a `<think>...</think>` block and/or a ```json``` code
   fence, `11` extracts and parses the structured evidence correctly (unit test with fixed
   strings, no network).
4. A completion with no extractable JSON object (including a `length`-truncated one) yields an
   explicit `insufficient_generation` result; the parser fabricates nothing.
5. The default assembly uses the v3 path; `embodied_prompt_mode="v1"` reproduces the v1 path
   byte-for-byte; the full network-free suite stays green (affected tests migrated); owner-boundary
   and ad-hoc-logging guards stay green.
6. An opt-in real-LLM smoke (not in CI) shows the v3 path producing a parseable structured thought
   end-to-end on a reasoning model.
7. `index.md` has a row 79; `OWNER_GUIDE` (`16` and `11` entries) and `PROGRESS_FLOW` record the
   v3 owner-grounded path and the parsing robustness, with sync lines naming R79.
