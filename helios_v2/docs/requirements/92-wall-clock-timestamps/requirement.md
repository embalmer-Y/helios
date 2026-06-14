# Requirement 92 - Wall-Clock Real Timestamps

## 1. Background and Problem

R91 closed the present-field gap (the operator's actual words now reach the `11`
internal-thought LLM prompt). The same R91 implementation also surfaced the next gap on
the same path: the runtime has no real wall-clock fact anywhere in its cognitive chain.

Concretely, the empirical 2026-06 emotion long-run captured the real `11` user prompt
(see ROADMAP §9.4 and §11.2) and confirmed two facts:

1. The only "time"-shaped fact reaching cognition was the R55 `temporal_signal` (an
   accumulated rest count, in unitless `[0,1]`, projected by R91 as
   `pacing: <signal>`). It is a tick-counted pacing signal, not a wall-clock fact.
2. Nowhere in the runtime — not on the per-tick `RuntimeFrame`, not on `RawSignal` /
   `Stimulus.metadata`, not on `PersistedExperienceRecord` — is the real wall-time
   recorded. The `06` durable memory therefore carries `tick_id` but no absolute
   "when did this happen". The `11` LLM cannot answer "how long ago did the operator
   speak" or "is this a quick follow-up or a one-day silence" from real evidence; only
   tick-pacing is available, and a tick is not a second.

This blocks two near-term needs that depend on real elapsed seconds, not tick counts:

1. R91-style present-field rendering of "last input: 4.3s ago" so the `11` LLM has
   real elapsed-time grounding (not the unitless pacing number).
2. Future memory probes (R90 family) and durable continuity claims of the form "we last
   spoke yesterday" need a real `created_at_wall` on every persisted experience record.

The runtime kernel already imports `time` (it uses `time.perf_counter` for stage
durations), but that is a monotonic clock used only for observability; it is not a wall
clock and is not exposed as a runtime fact.

## 2. Goal

Introduce a small backend-neutral wall-clock capability owner that produces one bounded
real-time fact per call, and expose that fact at three additive consumption points
without changing any owner's cognitive policy:

1. one `tick_wall_seconds` value seeded onto the per-tick `RuntimeFrame`,
2. one `received_at_wall` metadata stamp on every inbound channel packet (and therefore
   on the `02` `Stimulus.metadata` it normalizes into), and
3. one `created_at_wall` field on every `PersistedExperienceRecord` written this tick.

The R91 present-field bridge, which today renders `pacing: <signal>`, must additionally
render `last input: <seconds>s ago` when both the frame's wall-time and the rendered
stimulus's `received_at_wall` are present (real elapsed seconds), and must keep the
existing `pacing:` rendering otherwise (defined fallback). The wall-clock is injected
through a `RuntimeProfile` capability seam and is fully optional: when not injected,
all three consumption points hold honest `None` and downstream behavior is byte-for-byte
unchanged. The full network-free test suite must stay green.

## 3. Functional Requirements

### 3.1 Wall-clock capability owner

1. The runtime must expose a new owner package `helios_v2.wall_clock` whose only
   responsibility is to produce one bounded real-time reading on demand.
2. The owner must define a `WallClock` protocol with a single method `now()` returning
   a `WallClockReading` contract (one bounded `wall_seconds: float` plus an optional
   stable `clock_id: str` used for provenance, never interpreted as content).
3. The owner must ship two first-version implementations:
   1. `SystemWallClock` — calls `time.time()` and returns the result (production
      default when injected).
   2. `FixedWallClock` — accepts an injected sequence of seconds (or a single fixed
      value, or an explicit `advance(seconds)` step) and returns deterministic
      readings; used by every network-free test that exercises wall-time behavior.
4. The owner must own no cognitive policy. It must not import any cognitive owner
   package (`appraisal`, `feeling`, `memory`, `thought_gating`, `internal_thought`,
   `autonomy`, `evaluation`, `prompt_contract`, etc.) and must not interpret the
   `wall_seconds` value beyond range validation. Rendering "5 seconds ago" is
   composition glue, not this owner.

### 3.2 Bounded reading and fail-fast

1. `WallClockReading.wall_seconds` must be a finite, non-negative `float`. Construction
   must raise `WallClockError` on `NaN`, `+Inf`, `-Inf`, or a negative value (no silent
   defaulting to `0.0` or to "now").
2. A `WallClock` implementation that returns a structurally invalid reading must allow
   that invalid reading to fail fast at construction; the owner must not paper over a
   broken clock.
3. When no `WallClock` is injected at all (the default), the runtime must operate in an
   explicit "wall-clock-absent" mode: every consumption point holds an honest `None`.
   The runtime must not fall back to a hidden `time.time()` call elsewhere or fabricate
   a substitute timestamp.

