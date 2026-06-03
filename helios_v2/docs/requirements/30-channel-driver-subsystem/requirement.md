# Requirement 30 - Channel driver subsystem framework

## 1. Background and Problem

Helios v2 has a real cognition chain (`01-18`) that, after `25-29`, runs real LLM-backed thought, closes internal-only ticks, and grounds autonomy disposition in real cognition. But the system still cannot exchange anything with the outside world through a real transport. The only structural gap left in the brain-aligned flow is `M outward output` plus its inbound counterpart: there is no owner for channel transport.

Concretely:

1. Inbound is a hardcoded shim. `FirstVersionSensorySource` emits one fixed `RawSignal` ("hello runtime") per tick. There is no real input transport, no way to receive a real message, and no way to add or remove input sources at runtime.
2. Outbound has no owner at all. The `13` planner-bridge selects a channel and validates channel state, but it consumes a `channel_descriptor_snapshot` / `channel_status_snapshot` that the composition root hardcodes (`cli: {available: True, bound: True, execute_now: True}`). No owner actually transports an accepted `ActionDecision` to a real destination. The `16` outward-expression chain produces delivery drafts but explicitly disclaims transport authority.
3. Across requirements `01-20` this "channel execution / outward transport" concept was consistently referenced but never assigned an owner. It is a deliberate gap, not a missing implementation inside an existing owner. The `13` and `16` owner docs explicitly state they do not own channel transport.

The legacy `helios_v1` channel subsystem (`archive/helios_v1/helios_io`) demonstrated a relatively complete model: a transport-agnostic channel abstraction with per-channel descriptors, config contracts, lifecycle/management ops, a registry gateway, dynamic registration, and concrete bidirectional channels (CLI, QQ, TTS, STT, Vision). It also carried v1 debt that must not be copied: channels computed cognitive stimulus intensity and triggers (owner overreach into appraisal), channels owned both transport and normalization, and channels embedded `logging`.

This requirement establishes the channel transport owner as a Linux-kernel-driver-style subsystem: the owner is a thin driver framework (a registry plus a tick-boundary scheduler), and each channel is an independent driver implementing one uniform protocol. It deliberately reuses the v1 "what" (descriptor, config, ops, lifecycle, dynamic registration) while rejecting the v1 "how" (no cognitive evaluation, no normalization ownership, no embedded logging, protocol+injection style, fail-fast).

## 2. Goal

Establish a single channel-driver-subsystem owner that manages bidirectional channel drivers as runtime-pluggable units behind one uniform driver protocol, drains inbound transport packets into `RawSignal` objects for the sensory owner under a bounded NAPI-style per-tick budget, dispatches planner-accepted action decisions to drivers for outbound transport under a bounded budget, exposes per-driver descriptor/config/lifecycle/health through formal ops, tags each inbound packet with a transport-intrinsic QoS marker without judging cognitive salience, supports runtime registration and deregistration of drivers, and fails fast on missing critical driver capability, while owning no normalization (sensory), no salience or attention (appraisal), no channel selection or acceptance (planner), and no outward content shaping (outward-expression).

## 3. Functional Requirements

### 3.1 Owner boundary
1. The channel driver subsystem must be a dedicated owner in a new package `helios_v2.channel`. It owns: the driver registry, the uniform driver protocol, per-driver descriptor/config/lifecycle/status/health, the inbound drain scheduler, the outbound dispatch scheduler, and the transport-intrinsic QoS marker taxonomy.
2. The owner must not own normalization of raw signals into stimuli (that remains the `02` sensory owner), salience or attention (that remains the `03` appraisal owner), channel selection or action acceptance (that remains the `13` planner-bridge owner), or outward content shaping (that remains the `16` outward-expression owner).
3. A single physical bidirectional channel (for example QQ) must be representable as one driver that both receives and sends, so driver cohesion is preserved. The owner must not split one transport into separate inbound and outbound owners.

### 3.2 Uniform driver protocol (Linux-driver-style)
1. The owner must define one uniform `ChannelDriver` protocol that every concrete driver implements, analogous to a Linux driver implementing a uniform driver API.
2. Each driver must expose a descriptor declaring at least: stable driver id, supported input packet types/formats, supported output ops/formats, supported management ops, config fields (with mutability and validation hints), and health signals.
3. Each driver must expose an owned config snapshot and validated config update through ops, so configuration semantics live with the driver, not in composition wiring.
4. Each driver must expose lifecycle management through formal ops (at minimum init, connect, disconnect, deinit, pause, resume, health_check) returning structured management results with explicit status transitions; there must be no requirement to call concrete driver methods directly from outside the owner.
5. Each driver must report a lifecycle status from a fixed taxonomy that distinguishes at least uninitialized, connected, disconnected, paused, and error states.

