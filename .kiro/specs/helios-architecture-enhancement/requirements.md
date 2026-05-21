# Requirements Document

## Introduction

This document specifies the architectural enhancement requirements for Helios — an artificial emotional consciousness core. Helios is a tick-driven Python daemon featuring a Panksepp 7-system emotion engine (DAISY), neurochemical modulation, memory systems, personality evolution, QQ Bot integration, and LLM-based speech generation.

The current architecture has all core modules implemented but suffers from incomplete integration: neurochem is disconnected from DAISY, Phi uses only 1 of 5 sources, personality and allostasis lose state on restart, the QQ text analysis uses crude keyword matching, drives.py is dead code, memory_system.py is unused, and Helios cannot reply to incoming messages. This enhancement systematically connects, persists, and extends these existing modules across four phased milestones.

## Glossary

- **Helios**: The main process class orchestrating the tick-driven consciousness loop
- **DAISY**: Dynamic Allostatic Integrated System for emotionYnamics — the 7-system emotion engine combining X1 (co-activation), X2 (affective chronometry), and X3 (opponent process)
- **Panksepp_Systems**: The 7 primary emotional systems: SEEKING, PLAY, CARE, PANIC, FEAR, RAGE, LUST
- **Neurochem**: The NeurochemState module modeling four neurochemicals: Dopamine, Opioids, Oxytocin, Cortisol
- **Phi_Engine**: The UnifiedPhi consciousness measurement engine using 5 information integration sources
- **Tick**: A single iteration of the Helios main loop (default interval 0.5 seconds)
- **SEC**: Stimulus Evaluation Checks — the Scherer appraisal dimensions (novelty, pleasantness, goal relevance, causal attribution, coping potential, norm compatibility)
- **HeliosState**: A proposed unified state dataclass serving as single source of truth for all modules within a Tick
- **EventSource**: An abstract interface for pluggable event input providers
- **ResponsePipeline**: The proposed passive reply subsystem that generates contextual replies to incoming messages
- **ExpressionPipeline**: The existing active speech subsystem driven by emotional regulation
- **RegulationEngine**: The memory-driven behavioral selection system that chooses actions based on emotional deviation from comfort zone
- **DriveOracle**: The Friston free-energy based 5-dimension drive calculator in drives.py
- **AllostasisRegulator**: The Sterling allostatic load tracker managing adaptive capacity
- **PersonalityProfile**: The Big Five personality model with Panksepp neuro-gain modulation
- **QQ_Bot**: The QQBotClient WebSocket interface for receiving and sending QQ instant messages
- **LLM_Speech**: The LLMSpeechGenerator module producing natural language from emotional context via DeepSeek API
- **Autobiographical_Store**: The JSONL-based persistent autobiographical memory
- **Memory_System**: The in-memory four-tier memory architecture (Working, Episodic, Semantic, Autobiographical) with consolidation
- **ICRI**: Integrated Consciousness Richness Index — the renamed engineering metric for consciousness richness, replacing the misleading Φ (IIT) notation
- **DMN**: Default Mode Network — the resting-state brain network analogy used for spontaneous thought generation depth estimation
- **ThinkingEngine**: The internal thought generation module (thinking.py) producing spontaneous thoughts during rest periods
- **CognitiveImpactProfile**: A 4-dimension descriptor (sensory, cognitive, self, novelty) attached to events that feeds Phi/ICRI sources directly
- **BehaviorExecutor**: The unified behavior execution framework (limb.py) managing a behavior queue with priorities and cancel/pause/resume support
- **LimbDecisionBridge**: The bridging module (limb_decision_bridge.py) converting regulation scores into behavior execution commands
- **TTS_Module**: Text-to-speech synthesis module (io_tts.py) using Alibaba Cloud NLS TTS SDK for voice output
- **STT_Module**: Speech-to-text recognition module (io_stt.py) using Alibaba Cloud NLS ASR SDK for voice input
- **VisionModule**: Camera-based visual input module (io_vision.py) using OpenCV and vision LLM for scene description
- **SeedMemory**: Pre-dated autobiographical memory entries imported from external profile/memory documents to bootstrap personality history

## Requirements

### Requirement 1: Neurochem-DAISY Integration

