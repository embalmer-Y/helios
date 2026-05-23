# Helios Architecture Overview

> Status: Active
> Audience: developers and maintainers
> Source of truth: the codebase is authoritative; this document describes its stable structure and execution model

## 1. Project Shape

Helios is not a collection of one-shot task scripts. It is a continuously running affective and cognitive agent organized around a main loop in `helios_main.py`, with clear boundaries between substrate modules, memory, cognition, regulation, and external I/O.

After the cleanup and migration work, the architectural goal is to keep three boundaries explicit:

- the repository root holds only runtime entry surfaces and foundational affective substrate modules
- `helios_io/` owns all external interface and transport concerns
- `core/` holds only transport-agnostic runtime infrastructure

## 2. Runtime View

Standalone diagram: `diagrams/runtime_loop_overview.en.md`

This view emphasizes the continuous loop rather than a one-shot call chain. The system does not stop after producing one reply; external input, internal state change, behavior result, and later contact are all folded back into the next tick.

To keep the document grounded in the code, the diagram stays intentionally conservative. It shows stable loop direction without overstating multimodal output behavior that is not yet the default runtime path. In the current implementation, QQ remains the primary outbound path, while TTS is an available capability rather than the default sink for main-loop output.

Each tick of the main loop typically does the following:

1. collects input from channels and event sources
2. updates affective state, allostasis, mood, personality, and optional neurochemical or phi signals
3. runs memory write, retrieval, consolidation, and compression activity
4. performs cognitive appraisal, drive estimation, and endogenous thinking
5. turns internal state into behavioral tendencies through regulation
6. routes output back through `helios_io` as messages, speech, or other external actions

## 3. Layer Ownership

### 3.1 Repository root

The root now contains only:

- runtime and deployment surfaces such as `helios_main.py`, `dashboard.py`, `dashboard.html`, and service/shell assets
- foundational substrate modules such as `daisy_emotion.py`, `allostasis.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, and `habituation.py`

It no longer owns protocol clients, speech generation, channel abstractions, or compatibility shims.

### 3.2 `helios_io/`

`helios_io/` is the single owner of external interface code: anything that connects the internal agent to the outside world.

Key responsibilities:

- protocol clients: `protocols/qq.py`
- abstract channel types: `channel.py`
- gateway from channels into the event pipeline: `channel_gateway.py`
- concrete multimodal adapters: `channels/`
- LLM-backed outward generation: `llm/speech.py`
- conversation history, passive replies, and SEC evaluation
- execution boundary for outward behaviors via limb modules

The practical rule is straightforward: if code receives, sends, adapts, routes, serializes, or executes across an external boundary, it belongs in `helios_io/`.

### 3.3 `core/`

`core/` has been narrowed to lightweight runtime infrastructure:

- `event_source.py`
- `helios_state.py`
- `tick_guard.py`
- `trigger_merge.py`
- `separation_source.py`
- `drive_source.py`

`core/__init__.py` still re-exports some channel-facing symbols for compatibility, but ownership lives in `helios_io/`.

### 3.4 `memory/`

`memory/` owns autobiographical, episodic, semantic, working-memory, seed-import, and compression logic. It stores experience and exposes usable narrative context back to the runtime.

### 3.5 `cognition/`

`cognition/` owns appraisal, drives, phi, cognitive impact, and endogenous thinking. It interprets internal and external signals but does not own transport-specific protocol behavior.

### 3.6 `regulation/`

`regulation/` converts internal state into intent and behavioral pressure. It sits between cognition and execution, and it also receives feedback from completed behavior.

## 4. Key Runtime Surfaces

- `HeliosConfig` centralizes environment-driven configuration
- `Helios` composes the major runtime subsystems
- `ChannelGateway` normalizes channel input into the internal event flow
- `BehaviorExecutor` and `LimbDecisionBridge` map regulation output to external actions

## 5. Architectural Constraints

The current codebase should continue to follow these rules:

1. Do not add new protocol clients at the repository root.
2. Do not add transport-specific abstractions back into `core/`.
3. Add future protocol implementations under `helios_io/protocols/`.
4. Add future model-backed external generation under `helios_io/llm/`.
5. Keep `memory/`, `cognition/`, and `regulation/` focused on internal capability rather than protocol details.

## 6. Evolution Direction

Likely future improvements include:

- collecting the remaining root substrate modules into a more explicit package such as an affect or substrate namespace
- adding a clearer provider or plugin assembly model inside `helios_io/`
- keeping `current_structure.md` as the quick boundary sheet while this file stays the full architecture narrative

## 7. Theory-To-Layer Map

The current implementation no longer leaves research references as isolated comments. The codebase has a relatively stable mapping from theory clusters to architectural layers:

| Layer | Representative modules | Main theory frame |
| --- | --- | --- |
| Affective substrate | `daisy_emotion.py`, `allostasis.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, `habituation.py` | Panksepp primary affect systems, allostasis, ALMA, trait modulation, neuromodulatory background |
| Cognition | `cognition/phi.py`, `cognition/drives.py`, `cognition/appraisal.py`, `cognition/thinking_integration.py` | IIT, GNW, predictive processing, FEP, SEC appraisal, DMN |
| Memory | `memory/memory_system.py`, `memory/autobiographical.py`, `memory/memory_compressor.py` | multi-store memory, autobiographical continuity, consolidation and compression |
| Regulation | `regulation/regulation.py`, `helios_io/limb.py`, `helios_io/limb_decision_bridge.py` | affect regulation, action selection, outcome feedback learning |
| I/O boundary | `helios_io/response_pipeline.py`, `helios_io/llm_sec_evaluator.py`, `helios_io/channel_gateway.py` | SEC-guided interaction assessment, context-shaped expression, channel mediation |
| Main-loop orchestration | `helios_main.py` | system integration across the theory-bearing layers above |

For module, class, and key-method granularity, continue into `IMPLEMENTATION_REFERENCE.en.md`. For original materials, citation entries, and collection status, continue into `SOURCE_CATALOG.en.md`.

## 8. Document Roles

- this document explains how the system is organized now
- `DESIGN_PHILOSOPHY.en.md` explains how the system runs, why it is organized this way, and which design constraints should remain stable
- `IMPLEMENTATION_REFERENCE.en.md` explains which modules implement or explicitly draw from which theories, papers, and tests
- `SOURCE_CATALOG.en.md` explains which materials already exist in-repo, which citations are tracked, and which items still need to be collected
- `architecture_overview.html` provides the HTML architecture map, tick lifecycle flow, and key object-flow view
- `current_structure.md` is the short structural reference
- the other research notes are conceptual foundations rather than implementation-boundary documents