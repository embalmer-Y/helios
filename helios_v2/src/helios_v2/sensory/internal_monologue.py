"""Owner: sensory ingress — internal-monologue second-order stimulus source.

Provides the `InternalMonologueSource`, a sensory-source owner that emits the runtime's
self-produced internal-monologue content (the "self-talk" loop — R80) as bounded `RawSignal`s
into sensory ingress through the existing `SensorySource` protocol. This closes the
second-order stimulus path: an active thought the runtime itself produced in a prior tick
re-enters the `02 -> 03 -> 04` pipeline as a stimulus on the next tick, so the rumination
loop becomes a real input source rather than a prompt-time suggestion.

This owner is a peripheral afferent producer. It reports the runtime's self-generated
internal-monologue state as bounded facts; it holds no feeling, salience, or cognitive
policy, and it imports no feeling, appraisal, or neuromodulation owner. Sensory ingress
(`02`) owns normalization; the `03` appraisal owner owns how (and whether) these signals
shape the coarse salience dimensions.

The provider is the single seam where R80 connects to the LLM's self-talk output. R80
ships a `monologue_provider` argument (a `Callable[[], Mapping[str, object] | None]`)
that R81 wires to `RuntimeHandle._carry_internal_monologue` (per R79-parent task.md T7);
R80's tests inject a `StaticMonologueProvider` directly.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from helios_v2.sensory import RawSignal, SensorySource

#: Owner name for the internal-monologue source. Stable across R80 / R81 / R82.
INTERNAL_MONOLOGUE_SOURCE_NAME: str = "internal_monologue"

#: Owner name for the internal-monologue signal_id when a monologue is active.
INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID: str = "internal_monologue:active"

#: Owner name for the channel field on the `RawSignal`. Distinct from
#: "interoception" (R50) and the external channels; it tags the self-talk afferent.
INTERNAL_MONOLOGUE_CHANNEL: str = "self_talk"

#: Maximum bytes for the bounded JSON projection of the provider's monologue dict. The
#: runtime never lets a single self-talk payload grow unbounded into sensory ingress.
_INTERNAL_MONOLOGUE_CONTENT_MAX_BYTES: int = 1024


def _bounded_json(mapping: Mapping[str, object]) -> str:
    """Project a monologue mapping to a bounded JSON string.

    Owner: sensory ingress — internal-monologue source helper.

    Purpose:
        Give the source's `RawSignal.content` a deterministic, bounded string projection
        of the provider's mapping, so ingress does not have to interpret the dict and
        downstream consumers can read a stable surface.

    Inputs:
        A `Mapping[str, object]` (the provider's monologue dict).

    Returns:
        A JSON string up to `_INTERNAL_MONOLOGUE_CONTENT_MAX_BYTES` bytes. When the
        projection would exceed the bound, the projection is truncated by removing
        keys (in insertion order) until it fits; the result is suffixed with
        `"...<truncated>"` to flag the loss.

    Raises:
        `TypeError` propagates from `json.dumps` if the mapping contains a non-JSON-
        serializable value. The caller is expected to project to JSON-safe primitives
        before injection.
    """

    safe = {str(key): _coerce_jsonable(value) for key, value in mapping.items()}
    projection = json.dumps(safe, ensure_ascii=False, sort_keys=True)
    encoded = projection.encode("utf-8")
    if len(encoded) <= _INTERNAL_MONOLOGUE_CONTENT_MAX_BYTES:
        return projection
    # Bounded truncation: drop trailing keys until the projection fits, then mark.
    keys = list(safe.keys())
    while keys and len(encoded) > _INTERNAL_MONOLOGUE_CONTENT_MAX_BYTES:
        keys.pop()
        trimmed = {key: safe[key] for key in keys}
        projection = json.dumps(trimmed, ensure_ascii=False, sort_keys=True)
        encoded = projection.encode("utf-8")
    suffix = "...<truncated>"
    encoded = encoded[: _INTERNAL_MONOLOGUE_CONTENT_MAX_BYTES - len(suffix.encode("utf-8"))] + suffix.encode("utf-8")
    return encoded.decode("utf-8", errors="replace")


def _coerce_jsonable(value: object) -> object:
    """Coerce a monologue value to a JSON-safe primitive.

    Owner: sensory ingress — internal-monologue source helper.

    Purpose:
        Keep the bounded JSON projection stable by enforcing JSON-safe primitives.
        Tuples and nested mappings are preserved; arbitrary objects are stringified.

    Inputs:
        Any Python object.

    Returns:
        A JSON-safe primitive (`str`, `int`, `float`, `bool`, `None`, `list`, `dict`).
    """

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_coerce_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_coerce_jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _coerce_jsonable(item) for key, item in value.items()}
    return str(value)


@dataclass(frozen=True)
class InternalMonologueSource:
    """Owner: sensory ingress — internal-monologue second-order stimulus source.

    Purpose:
        Emit the runtime's self-produced internal-monologue content as a bounded
        `RawSignal` into sensory ingress, closing the second-order stimulus path
        (the rumination / self-talk loop).

    Failure semantics:
        Propagates an outright `monologue_provider()` exception as a hard stop —
        a failing provider is a real signal-source failure and must not be silently
        absorbed. A `None` or empty-dict return means "no active monologue" and the
        source emits an empty tuple (zero stimuli that tick).

    Notes:
        Owns only the provider-to-signal projection: at most one
        `signal_type="internal_monologue"` `RawSignal` per call, with provenance
        `source_name="internal_monologue"` and `signal_id="internal_monologue:active"`.
        The numeric content rides `metadata`; the `content` string is a bounded
        JSON projection of the provider's dict (truncated at
        `_INTERNAL_MONOLOGUE_CONTENT_MAX_BYTES`). Holds no feeling, salience, or
        cognitive policy and imports no feeling / appraisal / neuromodulation owner.
    """

    monologue_provider: Callable[[], Mapping[str, object] | None]
    source_name_value: str = INTERNAL_MONOLOGUE_SOURCE_NAME

    @property
    def source_name(self) -> str:
        """Stable source owner name consumed by sensory ingress registration."""

        return self.source_name_value

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        """Owner: sensory ingress.

        Purpose:
            Sample the runtime's current internal-monologue state and emit zero or one
            bounded `RawSignal` for the active monologue.

        Inputs:
            None.

        Returns:
            An immutable tuple of `RawSignal` values. The tuple is empty when the
            provider returns `None` or an empty mapping. Otherwise it is a one-element
            tuple containing one `RawSignal` with `signal_type="internal_monologue"`,
            `channel="self_talk"`, and `required=False` (idle ticks contribute zero
            stimuli rather than blocking batch publication).

        Raises:
            Propagates an outright `monologue_provider()` exception. A `None` or
            empty-dict return is a defined no-monologue state, not an error.
        """

        monologue = self.monologue_provider()
        if not monologue:
            return ()
        return (
            RawSignal(
                signal_id=INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID,
                source_name=self.source_name_value,
                signal_type="internal_monologue",
                content=_bounded_json(monologue),
                channel=INTERNAL_MONOLOGUE_CHANNEL,
                metadata={
                    "monologue_keys": tuple(sorted(str(key) for key in monologue.keys())),
                },
                required=False,
            ),
        )


__all__ = [
    "INTERNAL_MONOLOGUE_ACTIVE_SIGNAL_ID",
    "INTERNAL_MONOLOGUE_CHANNEL",
    "INTERNAL_MONOLOGUE_SOURCE_NAME",
    "InternalMonologueSource",
]