### 3.3 Frame-level wall-time seeding

1. `RuntimeFrame` must gain one additive optional field `tick_wall_seconds: float | None`
   defaulting to `None`. Existing fields and validation must be unchanged.
2. The runtime kernel must accept an injected `WallClock` (constructor parameter,
   default `None`). When wired, the kernel must call `WallClock.now()` exactly once at
   the start of each `tick()` and seed the resulting `wall_seconds` into every
   `RuntimeFrame` constructed for that tick (every stage in the same tick reads the
   same wall-time).
3. When the kernel has no injected `WallClock`, every `RuntimeFrame` must carry
   `tick_wall_seconds=None`. The kernel must not call `time.time()` itself for this
   purpose; the `time.perf_counter()` already used for stage durations is unrelated and
   must remain a separate concern.

### 3.4 Channel inbound stamping

1. The CLI channel driver (`helios_v2.channel.drivers.cli.CliChannelDriver`) must
   accept an optional injected `WallClock` (constructor parameter, default `None`).
2. When wired, `CliChannelDriver.submit_line()` must call `WallClock.now()` once per
   received line and store the resulting `wall_seconds` value in the inbound packet's
   metadata under the reserved key `received_at_wall`. The stamp must be the **arrival
   time**, captured at `submit_line` (the asynchronous receive point), not the
   `drain_inbound` time.
3. When no `WallClock` is wired, the metadata key `received_at_wall` must be absent
   (honest absence). The CLI driver must not hard-import `time` for this purpose.
4. The existing `02` `RawSignal -> Stimulus` normalization must preserve the
   `received_at_wall` metadata key verbatim (it already preserves the metadata mapping
   verbatim; this requirement adds no normalization logic).

### 3.5 Present-field rendering of real elapsed seconds

1. The R91 `_present_field_summary_text` composition helper must be extended so that
   when both `frame.tick_wall_seconds` and at least one rendered stimulus's
   `received_at_wall` are present, it renders one additional bounded clause shaped
   `last input: <X.X>s ago` (one decimal, monotonic non-negative; clamp a negative
   delta to `0.0s` to defend against an NTP rewind).
2. When `frame.tick_wall_seconds` or every rendered stimulus's `received_at_wall` is
   absent, the helper must keep rendering the existing `pacing: <signal>` clause
   exactly as today (defined fallback; the R91 `pacing:` line must not regress).
3. When both wall-clock-derived and pacing-derived clauses are available, the helper
   must emit both (`last input: 4.3s ago; pacing: 0.6`); they describe different facts
   (real elapsed seconds vs accumulated rest pacing) and must not be merged.
4. The 600-character `present_field_summary` cap continues to apply; over-cap input is
   already truncated deterministically by the existing R91 rule.

### 3.6 Persisted experience created-at wall-time

1. `PersistedExperienceRecord` must gain one additive optional field
   `created_at_wall: float | None = None`. Existing fields and validation must be
   unchanged.
2. The composition carry seams that durably append the `15` continuity stream and the
   `06` consolidation-worthy affect-memory (the existing `RuntimeHandle._persist_*`
   path) must read `frame.tick_wall_seconds` for the just-completed tick (or, when the
   tick wall-time is absent, write `None` honestly) and write it into the persisted
   record at write time.
3. The SQLite backend must accept the new field and persist it through a one-shot
   schema migration that follows the existing PRAGMA-guarded `ALTER TABLE` pattern
   (used previously for R45). Existing SQLite files must remain readable; rows written
   before R92 must read back with `created_at_wall=None`.
4. The in-memory backend (used by the test double) must persist and read back the
   field exactly. The semantic recall path (R34 `search_similar`), the affect-memory
   recall path (R52), and the recency-only path must preserve the new field as opaque
   metadata; this slice introduces no new ranking, decay, or filter on the field.

### 3.7 RuntimeProfile capability seam

1. `RuntimeProfile` must gain one additive optional field
   `wall_clock: WallClock | None = None` and the corresponding loose-kwarg surface on
   `assemble_runtime` (so existing callers may pass either the profile or a loose
   `wall_clock=` kwarg, consistent with the R58 capability-bundle pattern).
2. The default `RuntimeProfile()` must continue to mean "no wall-clock wired" — the
   default assembly must remain byte-for-byte unchanged when no clock is injected.
3. `assemble_production_runtime()` must wire a `SystemWallClock` by default (so the
   shipping production assembly carries real wall-time). Test/CI assemblies must
   explicitly inject `FixedWallClock` and never rely on `SystemWallClock`.
4. When a `WallClock` is wired, the same single instance must be threaded into
   1) the kernel (frame seeding),
   2) the CLI channel driver, when channel-bound,
   3) the persistence carry seams.
   No two consumers may construct independent `WallClock` instances.

