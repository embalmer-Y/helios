# Helios v2 Brain Architecture Comparison

> Status: baseline scientific-grounding snapshot on 2026-06-02
> Scope: cautious functional comparison for implemented and near-term Helios v2 owner domains
> Role: scientific grounding, explicit non-goals, and requirement-linked gap analysis

## 1. Purpose

This document is the active scientific-grounding companion to `ARCHITECTURE_BOUNDARIES.md`.

It does not claim that Helios v2 is biologically equivalent to a human brain, nor that one software owner corresponds to one brain region. It exists to:

1. map owner domains to cautious brain-function analogs,
2. distinguish stronger evidence from functional inspiration and engineering hypothesis,
3. record explicit non-goals,
4. connect major functional gaps back to concrete v2 requirements,
5. order the major gaps into an owner-wave roadmap rather than leaving them as an unprioritized list.

Companion progress-truth documents:

1. `OWNER_GUIDE.md` for the by-owner responsibility/completeness/next-step reference and the whole-system distance reading (section 5).
2. `requirements/index.md` for the authoritative per-requirement `Maturity` column.
3. `PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md` for the color-coded module progress map.

## 2. Comparison Rules

1. Comparisons are functional, not organ-equivalence claims.
2. A mapping may describe a role analogy, an engineering substitute, or a current absence.
3. No requirement may cite this document as proof of biological realism.
4. Boundary ownership remains governed by `ARCHITECTURE_BOUNDARIES.md`; this document does not redefine runtime owners.
5. When a capability is weak or missing, the gap must be stated explicitly rather than hidden by broad analogy language.

## 3. Evidence Categories

| Category | Meaning | How to use it |
| --- | --- | --- |
| `A_stronger_grounding` | Mature review literature or well-established findings support the functional concern and its architectural relevance | Safe for cautious functional framing, not for implementation literalism |
| `B_functional_inspiration` | Literature supports the direction of the analogy, but does not determine software structure on its own | Use as design motivation, not as implementation proof |
| `C_engineering_hypothesis` | The mapping is mainly an engineering comparison or planning hypothesis | Use only with explicit caveats and gap notes |

## 4. Domain Mapping Snapshot

