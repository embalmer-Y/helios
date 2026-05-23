# Helios Current Structure

> Status: Active Structural Reference
> Role: Short-form boundary sheet for the current codebase
> See also: `ARCHITECTURE.zh-CN.md`, `ARCHITECTURE.en.md`

## Purpose

This note records the post-cleanup, post-migration module boundaries for the active codebase. It is intended to prevent transport logic from drifting back into the repository root or into `core/`.

## Active Boundaries

### Repository root

The root now contains only top-level runtime assets and core affective substrate modules:

- `helios_main.py`: primary runtime entry point
- `dashboard.py` and `dashboard.html`: runtime dashboard surface
- `allostasis.py`, `daisy_emotion.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, `habituation.py`: affective and physiological substrate
- deployment/runtime assets such as `helios.service`, `heliosd.sh`, `helios.logrotate`

The root no longer owns protocol clients, speech generation modules, or channel abstractions.

### `helios_io/`

`helios_io/` owns all external I/O concerns.

- `helios_io/protocols/qq.py`: QQ transport client and message model
- `helios_io/llm/speech.py`: LLM-backed speech generation
- `helios_io/channel.py`: channel abstractions and transport message types
- `helios_io/channel_gateway.py`: gateway bridging channels into the event-source pipeline
- `helios_io/channels/`: concrete inbound/outbound channel adapters
- `helios_io/response_pipeline.py`: passive reply generation
- `helios_io/conversation_history.py`: conversation exchange storage
- `helios_io/llm_sec_evaluator.py`: SEC feature extraction via LLM
- `helios_io/icri_temperature.py`: ICRI-to-temperature mapping
- `helios_io/limb.py`, `helios_io/limb_decision_bridge.py`: behavior execution I/O boundary

Rule: if a module exists to receive, send, adapt, route, or generate content across an external interface, it belongs in `helios_io/`.

### `core/`

`core/` is now narrowed to runtime infrastructure and agent-internal event plumbing.

- `event_source.py`
- `helios_state.py`
- `tick_guard.py`
- `trigger_merge.py`
- `separation_source.py`
- `drive_source.py`

`core/__init__.py` still re-exports channel-related types for compatibility, but the owning implementations live in `helios_io/`.

### `memory/`, `cognition/`, `regulation/`

These packages keep their current package-level ownership:

- `memory/`: autobiographical, episodic, semantic, compression, and seed import logic
- `cognition/`: appraisal, drives, phi, and thinking layers
- `regulation/`: action selection, conation, and behavior regulation

## Practical Rules

1. Do not add new protocol clients at the repository root.
2. Do not add new transport abstractions or gateways under `core/`.
3. Add future protocol implementations under `helios_io/protocols/`.
4. Add future model-backed generation components under `helios_io/llm/`.
5. Keep `core/` limited to transport-agnostic runtime infrastructure.

## Status

Validated after the `io -> helios_io` rename, the protocol/speech/channel migration, and final wrapper removal. Full regression baseline at this stage: `pytest -q` -> `520 passed`.