## 4. Non-Functional Requirements

1. **Performance.** A `WallClock.now()` call must be O(1) and must not perform I/O
   beyond `time.time()` (or its deterministic test substitute). The kernel must call
   `now()` exactly once per tick (not per stage). The CLI driver must call `now()`
   exactly once per `submit_line`. The persistence seam must not call `now()` at all
   (it reads the already-seeded `frame.tick_wall_seconds`). R83 measured per-tick cost
   must not regress.
2. **Reliability.** A clock that returns an invalid reading raises `WallClockError`
   (fail-fast). A clock going backwards (NTP rewind during a real run) is the only
   tolerated anomaly: `last input: <neg>` is clamped to `0.0s` at the rendering
   boundary so the prompt never shows a negative ago. Persisted records may carry the
   raw value; this slice introduces no anomaly correction in storage.
3. **Observability.** No new logging mechanism. `21` observability remains the single
   logging owner, and the `LogEvent.timestamp` it already records is independent of
   this owner. No `print` / `import logging` anywhere under `src/`.
4. **Compatibility and migration.** Every change is additive. Default rollout: the
   default `assemble_runtime()` continues to leave wall-clock unwired (legacy and
   tests pass byte-for-byte). The standard production assembly opts in to
   `SystemWallClock`. Existing SQLite files migrate in place; old rows read back with
   `created_at_wall=None`. No `RuntimeProfile` invariant becomes coupled to the
   wall-clock field.

## 5. Code Behavior Constraints

1. **Forbidden — fabricated wall-time.** When no `WallClock` is wired, no consumer may
   substitute `time.time()`, the kernel's `time.perf_counter`, the `tick_id` modulo a
   constant, or any other surrogate. `tick_wall_seconds=None`,
   `received_at_wall` absent, and `created_at_wall=None` are the defined honest absent
   states; rendering and persistence must respect them.
2. **Forbidden — owner crossing.** The `helios_v2.wall_clock` owner may not import any
   cognitive owner. No cognitive owner may import `helios_v2.wall_clock` directly; the
   wall-clock fact reaches them only as opaque values on `RuntimeFrame` /
   `Stimulus.metadata` / `PersistedExperienceRecord` placed by composition.
3. **Forbidden — multi-instance threading.** `assemble_runtime` may not construct two
   independent `WallClock` instances. The same instance is threaded everywhere it is
   needed; `FixedWallClock` semantics depend on this.
4. **Boundary — composition is the only renderer.** `_present_field_summary_text` is
   the only place that turns `tick_wall_seconds` + `received_at_wall` into the human
   string `last input: X.Xs ago`. Owners do not perform this rendering.
5. **Boundary — no policy on wall-time.** No owner in this requirement may use
   `created_at_wall` for ranking, decay, eviction, or any cognitive decision in this
   slice. Such consumers belong to follow-up requirements (e.g. R83 family long-run,
   future P5 dual-track memory R93+ which already plans wall-time-based decay).
6. **Boundary — `receive` time, not `drain` time.** The CLI driver's
   `received_at_wall` must reflect when `submit_line` was called, not when
   `drain_inbound` later observes the line. This is a real arrival fact, not a
   scheduling artifact.

## 6. Impacted Modules

New:
1. `src/helios_v2/wall_clock/__init__.py` — public exports.
2. `src/helios_v2/wall_clock/contracts.py` — `WallClockError`, `WallClockReading`,
   `WallClock` protocol.
3. `src/helios_v2/wall_clock/engine.py` — `SystemWallClock`, `FixedWallClock`.

Modified:
4. `src/helios_v2/runtime/contracts.py` — additive `tick_wall_seconds` on
   `RuntimeFrame`.
5. `src/helios_v2/runtime/kernel.py` — accept injected `WallClock`; seed
   `tick_wall_seconds` once per tick.
6. `src/helios_v2/channel/drivers/cli.py` — accept injected `WallClock`; stamp
   `received_at_wall` in `submit_line`.
7. `src/helios_v2/composition/runtime_assembly.py` — `RuntimeProfile.wall_clock`,
   loose-kwarg parity, threading into kernel + CLI driver + persistence carry seam.
8. `src/helios_v2/composition/bridges.py` — extend `_present_field_summary_text` with
   the real-elapsed clause; persistence carry seam reads `frame.tick_wall_seconds`.
9. `src/helios_v2/persistence/contracts.py` — additive `created_at_wall` on
   `PersistedExperienceRecord` (and on the transient projection used at write time).
10. `src/helios_v2/persistence/engine.py` — SQLite schema migration; in-memory backend
    round-trip.

