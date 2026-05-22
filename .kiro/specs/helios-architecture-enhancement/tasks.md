# Implementation Plan: Helios Architecture Enhancement

## Overview

This plan implements the systematic integration, persistence, and extension of Helios's existing modules across four phases: Core Loop Completion, Passive Reply Capability, Architectural Refactoring, and Deep Enhancement. Tasks are ordered so each builds on previous work, with foundation pieces first (HeliosState, TickGuard, persistence) followed by subsystem integrations and finally directory restructuring. Python 3.10+ is the target runtime.

## Tasks

- [x] 1. Set up foundation infrastructure
  - [x] 1.1 Create HeliosState dataclass and data directory structure
    - Create `core/` package with `__init__.py`
    - Define `HeliosState` dataclass in `core/helios_state.py` with all fields (tick, timestamp, panksepp, valence, arousal, dominant_system, phi, consciousness_label, mood, neurochem levels, allostatic_load, personality_traits, separation_hours, last_action, pending_reply, drive_dominant, drive_urgency)
    - Create `data/` directory for persistence files
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 1.2 Implement TickGuard exception protection
    - Create `core/tick_guard.py` with `TickGuard` class
    - Implement `execute()` method with try-except wrapping tick function
    - Implement error counter increment on exception, reset on success
    - Implement safe mode entry when consecutive errors exceed 10
    - Implement safe mode exit after 100 consecutive successful ticks
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 1.3 Write property test for TickGuard error counter lifecycle
    - **Property 3: Tick Error Counter Lifecycle**
    - **Validates: Requirements 5.4, 5.5**

  - [x] 1.4 Implement StatePersistence utility
    - Create `utils/` package with `__init__.py`
    - Create `utils/persistence.py` with `StatePersistence` class
    - Implement atomic file write pattern (tempfile + rename)
    - Implement corruption-safe JSON load (handle JSONDecodeError, KeyError, FileNotFoundError)
    - Implement `save_personality()`, `load_personality()`, `save_allostasis()`, `load_allostasis()`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

  - [x]* 1.5 Write unit tests for persistence save/load round-trips
    - Test save then load returns identical data
    - Test corrupted file returns None with warning log
    - Test missing file returns None silently
    - _Requirements: 2.3, 3.3_

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement core subsystem integrations
  - [x] 3.1 Implement Neurochem-DAISY integration
    - Modify `daisy_emotion.py` to accept optional `neurochem` parameter in `cycle()` method
    - Implement `_apply_neurochem_modulation()` method
    - When dopamine > 0.5: reduce SEEKING decay rate proportionally to (dopamine - 0.5)
    - When cortisol > 0.5: increase FEAR activation proportionally to (cortisol - 0.5)
    - Pass neurochem state from main loop into DAISY each tick
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x]* 3.2 Write property tests for Neurochem-DAISY modulation
    - **Property 1: Neurochem Dopamine Modulates SEEKING Decay**
    - **Property 2: Neurochem Cortisol Amplifies FEAR**
    - **Validates: Requirements 1.3, 1.4**

  - [x] 3.3 Implement Phi multi-source activation and ceiling fix
    - Modify `phi.py` to ensure all 5 sources are fed each tick
    - Implement ignition source from active Panksepp system count exceeding baseline
    - Implement DMN source from thinking mode depth estimate
    - Implement self_model source from personality trait awareness
    - Implement non-linear scaling function (non-saturating) for aggregate
    - Ensure sensory source decays via TTL when no external input
    - Ensure full 0.0-1.0 range: >0.7 when all 5 high, <0.4 when only 1 active
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 15.1, 15.2, 15.3, 15.4_

  - [x]* 3.4 Write property tests for Phi integration
    - **Property 9: Phi Ignition from Active System Count**
    - **Property 10: Phi Dynamic Range**
    - **Validates: Requirements 4.4, 15.1, 15.2, 15.3, 15.4**

  - [x] 3.5 Integrate personality and allostasis persistence into main loop
    - Load personality on startup via `StatePersistence.load_personality()`
    - Load allostasis on startup via `StatePersistence.load_allostasis()`
    - Save both on shutdown
    - Save periodically every 600 ticks
    - Handle missing/corrupted files gracefully with defaults
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement EventSource abstraction and implementations
  - [x] 5.1 Create EventSource abstract base class
    - Create `core/event_source.py` with abstract `EventSource` class
    - Define `poll(state: HeliosState) -> Dict[str, float]` abstract method
    - Define `get_messages() -> List[dict]` abstract method
    - _Requirements: 10.1_

  - [x] 5.2 Implement SeparationAnxietySource
    - Create `core/separation_source.py`
    - Implement PANIC formula: `min(1.0, 1 - e^(-0.4 × hours))` when value > 0.2
    - Return empty dict when anxiety ≤ 0.2
    - Return empty list from `get_messages()`
    - _Requirements: 10.2_

  - [x]* 5.3 Write property test for Separation Anxiety formula
    - **Property 8: Separation Anxiety Formula**
    - **Validates: Requirements 10.2**

  - [x] 5.4 Implement QQEventSource
    - Create `core/qq_event_source.py`
    - Consume QQ message queue, evaluate via SEC, return merged triggers
    - Return pending messages needing reply from `get_messages()`
    - _Requirements: 10.3_

  - [x] 5.5 Implement InternalDriveSource
    - Create `core/drive_source.py`
    - Map dominant drive urgency to Panksepp triggers
    - Return empty list from `get_messages()`
    - _Requirements: 10.3_

  - [x] 5.6 Implement EventSource registry and trigger merging in main loop
    - Register all EventSource instances on startup
    - Iterate over sources each tick, collect triggers and messages
    - Merge trigger dictionaries using max-value semantics for overlapping keys
    - _Requirements: 10.4_

  - [x]* 5.7 Write property test for EventSource trigger merge
    - **Property 7: EventSource Trigger Merge with Max Semantics**
    - **Validates: Requirements 10.4**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement passive reply capability
  - [x] 7.1 Implement LLM SEC Evaluator
    - Create `io/llm_sec_evaluator.py` with `LLMSECEvaluator` class
    - Implement `evaluate()` method with LLM prompt for SEC feature extraction
    - Implement 3-second timeout with fallback to keyword-based `_qq_text_to_panksepp()`
    - Include last 3 messages of conversation context in prompt
    - Return dict with: novelty, pleasantness, goal_relevance, goal_congruence, coping_potential, agency, norm_compatibility
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x]* 7.2 Write unit tests for SEC Evaluator fallback
    - Test fallback triggers on LLM timeout
    - Test fallback triggers on LLM error
    - Test context inclusion in prompt
    - _Requirements: 6.3_

  - [x] 7.3 Implement ResponsePipeline
    - Create `io/response_pipeline.py` with `ResponsePipeline` class
    - Implement `should_reply()`: return True when (goal_relevance + novelty) > 0.3
    - Implement `generate_reply()`: build LLM prompt with emotional state, conversation history, personality, and memory context
    - Implement `record_exchange()`: append to per-user conversation history
    - Include dominant Panksepp system, valence, arousal, mood label as emotional context
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [x]* 7.4 Write property test for reply decision threshold
    - **Property 6: Reply Decision Threshold**
    - **Validates: Requirements 7.1**

  - [x] 7.5 Implement conversation history management
    - Create per-user conversation history buffer (max 20 exchanges)
    - Define `ConversationExchange` dataclass (timestamp, user_message, sec_result, reply, emotional_context)
    - Append message with timestamp and SEC result on receive
    - Append reply with emotional context on send
    - FIFO eviction when exceeding 20 entries
    - _Requirements: 7.4, 8.1, 8.2, 8.3, 8.4_

  - [x]* 7.6 Write property tests for conversation history
    - **Property 4: Conversation History Bounded Buffer**
    - **Property 5: Conversation Exchange Completeness**
    - **Validates: Requirements 7.4, 8.1, 8.2, 8.3, 8.4**

  - [x] 7.7 Wire ResponsePipeline into main tick loop
    - After event collection, evaluate each message via SEC
    - If `should_reply()` is True, call `generate_reply()` and send via QQ
    - Record exchange in conversation history
    - _Requirements: 7.3_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement drives-regulation unification
  - [x] 9.1 Integrate DriveOracle into tick pipeline
    - Compute DriveVector from DriveOracle each tick using current state
    - Write drive_dominant and drive_urgency into HeliosState
    - _Requirements: 12.1_

  - [x] 9.2 Modify RegulationEngine scoring to incorporate drives
    - Update action scoring to include drive urgency at 30% weight
    - Keep emotional deviation scoring at 70% weight
    - Final score = 0.7 × emotional_deviation_score + 0.3 × drive_urgency_score
    - _Requirements: 12.2, 12.3_

  - [x]* 9.3 Write property test for drive-regulation weighted scoring
    - **Property 11: Drive-Regulation Weighted Scoring**
    - **Validates: Requirements 12.2, 12.3**

