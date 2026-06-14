# Requirement 92 - Wall-Clock Real Timestamps — Design

## 1. Design Overview

R92 introduces one small infrastructure capability owner (`helios_v2.wall_clock`) and
threads its single fact — a real wall-time reading — into three additive consumption
points:

1. one `tick_wall_seconds` value seeded onto `RuntimeFrame` by the kernel,
2. one `received_at_wall` metadata stamp written by the CLI channel driver at
   `submit_line` time, preserved verbatim by `02` sensory normalization, and
3. one `created_at_wall` field on `PersistedExperienceRecord`, written by the existing
   composition `_persist_experience` / `_persist_memory` carry seam.

The R91 present-field bridge gets one extra clause shaped `last input: X.Xs ago`
(real elapsed seconds), kept side-by-side with the existing `pacing: <signal>` clause
(unitless rest pacing). The wall-clock is fully optional through `RuntimeProfile.wall_clock`;
when not wired, every consumption point holds an honest absent state and the default
runtime is byte-for-byte unchanged.

The owner ships two implementations: `SystemWallClock` (calls `time.time()`) for
production and `FixedWallClock` (deterministic) for every network-free test that
exercises wall-time behavior. The standard production assembly
(`assemble_production_runtime`) wires `SystemWallClock` by default; tests and the R83
long-run harness inject `FixedWallClock` so behavior remains reproducible.

## 2. Current State and Gap

- `helios_v2.runtime.kernel.RuntimeKernel.tick()` already imports `time` and calls
  `time.perf_counter()` to measure stage durations for `21` observability. That value
  is monotonic-clock-only and never exposed as a runtime fact; it is unrelated to
  wall-time and must remain so.
- `helios_v2.runtime.contracts.RuntimeFrame` carries `tick_id` and `stage_results`
  only. There is no field through which a wall-time fact can reach a stage owner.
- `helios_v2.channel.drivers.cli.CliChannelDriver.submit_line()` does not stamp arrival
  time. `drain_inbound` constructs the `InboundPacket` with metadata keys
  `user_label` / `session_label` only.
- `02` sensory ingress already preserves the `RawSignal.metadata` mapping verbatim
  onto `Stimulus.metadata` (this is the same seam used to carry `channel_qos`); a new
  reserved metadata key flows through automatically.
- `helios_v2.persistence.contracts.PersistedExperienceRecord` carries `tick_id`
  (`int | None`) but no wall-time. SQLite `engine.py` already supports an additive
  PRAGMA-guarded `ALTER TABLE` migration (the precedent is the `record_kind` column
  added by R45).
- `RuntimeProfile` already aggregates ten capability seams (R58); adding one more is a
  drop-in slot. `assemble_production_runtime()` (R82) is the natural place to wire
  `SystemWallClock` by default.
- The R91 `_present_field_summary_text` already orders three clauses (stimuli, focal,
  pacing) and joins them with `; `. It already accepts `frame` (which will gain
  `tick_wall_seconds`) and the optional `temporal_source`. Adding the new clause is a
  bounded edit inside this helper.

## 3. Target Architecture

### 3.1 Owner package (`helios_v2.wall_clock`)

```text
src/helios_v2/wall_clock/
  __init__.py     # exports
  contracts.py    # WallClockError, WallClockReading, WallClock protocol
  engine.py       # SystemWallClock, FixedWallClock
```

The owner imports nothing from any cognitive owner; only the standard library `time`
module (lazily, inside `SystemWallClock.now`) and `dataclasses`/`typing`.

### 3.2 Capability seam threading

```text
RuntimeProfile.wall_clock: WallClock | None = None
        │
        ├── kernel.RuntimeKernel(wall_clock=...)          # frame seeding
        ├── CliChannelDriver(wall_clock=...)              # submit_line stamping
        └── RuntimeHandle(wall_clock=...)                 # _persist_* read seam
```

Same `WallClock` instance is constructed at most once per assembly and threaded into
all three consumers. `FixedWallClock` semantics (deterministic sequence) depend on
exactly one instance.

### 3.3 R91 present-field rendering extension

The clause join order remains: `stimuli; focal; <time>`. The `<time>` slot now carries
zero, one, or two clauses:

- `last input: X.Xs ago` — when at least one rendered stimulus has `received_at_wall`
  in metadata AND `frame.tick_wall_seconds is not None`. The "X.X" is one decimal,
  monotonic non-negative (NTP-rewind clamp).
- `pacing: <signal>` — exactly the existing R91 clause, unchanged.

