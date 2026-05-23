# Helios Preconscious Path Research

> Status: Foundational Research
> Task coverage: T6-1, T6-2
> Scope: preconscious / non-conscious candidate generation before full reflective planning
> Related runtime surfaces: `cognition/thinking_integration.py`, `cognition/phi.py`, `helios_main.py`, `helios_io/interaction_policy.py`, `regulation/policy.py`

> Archive note: the current implementation view now lives one level up under `docs/`. Use `../DESIGN_PHILOSOPHY.en.md` and `../IMPLEMENTATION_REFERENCE.en.md` when you need the active runtime definition.

## 1. Research Goal

This note narrows what “preconscious” should mean inside Helios.

The target is not a second hidden planner with unrestricted agency. The target is a bounded fast path that:

1. reacts before full reflective deliberation when salience is high,
2. contributes candidate actions rather than direct execution,
3. stays subordinate to policy evaluation, channel planning, and safety review.

## 2. Source Set

### 2.1 Default Mode and Replay

- Raichle et al. (2001), `A Default Mode of Brain Function`
- Buckner et al. (2008), `The Brain's Default Network`
- Andrews-Hanna (2012), adaptive role of the default network
- Foster (2017), replay and preplay as planning-support phenomena
- Schacter, Addis et al. (2007, 2012), episodic simulation and future construction

### 2.2 Fast Appraisal and Low-Level Action Biasing

- LeDoux (1996), fast affective routing and subcortical prioritization
- Pessoa (2008), emotion-cognition integration instead of hard separation
- Barrett et al. appraisal / construction perspectives on fast relevance shaping

### 2.3 Engineering Interpretation

- Preconscious output should be biasing and candidate-producing.
- It should not own truth, memory persistence policy, or transport decisions.
- It should be observable and suppressible when the system enters fatigue, overload, or safety-sensitive states.

## 3. Findings Relevant to Helios

### 3.1 Preconscious is not equal to “random mind wandering”

DMN / replay literature supports spontaneous associative activity, but not unconstrained outward action. In Helios, this maps to internal candidate pressure, replay fragments, and anticipation signals, not direct outbound behavior.

### 3.2 Fast path should stay pre-linguistic and low-commitment

The fast layer should prefer compact intent categories such as:

- orient
- observe
- defer reply
- mark urgency
- raise intimacy caution
- raise comfort-seeking bias

This fits the current architecture where `ActionProposal` is the lowest safe outward-facing unit.

### 3.3 Replay and anticipation are the strongest theoretical anchors

Existing Helios code already has the strongest support in:

- endogenous thought generation,
- autobiographical write-back,
- ICRI feedback,
- affect-biased internal content.

That means the first practical preconscious path should sit near `thinking_integration` and state aggregation, not near channel code.

## 4. Architectural Mapping

### 4.1 Inputs the preconscious path may read

- recent inbound salience
- temporal state (`boredom`, `fatigue_pressure`, `novelty_hunger`)
- neurochemical gate
- dominant affect and ICRI
- recent execution outcomes
- compact autobiographical / episodic retrieval hits

### 4.2 Outputs it may emit

Only low-confidence `ActionProposal` candidates with:

- `source_type = "preconscious"`
- explicit confidence / urgency trace
- strong constraints
- no direct channel execution authority

### 4.3 It must not own

- direct `route_outbound()` calls
- registry activation
- memory backend persistence policy
- final channel choice
- safety override decisions

## 5. Minimal Module Boundary

Recommended first boundary:

```text
PreconsciousSignals -> PreconsciousAssessment -> list[ActionProposal]
```

Where the module is allowed to:

1. compress recent internal and external salience,
2. surface low-latency candidate intents,
3. attach traceable reasons for later policy evaluation.

## 6. Constraints for Implementation

1. Preconscious proposals must always pass through `PolicyEvaluator` and `ExecutionPlanner`.
2. Proposal scores should be capped below strong reflective proposals unless explicit urgency exists.
3. The module must expose a structured trace for tests.
4. The module should degrade to “no proposals” cleanly when signals are weak.
5. Generated internal thought may feed preconscious salience, but thought text itself should not be treated as executable intent.

## 7. Why this matters for current code

Helios already contains internal thought and replay-like behavior. Without a dedicated preconscious boundary, those effects leak only indirectly into ICRI and memory. This task formalizes the missing architectural layer between internal salience and explicit action proposals.

## 8. Completion Statement

T6 is considered satisfied when:

1. this source note exists,
2. `docs/design.md` defines the corresponding module boundary,
3. task tracking reflects that preconscious work is now specified as a controlled proposal path rather than an unbounded hidden executor.