# Requirement 87 - Consequence-truth corroboration: real-delivery verdict (B4 closeout)

## 1. Background and Problem

Requirement `32` made the internal-to-visible causal chain falsifiable: the `17` evaluation owner
corroborates the prior completed tick's self-reported consequence outcome against that same tick's `21`
kernel execution timeline, publishing a `corroborated` / `discrepant` / `unverifiable_no_timeline`
verdict. But that corroboration checks only **stage-completion truth** — "the planner-bridge stage
completed" — not **delivery truth** — "the action's real effect actually happened". The
`ARCHITECTURE_PHILOSOPHY` §13.3.1 blocking point `B4` requires that, until a real effector exists, `17`/
`23` must honestly annotate this corroboration as "flow-completed, not really-delivered".

`84`/`85`/`86` now ship real effectors (the sandboxed OS file-system driver, autonomous tool selection,
and the governed OS command driver) whose results re-enter `02` sensory as `tool_result` reafference
packets carrying the originating decision's correlation provenance. The delivery evidence therefore now
exists in the runtime. R87 closes `B4` by upgrading the `17` consequence corroboration from
"flow-completed" to a **really-delivered, falsifiable** verdict for effector actions, consuming the
`tool_result` reafference (and the `85`-declared `effect_class`). It is strictly additive and read-only:
it does not change the `32` outcome taxonomy or the `internal_to_visible_consequence` scoring.

## 2. Goal

Give the `17` evaluation owner a first-class, falsifiable **delivery verdict** for an executed effector
action: an `executed`/`continuity_written` claim whose action is a real effector op is corroborated
against whether a matching `tool_result` reafference actually arrived and reported success —
`really_delivered`, `delivered_failed` (a discrepancy), or `delivery_unverified` (honest absence, never
optimistic) — while a non-effector (relay reply / internal) action is `delivery_not_applicable` and the
existing `32` stage-completion corroboration stands unchanged. Then re-run the P0–P3 exit evaluation to
confirm `B4` is closed and formally record P0–P3 at 100%.

## 3. Functional Requirements

### 3.1 Claim carries the delivery-relevant decision facts (`17`)
1. The `ConsequenceClaim` gains additive, defaulted fields identifying the executed action:
   `decision_id`, `selected_op`, `op_effect_class`, `op_user_visible` (all optional, default `None`), so
   the claim carried forward to the next tick can be matched against a `tool_result` reafference by
   `decision_id` and classified as an effector vs relay action. The existing fields and the outcome
   vocabulary are unchanged; `to_evidence` additively carries the new fields.
2. The evaluation engine populates these from the planner evidence the bundle already carries (the
   accepted `ActionDecision`'s id, selected op, and the op's declared `effect_class`/`user_visible`),
   never by re-deriving a decision.

### 3.2 Delivery evidence reaches evaluation (`17` bundle + composition)
1. The `EvaluationEvidenceBundle` gains an additive `delivered_tool_result_evidence` category (default
   empty), each item carrying a `decision_id` and an `ok` boolean (plus the standard `evidence_id`).