When both are present they are emitted in this order: `last input: 4.3s ago; pacing: 0.6`.
When neither is present, no time clause is emitted.

The rendering uses the **earliest** rendered stimulus's `received_at_wall` (the one
the human said first) so the LLM reads "the message arrived 4.3s ago", not "the most
recent metadata stamp". Stimuli without a `received_at_wall` are ignored when picking
the elapsed source; if all rendered stimuli lack the stamp, the elapsed clause is
omitted.

### 3.4 Persistence write path

The existing `RuntimeHandle._persist_experience` (and `_persist_memory`) carry seam
already constructs a `PersistedExperienceRecord` from owner-published fields after
each tick. R92 adds one read of `frame.tick_wall_seconds` for the just-completed tick
and writes it into `created_at_wall`. When the runtime has no wall-clock,
`tick_wall_seconds` is `None` and `created_at_wall` is `None` (honest absence).

The SQLite migration runs once at backend init (mirroring R45):

```text
PRAGMA table_info(experience_records)
    -> if column 'created_at_wall' is missing:
        ALTER TABLE experience_records ADD COLUMN created_at_wall REAL  -- nullable
```

Old rows read back with `created_at_wall=None`; new rows carry the value.

The semantic recall path (`search_similar`) and the recency path are unchanged: they
still rank by cosine / recency and pass `created_at_wall` through verbatim. No owner
in this slice consumes the field.

### 3.5 Failure modes

- `WallClockReading(wall_seconds=NaN)` — raises `WallClockError` at construction.
- `WallClockReading(wall_seconds=-1.0)` — raises `WallClockError` at construction.
- `SystemWallClock.now()` is a thin wrapper; it never catches exceptions from
  `time.time()`. A platform that returns a structurally invalid value would surface
  through `WallClockReading.__post_init__`.
- `FixedWallClock` exhausted: `now()` after the seeded sequence is exhausted raises
  `WallClockError` (no silent reuse of the last value); tests opt-in to `advance=` to
  avoid this.
- NTP rewind during a real run: `last input: <neg>s ago` clamps to `0.0s` at the
  rendering boundary only. The persisted `received_at_wall` and `created_at_wall`
  remain whatever the clock returned (raw fact); anomaly correction in storage is
  out of scope.
- Profile + loose-kwarg overlap: `RuntimeProfile(wall_clock=...)` plus
  `assemble_runtime(wall_clock=...)` raises `CompositionError` (existing R58
  `_resolve_profile` rule extended with the new field name).

## 4. Data Structures

### 4.1 `WallClockReading` (new)

```python
@dataclass(frozen=True)
class WallClockReading:
    wall_seconds: float                 # finite, non-negative
    clock_id: str | None = None         # opaque provenance, never interpreted

    def __post_init__(self) -> None:
        if math.isnan(self.wall_seconds) or math.isinf(self.wall_seconds):
            raise WallClockError(...)
        if self.wall_seconds < 0.0:
            raise WallClockError(...)
```

### 4.2 `WallClock` protocol (new)

```python
@runtime_checkable
class WallClock(Protocol):
    def now(self) -> WallClockReading: ...
```

### 4.3 `SystemWallClock` and `FixedWallClock` (new)

```python
@dataclass
class SystemWallClock:
    clock_id: str = "system"

    def now(self) -> WallClockReading:
        return WallClockReading(wall_seconds=time.time(), clock_id=self.clock_id)


@dataclass
class FixedWallClock:
    seconds: float = 0.0
    advance: float = 0.0           # auto-advance per call (0.0 = constant)
    sequence: tuple[float, ...] | None = None  # explicit override
    clock_id: str = "fixed"
    _step: int = field(default=0, init=False, repr=False)

    def now(self) -> WallClockReading: ...
    def manual_advance(self, delta: float) -> None: ...   # explicit step API
```

### 4.4 `RuntimeFrame` additive field

```python
@dataclass(frozen=True)
class RuntimeFrame:
    tick_id: int
    stage_results: Mapping[str, object] | None = None
    tick_wall_seconds: float | None = None      # NEW (additive)
```

### 4.5 `Stimulus.metadata` reserved key

A new reserved metadata key string is added to `helios_v2.sensory.contracts` (or
re-exported from `helios_v2.wall_clock` to avoid cross-owner imports — see §8):

```python
RECEIVED_AT_WALL_METADATA_KEY: Final[str] = "received_at_wall"
```

The key's value is a `float` (seconds). Absence of the key is equally valid (honest
absence).

