# Helios Runtime Loop Overview

> Status: Active
> Role: show the continuous runtime loop at the system level
> Source of truth: current `helios_main.py` and `helios_io/` implementation

Related diagrams:

- `tick_runtime_flow.en.md`
- `tick_ingress_egress_sequence.en.md`

```mermaid
flowchart TD
    ENV[Environment\nQQ / STT / Vision / user contact] --> INCH[External ingress channels\nQQChannel / STTChannel / VisionChannel]
    INTERNAL[Internal inputs\nseparation anxiety / drive urgency] --> ISRC[Internal event sources\nSeparationSource / DriveSource]
    INCH --> GATEIN[Ingress normalization\nChannelMessage / metadata / evaluators]
    GATEIN --> EVTS[Event convergence\nChannelGateway + EventSource registry]
    ISRC --> EVTS
    EVTS --> TICK[helios_main tick\n_collect_events -> _tick_once]

    TICK --> AFFECT[Affective update\nHabituation -> DAISY -> Mood / Allostasis]
    TICK --> COG[Cognitive update\nPhi / Drives / Thinking]
    TICK --> MEM[Memory update\nWorking / Episodic / Autobio / Consolidation]

    AFFECT --> STATE[Current tick state\nHeliosState]
    COG --> STATE
    MEM --> STATE

    STATE --> PASSIVE[Interactive expression\nPassive Reply Pipeline]
    STATE --> ACTIVE[Agent-initiated expression\nRegulation -> LimbBridge -> Executor]

    PASSIVE --> OUTGATE[Unified egress\nChannelGateway.route_outbound]
    ACTIVE --> OUTGATE
    OUTGATE --> OUTCH[External channels\ncurrent primary path: QQ\navailable capability: TTS]
    OUTCH --> EFFECT[External result\nuser reply / new input / contact refresh]
    EFFECT --> ENV
```

This is still an overview diagram, but it now makes the main control points explicit: the external ingress path, the internal input path, event convergence, per-tick state update, the split between passive replies and active behavior, and the unified egress surface.

The “internal inputs” here are not abstract placeholders. They correspond to two implemented EventSource paths in the current code: `SeparationSource` emits `PANIC` from separation hours, and `DriveSource` emits mapped Panksepp triggers from the current dominant drive. If you want object-level call ordering, do not stop here; continue into `tick_ingress_egress_sequence.en.md`. In the current implementation, QQ remains the primary outbound path, while TTS is capability-ready but not the default main-loop sink.