### 3.3 Runtime-pluggable registry
1. The owner must maintain a driver registry supporting runtime registration and deregistration of driver instances without restarting the runtime.
2. Registration and deregistration must preserve descriptor discoverability and status visibility, and must be observable through structured results.
3. Deregistration must drive the driver through an explicit teardown (disconnect/deinit) before removal; a driver must never be dropped while still holding live transport resources without an explicit teardown attempt.

### 3.4 Inbound drain (NAPI-style, bounded)
1. Inbound transport must be asynchronous inside each driver (a driver may run its own background receive loop or queue), and synchronous at the owner boundary: the owner drains drivers only at an explicit tick-boundary drain call.
2. Each driver must hold a bounded inbound backlog. Backlog overflow must apply an explicit, documented overflow policy (for example drop-oldest or reject-newest) and record the overflow count; the backlog must never grow without bound and overflow must never be silent.
3. The owner must drain inbound packets under a bounded per-tick budget. The drain operation must return at most `budget` packets across drivers and an explicit indication of how much remains pending, so a flooded driver cannot starve the tick or the cognition chain.
4. A driver that still has pending packets after the budget is exhausted must remain in the ready set and be drained on a subsequent tick (backpressure becomes graceful latency growth, not tick explosion). Drain must be fair across drivers with pending packets.
5. The owner must emit drained packets as `RawSignal` objects suitable for the `02` sensory owner, preserving driver/source provenance. The owner must not normalize them into stimuli and must not score them.

### 3.5 Transport-intrinsic QoS marking
1. Each inbound packet must carry a transport-intrinsic QoS marker drawn from a fixed bounded taxonomy. The marker must be derived only from transport-visible, content-agnostic facts (for example packet type/format, source lane such as control vs bulk, transport urgency, size), never from message content or cognitive importance.
2. The QoS marker must travel as opaque transport metadata on the `RawSignal` and must be preserved unchanged when the sensory owner normalizes it onto the `Stimulus`. Neither the channel owner nor the sensory owner may interpret the marker as cognitive salience.
3. The channel owner may use the QoS marker only for transport scheduling (for example which lane to drain first when the budget is tight, which packet to drop on overflow). It must not use the marker to judge whether a packet is cognitively important; semantic salience and attention are owned exclusively by the `03` appraisal owner, which consumes the marker as one input among many.
4. First version: the marker taxonomy and its presence on `RawSignal`/`Stimulus` metadata are established, but QoS-conditioned multi-lane scheduling and QoS-based selective dropping beyond a single default policy are design-reserved and not required.

### 3.6 Outbound dispatch (bounded, planner-authority-preserving)
1. The owner must accept planner-accepted action decisions for outbound transport and dispatch them to the target driver. The owner must not re-decide channel selection or acceptance; it transports what the planner already accepted.
2. Outbound dispatch must run under a bounded per-tick budget and must respect the planner-provided execution priority ordering when present. Each driver must hold a bounded outbound queue with explicit backpressure on overflow.
3. Dispatch results (delivered, failed, driver-unavailable, dropped-on-overflow) must be published as structured outcomes that downstream owners (for example writeback) can consume, never silently swallowed.
4. The owner must expose real per-driver channel state (registered, connected, supported ops, ready) to the planner so the planner consumes real channel status instead of a hardcoded snapshot.

### 3.7 Fail-fast and capability readiness
1. A driver that declares a critical transport credential or resource (for example an API token) must expose a static readiness check. When the runtime binds such a driver as critical, missing readiness must fail startup fast through the existing dependency gate, with no degraded transport mode.
2. The owner must not invent a fallback transport when a driver is unavailable. An unavailable target driver yields an explicit dispatch outcome, not a silent substitution.
3. Missing or malformed driver inputs must fail through explicit owner errors.

## 4. Non-Functional Requirements

