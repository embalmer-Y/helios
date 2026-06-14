# -*- coding: utf-8 -*-
"""R93 Phase 2: planner-bridge `_select_channel` routing-priority tests.

Owner: planner-bridge.

These tests exercise the rewritten `FirstVersionPlannerBridgePath._select_channel`
in isolation. The new priority is `target_user` -> `preferred` -> `iteration-order`,
with `bound_user_ids` read off the composition-projected descriptor snapshot.

Cases covered:

- Iteration order when no hints are set.
- `preferred_channels` wins when no `target_user_id` is set.
- `target_user_id` filter is applied first when set.
- Wildcard driver (CLI) always passes the user filter.
- Non-wildcard driver with matching user passes.
- Non-wildcard driver with non-matching user is filtered out.
- `target_user` filter yielding an empty set falls through (fail-soft) to the
  unfiltered set, then to `preferred`, then to iteration order.
- All candidates filtered out yields `None`.
"""

from helios_v2.planner_bridge import (
    FirstVersionPlannerBridgePath,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _descriptor(
    channel_id: str,
    *,
    bound_user_ids: tuple[str, ...] = (),
    supported_ops: tuple[str, ...] = ("reply_message",),
):
    return {
        "supported_ops": supported_ops,
        "output_ops": supported_ops,
        "op_specs": {
            "reply_message": {
                "required_params": ("outbound_text", "target_user_id"),
                "user_visible": True,
                "effect_class": "external_world",
                "risk_class": "unrestricted",
                "bound_user_ids": bound_user_ids,
            },
        },
    }


def _status(*, available: bool = True, bound: bool = True, execute_now: bool = True):
    return {"available": available, "bound": bound, "execute_now": execute_now}


def _bridge_request(
    descriptors: dict,
    statuses: dict,
):
    """Build a `PlannerBridgeRequest` with the given snapshot dictionaries."""

    from helios_v2.planner_bridge import PlannerBridgeRequest

    return PlannerBridgeRequest(
        request_id="planner-bridge-request:001",
        source_externalization_result_id="externalization-result:001",
        normalized_proposal_present=True,
        behavior_snapshot={"registered": True, "reviewed": True, "minimum_score": 0.0, "proposal_score": 1.0},
        channel_descriptor_snapshot=descriptors,
        channel_status_snapshot=statuses,
        tick_id=1,
    )


def _fake_proposal(
    *,
    preferred_channels: tuple[str, ...] = (),
    target_user_id: str = "",
):
    """Build a duck-typed proposal the bridge-path can read.

    `_select_channel` only reads `proposal.preferred_channels` and
    `proposal.params["target_user_id"]`; the rest of the proposal surface is
    ignored.
    """

    class _P:
        pass

    p = _P()
    p.preferred_channels = preferred_channels
    p.params = {"target_user_id": target_user_id} if target_user_id else {}
    return p


# ---------------------------------------------------------------------------
# Iteration order (no hints)
# ---------------------------------------------------------------------------


def test_iteration_order_when_no_hints() -> None:
    """Without any hints, the bridge returns the first eligible candidate."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "alpha": _descriptor("alpha"),
            "beta": _descriptor("beta"),
        },
        statuses={"alpha": _status(), "beta": _status()},
    )
    selected = bridge._select_channel(request, "reply_message", _fake_proposal())
    assert selected == "alpha"


# ---------------------------------------------------------------------------
# preferred_channels
# ---------------------------------------------------------------------------


def test_preferred_wins_when_no_target_user() -> None:
    """With `preferred_channels` set and no `target_user_id`, the preferred driver wins."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "alpha": _descriptor("alpha"),
            "beta": _descriptor("beta"),
        },
        statuses={"alpha": _status(), "beta": _status()},
    )
    selected = bridge._select_channel(
        request,
        "reply_message",
        _fake_proposal(preferred_channels=("beta",)),
    )
    assert selected == "beta"


# ---------------------------------------------------------------------------
# target_user filter
# ---------------------------------------------------------------------------