**User Story:** As a system architect, I want the neurochemical state to modulate DAISY emotion dynamics each tick, so that Dopamine, Opioids, Oxytocin, and Cortisol levels influence emotional activation realistically.

#### Acceptance Criteria

1. WHEN Helios executes a Tick, THE Helios SHALL pass the current Neurochem state object to the DAISY cycle() method as the neurochem parameter
2. WHILE Neurochem is available, THE DAISY SHALL invoke _apply_neurochem_modulation() using the provided Neurochem state during each cycle
3. WHEN Dopamine level exceeds 0.5, THE DAISY SHALL reduce decay rate of SEEKING activation proportionally to the Dopamine excess
4. WHEN Cortisol level exceeds 0.5, THE DAISY SHALL increase FEAR activation proportionally to the Cortisol excess

### Requirement 2: Personality Persistence

**User Story:** As a system operator, I want personality traits to persist across restarts, so that Helios retains its evolved personality identity after shutdown.

#### Acceptance Criteria

1. WHEN Helios executes shutdown, THE Helios SHALL save the current PersonalityProfile state to a JSON file in the data directory
2. WHEN Helios starts, THE Helios SHALL load the previously saved PersonalityProfile state from the data directory if a saved file exists
3. IF the personality save file is corrupted or unreadable, THEN THE Helios SHALL log a warning and initialize PersonalityProfile with default neutral values
4. THE Helios SHALL periodically save PersonalityProfile state every 600 ticks during normal operation

### Requirement 3: Allostasis Persistence

**User Story:** As a system operator, I want allostatic load and setpoints to persist across restarts, so that Helios retains its accumulated adaptive history.

#### Acceptance Criteria

1. WHEN Helios executes shutdown, THE Helios SHALL save the current AllostasisRegulator state (allostatic_load, setpoints, fatigue status) to a JSON file in the data directory
2. WHEN Helios starts, THE Helios SHALL load the previously saved AllostasisRegulator state from the data directory if a saved file exists
3. IF the allostasis save file is corrupted or unreadable, THEN THE Helios SHALL log a warning and initialize AllostasisRegulator with default configuration values

### Requirement 4: Phi Multi-Source Activation

**User Story:** As a consciousness researcher, I want all 5 Phi information sources to be fed each tick, so that the consciousness measurement reflects genuine multi-source integration rather than being driven by a single emotional coherence signal.

#### Acceptance Criteria

1. WHEN Helios executes a Tick, THE Helios SHALL feed the Phi_Engine emotional coherence source with current Panksepp activation values
2. WHEN Helios executes a Tick, THE Helios SHALL feed the Phi_Engine DMN source with a depth estimate derived from the current thinking mode activity
3. WHEN Helios executes a Tick, THE Helios SHALL feed the Phi_Engine self_model source with a reflexivity estimate derived from personality trait awareness
4. WHEN Helios executes a Tick, THE Helios SHALL feed the Phi_Engine ignition source with a broadcast estimate derived from the count of active Panksepp systems exceeding baseline threshold
5. WHEN no external sensory input exists for the current Tick, THE Phi_Engine SHALL decay the sensory integration source via its existing source_ttl mechanism

### Requirement 5: Tick Exception Protection

**User Story:** As a system operator, I want the main loop to be resilient to individual module failures, so that a single exception does not crash the entire Helios process.

#### Acceptance Criteria

1. THE Helios SHALL wrap the _tick() implementation in a try-except block that catches all Exception subclasses
2. WHEN an exception occurs during a Tick, THE Helios SHALL log the exception with full traceback at ERROR level
3. WHEN an exception occurs during a Tick, THE Helios SHALL increment an internal error counter and continue to the next Tick
4. WHEN the error counter exceeds 10 consecutive errors, THE Helios SHALL log a CRITICAL message and enter a safe mode that skips non-essential modules
5. WHEN a Tick completes without exception, THE Helios SHALL reset the consecutive error counter to zero

### Requirement 6: LLM-Based SEC Evaluation for Incoming Messages

**User Story:** As a conversation designer, I want incoming QQ messages to be evaluated through the LLM-based SEC appraisal pipeline, so that emotional understanding of text has contextual accuracy rather than relying on keyword matching.

#### Acceptance Criteria