- [x] 10. Implement memory system integration
  - [x] 10.1 Initialize Memory_System in main loop
    - Initialize MemorySystem alongside existing AutobiographicalStore on startup
    - Ensure Working, Episodic, and Semantic memory tiers are available
    - _Requirements: 13.1_

  - [x] 10.2 Implement Working Memory TTL and eviction
    - Implement TTL expiration (default 300 seconds) during recall
    - Implement capacity limit (default 15) with oldest-item eviction
    - Promote items with importance > 0.5 to EpisodicMemory before expiry
    - Log debug message on promotion and expiration
    - Hold incoming QQ messages + SEC results in Working Memory
    - _Requirements: 13.5, 18.1, 18.2, 18.3, 18.4_

  - [x]* 10.3 Write property test for Working Memory lifecycle
    - **Property 18: Working Memory Bounded Lifecycle**
    - **Validates: Requirements 18.1, 18.2, 18.3**

  - [x] 10.4 Implement significant event recording to Episodic Memory
    - Record events when phi > 0.3 OR |valence| > 0.5
    - No recording when phi ≤ 0.3 AND |valence| ≤ 0.5
    - Include emotional tag, valence, arousal, phi, timestamp in MemoryItem
    - _Requirements: 13.2_

  - [x]* 10.5 Write property test for significant event recording threshold
    - **Property 12: Significant Event Recording Threshold**
    - **Validates: Requirements 13.2**

  - [x] 10.6 Implement Episodic Memory bounded growth and pruning
    - Enforce configurable max capacity (default 500)
    - Prune lowest-importance items when capacity exceeded
    - Promote items with importance > 0.4 to AutobiographicalStore before discard
    - Implement importance formula: `sqrt(V² + A²) × P × (1 + log(1 + C) × 0.1)`
    - Recalculate importance during consolidation cycles
    - _Requirements: 17.1, 17.2, 17.3, 17.4_

  - [x]* 10.7 Write property tests for Episodic Memory
    - **Property 15: Episodic Memory Capacity Invariant**
    - **Property 16: Episodic Memory Importance Formula**
    - **Property 17: Episodic Pruning Promotes High-Importance Items**
    - **Validates: Requirements 17.1, 17.2, 17.3, 17.4**

  - [x] 10.8 Implement Semantic Memory decay and forgetting
    - Apply confidence decay to facts not accessed within 7 days during consolidation
    - Decay rate: 0.001 per idle day beyond 7-day grace period
    - Remove facts when confidence drops below 0.15
    - Reset idle timer on access via `know()` or `know_with_confidence()`
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

  - [x]* 10.9 Write property test for Semantic Memory decay
    - **Property 19: Semantic Memory Decay and Forgetting**
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4**

  - [x] 10.10 Include relevant memories in LLM context for speech/reply generation
    - Retrieve relevant memories from MemorySystem when invoking LLM
    - Pass as additional context to ResponsePipeline and ExpressionPipeline
    - _Requirements: 13.3_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement habituation and memory lifecycle
  - [x] 12.1 Integrate HabituationTracker into event processing
    - Pass each event trigger through HabituationTracker before DAISY
    - Compute novelty factor and multiply trigger intensity by it
    - Register exposure after processing
    - Ensure recovery of novelty factor after stimulus gap
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ]* 12.2 Write property test for habituation modulation
    - **Property 13: Habituation Modulates Trigger Intensity**
    - **Validates: Requirements 14.1, 14.2, 14.3**

  - [x] 12.3 Implement memory consolidation scheduling
    - Trigger consolidation when Phi < 0.3 for 300 consecutive ticks
    - Cluster episodic memories by emotional tag during consolidation
    - Extract semantic patterns from clusters with 2+ members
    - Promote episodic memories with phi > 0.25 to AutobiographicalMemory
    - Rate limit: at most one consolidation per 600 ticks
    - Log counts of patterns extracted, memories promoted, items pruned
    - _Requirements: 13.4, 20.1, 20.2, 20.3, 20.4, 20.5_

  - [ ]* 12.4 Write property tests for consolidation
    - **Property 20: Consolidation Clustering and Promotion**
    - **Property 21: Consolidation Rate Limit**
    - **Validates: Requirements 20.2, 20.3, 20.4**

  - [x] 12.5 Implement Autobiographical Store disk safety enhancements
    - Flush to disk every 10 recorded moments or on shutdown
    - Use append-only JSONL writing
    - Skip malformed JSON lines on load, log warning per skipped line
    - Save chapter metadata to separate JSON file during flush/shutdown
    - Archive file with timestamp suffix when exceeding 50000 lines, retain most recent 5000
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

  - [ ]* 12.6 Write property tests for Autobiographical Store
    - **Property 22: Autobiographical Store Flush Periodicity**
    - **Property 23: JSONL Append-Only Resilience**
    - **Property 24: Autobiographical Store Archive Threshold**
    - **Validates: Requirements 21.1, 21.2, 21.3, 21.5**

  - [x] 12.7 Implement Memory System state persistence
    - Serialize SemanticMemory facts to JSON on shutdown
    - Load SemanticMemory facts from JSON on startup
    - Serialize EpisodicMemory items with importance > 0.3 on shutdown
    - Load high-importance EpisodicMemory items on startup
    - Handle corrupted files gracefully (log warning, init empty)
    - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5_

  - [ ]* 12.8 Write property test for selective episodic serialization
    - **Property 25: Selective Episodic Serialization**
    - **Validates: Requirements 22.3**

  - [x] 12.9 Implement memory usage monitoring
    - Log memory subsystem stats at each summary interval
    - Log WARNING when any collection exceeds 80% capacity
    - Expose memory statistics via `get_state()` method
    - Trigger immediate consolidation when total items exceed 2000
    - _Requirements: 23.1, 23.2, 23.3, 23.4_

  - [ ]* 12.10 Write property test for capacity monitoring alerts
    - **Property 26: Capacity Monitoring Alerts**
    - **Validates: Requirements 23.2, 23.4**

