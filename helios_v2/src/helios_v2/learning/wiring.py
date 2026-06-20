"""R-PROTO-LEARN.P-TEMPORAL — P5 mandatory wiring helpers.

Bridges the existing 15 sidecar P5 learners (in `helios_v2/learning/`)
with the canonical cognitive owners (in `helios_v2/{neuromodulation,
autonomy, feeling, ...}`).

The wiring protocol:

  1. Each canonical owner declares a `p5_parameter_mapping: ClassVar[
     dict[str, str]]` mapping each hardcoded field name to a
     `LearnedParameterCategory` literal (e.g. `alpha_phasic ->
     decay_speed_persistence`).
  2. The owner implements `apply_p5_policy(snapshot: _LearningSnapshot) ->
     None` which reads `snapshot.policy_output[i]` (where `i` is the
     category's index in the owner's category list) and overrides the
     mapped field via `setattr`, clipped to the field's declared range.
  3. Composition (or a test) calls `wire_learner_to_owner(learner,
     owner)` to bind them. After binding, each tick the composition
     calls `learner.update(...)` then `owner.apply_p5_policy(snapshot)`.

Wire-off: if `wire_learner_to_owner` is never called, the owner uses its
hardcoded defaults byte-for-byte (R-PROTO-LEARN.6 no-fallback philosophy).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .contracts import _LearningSnapshot


class P5WiringError(RuntimeError):
    """R-PROTO-LEARN.P-TEMPORAL — wiring protocol failure.

    Hard-stop error raised when a canonical owner's
    `p5_parameter_mapping` references an unknown field or unknown
    `LearnedParameterCategory`. There is no degraded path: an invalid
    mapping would silently misroute the policy output and corrupt the
    owner's behavior; raising is the only safe option.
    """


@runtime_checkable
class P5WiredOwner(Protocol):
    """R-PROTO-LEARN.P-TEMPORAL — canonical owner side of the wiring protocol.

    A canonical owner that opts into P5 wiring implements:

    - `p5_parameter_mapping: ClassVar[dict[str, str]]` mapping each
      hardcoded field name (str) to a `LearnedParameterCategory` literal (str).
    - `_p5_learner_binding: LearnerABC | None` (set by
      `wire_learner_to_owner`).
    - `apply_p5_policy(snapshot: _LearningSnapshot) -> None` consuming
      the snapshot's `policy_output` to override the mapped fields.
    """

    p5_parameter_mapping: dict[str, str]

    def apply_p5_policy(self, snapshot: _LearningSnapshot) -> None: ...


def get_p5_categories(owner: Any) -> tuple[str, ...]:
    """Return the sorted `LearnedParameterCategory` literals an owner covers.

    Reads `p5_parameter_mapping.values()` and dedupes into a stable
    sorted tuple. The order is the wire-binding index: i-th element is
    the index into `snapshot.policy_output` for fields mapped to that
    category.
    """

    mapping = getattr(owner, "p5_parameter_mapping", None)
    if not isinstance(mapping, dict) or not mapping:
        return ()
    return tuple(sorted({category for category in mapping.values()}))


def wire_learner_to_owner(learner: Any, owner: Any) -> None:
    """R-PROTO-LEARN.P-TEMPORAL — bind a learner to a canonical owner.

    Validates:
    - `learner.output_dim >= len(get_p5_categories(owner))` (learner
      has enough output dims to cover every category).
    - `owner.p5_parameter_mapping` references valid fields (via duck-typed
      `dataclasses.fields()` lookup or attribute existence).

    Sets `owner._p5_learner_binding = learner`. Idempotent: re-wiring
    replaces the binding.
    """

    if not hasattr(learner, "update") or not hasattr(learner, "output_dim"):
        raise P5WiringError(
            f"learner {type(learner).__name__} is not a LearnerABC "
            "(missing update() / output_dim)"
        )
    if not hasattr(owner, "apply_p5_policy"):
        raise P5WiringError(
            f"owner {type(owner).__name__} does not implement "
            "apply_p5_policy (not a P5WiredOwner)"
        )
    categories = get_p5_categories(owner)
    if not categories:
        raise P5WiringError(
            f"owner {type(owner).__name__} has empty p5_parameter_mapping"
        )
    if learner.output_dim < len(categories):
        raise P5WiringError(
            f"learner {type(learner).__name__}.output_dim="
            f"{learner.output_dim} < {len(categories)} categories required "
            f"by {type(owner).__name__}: {categories}"
        )
    # Validate every mapped field exists on the owner.
    mapping = owner.p5_parameter_mapping
    for field_name in mapping.keys():
        if not hasattr(owner, field_name):
            raise P5WiringError(
                f"p5_parameter_mapping references unknown field "
                f"'{field_name}' on {type(owner).__name__}"
            )
    owner._p5_learner_binding = learner


def unwire_learner_from_owner(owner: Any) -> None:
    """R-PROTO-LEARN.P-TEMPORAL — clear the learner binding (legacy path)."""

    if hasattr(owner, "_p5_learner_binding"):
        owner._p5_learner_binding = None


def apply_p5_policy_default(
    owner: Any,
    snapshot: _LearningSnapshot,
    *,
    field_ranges: dict[str, tuple[float, float]] | None = None,
) -> None:
    """R-PROTO-LEARN.P-TEMPORAL — default apply_p5_policy implementation.

    Walks the owner's `p5_parameter_mapping`, looks up each category's
    index in `get_p5_categories(owner)`, reads
    `snapshot.policy_output[index]`, clips to the field's declared range
    (if provided in `field_ranges`, otherwise to [0, 1]), and `setattr`s
    the field on the owner.

    Canonical owners that need custom routing (e.g. coupling gain
    rebalancing across multiple categories) override this method; the
    default implementation is the safe 1-to-1 mapping.

    Args:
        owner: canonical owner instance.
        snapshot: learner tick snapshot.
        field_ranges: optional per-field (min, max) range overrides.
            Defaults to (0.0, 1.0) per P5 normalized output.
    """

    categories = get_p5_categories(owner)
    if not categories:
        return
    category_index = {category: i for i, category in enumerate(categories)}
    for field_name, category in owner.p5_parameter_mapping.items():
        idx = category_index[category]
        if idx >= len(snapshot.policy_output):
            raise P5WiringError(
                f"snapshot.policy_output too short for category '{category}' "
                f"(idx={idx}, len={len(snapshot.policy_output)})"
            )
        value = snapshot.policy_output[idx]
        lo, hi = (0.0, 1.0)
        if field_ranges is not None and field_name in field_ranges:
            lo, hi = field_ranges[field_name]
        value = max(lo, min(hi, value))
        setattr(owner, field_name, value)
