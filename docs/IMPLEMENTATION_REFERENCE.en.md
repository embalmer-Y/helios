# Helios Implementation Reference

> Status: Active
> Audience: maintainers, research-oriented contributors, and subsystem authors
> Source of truth: the codebase remains authoritative; this document links current implementation surfaces to theories, papers, research notes, and validation clues

## 1. Document Role

This file fills the missing layer between the active architecture docs and the foundational research notes:

- `ARCHITECTURE.*` explains how the system is layered
- `DESIGN_PHILOSOPHY.*` explains how the system runs
- this document explains which modules implement or explicitly draw from which theories, papers, and research results

If a theoretical note and current runtime behavior diverge, the code and active docs win.

## 2. How To Read This File

Use the reference in this order:

1. identify the layer where a module lives
2. check which theory or paper it draws from
3. inspect the implementation evidence and key classes or methods
4. review related tests to understand whether the idea has been turned into executable behavior

## 3. Module-Level Mapping

| Module | Runtime role | Theory / papers | Research anchors | Implementation status | Validation |
| --- | --- | --- | --- | --- | --- |
| `allostasis.py` | dynamic setpoint regulation and load accumulation | Sterling & Eyer (1988), McEwen (1998), Schulkin (2003) | `fep_formalization.md`, `friston_panksepp_synthesis.md` | implemented | `tests/test_drive_regulation_scoring.py`, `tests/test_helios_state_pipeline_pbt.py` |
| `daisy_emotion.py` | seven-system affect dynamics engine | Panksepp (1998), Russell (1980), Kuppens (2010), Solomon & Corbit (1974), Davidson (2000), Barrett (2017) | `panksepp_helio_mapping.md` | implemented | `tests/test_habituation_integration.py`, `tests/test_drive_integration.py` |
| `mood_tracker.py` | mood layer and emotional inertia | Gebhard (2005) ALMA, Kuppens (2010), Russell (1980) | `panksepp_helio_mapping.md` | implemented | `tests/test_helios_state_pipeline_pbt.py` |
| `personality.py` | Big Five to primary affect-system modulation | McCrae & Costa (1997), Davis & Panksepp (2011), Roberts et al. (2006) | `panksepp_helio_mapping.md` | implemented | `tests/test_habituation_pbt.py`, `tests/test_helios_state_pipeline_pbt.py` |
| `neurochem.py` | neuromodulatory background dynamics | dopamine / opioid / oxytocin / cortisol modulation frame | `neurochem_model.md` | implemented | `tests/test_drive_integration.py`, `tests/test_icri_temperature_pbt.py` |
| `cognition/phi.py` | ICRI / unified phi aggregation | Tononi (2004), Dehaene (2006), Seth (2011) | `dmn_thinking_model.md`, `fep_formalization.md` | implemented | `tests/test_lifecycle_integration.py`, `tests/test_helios_state_pipeline_pbt.py` |
| `cognition/drives.py` | five-dimensional drive-gap estimation | Friston FEP / active inference | `fep_formalization.md`, `friston_panksepp_synthesis.md` | implemented | `tests/test_drive_integration.py`, `tests/test_drive_regulation_scoring.py` |
| `cognition/appraisal.py` | SEC-to-affect mapping | appraisal tradition / Stimulus Evaluation Checks | `anthropic_emotion_concepts.txt` | implemented | `tests/test_llm_sec_evaluator.py` |
| `cognition/thinking_integration.py` | endogenous thought and DMN gating | DMN / replay / endogenous thinking | `dmn_thinking_model.md` | implemented | `tests/test_lifecycle_integration.py` |
| `memory/memory_system.py` | working, episodic, semantic, and autobiographical memory | multi-store memory models, Baddeley working memory | `DESIGN_PHILOSOPHY.*` | implemented | `tests/test_memory_compression.py`, `tests/test_conversation_history.py` |
| `memory/memory_compressor.py` | autobiographical summarization and compression | long-range consolidation plus narrative summarization | `DESIGN_PHILOSOPHY.*` | implemented | `tests/test_memory_compression.py`, `tests/test_consolidation_scheduling.py` |
| `helios_io/response_pipeline.py` | passive reply generation with context and emotional state | SEC-informed response gating, ICRI temperature modulation | `anthropic_emotion_paper.txt`, `DESIGN_PHILOSOPHY.*` | implemented | `tests/test_conversation_history.py`, `tests/test_llm_sec_evaluator.py`, `tests/test_channel_gateway.py` |
| `regulation/regulation.py` | memory-driven action regulation | affect regulation through behavior selection and outcome feedback | `friston_panksepp_synthesis.md`, `DESIGN_PHILOSOPHY.*` | implemented | `tests/test_drive_regulation_scoring.py`, `tests/test_behavior_executor_pbt.py` |
| `helios_main.py` | runtime orchestration and tick lifecycle | integrated loop across FEP, Panksepp affect, memory, cognition, and regulation | `ARCHITECTURE.*`, `DESIGN_PHILOSOPHY.*` | implemented | `tests/test_lifecycle_integration.py`, `tests/test_helios_state_pipeline_pbt.py` |