### 4.6 `PersistedExperienceRecord` additive field

```python
@dataclass(frozen=True)
class PersistedExperienceRecord:
    record_id: str
    tick_id: int | None
    ...existing fields...
    created_at_wall: float | None = None   # NEW (additive, optional)
```

### 4.7 `RuntimeProfile` additive field

```python
@dataclass(frozen=True)
class RuntimeProfile:
    ...existing fields...
    wall_clock: WallClock | None = None    # NEW (additive)
```

`_RUNTIME_PROFILE_FIELD_NAMES` adds `"wall_clock"`. `assemble_runtime` adds the
matching loose-kwarg `wall_clock`.

## 5. Module Changes

### 5.1 `helios_v2.wall_clock` (new)

- `contracts.py`: `WallClockError`, `WallClockReading`, `WallClock` protocol,
  `RECEIVED_AT_WALL_METADATA_KEY`.
- `engine.py`: `SystemWallClock`, `FixedWallClock` (with both auto-`advance` and
  explicit `manual_advance`).
- `__init__.py`: public exports.

### 5.2 `helios_v2.runtime.contracts`

Add additive `tick_wall_seconds: float | None = None` on `RuntimeFrame`. No other
field or validation changes. The dataclass remains frozen.

### 5.3 `helios_v2.runtime.kernel`

`RuntimeKernel.__init__` accepts an optional `wall_clock: WallClock | None = None`.
In `tick()`, just before the stage loop:

```python
tick_wall_seconds: float | None = None
if self.wall_clock is not None:
    tick_wall_seconds = self.wall_clock.now().wall_seconds
```

Every `RuntimeFrame(tick_id=next_tick_id, stage_results=stage_results,
tick_wall_seconds=tick_wall_seconds)` constructed within that tick uses the same
`tick_wall_seconds`. The kernel imports `WallClock` from `helios_v2.wall_clock` at the
top.

### 5.4 `helios_v2.channel.drivers.cli.CliChannelDriver`

`__init__` accepts an optional `wall_clock: WallClock | None = None`. The internal
`_backlog` is changed from `deque[str]` to `deque[tuple[str, float | None]]` so the
arrival timestamp is recorded at `submit_line` time:

```python
def submit_line(self, text: str) -> bool:
    ...
    received_at = self.wall_clock.now().wall_seconds if self.wall_clock else None
    self._backlog.append((text, received_at))
    ...
```

`drain_inbound` reads the tuple back and adds `received_at_wall` to the packet's
metadata only when present:

```python
metadata = {
    "user_label": self.config.user_label,
    "session_label": self.config.session_label,
}
if received_at is not None:
    metadata[RECEIVED_AT_WALL_METADATA_KEY] = received_at
```

### 5.5 `helios_v2.composition.runtime_assembly`

- Add `wall_clock: WallClock | None = None` to `RuntimeProfile`.
- Add `"wall_clock"` to `_RUNTIME_PROFILE_FIELD_NAMES`.
- Add the `wall_clock=_UNSET` loose kwarg to `assemble_runtime` and the same to
  `assemble_production_runtime` (the latter defaults to `SystemWallClock()` when
  caller passes nothing).
- Thread one resolved `wall_clock` instance into:
  1. `RuntimeKernel(wall_clock=wall_clock, ...)`,
  2. `CliChannelDriver(wall_clock=wall_clock, ...)` when `channel_cli` is wired,
  3. `RuntimeHandle(wall_clock=wall_clock, ...)` for the persistence carry seam.

`RuntimeHandle._persist_experience` / `_persist_memory` already receive the just-
completed tick's `RuntimeTickResult`; the kernel must additionally make
`tick_wall_seconds` reachable here. Two options:

- **(a)** add `tick_wall_seconds: float | None` to `RuntimeTickResult` (additive).
- **(b)** read it from the seeded frames inside the result dict (already a
  `Mapping[str, object]`).

We pick **(a)** — it is the cleanest contract: `RuntimeTickResult` already carries
`tick_id`; adding `tick_wall_seconds` keeps it a coherent per-tick fact bundle.

### 5.6 `helios_v2.composition.bridges`

- Extend `_present_field_summary_text(frame, temporal_source)`. New logic:

```python
elapsed = _present_field_elapsed_clause(frame)  # may return None
if elapsed is not None:
    parts.append(elapsed)                       # "last input: 4.3s ago"
if temporal_source is not None:
    parts.append(f"pacing: {round(...)}")       # existing clause unchanged
```