- [x] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implement conversation personalization and pipeline wiring
  - [x] 14.1 Implement conversation personalization from Autobiographical Memory
    - Query AutobiographicalStore for memories related to conversation topic/user
    - Include up to 3 relevant memory narratives in LLM context for reply generation
    - Handle gracefully when no relevant memories exist (no error)
    - _Requirements: 16.1, 16.2, 16.3_

  - [ ]* 14.2 Write property test for autobiographical memory inclusion bound
    - **Property 14: Autobiographical Memory Inclusion Bound**
    - **Validates: Requirements 16.2**

  - [x] 14.3 Wire complete enhanced tick pipeline
    - Implement full tick pipeline as described in design: create state → collect events → habituation → DAISY → neurochem → Phi → personality → allostasis → drives → regulation → memory → reply → expression → consolidation check → periodic persistence
    - Ensure HeliosState forward propagation (modules see updated values from earlier pipeline stages)
    - _Requirements: 9.4_

  - [ ]* 14.4 Write property test for HeliosState pipeline forward propagation
    - **Property 27: HeliosState Pipeline Forward Propagation**
    - **Validates: Requirements 9.4**

- [ ] 15. Implement directory restructuring
  - [x] 15.1 Reorganize source files into domain packages
    - Move files into `core/`, `memory/`, `cognition/`, `io/`, `regulation/`, `utils/` packages
    - Keep `helios_main.py` at project root as entry point
    - Create `__init__.py` in each package re-exporting public interfaces
    - Preserve all existing module public APIs without breaking changes
    - Update all imports throughout the codebase
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 15.2 Write unit tests verifying directory structure and imports
    - Test that all public interfaces are importable from new locations
    - Test that no existing API signatures have changed
    - _Requirements: 11.4_