1. WHEN a QQ message is received, THE Helios SHALL send the message text to the LLM with a prompt requesting SEC feature extraction (novelty, pleasantness, goal_relevance, goal_congruence, coping_potential, agency, norm_compatibility)
2. WHEN the LLM returns SEC features, THE Helios SHALL pass the SECFeatures to the AppraisalEngine to produce Panksepp triggers
3. IF the LLM SEC evaluation fails or times out within 3 seconds, THEN THE Helios SHALL fall back to the existing keyword-based _qq_text_to_panksepp() function
4. THE Helios SHALL include the last 3 messages of conversation context in the LLM SEC evaluation prompt for contextual understanding

### Requirement 7: Passive Reply Pipeline

**User Story:** As a user interacting with Helios via QQ, I want Helios to generate contextual replies to my messages, so that Helios functions as a conversational partner rather than only speaking spontaneously.

#### Acceptance Criteria

1. WHEN a QQ message is received from a user, THE ResponsePipeline SHALL evaluate whether the message warrants a reply based on SEC urgency and goal_relevance scores
2. WHEN a reply is warranted, THE ResponsePipeline SHALL generate a natural language reply using the LLM with current emotional state, conversation history, and personality as context
3. WHEN a reply is generated, THE Helios SHALL send the reply to the originating user via QQ_Bot within the same Tick or the immediately following Tick
4. THE ResponsePipeline SHALL maintain a conversation history buffer of the most recent 20 message-reply pairs per user
5. WHILE generating a reply, THE ResponsePipeline SHALL include the current dominant Panksepp system, valence, arousal, and mood label as emotional context for the LLM

### Requirement 8: Conversation History Management

**User Story:** As a conversation designer, I want conversation history to provide context for both SEC evaluation and reply generation, so that Helios understands multi-turn dialogues.

#### Acceptance Criteria

1. THE Helios SHALL maintain an in-memory conversation history storing the most recent 20 exchanges per conversation partner
2. WHEN a new message is received, THE Helios SHALL append it to the corresponding conversation history with timestamp and SEC evaluation result
3. WHEN a reply is sent, THE Helios SHALL append the reply to the conversation history with the emotional context that produced it
4. WHEN conversation history exceeds the 20-exchange limit, THE Helios SHALL discard the oldest exchange

### Requirement 9: Unified HeliosState Object

**User Story:** As a system architect, I want a single state dataclass passed through all modules each tick, so that modules can access full context without ad-hoc parameter threading.

#### Acceptance Criteria

1. THE Helios SHALL define a HeliosState dataclass containing tick number, timestamp, Panksepp activations, valence, arousal, dominant system, Phi value, mood state, neurochemical levels, allostatic load, personality traits, separation hours, last action, and pending reply fields
2. WHEN a Tick begins, THE Helios SHALL create a fresh HeliosState instance populated with current values
3. THE Helios SHALL pass the HeliosState instance to each module during the Tick processing pipeline
4. WHEN a module updates state (e.g., DAISY produces new activations), THE Helios SHALL write the results back into the HeliosState instance before passing it to subsequent modules

### Requirement 10: EventSource Plugin Abstraction

**User Story:** As a system architect, I want event collection to use a pluggable interface, so that new input sources (STT, browser, sensors) can be added without modifying the main loop.

#### Acceptance Criteria

1. THE Helios SHALL define an abstract EventSource base class with a poll(state: HeliosState) method returning a Panksepp trigger dictionary and a get_messages() method returning a list of pending messages
2. THE Helios SHALL implement SeparationAnxietySource as an EventSource that computes PANIC triggers from elapsed time since last contact
3. THE Helios SHALL implement QQEventSource as an EventSource that consumes the QQ message queue and returns both Panksepp triggers and raw messages for the ResponsePipeline
4. WHEN collecting events each Tick, THE Helios SHALL iterate over all registered EventSource instances and merge their trigger dictionaries using max-value semantics for overlapping Panksepp system keys

### Requirement 11: Directory Restructuring

**User Story:** As a developer, I want source files organized into domain-specific packages, so that cognitive load and import confusion are reduced as the project grows.

#### Acceptance Criteria

