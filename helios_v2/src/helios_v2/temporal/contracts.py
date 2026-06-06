"""Owner: temporal pacing and rest-state source.

Owns:
- the bounded temporal/rest-state gate-input sample contract
- the injected temporal-source protocol boundary (sample + cross-tick advance)

Does not own:
- the thought-gate decision or its weights (owned by `09` thought gating)
- salience scoring (`03`), feeling (`05`), or neuromodulator state (`04`)
- sensory normalization (`02`)

This owner reports two real situational facts the `09` gate consumes: whether the default-mode
network is engaged (rest vs external task) and how much spontaneous-thought pacing has accumulated
from elapsed rest. It interprets nothing and makes no cognitive decision; the `09` owner keeps the
gate weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class TemporalError(RuntimeError):
    """Hard-stop error raised when temporal-source invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise TemporalError(f"{name} must be within [0.0, 1.0]")


@dataclass(frozen=True)
class TemporalPacingSample:
    """Owner: temporal pacing and rest-state source.

    Purpose:
        One bounded snapshot of the runtime's temporal/rest-state gate inputs for one tick.

        `temporal_signal` is the spontaneous-thought pacing accumulated from elapsed rest (`[0,1]`):
        higher means the system has been at rest longer without thinking, so it is more inclined to
        start an internally-generated thought. `dmn_available` reports whether the default-mode
        network is engaged: `True` at rest (no external task), `False` when an external stimulus is
        present (the task-positive network suppresses the DMN).

    Failure semantics:
        Construction raises `TemporalError` if `temporal_signal` is outside `[0.0, 1.0]`.

    Notes:
        This is a situational fact, not a cognitive decision. The `09` gate owner keeps the weights
        that turn it into a gate-score contribution.
    """

    temporal_signal: float
    dmn_available: bool

    def __post_init__(self) -> None:
        _validate_unit_interval("TemporalPacingSample.temporal_signal", self.temporal_signal)


@runtime_checkable
class TemporalSource(Protocol):
    """Owner: temporal pacing and rest-state source.

    Purpose:
        The injected boundary behind which a concrete temporal/rest-state source is provided, so
        the runtime never hard-depends on a specific clock or rest-state backend.

    Notes:
        `sample` reports the current tick's pacing + DMN fact from the source's own cross-tick
        elapsed state plus the per-tick external-stimulus fact it is given. `observe_tick` advances
        that cross-tick state after the tick from the published gate decision. Implementations must
        be cheap, synchronous, network-free, and deterministic for a fixed observation sequence.
    """

    def sample(self, external_stimulus_present: bool) -> TemporalPacingSample:
        """Owner: temporal pacing and rest-state source.

        Purpose:
            Produce the current tick's bounded temporal/rest-state sample.

        Inputs:
            `external_stimulus_present` - whether the current tick carries an external (non-internal)
            stimulus, supplied by composition from the `02` batch.

        Returns:
            One `TemporalPacingSample` (`temporal_signal` from the source's elapsed-rest state,
            `dmn_available` from the rest fact).

        Raises:
            May raise `TemporalError` on an internal invariant violation; it never fabricates a fact.

        Notes:
            Reads the source's own cross-tick state; it does not advance it (use `observe_tick`).
        """

        ...

    def observe_tick(self, fired: bool) -> None:
        """Owner: temporal pacing and rest-state source.

        Purpose:
            Advance the source's cross-tick elapsed-rest state after one completed tick.

        Inputs:
            `fired` - whether the `09` gate fired a thought this tick (from the published decision).

        Returns:
            None.

        Notes:
            A fire resets the accumulated rest (the system just thought); a no-fire advances it
            (the system stayed at rest). The source owns this state; composition only observes the
            published decision and calls this method.
        """

        ...