## 4. Key Module Details

### 4.1 `allostasis.py`

- Role: dynamically shifts setpoints from predicted demand and accumulated load rather than holding a fixed baseline.
- Theory: allostasis and allostatic load.
- Evidence: the module docstring explicitly cites Sterling & Eyer, McEwen, and Schulkin; `AllostaticState.update_demand()`, `accumulate_load()`, and `update_setpoint()` implement demand, load penalty, and recovery.
- Key classes and methods:
  - `AllostasisConfig`: parameterizes demand smoothing, load thresholds, and recovery.
  - `AllostaticState.update_demand()`: recent peaks drive predicted demand.
  - `AllostaticState.accumulate_load()`: deviation from baseline turns into load.
  - `AllostaticState.update_setpoint()`: setpoint drifts under demand and fatigue.

### 4.2 `daisy_emotion.py`

- Role: implements co-activated seven-system affect dynamics with chronometry and opponent process.
- Theory:
  - Panksepp primary affect systems
  - Russell valence-arousal circumplex
  - Kuppens emotional inertia
  - Solomon and Corbit opponent process
  - Davidson affective chronometry
  - Barrett-style co-activation rather than winner-take-all emotion labels
- Evidence: the module docstring plus `CHRONOMETRY`, `OPPONENT_PAIRS`, `VALENCE_BIAS`, `AROUSAL_BIAS`, and `BASELINE`; `AffectiveChronometer` and `OpponentRegulator` are the clearest theory-bearing structures.
- Key classes and methods:
  - `AffectState`: current affect snapshot over seven systems plus valence and arousal.
  - `AffectiveChronometer.tick()`: rise, peak, and decay dynamics.
  - `OpponentRegulator`: delayed rebound and repeated-exposure shaping.

### 4.3 `mood_tracker.py`

- Role: turns fast emotional states into a slower mood variable and feeds mood bias back into later event interpretation.
- Theory: ALMA, emotional inertia, Russell circumplex.
- Evidence: the module docstring, `MoodConfig.beta_valence`, `beta_arousal`, and `MoodState._update_label()`.
- Key classes and methods:
  - `MoodTracker.update()`: EMA accumulation from emotion to mood.
  - `MoodTracker.modulate_event()`: mood reshapes perceived event valence and arousal.
  - `MoodTracker.modulate_triggers()`: mood up-regulates or suppresses Panksepp triggers.

### 4.4 `personality.py`

