# Helios Tick Ingress and Egress Sequence

> Status: Active
> Role: show object-level ingress enrichment, main-loop handling, and egress paths
> Source of truth: `helios_main.py`, `channel_gateway.py`, `qq_channel.py`, `response_pipeline.py`, `regulation.py`, `limb.py`

Related diagrams:

- `research/diagrams/runtime_loop_overview.en.md`
- `research/diagrams/tick_runtime_flow.en.md`

```mermaid
sequenceDiagram
    autonumber

    actor User as QQ user
    actor Mic as microphone
    actor Cam as camera
    participant QQBot as QQBotClient
    participant QQQ as _msg_queue
    participant QQCh as QQChannel
    participant STT as STTChannel
    participant VIS as VisionChannel
    participant Gate as ChannelGateway
    participant Sep as SeparationSource
    participant DriveSrc as InternalDriveSource
    participant Main as Helios._tick_once
    participant State as HeliosState
    participant Hab as Habituation
    participant Daisy as DaisySystemEngine
    participant Phi as UnifiedPhi
    participant Drive as DriveOracle
    participant Think as ThinkingIntegration
    participant Mem as MemorySystem
    participant SEC as LLMSECEvaluator
    participant Reply as ResponsePipeline
    participant Reg as RegulationEngine
    participant Bridge as LimbDecisionBridge
    participant Exec as BehaviorExecutor
    participant Speech as LLMSpeechGenerator
    participant Out as ChannelGateway.route_outbound

    Note over User,QQQ: QQ ingress is asynchronous and lands in the message queue before the tick
    User->>QQBot: send QQ message
    QQBot->>QQQ: on_message(msg)
    Mic->>STT: utterance complete(text)
    Cam->>VIS: frame available

    loop each tick
        Main->>State: create fresh HeliosState
        par collect external channel input
            Main->>Gate: poll(state)
            Gate->>QQCh: poll()
            QQCh->>QQQ: drain queued messages
            QQQ-->>QQCh: raw QQ messages
            QQCh->>QQCh: normalize + annotate metadata
            Note over QQCh: event_triggers / sec_result / cognitive_impact
            QQCh-->>Gate: ChannelMessage
            Gate->>STT: poll()
            STT->>STT: utterance -> ChannelMessage
            STT-->>Gate: ChannelMessage
            Gate->>VIS: poll()
            VIS->>VIS: capture -> describe -> triggers
            VIS-->>Gate: ChannelMessage
        and collect internal event sources
            Main->>Sep: poll(separation_hours)
            Sep-->>Main: PANIC trigger or empty
            Main->>DriveSrc: poll(drive_dominant, drive_urgency)
            DriveSrc-->>Main: mapped drive trigger or empty
        end

        Gate->>Gate: evaluate inbound messages
        Gate-->>Main: merged_triggers + pending_messages
        Main->>Hab: novelty discount on triggers
        Hab-->>Main: habituated triggers
        Main->>Daisy: cycle(triggers, neurochem)
        Daisy-->>State: panksepp / valence / arousal / dominant
        Main->>Phi: feed impact + affect + self-model + DMN
        Phi-->>State: icri / temperature / style
        Main->>Drive: cycle(HeliosSnapshot)
        Drive-->>State: drive_dominant / urgency
        Main->>Think: generate(state)
        Think-->>Main: thought or None
        Main->>Mem: write working / episodic / autobio as thresholds allow

        alt there are inbound messages
            loop for each message
                Main->>SEC: evaluate(text, recent context)
                SEC-->>Main: sec_result
                Main->>Mem: hold(message + sec_result)
                Main->>Reply: should_reply(message, sec_result)
                alt should reply
                    Main->>Reply: generate_reply(message, state, sec_result)
                    Reply-->>Main: reply text or None
                    alt reply exists
                        Main->>Out: route_outbound(ChannelMessage[qq])
                        Out-->>User: QQ reply text
                    end
                end
                Main->>Reply: record_exchange(...)
            end
        end

        Main->>Reg: tick(panksepp, valence, hour, drive info)
        alt regulation chooses action
            Reg-->>Main: action + score
            Main->>Bridge: convert_and_enqueue(action, score)
            Bridge->>Exec: enqueue command
            Main->>Exec: drain current behavior
            Exec-->>Main: current action
            alt speak_* / request / intimate
                Main->>Speech: generate speech or fallback template
                Speech-->>Main: text or None
                alt text exists
                    Main->>Out: route_outbound(ChannelMessage[qq])
                    Out-->>User: active outbound text
                end
            else internal-intent action
                Main->>Main: mark internal action handled
            end
            Main->>Exec: complete_current(result)
            Exec-->>Reg: behavior result callback
        end

        Main->>Mem: consolidate / compress / persist when thresholds hit
    end
```

Reading priority: external input is first standardized into `ChannelMessage`; passive replies and active behaviors are separate paths; the stable primary outbound path is still QQ.