- Add `_present_field_elapsed_clause(frame)`: walk the same external-stimulus subset
  the existing `_present_field_stimuli_clause` already filters; pick the earliest
  `received_at_wall`; compare to `frame.tick_wall_seconds`; return None when either
  side is absent; clamp negative to 0.0; format `f"last input: {ago:.1f}s ago"`.

- Persistence carry seam: `RuntimeHandle._persist_experience` reads
  `result.tick_wall_seconds` and writes it into the new
  `PersistedExperienceRecord.created_at_wall`.

### 5.7 `helios_v2.persistence.contracts`

Add `created_at_wall: float | None = None` to `PersistedExperienceRecord`. Update
`_replace_*` helpers (the existing record-mutation helpers) to preserve the field.

### 5.8 `helios_v2.persistence.engine`

- `SqliteExperienceStoreBackend.__init__`: extend the existing PRAGMA-guarded
  migration to add `created_at_wall REAL` when missing. Mirror R45's column-add
  pattern verbatim.
- `_row_to_record`: read the column when present, fall back to `None` when missing
  (defensive for old rows).
- `_record_to_row`: write the value as `REAL` (nullable).
- `InMemoryExperienceStoreBackend`: trivially preserves the field as part of the
  frozen dataclass; no code change beyond the contract update.

## 6. Module Changes (summary table)

| File | Change kind | Summary |
| --- | --- | --- |
| `helios_v2/wall_clock/__init__.py` | NEW | exports |
| `helios_v2/wall_clock/contracts.py` | NEW | error / reading / protocol / metadata key |
| `helios_v2/wall_clock/engine.py` | NEW | `SystemWallClock`, `FixedWallClock` |
| `helios_v2/runtime/contracts.py` | MOD additive | `RuntimeFrame.tick_wall_seconds` |
| `helios_v2/runtime/kernel.py` | MOD | inject `wall_clock`; seed frame; carry on `RuntimeTickResult` |
| `helios_v2/channel/drivers/cli.py` | MOD additive | inject `wall_clock`; stamp `submit_line` |
| `helios_v2/composition/runtime_assembly.py` | MOD additive | `RuntimeProfile.wall_clock`, threading |
| `helios_v2/composition/bridges.py` | MOD additive | `last input: X.Xs ago` clause; persistence read |
| `helios_v2/persistence/contracts.py` | MOD additive | `PersistedExperienceRecord.created_at_wall` |
| `helios_v2/persistence/engine.py` | MOD | SQLite migration; row r/w |

## 7. Migration Plan

1. **In-process migration**: every additive contract field defaults to `None` and the
   default `RuntimeProfile.wall_clock` is `None`. Existing tests, the default
   `assemble_runtime()`, and existing callers see no change.
2. **SQLite migration**: on backend init, the existing PRAGMA `table_info` check is
   extended to add the `created_at_wall` column when missing. This is one-shot and
   idempotent. Existing files migrate the first time R92 code opens them; old rows
   read back with `created_at_wall=None`.
3. **Production opt-in**: `assemble_production_runtime()` wires `SystemWallClock`
   automatically. R83 long-run harness, R88/R89/R90 evaluators, and any future
   long-run script gain real wall-time on the production assembly without any caller
   change.
4. **Test opt-in**: any test that exercises wall-time behavior injects
   `FixedWallClock`. Tests that do not exercise wall-time keep passing with the
   default `wall_clock=None` and explicitly assert `tick_wall_seconds is None` /
   `received_at_wall` absent / `created_at_wall is None` in the relevant places.

## 8. Failure Modes and Constraints

1. **Owner crossing**: `helios_v2.wall_clock` imports nothing from any cognitive
   owner. The `RECEIVED_AT_WALL_METADATA_KEY` reserved string lives in
   `helios_v2.wall_clock.contracts` (not in `helios_v2.sensory.contracts`); the CLI
   driver imports the key from there. `02` sensory continues to preserve metadata
   verbatim and remains ignorant of this owner.
2. **Multi-instance threading**: `assemble_runtime` constructs at most one
   `WallClock` instance per call; the same instance is threaded everywhere. A test
   asserts identity across the three consumers.
3. **Profile + loose-kwarg overlap**: extending `_RUNTIME_PROFILE_FIELD_NAMES`
   automatically routes `wall_clock` through the existing `_resolve_profile`
   conflict check. A test asserts `CompositionError` when both are passed.
4. **Default rollout**: every existing test that does not opt-in must remain
   byte-for-byte green; the existing 1019-test baseline is the falsifier.
