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

1. `REQUIREMENT_DISTANCE_TO_FINAL_GOAL.md` for requirement-by-requirement distance assessment.
2. `TOTAL_DISTANCE_TO_FINAL_GOAL.md` for whole-system distance assessment.

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
| `03-07` appraisal, neuromodulation, feeling, memory-affect, workspace | salience shaping, state modulation, working competition, bounded reportable content preparation | functional analogy | `A_stronger_grounding` | baseline owner set exists, but cross-domain integration depth is still uneven | modulation still influences later owners more weakly than a strong biological analog would imply | `03`, `04`, `05`, `06`, `07`, `08` |
| `08` conscious content | globally reportable committed content rather than raw latent candidates | functional analogy | `A_stronger_grounding` | owner boundary is explicit and committed-content semantics are formalized | conscious commitment still does not guarantee meaningful downstream behavioral consequence | `08`, `17`, `18` |
| `09-11` gating, retrieval, internal thought | selective ignition, memory-guided maintenance, internally generated cognitive continuation | functional analogy | `A_stronger_grounding` | owner chain exists and runs in the runtime path | multi-tick continuity is improved but still bounded and policy-shallow compared with long-horizon subjective continuity | `09`, `10`, `11`, `18` |
| `13-16` planner, writeback, prompt, outward-expression chain | action selection, consequence recording, controlled motor preparation, pre-execution externalization shaping | engineering substitute | `B_functional_inspiration` | owner boundaries are explicit and safer than earlier monolithic reply paths | final outward consequence still depends on policy and transport layers that are not yet deeply proactive | `13`, `15`, `16`, `18` |
| `17` evaluation | read-only metacognitive-style audit and provenance-based self-check | engineering substitute | `B_functional_inspiration` | formal evidence bundle and diagnostic artifact owner now exists | diagnostic depth remains shallower than the final project goal and still under-consumes richer autonomy continuity semantics | `17`, `18` |
| `18` autonomy | self-directed continuation pressure integration, deferred continuity, bounded proactive tendency | functional analogy | `B_functional_inspiration` | owner now supports multi-tick deferred continuity with long-horizon decay, merge, and resolution accounting | still deterministic and bounded, not a rich open-ended autonomy policy or independently grounded motive system | `18` |
| identity and governance path | persistent self-model maintenance, self-revision constraint, continuity-preserving identity updates | engineering substitute | `B_functional_inspiration` | self-revision governance owner is explicit | long-horizon self-model evolution remains more audited than genuinely developmental | `14`, `18` |
| observability plus documentation owners | structured runtime traceability plus explicit theory-of-system discipline rather than a brain analogue | engineering substitute for auditability plus current absence of biological analogue by design | `C_engineering_hypothesis` | documentation discipline is formalized and kernel-level runtime observability now exists | observability is still kernel-scoped and documentation truth is still not backed by automated consistency checks | `19`, `20`, `21` |

## 5. Explicit Gap Analysis

| Gap id | Gap statement | Why it matters for brain-like claims | Requirement links |
| --- | --- | --- | --- |
| `gap_behavioral_consequence_binding` | Evaluation now consumes the prior-tick execution timeline and scores explicit consequence-binding path outcomes (internally-activated, blocked, rejected, executed, continuity-written), but the scored cognition chain is still deterministic shim, so the binding is measurable yet not yet exercised against non-deterministic behavior | Brain-like claims are weak if internal state does not reliably shape externally consequential action or inaction; the measurement framework now exists, and its falsifiability value grows once real cognition lands | `17`, `21`, `22`, `23`, `18` |
| `gap_long_horizon_autonomy` | Autonomy now aggregates deferred continuity into reinforceable, conflict-arbitrated long-horizon threads with an owner-owned long-horizon state, but the thread layer is still a deterministic skeleton pending real motive content | Stronger subjective continuity requires richer persistence, conflict handling, and motive evolution; the thread structure now exists and its value grows once real cognition populates it | `18`, `24` |
| `gap_grounded_self_revision` | Identity governance exists, but self-evolution remains tightly audited and relatively shallow | Brain-inspired self-model claims need explicit long-term continuity, not only controlled patch updates | `14`, `18` |
| `gap_execution_closure` | Proactive tendency does not yet close into a richer external action ecology with the same strength as internal traces | A system that mostly sustains internal traces without robust external consequence remains only partially aligned with action-oriented cognition | `13`, `16`, `18` |
| `gap_scientific_traceability` | Grounding claims are formalized, kernel-level observability exists, and evaluation now consumes the execution timeline as formal evidence, but the consumed behavior is still deterministic shim pending real cognition | Scientific-grounding language drifts easily unless later requirements keep traceability active and consume the new evidence surfaces | `19`, `20`, `21`, `23` |

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
| `wave_A_behavioral_truth` | `17`, supporting `21`, adjacent `18` evidence publication | highest | internal activation has externally consequential diagnostic truth | `gap_behavioral_consequence_binding` | current brain-like claims are weakest where internal evidence can still outrun visible outcome, and `21` now provides the baseline execution timeline needed for better diagnostics | evaluation artifacts explicitly score internal-to-visible consequence binding and consume both richer autonomy continuity evidence and the `21` kernel timeline |
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

1. The next owner-wave priority remains `wave_A_behavioral_truth`, not further documentation expansion in isolation.
2. `wave_B_long_horizon_subjectivity` should follow immediately after `17` closes the strongest behavioral-truth gap.
3. `wave_C_execution_closure` becomes the right focus only after the system can measure whether richer subjectivity is actually becoming behaviorally consequential.
4. `wave_D_grounding_governance` is continuous maintenance work, but it should trail substantive runtime owner movement rather than run ahead of it.