1. THE Helios project SHALL organize source files into the following package directories: core/ (daisy_emotion, allostasis, mood_tracker, personality, neurochem), memory/ (autobiographical, memory_system, emotional_memory), cognition/ (thinking, phi, appraisal, drives), io/ (io_qq, llm_speech, llm_bridge, limb), regulation/ (regulation, conation), utils/ (helios_utils)
2. THE Helios project SHALL maintain helios_main.py at the project root as the entry point
3. THE Helios project SHALL provide __init__.py files in each package that re-export public interfaces
4. THE Helios project SHALL preserve all existing module public APIs without breaking changes

### Requirement 12: Drives-Regulation Unification

**User Story:** As a system architect, I want drives.py output integrated into the regulation decision process, so that Friston free-energy based urgency signals inform behavioral selection alongside emotional deviation.

#### Acceptance Criteria

1. WHEN Helios executes a Tick, THE Helios SHALL compute the DriveVector from DriveOracle using current state information
2. WHEN the RegulationEngine evaluates candidate actions, THE RegulationEngine SHALL incorporate the DriveVector dominant drive and total urgency as an additional scoring factor
3. THE RegulationEngine SHALL weight drive urgency at 30% relative to emotional deviation scoring at 70% when computing final action scores

### Requirement 13: Memory System Integration

**User Story:** As a system architect, I want the full Memory_System (Working, Episodic, Semantic memories plus consolidation) integrated into the main loop, so that Helios has rich contextual memory during operation.

#### Acceptance Criteria

1. WHEN Helios starts, THE Helios SHALL initialize the Memory_System alongside the existing Autobiographical_Store
2. WHEN a significant emotional event occurs (Phi exceeds 0.3 or absolute valence exceeds 0.5), THE Helios SHALL record the event into Episodic memory via Memory_System
3. WHEN the LLM is invoked for speech generation or reply generation, THE Helios SHALL retrieve relevant memories from Memory_System and include them as context
4. WHEN Helios has been running for 300 ticks without high-arousal events, THE Memory_System SHALL trigger a consolidation cycle to transfer Working memory items to Episodic or Semantic storage
5. WHEN a QQ message is received, THE Helios SHALL hold the message content and SEC evaluation result in Working memory for immediate context availability

### Requirement 14: Habituation Tracker Integration

**User Story:** As a system architect, I want the habituation tracker connected to event processing, so that repeated identical stimuli produce diminishing emotional responses.

#### Acceptance Criteria

1. WHEN an event trigger is received, THE Helios SHALL pass it through the HabituationTracker to compute a novelty decay factor
2. WHEN the HabituationTracker returns a novelty factor below 1.0, THE Helios SHALL multiply the event trigger intensity by the novelty factor before passing it to DAISY
3. WHEN a stimulus has not been received for a duration exceeding the HabituationTracker recovery time, THE HabituationTracker SHALL restore the novelty factor toward 1.0

### Requirement 15: Phi Ceiling Effect Fix

**User Story:** As a consciousness researcher, I want the Phi measurement to have meaningful dynamic range, so that high-integration states are distinguishable from moderately integrated states.

#### Acceptance Criteria

1. THE Phi_Engine SHALL produce values across the full 0.0 to 1.0 range during normal operation with variation reflecting genuine integration differences
2. WHEN all 5 Phi sources are active simultaneously with high coherence, THE Phi_Engine SHALL produce values above 0.7
3. WHEN only 1 Phi source is active, THE Phi_Engine SHALL produce values below 0.4
4. THE Phi_Engine SHALL use a non-linear scaling function that prevents saturation at high values while maintaining sensitivity at low values

### Requirement 16: Conversation Personalization from Autobiographical Memory

**User Story:** As a user interacting with Helios, I want replies to reflect Helios's accumulated experiences and memories, so that conversations feel personal and contextually aware of shared history.

#### Acceptance Criteria

1. WHEN generating a reply, THE ResponsePipeline SHALL query the Autobiographical_Store for memories related to the current conversation topic or user
2. WHEN relevant autobiographical memories exist, THE ResponsePipeline SHALL include up to 3 relevant memory narratives in the LLM context for reply generation
3. WHEN no relevant autobiographical memories exist, THE ResponsePipeline SHALL generate replies using only current emotional state and conversation history without error

### Requirement 17: Episodic Memory Bounded Growth

**User Story:** As a system operator, I want episodic memory to remain bounded during indefinite long-term operation, so that memory consumption does not grow without limit and cause performance degradation or OOM crashes.