2. Composition's evaluation request bridge projects the **current tick's** drained `tool_result`
   reafferences (from the `channel_inbound_drain` stage result's `RawSignal`s whose `signal_type ==
   "tool_result"`, reading each one's correlation `decision_id` and `ok` from its preserved metadata)
   into `delivered_tool_result_evidence`. This is owner-neutral forwarding of already-published
   transport facts; evaluation interprets them, composition computes no verdict. In an assembly with no
   channel subsystem (the default), the category is empty.
3. The timing is sound: an effector decision dispatched at the end of tick N has its result drained at
   the start of tick N+1 (the inbound-drain stage runs first), so the tick N+1 evaluation — which
   corroborates the carried tick-N claim — observes that decision's reafference in the same frame.

### 3.3 Real-delivery corroboration verdict (`17`)
1. The evaluation owner publishes an additive `consequence_delivery` verdict (plus a bounded
   `consequence_delivery_detail`) in the artifact's gap summary, derived from the prior claim and the
   delivered-tool-result evidence:
   - the prior outcome is not `executed`/`continuity_written`, or the prior action is not an effector op
     (it is user-visible, its effect class is `internal_cognitive`, or it carries no `decision_id`) →
     `delivery_not_applicable` (the `32` stage-completion corroboration stands).
   - a `tool_result` reafference matching the prior claim's `decision_id` is observed with `ok == True`
     → `really_delivered`.
   - a matching reafference is observed with `ok == False` → `delivered_failed` (a discrepancy: the
     claim said executed but the effector reported failure) → a dedicated fidelity warning.
   - the prior action is an effector op but no matching reafference is observed → `delivery_unverified`
     (honest absence — e.g. a still-running async op — never an optimistic `really_delivered`).
2. The verdict is strictly additive: it does not change the `32` `consequence_corroboration` verdict,
   the outcome taxonomy, the `internal_to_visible_consequence` score, or any existing dimension. It is a
   new gap-summary field plus an optional warning.
3. `effect_class` is now a real consumer (closing the R85 "declared, consumed by `17`/`23` in R87"
   commitment). `op_user_visible` distinguishes a relay reply (rendered to a sink, no `tool_result`
   reafference expected) from a non-user-visible effector op (produces a reafference).

### 3.4 P0–P3 exit re-evaluation (B4 closeout)
1. A focused exit-evaluation test (mirroring the R64/R72/R73 pattern) asserts that, on the channel-bound
   assembly with an effector bound, an executed effector action's next-tick delivery verdict is
   `really_delivered`, and that a non-effector tick is `delivery_not_applicable` — demonstrating B4 is
   closed (consequence corroboration is now really-delivered-falsifiable, not only flow-completed).

## 4. Non-Functional Requirements

1. Read-only: `17` mutates no runtime state; it consumes only already-published owner/transport facts.
2. Strictly additive: the `32` corroboration verdict, outcome taxonomy, and scoring are byte-for-byte
   unchanged; the default and non-channel assemblies are unchanged (the new category is empty and the
   verdict is `delivery_not_applicable`).
3. No optimism: absence of a reafference is `delivery_unverified`, never `really_delivered`. A failure
   reafference is a `delivered_failed` discrepancy, never silently dropped.
4. No new logging mechanism; no `logging`/`print` under `src/`; owner-boundary + ad-hoc-logging guards
   stay green. Network-free, subprocess-free CI.

## 5. Code Behavior Constraints

1. `17` stays read-only; it never parses raw `LogEvent`s and never scrapes transient locals. Delivery
   evidence arrives as an owner-neutral bundle category projected by composition from a published stage
   result, exactly as the timeline/claim evidence does.
2. Composition forwards transport facts only (decision_id + ok from the reafference correlation); it
   computes no delivery verdict and no scoring.
3. The delivery corroboration re-derives no owner decision; it matches by `decision_id` and reads the
   reafference `ok` fact only.
4. No change to the `tool_result` packet shape, the drivers, the planner, or the channel subsystem.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/evaluation/contracts.py` (additive `ConsequenceClaim` fields + bundle
   category)
2. `helios_v2/src/helios_v2/evaluation/engine.py` (claim population + `_corroborate_delivery` +
   published verdict/warning)
3. `helios_v2/src/helios_v2/composition/bridges.py` (evaluation request bridge: project the decision
   facts into planner evidence + the drained `tool_result` reafferences into the new category)
4. `helios_v2/tests/test_evaluation_engine.py`, `test_evaluation_contracts.py`,
   `test_runtime_composition.py`, a P0–P3 exit-evaluation test
5. `helios_v2/docs/requirements/index.md`, `OWNER_GUIDE.*`, `PROGRESS_FLOW.*`,
   `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, `ROADMAP.zh-CN.md`

## 7. Acceptance Criteria

1. `ConsequenceClaim` additively carries `decision_id`/`selected_op`/`op_effect_class`/`op_user_visible`
   (default `None`) and `to_evidence` carries them; existing claim tests are unchanged.
2. The evaluation bundle additively carries `delivered_tool_result_evidence`; composition projects the
   current tick's drained `tool_result` reafferences (decision_id + ok) into it.
3. The evaluation artifact publishes `consequence_delivery` ∈ {`really_delivered`, `delivered_failed`,
   `delivery_unverified`, `delivery_not_applicable`} with a bounded detail, derived from the prior claim
   + the delivered evidence; `delivered_failed` raises a dedicated fidelity warning; the `32`
   `consequence_corroboration` verdict and scoring are unchanged.
3. End-to-end (channel-bound, deterministic): an executed effector action (`fs_write` or `run_command`)
   is `really_delivered` on the next tick; a failure reafference yields `delivered_failed`; a no-effector
   tick is `delivery_not_applicable`.
4. A P0–P3 exit re-evaluation test asserts B4 is closed; index/owner-guide/progress-flow/boundary/
   grounding/roadmap docs record P0–P3 at 100%.
5. Default and full suite green and network-free; owner-boundary + ad-hoc-logging guards pass.

## 8. Future Extension Scope

1. `23`-side long-range delivery diagnostics (cross-tick delivery-latency / retry accounting) build on
   this verdict.
2. Real external (network) drivers (QQ/Lark/voice) reuse the same delivery corroboration once their
   inbound acknowledgements re-enter as `tool_result`-class reafferences.
3. Retroactive upgrade of a `delivery_unverified` verdict once a late async reafference arrives is out
   of scope (the verdict is per-tick and honest at evaluation time).