- [x] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Implement adaptive ICRI engine and Phi-to-ICRI rename
  - [x] 17.1 Implement AdaptiveAlphaICRI class in phi.py
    - Create `AdaptiveAlphaICRI` class with 3-tier adaptive EMA alpha (0.55 for intensity > 0.60, 0.30 for 0.30-0.60, 0.10 for < 0.10)
    - Implement `select_alpha(max_event_intensity)` method with deterministic tier selection
    - Implement `aggregate(max_event_intensity)` method using adaptive alpha EMA smoothing
    - Implement non-linear scaling function `1.0 - (1.0 / (1.0 + raw * 2.5))` to prevent saturation
    - Rename `temporal_depth` source to `dmn_depth` in source dictionary
    - Ensure ICRI increase of at least 0.10 when QQ message arrives
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

  - [ ]* 17.2 Write property test for adaptive alpha tier selection
    - **Property 28: Adaptive Alpha Tier Selection**
    - **Validates: Requirements 24.1, 24.2, 24.3**

  - [x] 17.3 Implement CognitiveImpactProfile dataclass and ICRI source feeding
    - Create `CognitiveImpactProfile` dataclass with four dimensions: sensory, cognitive, self_, novelty (all float [0, 1])
    - Implement `feed_from_impact(impact: CognitiveImpactProfile)` method in AdaptiveAlphaICRI
    - Map sensory → sensory_integration, cognitive → dmn_depth, self_ → self_reflection, novelty → global_ignition
    - Implement fallback to existing approximation methods when event has no CognitiveImpactProfile
    - Reset source TTLs for fed sources on impact feed
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 27.6_

  - [ ]* 17.4 Write property test for CognitiveImpactProfile feeding ICRI sources
    - **Property 30: CognitiveImpactProfile Feeds ICRI Sources**
    - **Validates: Requirements 27.2, 27.3, 27.4, 27.5**

  - [x] 17.5 Rename Phi to ICRI throughout codebase
    - Rename internal variable references from `phi` to `icri` in module interfaces and HeliosState
    - Update documentation, display outputs, and dashboard labels to use ICRI terminology
    - Add backward compatibility: accept old `phi` key in config files, map to `icri` internally
    - Add deprecated `phi` property alias that returns `icri` value
    - Ensure external monitoring tools can query both `phi` and `icri` field names during deprecation period
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_