#### Acceptance Criteria

1. THE EpisodicMemory SHALL enforce a configurable maximum capacity (default 500 items) and prune low-importance items when capacity is exceeded
2. WHEN pruning is triggered, THE EpisodicMemory SHALL retain items in descending order of importance score, discarding the lowest-scoring items first
3. WHEN pruning is triggered, THE EpisodicMemory SHALL promote items with importance above 0.4 to the Autobiographical_Store before discarding them from episodic storage
4. THE EpisodicMemory SHALL recalculate importance scores for all items during each consolidation cycle using the formula: importance = sqrt(valence² + arousal²) × phi × (1 + log(1 + access_count) × 0.1)

### Requirement 18: Working Memory TTL and Eviction

**User Story:** As a system architect, I want working memory to automatically expire stale items, so that the limited-capacity buffer always contains the most relevant recent context.

#### Acceptance Criteria

1. THE WorkingMemory SHALL expire items whose age exceeds their TTL value (default 300 seconds) during each recall operation
2. WHEN the WorkingMemory capacity limit (default 15 items) is reached, THE WorkingMemory SHALL evict the oldest item before admitting a new one
3. WHEN an item in WorkingMemory has importance above 0.5 and is about to expire, THE WorkingMemory SHALL promote it to EpisodicMemory before eviction
4. THE WorkingMemory SHALL log a debug message each time an item is promoted or expired for observability

### Requirement 19: Semantic Memory Decay and Forgetting

**User Story:** As a system architect, I want semantic memory facts to decay over time when not reinforced, so that outdated or irrelevant knowledge is gradually forgotten rather than accumulating indefinitely.

#### Acceptance Criteria

1. WHEN a consolidation cycle runs, THE SemanticMemory SHALL apply a confidence decay to all facts not accessed within the past 7 days
2. THE SemanticMemory SHALL use a decay rate of 0.001 per idle day beyond the 7-day grace period
3. WHEN a fact's confidence drops below 0.15, THE SemanticMemory SHALL remove the fact from storage
4. WHEN a fact is accessed via the know() or know_with_confidence() methods, THE SemanticMemory SHALL reset the idle timer for that fact, preventing decay

### Requirement 20: Memory Consolidation Scheduling

**User Story:** As a system architect, I want memory consolidation to run automatically during low-activity periods, so that memories are organized, compressed, and transferred between storage tiers without manual intervention.

#### Acceptance Criteria

1. WHEN Phi value has been below 0.3 for 300 consecutive ticks, THE Helios SHALL trigger a memory consolidation cycle
2. WHEN a consolidation cycle runs, THE MemoryConsolidator SHALL cluster episodic memories by emotional tag and extract semantic patterns from clusters with 2 or more members
3. WHEN a consolidation cycle runs, THE MemoryConsolidator SHALL promote high-phi (above 0.25) episodic memories to the AutobiographicalMemory timeline
4. THE Helios SHALL limit consolidation cycles to at most one per 600 ticks to avoid excessive CPU usage during sustained low-activity periods
5. WHEN a consolidation cycle completes, THE Helios SHALL log the number of patterns extracted, memories promoted, and items pruned

### Requirement 21: Autobiographical Store Disk Safety

**User Story:** As a system operator, I want the autobiographical JSONL store to be resilient to crashes and corruption, so that long-term memory survives unexpected process terminations.

#### Acceptance Criteria

1. THE Autobiographical_Store SHALL flush unflushed moments to disk every 10 recorded moments or upon receiving a shutdown signal
2. THE Autobiographical_Store SHALL use append-only JSONL writing so that a crash mid-write corrupts at most one line
3. WHEN loading from disk at startup, THE Autobiographical_Store SHALL skip malformed JSON lines and log a warning for each skipped line without aborting the load
4. THE Autobiographical_Store SHALL save chapter metadata to a separate JSON file during flush and shutdown operations
5. IF the JSONL file exceeds 50000 lines, THEN THE Autobiographical_Store SHALL archive the file by renaming it with a timestamp suffix and start a new file, retaining the most recent 5000 moments in the active file

### Requirement 22: Memory System State Persistence

**User Story:** As a system operator, I want the in-memory semantic facts and episodic memory summaries to persist across restarts, so that Helios retains learned knowledge and significant experiences after shutdown.