1. Performance: inbound drain and outbound dispatch per tick must be bounded by their budgets; a flooded driver must not increase per-tick work beyond the budget. Driver background I/O must not block the tick.
2. Reliability: the registry, drain, and dispatch behavior must be deterministic for a fixed driver set and fixed inputs; the only non-deterministic boundary is a concrete driver's real transport, which tests replace with a deterministic fake driver.
3. Observability and logging: the owner must not introduce a second logging mechanism and must not use `logging` or `print`. Transport facts (drain counts, overflow counts, dispatch outcomes, status transitions) travel through formal owner contracts and the existing `21` observability surface.
4. Compatibility and migration: the owner is additive. It introduces a new package, a new inbound source that replaces the hardcoded `FirstVersionSensorySource` only when bound, and a real channel-state provider for the planner that replaces the composition hardcoded snapshot only when bound. A runtime that binds no channel driver must remain assemblable and runnable.

## 5. Code Behavior Constraints

1. The driver registry, driver protocol, drain/dispatch schedulers, and QoS taxonomy must live in `helios_v2.channel`. No other module may construct a concrete transport client directly.
2. Concrete drivers must be injected behind the driver protocol. A driver that needs a vendor SDK or network resource must import it lazily inside its own call path, so importing `helios_v2.channel` never requires that SDK.
3. The owner must not compute cognitive salience, must not normalize raw signals into stimuli, must not re-decide channel selection or acceptance, and must not shape outward content.
4. Inbound backlog and outbound queue must be bounded; overflow must be explicit and counted, never silent or unbounded.
5. No degraded or fallback transport mode is allowed; missing critical driver readiness fails fast.
6. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/channel/__init__.py`
2. `helios_v2/src/helios_v2/channel/contracts.py`
3. `helios_v2/src/helios_v2/channel/engine.py`
4. `helios_v2/src/helios_v2/sensory/contracts.py` (only if `RawSignal` needs an explicit QoS field rather than a metadata convention)
5. `helios_v2/src/helios_v2/composition/dependencies.py` (driver readiness as a critical dependency when bound)
6. `helios_v2/tests/test_channel_contracts.py`
7. `helios_v2/tests/test_channel_engine.py`
8. `helios_v2/docs/requirements/index.md`
9. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
10. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
11. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. `helios_v2.channel` exposes a documented uniform `ChannelDriver` protocol, a driver `Descriptor`/`ConfigSnapshot`/`ManagementResult`/status taxonomy, a bounded inbound packet/`RawSignal` contract with a transport-intrinsic QoS marker taxonomy, a bounded outbound decision/dispatch-outcome contract, a `ChannelError`, and a `ChannelSubsystem` owner with a public API.
2. A driver can be registered and deregistered at runtime through the owner, with descriptor/status discoverable while registered and gone after deregistration, verified by focused tests with a deterministic fake driver.
3. Inbound drain returns at most the configured budget of `RawSignal` objects across drivers plus an explicit pending indication; a driver flooded beyond the budget retains its remainder for a later drain and its backlog overflow is bounded and counted, verified with a fake driver that supplies more than the budget.
4. Each drained `RawSignal` carries a transport-intrinsic QoS marker from the fixed taxonomy, derived without reading content; the owner uses it only for transport scheduling and never as salience.
5. Outbound dispatch transports a planner-accepted decision to the target driver under a bounded budget, respects execution priority when present, and publishes an explicit dispatch outcome for delivered/failed/unavailable/dropped cases; the owner exposes real per-driver channel state for the planner.
6. A driver declaring a critical credential exposes a static readiness check that fails startup fast when unmet, with no degraded transport; the single-logging-mechanism guard test still passes and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement ships the framework owner and its contracts only; the first concrete driver (CLI) is requirement `31`. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. QoS-conditioned multi-lane inbound scheduling and QoS-based selective dropping under heavy load.
2. Concrete real-transport drivers with external side effects (QQ, voice STT/TTS, vision), each with its own readiness gate.
3. Composition wiring that makes a channel driver the default inbound source and the planner's real channel-state provider, replacing the current shims, once a real driver is bound.
4. Richer outbound delivery semantics (acknowledgements, retries, multi-recipient) layered above the bounded dispatch contract.

None of these may be smuggled into this slice. This requirement does not introduce cognitive evaluation, does not move normalization or salience ownership, does not grant the channel owner channel-selection or acceptance authority, and does not introduce any external network transport (the first driver in `31` is local CLI only).