| Helios v2 domain | Brain-function analog | Mapping type | Evidence category | Current grounding status | Primary gaps | Requirement links |
| --- | --- | --- | --- | --- | --- | --- |
| `03-07` appraisal, neuromodulation, feeling, memory-affect, workspace | salience shaping, state modulation, working competition, bounded reportable content preparation | functional analogy | `A_stronger_grounding` | baseline owner set exists; with `35` the `03` novelty dimension is the first real signal (novelty = distance from stored memory via the `34` embedding substrate), with `36` the `04` neuromodulator levels derive from real appraisal salience, and with `37`+`38` both of `04`'s downstream consumers are now real: `37` couples the real norepinephrine level into the `09` gate decision (arousal term), and `38` makes the `05` interoceptive feeling vector a real bounded function of the `04` state (valence from dopamine/opioid/serotonin vs cortisol, arousal from norepinephrine, tension/pain_like from cortisol, social_safety from oxytocin). The other four `03` dimensions, `04`'s dual-timescale dynamics, `06-07`, and the cortisol/inhibition hard gate are still shim, and cross-domain integration depth is still uneven | the four non-novelty `03` dimensions and `06-07` remain constant first-version shim; `04`/`05` are now real but stateless (no prior-tick tonic/phasic decay or feeling persistence), the real `05` feeling does not yet measurably shape `06` memory-affect/behavior, and the cortisol/inhibition hard gate is not yet coupled, so modulation shapes later owners more narrowly than a strong biological analog would imply | `03`, `04`, `05`, `06`, `07`, `08`, `09`, `34`, `35`, `36`, `37`, `38` |
| `08` conscious content | globally reportable committed content rather than raw latent candidates | functional analogy | `A_stronger_grounding` | owner boundary is explicit and committed-content semantics are formalized | conscious commitment still does not guarantee meaningful downstream behavioral consequence | `08`, `17`, `18` |
| `09-11` gating, retrieval, internal thought | selective ignition, memory-guided maintenance, internally generated cognitive continuation | functional analogy | `A_stronger_grounding` | owner chain exists and runs in the runtime path; with `37` the `09` gate decision is, under the semantic-memory assembly, the first real consumer of an `04` neuromodulator level (norepinephrine couples into selective ignition as a bounded arousal term) | multi-tick continuity is improved but still bounded and policy-shallow compared with long-horizon subjective continuity; the gate's other inputs remain first-version shim | `09`, `10`, `11`, `18`, `37` |
| `13-16` planner, writeback, prompt, outward-expression chain | action selection, consequence recording, controlled motor preparation, pre-execution externalization shaping | engineering substitute | `B_functional_inspiration` | owner boundaries are explicit and safer than earlier monolithic reply paths | final outward consequence still depends on policy and transport layers that are not yet deeply proactive | `13`, `15`, `16`, `18` |
| `17` evaluation | read-only metacognitive-style audit and provenance-based self-check | engineering substitute | `B_functional_inspiration` | formal evidence bundle and diagnostic artifact owner now exists | diagnostic depth remains shallower than the final project goal and still under-consumes richer autonomy continuity semantics | `17`, `18` |
| `18` autonomy | self-directed continuation pressure integration, deferred continuity, bounded proactive tendency | functional analogy | `B_functional_inspiration` | owner now supports multi-tick deferred continuity with long-horizon decay, merge, and resolution accounting | still deterministic and bounded, not a rich open-ended autonomy policy or independently grounded motive system | `18` |
| `30` channel driver subsystem | peripheral afferent/efferent transport pathways (sensory transduction relay inbound, motor-output relay outbound) rather than cognition | engineering substitute | `C_engineering_hypothesis` | a dedicated transport owner exists with a uniform driver protocol, bounded NAPI-style inbound drain, bounded outbound dispatch, transport-intrinsic QoS, and fail-fast readiness; with `31` a first concrete local driver (CLI) is bound and an opt-in channel-bound runtime runs a real local afferent/efferent round trip | real external (network) afferent/efferent traffic (QQ/voice/vision) is still future; the channel-bound assembly is opt-in, not the default runtime | `30`, `31`, `02`, `03`, `13` |
| identity and governance path | persistent self-model maintenance, self-revision constraint, continuity-preserving identity updates | engineering substitute | `B_functional_inspiration` | self-revision governance owner is explicit | long-horizon self-model evolution remains more audited than genuinely developmental | `14`, `18` |
| observability plus documentation owners | structured runtime traceability plus explicit theory-of-system discipline rather than a brain analogue | engineering substitute for auditability plus current absence of biological analogue by design | `C_engineering_hypothesis` | documentation discipline is formalized and kernel-level runtime observability now exists | observability is still kernel-scoped and documentation truth is still not backed by automated consistency checks | `19`, `20`, `21` |

## 5. Explicit Gap Analysis