- [ ] 18. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 19. Implement LLM temperature modulation
  - [x] 19.1 Implement ICRITemperatureMapper class
    - Create `ICRITemperatureMapper` class in `io/icri_temperature.py`
    - Implement 5-tier static mapping: ICRI < 0.10 → 0.3, [0.10, 0.25) → 0.5, [0.25, 0.45) → 0.75, [0.45, 0.65) → 1.0, ≥ 0.65 → 1.3
    - Implement `map_temperature(icri: float) -> float` static method
    - Implement `get_style_label(icri: float) -> str` for dashboard display
    - Ensure mapping is monotonically non-decreasing with ICRI
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5_

  - [ ]* 19.2 Write property test for ICRI-to-temperature mapping
    - **Property 29: ICRI-to-Temperature 5-Tier Mapping**
    - **Validates: Requirements 26.1, 26.2, 26.3, 26.4, 26.5**

  - [ ] 19.3 Wire ICRITemperatureMapper into LLM speech generation
    - Modify `LLMSpeechGenerator` to accept temperature override parameter from HeliosState ICRI value
    - Call `ICRITemperatureMapper.map_temperature(state.icri)` before each LLM invocation
    - Write `llm_temperature` and `speech_style` into HeliosState each tick
    - Pass computed temperature to both ResponsePipeline and ExpressionPipeline LLM calls
    - _Requirements: 26.6_