#### Acceptance Criteria

1. WHEN Helios executes shutdown, THE Memory_System SHALL serialize SemanticMemory facts to a JSON file in the data directory
2. WHEN Helios starts, THE Memory_System SHALL load previously saved SemanticMemory facts from the data directory if a saved file exists
3. WHEN Helios executes shutdown, THE Memory_System SHALL serialize EpisodicMemory items with importance above 0.3 to a JSON file in the data directory
4. WHEN Helios starts, THE Memory_System SHALL load previously saved high-importance EpisodicMemory items from the data directory if a saved file exists
5. IF any memory persistence file is corrupted, THEN THE Memory_System SHALL log a warning and initialize with empty storage without crashing

### Requirement 23: Memory Usage Monitoring

**User Story:** As a system operator, I want visibility into memory subsystem health during long-term operation, so that I can detect memory leaks, unbounded growth, or degradation before they become critical.

#### Acceptance Criteria

1. THE Helios SHALL log memory subsystem statistics (working items count, episodic items count, semantic facts count, autobiographical moments count) at each summary interval
2. WHEN any in-memory collection (episodic items, state history, conversation history) exceeds 80% of its configured capacity, THE Helios SHALL log a WARNING message indicating which collection is approaching capacity
3. THE Helios SHALL expose memory statistics through the get_state() method for external monitoring tools
4. WHEN the total in-memory item count across all memory tiers exceeds 2000 items, THE Helios SHALL trigger an immediate consolidation cycle regardless of Phi level to reduce memory pressure

### Requirement 24: Phi Dynamic Smoothing Alpha

**User Story:** As a consciousness researcher, I want the EMA smoothing alpha to adapt dynamically based on event intensity, so that high-impact events produce immediate visible jumps in ICRI while resting periods drift slowly.

#### Acceptance Criteria

1. WHEN an event with intensity exceeding 0.60 occurs, THE Phi_Engine SHALL use an EMA alpha value of 0.55 for fast response in the current Tick
2. WHEN an event with intensity between 0.30 and 0.60 occurs, THE Phi_Engine SHALL use an EMA alpha value of 0.30 for normal tracking
3. WHILE no event exceeds intensity 0.10 (resting state), THE Phi_Engine SHALL use an EMA alpha value of 0.10 for slow drift
4. WHEN a QQ message is received, THE Phi_Engine SHALL produce an ICRI increase of at least 0.10 from the pre-message baseline
5. WHEN a high-impact event occurs (intensity exceeding 0.60), THE Phi_Engine SHALL produce an ICRI value capable of reaching 0.30 or above

### Requirement 25: Rename Phi to ICRI

**User Story:** As a developer, I want the consciousness metric renamed from Φ to ICRI (Integrated Consciousness Richness Index) throughout the codebase, so that the metric name accurately reflects its engineering nature without implying IIT theoretical compliance.

#### Acceptance Criteria

1. THE Helios codebase SHALL use the term ICRI in all documentation, display outputs, and dashboard labels where the consciousness metric is referenced
2. THE Phi_Engine SHALL rename the temporal_depth source to dmn_depth to accurately reflect its Default Mode Network derivation
3. THE Helios codebase SHALL rename internal variable references from phi to icri in module interfaces and state objects
4. THE Helios SHALL maintain backward compatibility by accepting the old phi key in configuration files and mapping it to icri internally
5. IF external monitoring tools query the legacy phi field, THEN THE Helios SHALL return the ICRI value under both field names during a deprecation period

### Requirement 26: LLM Temperature Modulation from Consciousness Level

**User Story:** As a conversation designer, I want LLM speech generation temperature to be dynamically modulated by the ICRI level, so that Helios speaks mechanically when consciousness is low and creatively when consciousness is high.

#### Acceptance Criteria

1. WHILE ICRI is below 0.10, THE LLM_Speech SHALL use a temperature value of 0.3 producing mechanical and brief outputs
2. WHILE ICRI is between 0.10 and 0.25, THE LLM_Speech SHALL use a temperature value of 0.5 producing warm and moderate outputs
3. WHILE ICRI is between 0.25 and 0.45, THE LLM_Speech SHALL use a temperature value of 0.75 producing creative outputs
4. WHILE ICRI is between 0.45 and 0.65, THE LLM_Speech SHALL use a temperature value of 1.0 producing highly creative outputs
5. WHILE ICRI exceeds 0.65, THE LLM_Speech SHALL use a temperature value of 1.3 producing wild associative outputs
6. WHEN generating speech, THE LLM_Speech SHALL accept a temperature override parameter derived from the current ICRI value in the HeliosState