| Gap id | Gap statement | Why it matters for brain-like claims | Requirement links |
| --- | --- | --- | --- |
| `gap_behavioral_consequence_binding` | Evaluation consumes the prior-tick execution timeline and scores explicit consequence-binding path outcomes (internally-activated, internal-only-decision, blocked, rejected, executed, continuity-written). With `27` the model's structured output drives the `11` owner's sufficiency/continuation/action decisions; with `28` a model continue/no-action decision closes through the full chain as an explicit `internal_only_decision`; with `29` the `18` autonomy disposition is derived from that real cognition (act -> externalize, no-action -> reflect/defer); and with `32` evaluation now corroborates the prior tick's self-reported outcome against that same tick's kernel execution timeline and publishes a `corroborated` / `discrepant` / `unverifiable_no_timeline` verdict, escalating any contradiction to a `consequence_discrepancy` warning, so the internal-to-visible causal chain is now falsifiable against execution truth rather than self-report alone. Remaining: real outward channel execution of a proposal is still pending (wave_C outward closure), the surrounding shim owners (`03-10`) are still deterministic, and richer discrepancy depth awaits non-deterministic cognition and `21` owner-level emission | Brain-like claims are weak if internal state does not reliably shape consequential action or restraint, and weaker still if the claimed chain cannot be falsified; cognition now shapes the thought-owner decision, both act and no-act paths close through the chain, the proactive disposition faithfully reflects the decision, and the self-reported consequence is now checked against execution truth | `17`, `21`, `22`, `23`, `18`, `25`, `26`, `27`, `28`, `29`, `32` |
| `gap_long_horizon_autonomy` | Autonomy aggregates deferred continuity into reinforceable, conflict-arbitrated long-horizon threads with an owner-owned long-horizon state. With `29` the thread layer now actually runs on real cognition: real no-action deferrals form and reinforce threads, where before `29` the hardcoded externalize-every-tick drive kept `active_thread_count` permanently 0. The thread layer is still a deterministic skeleton pending real motive content, and cross-tick reinforcement strength is bounded by the existing `18` continuity-key scheme | Stronger subjective continuity requires richer persistence, conflict handling, and motive evolution; the thread structure now forms on genuine cognition and its value grows once real motive content and a sharper key scheme land | `18`, `24`, `29` |
| `gap_grounded_self_revision` | Identity governance exists, but self-evolution remains tightly audited and relatively shallow | Brain-inspired self-model claims need explicit long-term continuity, not only controlled patch updates | `14`, `18` |
| `gap_execution_closure` | Proactive tendency does not yet close into a richer external action ecology with the same strength as internal traces. With `30` the transport substrate exists as a dedicated owner; with `31` the first concrete driver (local CLI) is bound and an opt-in channel-bound runtime runs a real local round trip end to end (operator line -> stimulus -> cognition chain -> externalizing decision rendered to the channel sink), proving the inbound-drain-to-sensory and planner-to-outbound-dispatch seams. The closure is still local-only: real external (network) drivers (QQ/voice/vision) and making a channel-bound assembly the default runtime remain future requirements | A system that mostly sustains internal traces without robust external consequence remains only partially aligned with action-oriented cognition; outward closure is now demonstrated locally end to end, and broadens once real external drivers land | `13`, `16`, `18`, `30`, `31` |
| `gap_scientific_traceability` | Grounding claims are formalized, kernel-level observability exists, and evaluation consumes the execution timeline as formal evidence. Real LLM-backed thought content (`25`, `26`) now flows through the same evaluation surfaces, so traceability is exercised against non-deterministic thought content; the remaining shim owners (`03-10`, `12-16`) keep this gap open until they too land real signals | Scientific-grounding language drifts easily unless later requirements keep traceability active and consume the new evidence surfaces | `19`, `20`, `21`, `23`, `25`, `26` |
| `gap_persistence_and_learning` | Until `33` the runtime had no durable memory at all: every continuity packet, autobiographical trace, and the whole experience stream were lost on process exit, so the system could not subjectively re-enter a prior existence and no learning could accumulate. With `33` (P2 opener) the `15` experience-writeback continuity stream is durably persisted (SQLite file backend) and, on an opt-in persistent assembly, re-enters the `10` directed-retrieval thought window after a restart; with `34` recall is now semantic rather than recency-only: a backend-neutral embedding owner embeds each record at write, the store ranks by bounded cosine similarity, and `10` recalls the experience most relevant to the current query (including a prior session's, after a restart). The gap remains partially open: only the `15` stream is persisted (memory items `06`, interoceptive/neuromodulator state `04`/`05`, identity state `14` are not yet durable), there is no latest-state checkpoint/restore, `03` novelty does not yet consume the embedding substrate (the first P3 slice), and no parameter learning yet consumes the durable base (that is P5) | Brain-like claims about a continuous self require that experience survive and re-enter across sessions by relevance, and self-evolution requires a durable substrate on which learning can accumulate; semantic restart recall of real experience now exists, but richer persistence, state checkpointing, real novelty-from-memory, and actual learning remain future P2/P3/P5 work | `33`, `34`, `15`, `10`, `25` |

## 6. Explicit Non-Goals

This document does not justify or prioritize:

1. one-to-one brain-region naming for software modules,
2. neuron-level or synapse-level simulation,
3. neurotransmitter-equation realism as a short-term requirement goal,
4. promotional claims that Helios v2 is conscious, sentient, or biologically brain-equivalent,
5. replacing owner-boundary engineering truth with neuroscience vocabulary.

## 7. Literature Grounding Snapshot

1. Miller EK, Cohen JD. An integrative theory of prefrontal cortex function. Annual Review of Neuroscience, 2001.
   Role: supports cautious comparison for goal maintenance, selection, and executive control.
   Category: `A_stronger_grounding`.
2. Squire LR. Memory systems of the brain: a brief history and current perspective. Neurobiology of Learning and Memory, 2004.
   Role: supports memory-system differentiation and bounded analogy to layered memory owners.
   Category: `A_stronger_grounding`.
3. Dehaene S, Changeux JP. Experimental and theoretical approaches to conscious processing. Neuron, 2011.
   Role: supports comparing reportable committed content and broad broadcast-style integration without claiming one module equals consciousness.
   Category: `A_stronger_grounding`.
4. Sterling P. Allostasis: a model of predictive regulation. Physiology & Behavior, 2012.
   Role: supports predictive-regulation framing for modulation and internal-state pressure.
   Category: `A_stronger_grounding`.
5. Pessoa L. A network model of the emotional brain. Trends in Cognitive Sciences, 2017.
   Role: supports networked emotion-control coupling rather than isolated emotion-module thinking.
   Category: `A_stronger_grounding`.
6. Northoff G, Heinzel A, de Greck M, Bermpohl F, Dobrowolny H, Panksepp J. Self-referential processing in our brain: a meta-analysis of imaging studies on the self. NeuroImage, 2006.
   Role: supports cautious comparison for self-model continuity while avoiding simplistic persona equivalence.
   Category: `B_functional_inspiration`.

## 8. Direct Constraints on Later Work

1. Later requirements may reuse this document for cautious grounding language, but they must still cite concrete owner requirements for implementation truth.
2. `17` should continue tightening the link between internal evidence and visible behavioral consequence.
3. `18` should deepen subjective continuity only through explicit owner policy, not through hidden orchestration shortcuts.
4. Later documentation updates must preserve the distinction between functional analogy, engineering substitute, and current absence.
5. If a later owner materially changes the grounding picture, this document and requirement `20` must be updated together.

## 9. Owner-Wave Gap Roadmap

The roadmap below turns the current gap list into an owner-ordered planning sequence. It does not replace requirement packages; it identifies which owner wave should close which grounding gap first.

### 9.1 Roadmap rules

1. A wave is ordered by owner leverage, not by how easy the work sounds.
2. A later wave should not claim to solve a gap that still depends on an earlier owner truth remaining weak.
3. Each wave must name the grounding claim it strengthens and the failure mode it prevents.

### 9.2 Wave sequence

| Wave | Primary owners | Priority level | Grounding claim strengthened | Main gaps targeted | Why this wave comes now | Exit signal |
| --- | --- | --- | --- | --- | --- | --- |
| `wave_A_behavioral_truth` | `17`, supporting `21`, adjacent `18` evidence publication | closed at baseline (`32`) | internal activation has externally consequential diagnostic truth | `gap_behavioral_consequence_binding` | current brain-like claims are weakest where internal evidence can still outrun visible outcome, and `21` now provides the baseline execution timeline needed for better diagnostics | CLOSED at baseline by `32`: evaluation explicitly scores internal-to-visible consequence binding, consumes richer autonomy continuity evidence and the `21` kernel timeline, and now corroborates the prior tick's self-reported outcome against that timeline (`corroborated`/`discrepant`/`unverifiable_no_timeline`), making the causal chain falsifiable against execution truth. Deeper discrepancy depth is gated on non-deterministic cognition and `21` owner-level emission |
| `wave_B_long_horizon_subjectivity` | `18`, adjacent `14` and `15` continuity surfaces | highest | subjective continuity is more than bounded carry-forward | `gap_long_horizon_autonomy`, `gap_grounded_self_revision` | autonomy now has a real owner path, so the next leverage is richer persistence, conflict handling, and self-model continuity | autonomy and identity traces expose longer-horizon continuity states that remain owner-owned and diagnostically visible |
| `wave_C_execution_closure` | `13`, `16`, adjacent policy/externalization surfaces | medium_high | proactive tendency can close into constrained outward consequence rather than staying mostly internal | `gap_execution_closure` | stronger autonomy claims will still look shallow if proactive traces rarely become formal outward outcomes | proactive-origin action paths reach planner and outward consequence with explicit provenance and bounded rejection semantics |
| `wave_D_grounding_governance` | `19`, `20` | medium | scientific-grounding and owner truth remain traceable rather than drifting into narrative | `gap_scientific_traceability` | once earlier owner waves move, grounding docs must keep pace or the comparison layer becomes stale | grounding and boundary docs explicitly record changed claims, retired gaps, and newly opened gaps |

### 9.3 Wave details

#### Wave A - behavioral truth

1. Primary requirement target: `17`.
2. Supporting requirement target: `21` as the baseline structured execution-evidence substrate.
3. Adjacent requirement target: `18` only where new autonomy evidence must cross into diagnostics.
4. Grounding rationale: systems should not receive strong brain-like credit for internal dynamics that do not reliably affect visible behavior or visible restraint.
5. Minimum closeout markers:
   - evaluation artifacts distinguish internal activation from external consequence more sharply,
   - the `21` kernel timeline is consumed as evidence rather than existing as a disconnected log surface,
   - autonomy evidence includes enough continuity detail for evaluation to detect preserved vs resolved vs degraded continuity,
   - requirement-linked gap language in this document can narrow `gap_behavioral_consequence_binding` rather than merely restate it.
6. Closeout status: CLOSED at baseline by `32`. Evaluation consumes the `21` timeline as both an existence signal and a corroboration signal, publishing a per-tick `ConsequenceClaim` and an execution-truth corroboration verdict (`corroborated`/`discrepant`/`unverifiable_no_timeline`) that escalates contradictions to a `consequence_discrepancy` warning. The remaining depth (richer discrepancy taxonomies, preserved-vs-resolved-vs-degraded continuity corroboration, owner-level emission corroboration) is intentionally deferred to later non-deterministic cognition, wave_B, and the `21` owner-level emission slice, each via its own requirement.

#### Wave B - long-horizon subjectivity

1. Primary requirement target: `18`.
2. Adjacent requirement targets: `14`, `15`.
3. Grounding rationale: bounded carry and deferred continuity are meaningful, but still too thin to support stronger claims about long-horizon subjectivity or self-directed evolution.
4. Minimum closeout markers:
   - autonomy policy handles richer continuity evolution than simple bounded carry,
   - self-model or identity-governance traces can absorb longer-horizon change without bypassing audit ownership,
   - writeback and continuity surfaces preserve the relevant long-horizon evidence.

#### Wave C - execution closure

1. Primary requirement targets: `13`, `16`.
2. Adjacent requirement target: `18` where proactive provenance must survive into action selection.
3. Grounding rationale: a system that mostly carries inward traces but cannot robustly close them into external action remains only partially aligned with executive-control analogies.
4. Minimum closeout markers:
   - planner and externalization paths recognize proactive provenance explicitly,
   - outward-consequence success and rejection traces remain owner-bounded,
   - proactive externalization no longer depends on reply-first historical assumptions.

#### Wave D - grounding governance

1. Primary requirement targets: `19`, `20`.
2. Grounding rationale: once earlier waves deepen the runtime, the grounding layer must retire outdated claims and record new evidence levels or gap movement explicitly.
3. Minimum closeout markers:
   - this document records which gaps narrowed, shifted, or split,
   - boundary truth and grounding truth remain aligned,
   - later requirement packages cite the same roadmap vocabulary rather than inventing new ad hoc grounding language.

### 9.4 Near-term planning implication

1. `wave_A_behavioral_truth` is now closed at baseline by `32`; the next owner-wave priority is `wave_B_long_horizon_subjectivity`, not further documentation expansion in isolation. Per the locked phase roadmap in `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §13, the `P2` persistence base (`gap_persistence_and_learning`) is the highest strategic prerequisite once `P1` internal-closure work is sufficiently advanced.
2. `wave_B_long_horizon_subjectivity` now follows directly, since `32` closed the strongest behavioral-truth gap; richer long-horizon continuity should expose preserved-vs-resolved-vs-degraded continuity to the corroboration surface `32` established.
3. `wave_C_execution_closure` becomes the right focus only after the system can measure whether richer subjectivity is actually becoming behaviorally consequential.
4. `wave_D_grounding_governance` is continuous maintenance work, but it should trail substantive runtime owner movement rather than run ahead of it.
