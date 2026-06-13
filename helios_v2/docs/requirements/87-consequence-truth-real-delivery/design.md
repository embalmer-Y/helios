# Requirement 87 - Consequence-truth corroboration: real-delivery verdict (design)

## 1. Design Overview

R87 upgrades the `17` consequence corroboration from "flow-completed" (the `32` stage-completion check)
to a falsifiable **really-delivered** verdict for effector actions, by consuming the `tool_result`
reafference that `84`/`85`/`86` already produce. It is strictly additive and read-only: a new claim
field set, a new bundle evidence category, a new `consequence_delivery` gap-summary verdict + optional
warning, and an owner-neutral composition projection. The `32` verdict, the outcome taxonomy, and the
`internal_to_visible_consequence` scoring are byte-for-byte unchanged. No new carry holder is needed: an
effector decision dispatched at the end of tick N has its reafference drained at the start of tick N+1
(the inbound-drain stage runs first), and the tick N+1 evaluation already corroborates the carried
tick-N claim — so the same frame that carries the prior claim also carries that decision's reafference.

## 2. Current State and Gap

1. `ConsequenceClaim` carries `tick_id`/`consequence_path_outcome`/`planner_status`/`action_status`/
   `continuity_written`; it does not identify the executed action (no `decision_id`/op facts), so a
   claim cannot be matched to a reafference.
2. `EvaluationEvidenceBundle` carries timeline + prior-claim evidence; there is no delivered-tool-result
   category.
3. `_corroborate_consequence` checks the prior claim vs the prior timeline (stage completed/failed) only
   — "flow-completed". `_SHIM_DERIVED_DIMENSIONS` annotates shim dimensions; `effect_class` has no
   consumer yet (R85 deferred it to R87).