New tests:
11. `tests/test_wall_clock_contracts.py` — `WallClockReading` invariants;
    `SystemWallClock` returns a non-negative finite reading; `FixedWallClock`
    determinism (sequence, advance).
12. `tests/test_runtime_frame_wall_clock.py` — `RuntimeFrame` carries
    `tick_wall_seconds` when wired; `None` when absent; same value across stages of
    the same tick.
13. `tests/test_cli_driver_wall_clock_stamp.py` — `submit_line` stamps
    `received_at_wall` only when wired; arrival time, not drain time; absent metadata
    key when not wired.
14. `tests/test_present_field_wall_clock_rendering.py` — `last input: X.Xs ago`
    renders when both ends are present; `pacing:` fallback when either is absent;
    NTP-rewind clamp; both clauses coexist when both available.
15. `tests/test_persistence_wall_clock_field.py` — `created_at_wall` round-trips on
    both backends; SQLite migration of an old file leaves old rows `None`; new rows
    carry the value.
16. `tests/test_assemble_runtime_wall_clock_profile.py` — `RuntimeProfile.wall_clock`
    threads through to all three consumers from one instance; profile + loose-kwarg
    overlap raises `CompositionError`; `assemble_production_runtime` wires
    `SystemWallClock` by default.

Documentation (cross-file rule §8):
17. `docs/requirements/index.md` — new R92 row.
18. `docs/OWNER_GUIDE.md` / `docs/OWNER_GUIDE.zh-CN.md` — new wall-clock owner
    section + status header sync.
19. `docs/PROGRESS_FLOW.en.md` / `docs/PROGRESS_FLOW.zh-CN.md` — new infrastructure
    box (blue) + last-synced sync.
20. `docs/ARCHITECTURE_BOUNDARIES.md` — new owner row + boundary rules.
21. `docs/BRAIN_ARCHITECTURE_COMPARISON.md` — wall-clock as raw timing-system afferent
    timestamp (`C_engineering_hypothesis`, brief functional analog).
22. `docs/ROADMAP.zh-CN.md` — mark R92 done; advance W1 status.

Probe (per §8.2 prompt-change validation):
23. `scripts/r92_probes/01_with_wall_clock.json` — real-LLM probe with the new
    `last input: 4.3s ago` clause; verifies the model uses the elapsed-seconds fact
    and does not fabricate one when absent.

## 7. Acceptance Criteria

1. The new owner package exists with `WallClockReading` / `WallClock` /
   `SystemWallClock` / `FixedWallClock`, validates fail-fast on `NaN`/`Inf`/negative,
   and imports no cognitive owner.
2. With a `FixedWallClock(advance=1.0)` injected, every `RuntimeFrame` of the same
   tick carries the same `tick_wall_seconds` value, and successive ticks advance by
   exactly 1.0; with no clock injected, every frame carries `tick_wall_seconds=None`.
3. With a `FixedWallClock` injected into `CliChannelDriver`, a line submitted at
   `t=10.0` and drained on a later tick carries `received_at_wall=10.0` (arrival time,
   not drain time). With no clock injected, the metadata key is absent.
4. `_present_field_summary_text` renders `last input: 3.0s ago` when the rendered
   stimulus arrived at `t=10.0` and `frame.tick_wall_seconds=13.0`; falls back to the
   pre-R92 `pacing: <signal>` line when either side is absent; clamps a negative delta
   to `0.0s`.
5. A new SQLite file persists `created_at_wall` on every record written under a wired
   wall-clock; an existing pre-R92 SQLite file migrates in place, preserves all
   existing rows readable with `created_at_wall=None`, and accepts new writes with the
   new field populated.
6. `assemble_runtime(wall_clock=SystemWallClock())` and
   `assemble_runtime(profile=RuntimeProfile(wall_clock=SystemWallClock()))` produce
   equivalent threading; passing both raises `CompositionError`.
   `assemble_production_runtime()` wires `SystemWallClock` by default and remains the
   stable production seam.
7. The default `assemble_runtime()` (no `wall_clock` kwarg, no profile field) is
   byte-for-byte unchanged: every existing R83 long-run trace, every R88/R89/R90
   evaluation, and every existing test passes without modification.
8. The R91 present-field probe set (`scripts/r91_probes/`) continues to pass; a new
   `scripts/r92_probes/01_with_wall_clock.json` real-LLM probe verifies the model
   correctly uses the new `last input: 4.3s ago` evidence in dialog (judge notes
   recorded under git-ignored `logs/`).
9. The full network-free test suite is green; the composition owner-boundary guard,
   the no-ad-hoc-logging guard, and the existing 1019 tests continue passing.
10. `docs/requirements/index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps,
    `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, and
    `ROADMAP.zh-CN.md` are synced in this same change set.