def test_target_user_filter_wildcard_driver_passes() -> None:
    """The CLI driver (wildcard `bound_user_ids=()`) always passes the user filter."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "cli": _descriptor("cli"),  # wildcard
            "telegram": _descriptor("telegram", bound_user_ids=("user:tg",)),
        },
        statuses={"cli": _status(), "telegram": _status()},
    )
    selected = bridge._select_channel(
        request,
        "reply_message",
        _fake_proposal(target_user_id="user:cli-only"),
    )
    assert selected == "cli"


def test_target_user_filter_non_wildcard_matching_user() -> None:
    """A non-wildcard driver whose `bound_user_ids` contains the target passes."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "cli": _descriptor("cli"),  # wildcard
            "telegram": _descriptor("telegram", bound_user_ids=("user:tg",)),
        },
        statuses={"cli": _status(), "telegram": _status()},
    )
    selected = bridge._select_channel(
        request,
        "reply_message",
        _fake_proposal(target_user_id="user:tg"),
    )
    # CLI (wildcard) and Telegram (matching) both pass; iteration order -> CLI.
    assert selected == "cli"
    # But when CLI is filtered out (e.g. not in the candidate set), Telegram wins.
    request_no_cli = _bridge_request(
        descriptors={
            "telegram": _descriptor("telegram", bound_user_ids=("user:tg",)),
        },
        statuses={"telegram": _status()},
    )
    selected_no_cli = bridge._select_channel(
        request_no_cli,
        "reply_message",
        _fake_proposal(target_user_id="user:tg"),
    )
    assert selected_no_cli == "telegram"


def test_target_user_filter_non_wildcard_non_matching_user_filtered_out() -> None:
    """A non-wildcard driver whose `bound_user_ids` does NOT contain the target is filtered out."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "cli": _descriptor("cli"),  # wildcard
            "telegram": _descriptor("telegram", bound_user_ids=("user:tg",)),
        },
        statuses={"cli": _status(), "telegram": _status()},
    )
    selected = bridge._select_channel(
        request,
        "reply_message",
        _fake_proposal(target_user_id="user:not-tg"),
    )
    # Telegram filtered out; CLI (wildcard) passes.
    assert selected == "cli"


def test_target_user_filter_falls_through_when_empty() -> None:
    """When the user-serving filter is empty, the planner falls through (fail-soft).

    In the test setup, the only candidate is a non-wildcard driver that doesn't
    match the target, so the user-serving filter is empty. The planner falls
    through to the unfiltered set and returns the (still-eligible) candidate.
    """

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "telegram": _descriptor("telegram", bound_user_ids=("user:tg",)),
        },
        statuses={"telegram": _status()},
    )
    selected = bridge._select_channel(
        request,
        "reply_message",
        _fake_proposal(target_user_id="user:not-tg"),
    )
    # Telegram is filtered out by target_user; fail-soft: the planner falls
    # through to the unfiltered candidate set and returns "telegram" (the only
    # eligible driver). This is the documented "fall through, do not reject" rule.
    assert selected == "telegram"


def test_target_user_filter_intersect_with_preferred() -> None:
    """When both `target_user` and `preferred` are set, the user-serving + preferred intersection wins."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "cli": _descriptor("cli", bound_user_ids=("user:cli-only",)),  # non-wildcard
            "telegram": _descriptor("telegram", bound_user_ids=("user:cli-only",)),
        },
        statuses={"cli": _status(), "telegram": _status()},
    )
    selected = bridge._select_channel(
        request,
        "reply_message",
        _fake_proposal(target_user_id="user:cli-only", preferred_channels=("telegram",)),
    )
    # Both pass the user filter; the preferred intersection picks Telegram.
    assert selected == "telegram"


# ---------------------------------------------------------------------------
# Empty candidate set
# ---------------------------------------------------------------------------


def test_no_candidates_yields_none() -> None:
    """All candidates filtered out (e.g. no available driver) yields `None`."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "alpha": _descriptor("alpha"),
        },
        statuses={"alpha": _status(available=False)},
    )
    selected = bridge._select_channel(request, "reply_message", _fake_proposal())
    assert selected is None


# ---------------------------------------------------------------------------
# Op missing
# ---------------------------------------------------------------------------


def test_op_not_in_supported_ops_yields_none() -> None:
    """A driver that does not offer the requested op is not a candidate."""

    bridge = FirstVersionPlannerBridgePath()
    request = _bridge_request(
        descriptors={
            "alpha": _descriptor("alpha", supported_ops=("other_op",)),
        },
        statuses={"alpha": _status()},
    )
    selected = bridge._select_channel(request, "reply_message", _fake_proposal())
    assert selected is None