5. **Composition guard**: the boundary guard test is extended to assert that no
   `time.time(` call appears in `composition/` outside the explicit
   `SystemWallClock` injection point (the kernel's existing `time.perf_counter`
   monotonic clock is unrelated and continues to be allowed).
6. **No-ad-hoc-logging guard**: this requirement adds no logging surface; the
   existing guard remains green.

## 9. Observability and Logging

No new logging mechanism. `21` observability already records `LogEvent.timestamp`
independently of this owner. Wall-clock facts travel through `RuntimeFrame`,
`Stimulus.metadata`, and `PersistedExperienceRecord` only; they are not log content.
Tests assert no new log events are emitted.

## 10. Validation Strategy

### 10.1 Network-free unit/contract tests

| File | Asserts |
| --- | --- |
| `tests/test_wall_clock_contracts.py` | `WallClockReading` rejects NaN/Inf/negative; `SystemWallClock.now()` returns finite non-negative; `FixedWallClock(seconds=10, advance=0)` returns 10 forever; `FixedWallClock(seconds=10, advance=1.0)` returns 10, 11, 12; `manual_advance` works; sequence-based variant exhausts to error |
| `tests/test_runtime_frame_wall_clock.py` | Default `RuntimeFrame` has `tick_wall_seconds=None`; with kernel + `FixedWallClock`, all stages of one tick read the same value; tick 1 reads 10.0, tick 2 reads 11.0 (advance=1) |
| `tests/test_cli_driver_wall_clock_stamp.py` | Without `wall_clock`, packet metadata has no `received_at_wall`; with `FixedWallClock`, `submit_line` at `t=10` enqueues; `drain_inbound` at later tick produces packet with `received_at_wall=10.0` (arrival, not drain); two lines with two clocks (advanced) carry their respective arrivals |
| `tests/test_present_field_wall_clock_rendering.py` | With both ends present: `last input: 3.0s ago` rendered at start of time clauses, `pacing: <signal>` follows; with one side absent: only `pacing:` clause; clock rewound (`now < received`): clamps to `0.0s ago`; over-cap is still truncated by R91 rule |
| `tests/test_persistence_wall_clock_field.py` | `PersistedExperienceRecord(created_at_wall=12.5)` round-trips through both backends; old SQLite file (without column) accepts the migration and reads old rows as `None`; new writes carry the value; semantic search and recency unchanged in ranking |
| `tests/test_assemble_runtime_wall_clock_profile.py` | `assemble_runtime(wall_clock=fc)` and `assemble_runtime(profile=RuntimeProfile(wall_clock=fc))` produce equivalent runtime; both supplied raises `CompositionError`; `assemble_production_runtime()` wires `SystemWallClock` by default; identity check that one instance reaches kernel + cli driver + handle |

### 10.2 Composition / boundary guards

- The composition owner-boundary guard test stays green (no new owner-policy strings
  fall into `composition/`).
- The no-ad-hoc-logging guard stays green (no new `print` / `logging`).

### 10.3 Real-LLM probe (per §8.2)

`scripts/r92_probes/01_with_wall_clock.json` — a probe carrying the expected enhanced
`Present field` line:

```text
Present field: cli via cli said: "..."; focal: ...; last input: 4.3s ago; pacing: 0.4
```

The probe verifies:

1. The model engages the elapsed-seconds fact ("4.3 seconds ago" / "刚刚" / "几秒前"
   in its reply or thought).
2. The model does NOT fabricate a time when the probe omits the `last input:` line
   (negative control).

Output saved to git-ignored `logs/prerun/r92_probes/`; observed PASS recorded in this
design's §10 after run. (`--strip-reasoning`, `--max-tokens >= 2048` for reasoning
models.)

### 10.4 Implementation-time smoke

After the code lands, run a short CLI dialogue with the production assembly +
`SystemWallClock` and capture the actual `11` user prompt (via the existing
`emotion_test_run.py` `--llm-log` switch). Confirm the captured prompt actually
contains `last input: <real seconds>s ago`. R91's lesson (`§11.2`) is the gold
standard: probe verifies the model end, smoke verifies the composition end; both must
pass.

### 10.5 Acceptance gate

The full network-free test suite (currently 1019 passed / 4 skipped) must reach
≥ 1019 + N (where N is the number of new R92 tests, expected ≈ 25–35) with 0
regressions; the composition owner-boundary guard and the no-ad-hoc-logging guard
remain green; both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, the boundary doc,
the comparison doc, the index, and the ROADMAP are synced in this same change set.