### Requirement 27: Event Cognitive Impact Dimensions

**User Story:** As a consciousness researcher, I want events to carry a 4-dimension cognitive impact profile, so that ICRI sources receive direct measurements rather than relying on approximate derivations from valence and arousal alone.

#### Acceptance Criteria

1. THE Helios event definition SHALL include a CognitiveImpactProfile with four dimensions: sensory (multimodal information load), cognitive (understanding demand), self (self-relevance), and novelty (versus repetition)
2. WHEN an event carries a CognitiveImpactProfile, THE Phi_Engine SHALL use the sensory dimension to feed the sensory_integration source directly
3. WHEN an event carries a CognitiveImpactProfile, THE Phi_Engine SHALL use the cognitive dimension to feed the dmn_depth source directly
4. WHEN an event carries a CognitiveImpactProfile, THE Phi_Engine SHALL use the self dimension to feed the self_reflection source directly
5. WHEN an event carries a CognitiveImpactProfile, THE Phi_Engine SHALL use the novelty dimension to feed the global_ignition source directly
6. IF an event does not carry a CognitiveImpactProfile, THEN THE Phi_Engine SHALL fall back to the existing approximation methods for source computation

### Requirement 28: Internal Thought Stream Integration

**User Story:** As a consciousness designer, I want Helios to generate spontaneous internal thoughts during rest periods, so that the system exhibits mind-wandering behavior characteristic of conscious entities rather than remaining inert between external events.

#### Acceptance Criteria

1. WHILE ICRI exceeds 0.10 and DMN is active, THE ThinkingEngine SHALL generate spontaneous thoughts at a frequency of approximately one thought per 5 seconds
2. THE ThinkingEngine SHALL support the following thought types: episodic_fragment, counterfactual, future_projection, self_question, free_association, and rumination
3. WHEN the dominant Panksepp system is PANIC, THE ThinkingEngine SHALL bias thought generation toward rumination and future_projection (worry-type) thoughts
4. WHEN the dominant Panksepp system is SEEKING, THE ThinkingEngine SHALL bias thought generation toward free_association and self_question (curiosity-type) thoughts
5. WHEN a thought is generated, THE ThinkingEngine SHALL store the thought in the Autobiographical_Store and optionally trigger regulation evaluation
6. THE ThinkingEngine SHALL enforce a 30-second cooldown per thought type to prevent repetitive thought loops
7. WHEN ICRI is below 0.10 or DMN is inactive, THE ThinkingEngine SHALL suppress thought generation entirely

### Requirement 29: Behavioral Execution Abstraction Layer

**User Story:** As a system architect, I want behavior execution handled by a unified framework with queue management, so that regulation decisions are cleanly separated from execution mechanics and support priorities, cancellation, and pause/resume.

#### Acceptance Criteria

1. THE BehaviorExecutor SHALL maintain a priority-ordered behavior queue where higher-priority behaviors preempt lower-priority ones
2. WHEN the RegulationEngine selects an action, THE LimbDecisionBridge SHALL convert the regulation score into a behavior command and enqueue it in the BehaviorExecutor
3. THE BehaviorExecutor SHALL support cancel, pause, and resume operations on queued or executing behaviors
4. WHEN a higher-priority behavior is enqueued while a lower-priority behavior is executing, THE BehaviorExecutor SHALL pause the current behavior and execute the higher-priority one
5. WHEN a behavior completes execution, THE BehaviorExecutor SHALL report the execution result back to the RegulationEngine for memory feedback

### Requirement 30: TTS Voice Synthesis

**User Story:** As a system operator, I want Helios to synthesize speech audio from LLM text output, so that Helios can communicate through voice when audio hardware is available.

#### Acceptance Criteria