4. `84`/`85`/`86` `tool_result` reafference packets carry `metadata["correlation"]` (the originating
   decision's provenance, incl. `decision_id`) and `metadata["ok"]`, drained into `02` via the
   `channel_inbound_drain` stage on the next tick.

## 3. Target Architecture

### 3.1 `ConsequenceClaim` additive fields (`evaluation/contracts.py`)

```python
@dataclass(frozen=True)
class ConsequenceClaim:
    claim_id: str
    tick_id: int | None
    consequence_path_outcome: str
    planner_status: str | None
    action_status: str | None
    continuity_written: bool
    decision_id: str | None = None        # R87: the accepted ActionDecision id (match key)
    selected_op: str | None = None        # R87
    op_effect_class: str | None = None    # R87: from the op's declared ChannelOpSpec
    op_user_visible: bool | None = None    # R87: relay reply (True) vs effector (False)
    # to_evidence additively carries the four new fields
```

The engine populates them from `planner_evidence` (see 3.4); all default `None`, so existing
construction and the R32 carry are unchanged when absent.

### 3.2 `EvaluationEvidenceBundle` additive category (`evaluation/contracts.py`)

```python
    delivered_tool_result_evidence: tuple[Mapping[str, object], ...] = ()
    # each item: {"evidence_id": str, "decision_id": str, "ok": bool}
```

Validated like the other evidence categories (non-empty `evidence_id`); default empty.

### 3.3 `_corroborate_delivery` (`evaluation/engine.py`)

A new read-only helper, parallel to `_corroborate_consequence`, mapping the prior claim + the delivered
evidence into a verdict + detail:

```
prior = prior_consequence_claim_evidence[0]  (or none -> delivery_not_applicable:no_prior_claim)
outcome = prior.consequence_path_outcome
if outcome not in {executed, continuity_written}: -> delivery_not_applicable:outcome
decision_id = prior.decision_id
effect_class = prior.op_effect_class
user_visible = prior.op_user_visible
if decision_id is None or user_visible is True or effect_class == "internal_cognitive":
    -> delivery_not_applicable:non_effector
match = the delivered item whose decision_id == prior.decision_id
if match is None:        -> delivery_unverified:no_reafference
if match.ok is True:     -> really_delivered
else:                    -> delivered_failed:effector_reported_failure
```

The verdict + detail are published in `gap_summary["consequence_delivery"]` /
`["consequence_delivery_detail"]`. A `delivered_failed` verdict appends a dedicated
`consequence_delivery_discrepancy` fidelity warning (referencing the prior claim + delivered evidence
ids). The existing `consequence_corroboration` verdict, the outcome taxonomy, and all dimension scores
are untouched.

### 3.4 Composition evaluation request bridge (`composition/bridges.py`)

Two additive projections in the bridge that builds the `EvaluationEvidenceBundle`:

1. Planner evidence gains additive keys for the accepted decision: `decision_id`, `selected_op`,
   `op_effect_class` (from the decision's `policy_trace["op_effect_class"]`), and `op_user_visible`
   (from the channel-state op spec's `user_visible`, projected the same way `op_specs` already is). The
   engine reads these to populate the claim. Absent (no decision / non-channel) → the claim's new fields
   stay `None` → `delivery_not_applicable`.
2. A new `delivered_tool_result_evidence` projection: read the current frame's `channel_inbound_drain`
   stage result (when present); for each drained `RawSignal` with `signal_type == "tool_result"`, read
   `metadata["correlation"]["decision_id"]` and `metadata["ok"]` and emit `{evidence_id, decision_id,
   ok}`. Owner-neutral transport forwarding; no verdict computed. Absent stage / non-channel assembly →
   empty.

### 3.5 No new carry holder

The R32 `prior_consequence_claim` carry already moves the tick-N claim into the tick N+1 bundle. The
tick N+1 frame's `channel_inbound_drain` already holds the tick-N decision's reafference. So the bridge
reads both from the tick N+1 frame/carry and the engine matches them — no additional `RuntimeHandle`
carry seam is introduced. (Production async: a still-running op simply yields `delivery_unverified` at
N+1; CI inline delivers at N+1 deterministically.)

## 4. Data Structures

1. `ConsequenceClaim`: +4 additive optional fields + `to_evidence` carries them.
2. `EvaluationEvidenceBundle`: +`delivered_tool_result_evidence` (additive, default empty).
3. `EvaluationArtifact.gap_summary`: +`consequence_delivery` / `consequence_delivery_detail` (additive
   keys); a new `consequence_delivery_discrepancy` warning kind on `delivered_failed`.
4. No change to `tool_result` packets, drivers, planner, channel subsystem, or the `32` claim/timeline
   carry.

## 5. Module Changes

1. `evaluation/contracts.py` — additive claim fields + bundle category + validation.
2. `evaluation/engine.py` — populate the claim from planner evidence; `_corroborate_delivery`; publish
   the verdict + optional warning.
3. `composition/bridges.py` — the evaluation request bridge's planner-evidence + delivered-tool-result
   projections.
4. Tests + docs (see `task.md`).

## 6. Migration Plan

1. Additive and read-only. With no effector action (default/non-channel assembly), the new claim fields
   are `None`, the new category is empty, and `consequence_delivery` is `delivery_not_applicable` — the
   artifact is otherwise byte-for-byte unchanged.
2. The `32` corroboration path, vocabulary, and scoring are untouched; existing evaluation tests stay
   green.
3. `effect_class` becomes a real consumer here (R85 forward-declaration honored).

## 7. Failure Modes and Constraints

1. No prior claim / non-executed outcome / non-effector op → `delivery_not_applicable` (no warning).
2. Effector op, no reafference yet → `delivery_unverified` (honest; no warning; never optimistic).
3. Effector op, reafference `ok=False` → `delivered_failed` + `consequence_delivery_discrepancy` warning.
4. Read-only; no runtime mutation; no raw `LogEvent` parsing; owner-neutral composition projection only.

## 8. Observability and Logging

No new logging mechanism. The delivery verdict rides the existing `EvaluationArtifact` gap summary and
fidelity warnings; the delivered evidence rides the existing `tool_result` reafference metadata. Fully
reconstructable through `21`/`17`/`23`. No `logging`/`print` under `src/`.

## 9. Validation Strategy

1. Unit (contracts): `ConsequenceClaim` with the new fields round-trips through `to_evidence`; the bundle
   validates `delivered_tool_result_evidence`.
2. Unit (engine): `_corroborate_delivery` over a matrix — non-executed outcome, non-effector op,
   matching ok=true (`really_delivered`), matching ok=false (`delivered_failed` + warning), effector op
   with no reafference (`delivery_unverified`); the `32` `consequence_corroboration` verdict and scores
   are unchanged in every case.
3. Composition (network-free, deterministic): channel-bound assembly with an effector bound — an executed
   `fs_write`/`run_command` is `really_delivered` on the next tick; a failure-injected reafference is
   `delivered_failed`; a reply/no-action tick is `delivery_not_applicable`; the default assembly's
   artifact is unchanged.
4. P0–P3 exit re-evaluation test (R64/R72/R73 pattern) asserting B4 closed.
5. Guards: owner-boundary + ad-hoc-logging green; full network-free suite green.