- [ ] 20. Implement internal thought stream
  - [ ] 20.1 Implement ThinkingEngineIntegration class
    - Create `cognition/thinking_integration.py` with `ThinkingEngineIntegration` class
    - Implement `should_generate(icri, dmn_active, now)` — suppress when ICRI < 0.10 or DMN inactive
    - Implement `get_biased_types(dominant_system)` using EMOTION_THOUGHT_BIAS mapping (PANIC/FEAR → rumination/future_projection, SEEKING → free_association/self_question)
    - Implement `is_type_on_cooldown(thought_type, now)` with 30-second per-type cooldown
    - Implement `generate(state: HeliosState)` method producing Thought dataclass instances
    - Define `Thought` dataclass (type, content, timestamp, triggered_by)
    - Define `THOUGHT_TYPES` list and `EMOTION_THOUGHT_BIAS` mapping
    - Store generated thoughts in AutobiographicalStore
    - Generation interval: approximately one thought per 5 seconds
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5, 28.6, 28.7_

  - [ ]* 20.2 Write property test for emotion-biased thought type generation
    - **Property 31: Emotion-Biased Thought Type Generation**
    - **Validates: Requirements 28.3, 28.4**

  - [ ]* 20.3 Write property test for thought type cooldown enforcement
    - **Property 32: Thought Type Cooldown Enforcement**
    - **Validates: Requirements 28.6**

  - [ ]* 20.4 Write property test for thought suppression below ICRI threshold
    - **Property 33: Thought Suppression Below ICRI Threshold**
    - **Validates: Requirements 28.7**

  - [ ] 20.5 Wire ThinkingEngineIntegration into tick pipeline
    - Initialize ThinkingEngineIntegration on startup with thinking_engine and autobio_store
    - Call `generate(state)` each tick after Phi/ICRI computation
    - Write `dmn_active`, `last_thought_type`, `thought_generated_this_tick` into HeliosState
    - Feed generated thought content to ICRI dmn_depth source
    - _Requirements: 28.1, 28.5_

- [ ] 21. Implement behavioral execution abstraction
  - [x] 21.1 Implement BehaviorExecutor class
    - Create `io/limb.py` with `BehaviorExecutor` class
    - Define `BehaviorStatus` enum (QUEUED, EXECUTING, PAUSED, COMPLETED, CANCELLED)
    - Define `BehaviorCommand` dataclass (priority, name, action, params, status, result)
    - Implement priority-ordered queue using negated priority min-heap
    - Implement `enqueue()` with preemption logic (higher priority pauses current)
    - Implement `cancel(name)`, `pause(name)`, `resume(name)` operations
    - Implement `complete_current(result)` with result callback to RegulationEngine
    - Implement `_advance()` to dequeue next behavior after completion/cancel
    - _Requirements: 29.1, 29.3, 29.4, 29.5_

  - [ ]* 21.2 Write property test for priority-ordered behavior execution with preemption
    - **Property 34: Priority-Ordered Behavior Execution with Preemption**
    - **Validates: Requirements 29.1, 29.4**

  - [ ]* 21.3 Write property test for behavior completion feedback
    - **Property 35: Behavior Completion Produces Feedback**
    - **Validates: Requirements 29.2, 29.5**

  - [x] 21.4 Implement LimbDecisionBridge class
    - Create `io/limb_decision_bridge.py` with `LimbDecisionBridge` class
    - Define priority threshold mapping: score ≥ 0.8 → 100, ≥ 0.6 → 75, ≥ 0.4 → 50, ≥ 0.2 → 25, else → 10
    - Implement `convert_and_enqueue(action, score, params)` converting regulation scores to priority-ordered BehaviorCommands
    - Implement `_score_to_priority(score)` mapping function
    - _Requirements: 29.2_

  - [ ] 21.5 Wire BehaviorExecutor into regulation pipeline
    - Initialize BehaviorExecutor and LimbDecisionBridge on startup
    - Replace direct action execution with `LimbDecisionBridge.convert_and_enqueue()` calls from RegulationEngine
    - Set result callback on BehaviorExecutor to feed back to RegulationEngine memory
    - Write `behavior_queue_depth` and `current_behavior` into HeliosState each tick
    - _Requirements: 29.1, 29.2, 29.5_