- Role: uses Big Five traits as the long-range trait layer that modulates affect-system gains and chronometry while also allowing slow personality drift.
- Theory: Big Five, Davis and Panksepp on personality-primary affect coupling, Roberts et al. on trait change over time.
- Evidence: the module docstring plus `BIG5_TO_PANKSEPP` and `BIG5_TO_CHRONO`.
- Key classes and methods:
  - `PersonalityProfile._recompute()`: recalculates neuro gains and chronometry modifiers.
  - `PersonalityProfile.get_baseline()`: returns trait-modulated baseline activation.
  - `PersonalityProfile.adapt()`: long-range affective experience reshapes traits.

### 4.5 `cognition/phi.py`

- Role: aggregates sensory integration, emotional coherence, DMN depth, self-reflection, and global ignition into ICRI / phi.
- Theory: IIT, global neuronal workspace, predictive processing.
- Evidence: the module theory section and the five component fields on `UnifiedPhi`.
- Key classes and methods:
  - `UnifiedPhi.feed_emotional()`: converts multi-system resonance into emotional coherence.
  - `UnifiedPhi.feed_dmn()`: estimates temporal depth from thought count, novelty, and variety.
  - `UnifiedPhi.feed_ignition_from_panksepp()`: approximates global broadcast from distributed activation.

### 4.6 `cognition/drives.py`

- Role: computes curiosity, social, homeostatic, achievement, and aesthetic drive gaps.
- Theory: free energy principle and active inference.
- Evidence: the module-level `D(t) = Σ w_i × deficit_i(t)` framing, `DriveVector.total`, and the per-drive `_compute_*` methods.
- Key classes and methods:
  - `DriveVector`: thresholds, dominance, and weighted drive total.
  - `HeliosSnapshot`: light cross-layer input surface for drive estimation.
  - `DriveOracle.cycle()`: computes the five-dimensional drive state and applies neurochemical modulation.

### 4.7 `cognition/appraisal.py`

- Role: maps SEC features into Panksepp activation and affective bias signals.
- Theory: appraisal tradition and Stimulus Evaluation Checks.
- Evidence: `SECFeatures` exposes novelty, pleasantness, goal relevance, coping potential, urgency, and related variables; `AppraisalEngine.evaluate()` turns them into system activations and valence/arousal bias.
- Key classes and methods:
  - `SECFeatures`: standard appraisal input structure.
  - `AppraisalEngine.evaluate()`: rule-based appraisal projection into affective terms.
  - `EVENT_SEC_PROFILES`: canonical event profiles.

### 4.8 `cognition/thinking_integration.py`

- Role: triggers endogenous thought when DMN conditions hold and writes resulting thought activity back into autobiographical memory and the ICRI path.
- Theory: DMN, replay, and emotion-biased endogenous thought.
- Evidence: `EMOTION_THOUGHT_BIAS`, `should_generate()`, and `_determine_dmn_activity()`.
- Key classes and methods:
  - `ThinkingEngineIntegration.should_generate()`: ICRI threshold, DMN gate, and throttling.
  - `ThinkingEngineIntegration.get_biased_types()`: dominant affect biases thought type.
  - `ThinkingEngineIntegration._record_thought()`: persists generated thought as autobiographical material.

### 4.9 `memory/memory_system.py`

- Role: unifies working, episodic, semantic, and autobiographical memory with consolidation and retrieval entry points.
- Theory: multi-store memory models, Baddeley working memory, episodic-to-semantic consolidation.
- Evidence: the module docstring and the explicit `WorkingMemory` reference to Baddeley and Miller.
- Key classes and methods:
  - `MemoryItem`: shared memory atom across stores.
  - `WorkingMemory.recall()`: expires or promotes items into episodic memory.
  - `MemoryItem.recalc_importance()`: combines valence, arousal, phi, and reuse into memory importance.

### 4.10 `memory/memory_compressor.py`

- Role: compresses older autobiographical moments into day-level narrative summaries.
- Theory: long-range autobiographical summarization after consolidation.
- Evidence: `find_compressible_days()`, `compress_day()`, and `execute_compression()`.
- Key classes and methods:
  - `CompressedSummary`: retains date, emotional arc, key events, and source ids.
  - `MemoryCompressor._build_emotional_arc()`: reduces many moments into one emotional trajectory.

