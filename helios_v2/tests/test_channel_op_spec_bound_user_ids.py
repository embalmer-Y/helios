# -*- coding: utf-8 -*-
"""R93 Phase 2: ChannelOpSpec.bound_user_ids contract tests.

Owner: channel driver subsystem.

These tests exercise the new `bound_user_ids` field on `ChannelOpSpec` and its
threading through the composition provider snapshot. The planner's
`_select_channel` reads `op_specs[op].bound_user_ids` off the snapshot to
filter candidates by the proposal's `target_user_id`; a non-wildcard driver
declares the specific users it serves, an empty frozenset is the wildcard.

Cases covered:

- `ChannelOpSpec` carries the new field.
- Default `frozenset()` (wildcard).
- Non-empty set honored.
- `__post_init__` validation: non-string / empty raises `ChannelError`.
- The CLI driver sets `frozenset()` on its `reply_message` op spec.
- The composition provider threads the field through the snapshot.
- A non-CLI driver may declare a non-wildcard set.
"""

from helios_v2.channel.contracts import (
    ChannelDriverDescriptor,
    ChannelError,
    ChannelOpSpec,
)
from helios_v2.channel.drivers.cli import (
    CLI_DRIVER_ID,
    CLI_OUTPUT_OP,
    CliDriverConfig,
    _cli_descriptor,
)
from helios_v2.composition.bridges import ChannelSubsystemStateProvider


# ---------------------------------------------------------------------------
# ChannelOpSpec itself
# ---------------------------------------------------------------------------


def test_op_spec_default_bound_user_ids_is_empty_frozenset() -> None:
    """Default `bound_user_ids` is the wildcard `frozenset()`."""

    spec = ChannelOpSpec(op_name="op")
    assert spec.bound_user_ids == frozenset()


def test_op_spec_non_empty_bound_user_ids_honored() -> None:
    """A non-empty `bound_user_ids` is preserved as a frozenset."""

    spec = ChannelOpSpec(
        op_name="op",
        bound_user_ids=frozenset({"user:001", "user:002"}),
    )
    assert spec.bound_user_ids == frozenset({"user:001", "user:002"})


def test_op_spec_rejects_non_string_in_bound_user_ids() -> None:
    """A non-string entry in `bound_user_ids` raises `ChannelError`."""

    with_error = None
    try:
        ChannelOpSpec(op_name="op", bound_user_ids=frozenset({42}))  # type: ignore[arg-type]
    except ChannelError as exc:
        with_error = exc
    assert with_error is not None
    assert "bound_user_ids" in str(with_error)


def test_op_spec_rejects_empty_string_in_bound_user_ids() -> None:
    """An empty-string entry in `bound_user_ids` raises `ChannelError`."""

    with_error = None
    try:
        ChannelOpSpec(op_name="op", bound_user_ids=frozenset({""}))
    except ChannelError as exc:
        with_error = exc
    assert with_error is not None
    assert "bound_user_ids" in str(with_error)


# ---------------------------------------------------------------------------
# CLI driver descriptor
# ---------------------------------------------------------------------------


def test_cli_driver_descriptor_reply_message_has_wildcard_bound_user_ids() -> None:
    """The CLI driver's `reply_message` op spec sets `bound_user_ids=frozenset()`.

    The CLI driver is the wildcard operator-facing channel: it serves any user
    id, so its op spec declares an empty frozenset.
    """

    descriptor = _cli_descriptor(CliDriverConfig())
    specs_by_op = {spec.op_name: spec for spec in descriptor.output_op_specs}
    assert CLI_OUTPUT_OP in specs_by_op
    cli_reply_spec = specs_by_op[CLI_OUTPUT_OP]
    assert cli_reply_spec.bound_user_ids == frozenset()
    assert cli_reply_spec.bound_user_ids == frozenset()  # wildcard, empty == serves everyone


# ---------------------------------------------------------------------------
# Composition provider threads the field through the snapshot
# ---------------------------------------------------------------------------


def test_composition_provider_threads_bound_user_ids_into_snapshot() -> None:
    """The composition provider projects `bound_user_ids` into `op_specs[op]`."""

    # Build a single-driver subsystem (real driver protocol is not required for
    # the snapshot projection: the provider consumes `subsystem.channel_state_snapshot()`
    # which returns a `ChannelStateSnapshot` carrying `descriptors`).
    from helios_v2.channel.contracts import ChannelStateSnapshot

    driver_descriptor = _cli_descriptor(CliDriverConfig())
    # Add a non-wildcard op spec on a second descriptor (a hypothetical "telegram" driver
    # for the multi-driver routing case) to exercise the non-empty path.
    telegram_descriptor = ChannelDriverDescriptor(
        driver_id="telegram",
        display_name="Telegram",
        directions=("outbound",),
        input_packet_types=("text",),
        output_ops=("reply_message",),
        output_op_specs=(
            ChannelOpSpec(
                op_name="reply_message",
                required_params=("outbound_text", "target_user_id"),
                user_visible=True,
                effect_class="external_world",
                risk_class="unrestricted",
                bound_user_ids=frozenset({"user:telegram-only"}),
            ),
        ),
    )

    fake_subsystem = _FakeSubsystem(
        state=ChannelStateSnapshot(
            descriptors=(driver_descriptor, telegram_descriptor),
            statuses=(),
        )
    )

    provider = ChannelSubsystemStateProvider(subsystem=fake_subsystem)
    snapshot = provider.channel_descriptor_snapshot()

    # CLI: wildcard.
    cli_specs = snapshot["cli"]["op_specs"]["reply_message"]
    assert cli_specs["bound_user_ids"] == ()

    # Telegram: non-wildcard.
    tg_specs = snapshot["telegram"]["op_specs"]["reply_message"]
    assert tg_specs["bound_user_ids"] == ("user:telegram-only",)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeSubsystem:
    """Minimal stand-in for the channel subsystem used by the provider test."""

    def __init__(self, state) -> None:
        self._state = state

    def channel_state_snapshot(self):
        return self._state