- [ ] 22. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 23. Implement multimodal I/O modules
  - [ ] 23.1 Implement TTSModule
    - Create `io/io_tts.py` with `TTSModule` class
    - Implement graceful initialization: check for Alibaba NLS SDK (`nls`) and credentials
    - Implement `synthesize_and_play(text)` wrapping nls.NlsSpeechSynthesizer
    - Implement `is_available` property for runtime hardware probing
    - Implement `register()` and `deregister()` for runtime-pluggable operation
    - Log warning and continue text-only when SDK or credentials unavailable
    - Wire into LLM speech output path (call synthesize after text generation when available)
    - _Requirements: 30.1, 30.2, 30.3, 30.4_

  - [ ] 23.2 Implement STTModule as EventSource
    - Create `io/io_stt.py` with `STTModule` class implementing `EventSource` interface
    - Implement graceful initialization: check for nls SDK, pyaudio, and microphone hardware
    - Implement `poll(state)` returning empty dict (triggers come from SEC evaluation of text)
    - Implement `get_messages()` returning pending transcribed utterances as message dicts
    - Implement `_on_utterance_complete(text)` callback from ASR SDK
    - Remain dormant when hardware/dependencies unavailable
    - Register with EventSource registry on startup when available
    - _Requirements: 31.1, 31.2, 31.3, 31.4_

  - [ ] 23.3 Implement VisionModule as EventSource
    - Create `io/io_vision.py` with `VisionModule` class implementing `EventSource` interface
    - Implement graceful initialization: check for OpenCV and camera device availability
    - Implement `poll(state)` with configurable capture interval (default 5 seconds)
    - Implement `_capture_and_analyze()` using OpenCV frame capture + vision LLM description
    - Convert scene descriptions to CognitiveImpactProfile + Panksepp triggers
    - Implement `get_messages()` returning scene descriptions for awareness logging
    - Remain dormant when hardware unavailable
    - Register with EventSource registry on startup when available
    - _Requirements: 32.1, 32.2, 32.3, 32.4_

- [ ] 24. Implement long-running stability and memory lifecycle
  - [ ] 24.1 Implement StabilityMonitor class
    - Create `utils/stability_monitor.py` with `StabilityMonitor` class
    - Implement `rss_mb` property using `psutil.Process().memory_info().rss`
    - Implement `check_memory()` returning False when RSS exceeds 100MB limit
    - Implement `uptime_hours` property tracking continuous operation time
    - Implement `check_log_rotation(log_path)` checking file size against 100MB limit
    - Write `rss_mb` and `uptime_hours` into HeliosState each tick
    - Configure logrotate integration (create `helios.logrotate` config file)
    - _Requirements: 33.1, 33.2, 33.5_

  - [ ] 24.2 Implement WebSocketReconnector
    - Create `WebSocketReconnector` class in `io/io_qq.py` (or separate util)
    - Implement `on_disconnect()` incrementing attempt counter
    - Implement `get_backoff()` with exponential backoff capped at 30 seconds
    - Implement `on_reconnect()` resetting counter and logging success
    - Wire into QQBotClient WebSocket connection lifecycle
    - Implement automatic token refresh before expiry without interrupting message flow
    - _Requirements: 33.3, 33.4_

  - [ ] 24.3 Implement MemoryCompressor class
    - Create `memory/memory_compressor.py` with `MemoryCompressor` class
    - Define `CompressedSummary` dataclass (date, summary, emotional_arc, moment_count, key_events, source_ids)
    - Implement `find_compressible_days()` — identify days > 7 days old with > 100 moments
    - Implement `compress_day(date, moments)` — extract emotional arc, identify key events, generate summary via LLM or template
    - Implement `execute_compression()` — replace individual moments with summary in active store, preserve raw JSONL archive unmodified
    - Log compression stats (moments compressed, summaries produced, days compressed)
    - _Requirements: 34.1, 34.2, 34.3, 34.4_

  - [ ]* 24.4 Write property test for memory compression trigger condition
    - **Property 36: Memory Compression Trigger Condition**
    - **Validates: Requirements 34.1**

  - [ ]* 24.5 Write property test for compression preserving archive
    - **Property 37: Compression Reduces Active Store Preserving Archive**
    - **Validates: Requirements 34.3**

  - [ ] 24.6 Implement SeedMemoryImporter class
    - Create `memory/seed_memory_importer.py` with `SeedMemoryImporter` class
    - Define `SeedMoment` dataclass (summary, timestamp, valence, arousal, emotional_tag, source, original_section)
    - Implement `import_document(content, source_label, base_date)` — parse markdown, create seed moments with timestamps predating system start
    - Implement `_parse_sections(content)` for markdown heading/text extraction
    - Tag each seed memory with source label indicating migration origin
    - Persist seed moments into AutobiographicalStore via `record_moment()`
    - Implement `verify_seed_integrity()` confirming all seeds are pre-dated and tagged
    - Ensure seed memories survive save/reload cycles identically to organic memories
    - Allow personality to evolve naturally from seed valence — no direct PersonalityProfile modification
    - _Requirements: 35.1, 35.2, 35.3, 35.4, 35.5_

  - [ ]* 24.7 Write property test for seed memory creation
    - **Property 38: Seed Memory Creation with Pre-dated Timestamps and Source Tags**
    - **Validates: Requirements 35.1, 35.2**

  - [ ]* 24.8 Write property test for seed memory equivalence
    - **Property 39: Seed Memory Equivalence in Persistence and Retrieval**
    - **Validates: Requirements 35.3, 35.5**

  - [ ] 24.9 Wire stability and memory lifecycle into main loop
    - Initialize StabilityMonitor, WebSocketReconnector, MemoryCompressor on startup
    - Call `StabilityMonitor.check_memory()` every 100 ticks, log warning if exceeded
    - Schedule memory compression during consolidation cycles (after standard consolidation completes)
    - Run seed memory import on first startup when seed documents are present in `data/seeds/` directory
    - Register hardware I/O modules (TTS, STT, Vision) with EventSource registry when available
    - _Requirements: 33.1, 33.2, 34.1, 35.1_