### 4.11 `helios_io/response_pipeline.py`

- Role: generates passive replies from message text, SEC evaluation, memory context, autobiographical context, emotional state, and ICRI-shaped generation parameters.
- Theory: appraisal-informed response gating plus consciousness-shaped expression.
- Evidence: `should_reply()` gates on goal relevance and novelty, while `generate_reply()` pulls history, memory, autobiographical traces, emotion, personality, and temperature into the prompt.
- Key classes and methods:
  - `ResponsePipeline.should_reply()`: minimum urgency threshold from appraisal variables.
  - `ResponsePipeline.generate_reply()`: multi-context prompt construction plus LLM invocation.
  - `ResponsePipeline.record_exchange()`: deposits the interaction back into conversation history.

### 4.12 `regulation/regulation.py`

- Role: chooses regulating behavior from emotional deviation and remembered past outcomes instead of a rigid lookup table.
- Theory: regulation as a route back toward comfort or stability through action and feedback.
- Evidence: the module docstring explicitly frames behavior as a regulation tool; `RegulationMemory` stores outcome estimates; `BOOTSTRAP_REGULATION` is presented as overridable initialization rather than final policy.
- Key classes and methods:
  - `RegulationMemory.update()`: learns from later outcome deltas.
  - `ActionCandidate.score`: blends expected benefit and confidence.
  - `RegulationEngine.tick()`: selects actions from current affect, time, and drive state.

### 4.13 `helios_main.py`

- Role: the runtime orchestrator that fixes the tick lifecycle and closes the loop among affect, memory, cognition, regulation, and outward execution.
- Theory: not a single-paper module, but the concrete integration surface for FEP, Panksepp affect, DMN thinking, memory consolidation, and behavior feedback.
- Evidence: the active design docs mirror the current initialization and tick phases in code, including DAISY, allostasis, mood, personality, memory, phi, drives, thinking, passive reply, and regulation-to-limb execution.

## 5. Layer-To-Theory Map

| Layer | Main modules | Main theory frame |
| --- | --- | --- |
| Affective substrate | `daisy_emotion.py`, `allostasis.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, `habituation.py` | Panksepp affect systems, allostasis, mood inertia, trait modulation, neuromodulatory background |
| Cognition | `cognition/phi.py`, `cognition/drives.py`, `cognition/appraisal.py`, `cognition/thinking_integration.py` | IIT, GNW, predictive processing, FEP, appraisal, DMN |
| Memory | `memory/memory_system.py`, `memory/autobiographical.py`, `memory/memory_compressor.py` | multi-store memory, autobiographical continuity, consolidation and compression |
| Regulation | `regulation/regulation.py`, `helios_io/limb.py`, `helios_io/limb_decision_bridge.py` | affect regulation, action selection, feedback learning |
| I/O boundary | `helios_io/response_pipeline.py`, `helios_io/llm_sec_evaluator.py`, `helios_io/channel_gateway.py` | SEC-guided response, context-conditioned expression, channel mediation |
| Main loop orchestration | `helios_main.py` | integrated system loop across affect, memory, cognition, regulation, and execution |

## 6. Annotation Rules

When new research-linked modules are added or rewritten, prefer this minimum standard:

1. module docstring states theory origin and implementation boundary
2. classes or key methods that directly embody a theory component say so explicitly
3. code should point to curated `docs/foundations/` notes rather than embedding long paper excerpts
4. if a module is only inspired by a theory rather than implementing it directly, say that clearly

## 7. Relationship To Other Docs

- `ARCHITECTURE.*`: layer ownership and boundaries
- `DESIGN_PHILOSOPHY.*`: tick flow and object collaboration
- `SOURCE_CATALOG.*`: in-repo materials, citations, and collection backlog
- foundational notes: theoretical background and deeper rationale