1. WHEN LLM_Speech generates text output and TTS hardware is available, THE TTS_Module SHALL synthesize the text into audio using the Alibaba Cloud NLS TTS SDK
2. WHEN audio synthesis completes, THE TTS_Module SHALL play the audio through the system speaker
3. IF the TTS service is unavailable or credentials are missing, THEN THE TTS_Module SHALL log a warning and allow text-only operation without error
4. WHERE TTS is enabled, THE TTS_Module SHALL operate as a pluggable EventSource-compatible output module that can be registered or deregistered at runtime

### Requirement 31: STT Speech Recognition

**User Story:** As a system operator, I want Helios to accept voice input through speech recognition, so that Helios can perceive spoken language from its environment when microphone hardware is available.

#### Acceptance Criteria

1. WHILE a microphone device is available and STT is enabled, THE STT_Module SHALL capture audio and perform real-time transcription using the Alibaba Cloud NLS ASR SDK
2. WHEN transcription produces a complete utterance, THE STT_Module SHALL emit it as an EventSource input to Helios with appropriate SEC evaluation
3. IF the STT service is unavailable or microphone hardware is missing, THEN THE STT_Module SHALL log a warning and remain dormant without affecting other system operation
4. WHERE STT is enabled, THE STT_Module SHALL implement the EventSource interface and register itself with the Helios event collection system

### Requirement 32: Vision Input

**User Story:** As a system operator, I want Helios to perceive visual input from a camera, so that Helios can generate emotional events from its visual environment when camera hardware is available.

#### Acceptance Criteria

1. WHILE a camera device is available and vision is enabled, THE VisionModule SHALL capture frames at a configurable interval (default 5 seconds) using OpenCV
2. WHEN a frame is captured, THE VisionModule SHALL generate a scene description using a lightweight vision LLM and convert the description into emotional event triggers
3. IF the camera hardware is unavailable, THEN THE VisionModule SHALL log a warning and remain dormant without affecting other system operation
4. WHERE vision is enabled, THE VisionModule SHALL implement the EventSource interface and register itself with the Helios event collection system

### Requirement 33: Long-Running Stability Verification

**User Story:** As a system operator, I want Helios to operate stably for extended periods without degradation, so that the daemon can run indefinitely as a background service with confidence in reliability.

#### Acceptance Criteria

1. THE Helios SHALL operate for 24 continuous hours without crashing under normal event load
2. THE Helios SHALL maintain process RSS memory usage below 100MB during 24-hour continuous operation
3. WHEN the QQ WebSocket connection drops, THE QQ_Bot SHALL automatically reconnect within 30 seconds without manual intervention
4. WHEN the access_token expires, THE QQ_Bot SHALL automatically refresh the token without interrupting message processing
5. THE Helios SHALL integrate with logrotate or equivalent to prevent log files from growing beyond 100MB per file

### Requirement 34: Memory Compression for Old Memories

**User Story:** As a system operator, I want old autobiographical memories periodically compressed into summary narratives, so that storage remains bounded and retrieval performance does not degrade over months of continuous operation.

#### Acceptance Criteria

1. WHEN autobiographical moments older than 7 days exceed 100 items for a single day, THE Autobiographical_Store SHALL compress those moments into a summary narrative
2. THE Autobiographical_Store SHALL produce summary narratives that preserve the emotional arc and key events of the compressed period
3. WHEN compression occurs, THE Autobiographical_Store SHALL replace the individual moments with the summary narrative in the active store while retaining the raw JSONL archive on disk
4. THE Autobiographical_Store SHALL log the number of moments compressed and summaries produced during each compression cycle

### Requirement 35: Seed Memory Migration

**User Story:** As a system operator, I want external profile and memory documents imported as seed autobiographical memories, so that Helios starts with a pre-existing experiential history that informs personality evolution naturally.

#### Acceptance Criteria

1. WHEN seed documents are provided, THE Autobiographical_Store SHALL parse the documents and create seed autobiographical moments with timestamps predating the system start time
2. THE Autobiographical_Store SHALL tag each seed memory with a source label indicating its migration origin
3. THE Autobiographical_Store SHALL preserve seed memories across restarts identically to organically generated memories
4. THE Helios SHALL allow personality to evolve naturally from seed memory emotional valence without directly modifying PersonalityProfile parameters
5. WHEN generating replies, THE ResponsePipeline SHALL treat seed memories identically to organic memories when retrieving relevant context for conversation