- [ ] 25. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation between phases
- Property tests validate universal correctness properties using Hypothesis (Python)
- Unit tests validate specific examples and edge cases using pytest
- The design specifies Python 3.10+ as the target runtime
- All persistence operations use atomic write (tempfile + rename) to prevent corruption
- Directory restructuring (task 15) is done after core integrations to avoid import churn
- Tasks 17-25 cover deep enhancement requirements (24-35): adaptive ICRI, temperature modulation, cognitive impact, internal thought stream, behavior execution, multimodal I/O, stability, memory compression, and seed memory import
- Multimodal I/O modules (TTS, STT, Vision) are hardware-optional and degrade gracefully
- The Phi→ICRI rename maintains backward compatibility via deprecated property aliases

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "5.1"] },
    { "id": 2, "tasks": ["1.5", "3.1", "5.2"] },
    { "id": 3, "tasks": ["3.2", "3.3", "5.3", "5.4", "5.5"] },
    { "id": 4, "tasks": ["3.4", "3.5", "5.6", "7.1"] },
    { "id": 5, "tasks": ["5.7", "7.2", "7.3", "7.5", "9.1"] },
    { "id": 6, "tasks": ["7.4", "7.6", "7.7", "9.2"] },
    { "id": 7, "tasks": ["9.3", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.4", "10.8"] },
    { "id": 9, "tasks": ["10.3", "10.5", "10.6", "10.9", "10.10"] },
    { "id": 10, "tasks": ["10.7", "12.1", "12.3", "12.5"] },
    { "id": 11, "tasks": ["12.2", "12.4", "12.6", "12.7", "12.9"] },
    { "id": 12, "tasks": ["12.8", "12.10", "14.1"] },
    { "id": 13, "tasks": ["14.2", "14.3"] },
    { "id": 14, "tasks": ["14.4", "15.1"] },
    { "id": 15, "tasks": ["15.2"] },
    { "id": 16, "tasks": ["17.1", "19.1", "21.1"] },
    { "id": 17, "tasks": ["17.2", "17.3", "19.2", "21.2", "21.3", "21.4"] },
    { "id": 18, "tasks": ["17.4", "17.5", "19.3", "21.5"] },
    { "id": 19, "tasks": ["20.1", "23.1", "23.2", "23.3"] },
    { "id": 20, "tasks": ["20.2", "20.3", "20.4", "20.5", "24.1", "24.2"] },
    { "id": 21, "tasks": ["24.3", "24.6"] },
    { "id": 22, "tasks": ["24.4", "24.5", "24.7", "24.8"] },
    { "id": 23, "tasks": ["24.9"] }
  ]
}
```
