"""Owner: 14 identity governance (R85-T19 L18 forget-permission gate).

Owns:
- the L18-styled governance decision for "should this MemoryRecord be
  eligible for soft-deletion?"
- a single function `check_forget_permission` that returns a typed
  `GovernanceVerdict`

Does not own:
- the actual soft-delete (owner 06 memory store)
- identity-state mutation (owner 14 main contracts)
- owner 31 dispatch logic (memory_tool_channel)

The default policy is fail-closed:
- L5_autobiographical is never forgettable (it is part of the agent's
  identity narrative)
- All other layers are forgettable, conditional on a non-empty reason

This module exists separately from `IdentityGovernanceEngine` because
the L18 forget gate is on the runtime hot path of owner 31 dispatch and
must not require a full identity-governance tick to resolve.
"""

from __future__ import annotations

from dataclasses import dataclass

from helios_v2.memory.contracts import MemoryRecord


@dataclass(frozen=True)
class GovernanceVerdict:
    """Result of a single L18 governance check.

    Owner: 14 identity governance.

    Attributes:
        allow: True iff the requested action is permitted.
        reason: human-readable explanation; always set, even on allow,
            so the audit trail captures intent.
        policy_id: stable identifier of the policy rule that decided
            (e.g. "L18_forget_L5_protected", "L18_forget_default_allow").
    """

    allow: bool
    reason: str
    policy_id: str


# Hard-coded strings (no Enum to keep this off the owner 14 enum surface
# and align with R79-A's R-number ban in owner API).
_POLICY_PROTECTED = "L18_forget_L5_protected"
_POLICY_ALLOW = "L18_forget_default_allow"
_POLICY_NO_REASON = "L18_forget_missing_reason"


def check_forget_permission(record: MemoryRecord, reason: str) -> GovernanceVerdict:
    """Decide whether a `MemoryRecord` may be soft-deleted.

    Owner: 14 identity governance (L18 forget-permission gate).

    Purpose:
        Apply the L18 policy in a single function so owner 31's forget
        sub-driver can call it on every forget call without spinning
        up a full identity-governance tick.

    Inputs:
        record: the `MemoryRecord` the caller is proposing to forget.
        reason: free-text justification supplied by the caller; must
            be non-empty.

    Returns:
        A `GovernanceVerdict` with `allow=True` iff the record is not
        L5_autobiographical and a non-empty reason is provided.

    Raises:
        None. The function returns a deny verdict rather than raising,
        so the dispatcher's `error` result path is exercised on denial.

    Notes:
        - The function is fail-closed: any ambiguity is a deny.
        - Soft-deleted records are not rejected by this gate; the
          store's own `soft_delete` rejects double-deletion. The gate
          only asks "could this record be forgotten, if not already?".
        - Future R86+ may extend the policy (e.g. L4 with tags
          {"identity"} becomes protected). For now, only L5 is
          hard-protected.
    """
    if record.layer == "L5_autobiographical":
        return GovernanceVerdict(
            allow=False,
            reason=(
                f"record {record.record_id!r} is L5_autobiographical "
                "and cannot be forgotten (L18 protected)"
            ),
            policy_id=_POLICY_PROTECTED,
        )
    if not reason or not reason.strip():
        return GovernanceVerdict(
            allow=False,
            reason="forget reason is required and must be non-empty",
            policy_id=_POLICY_NO_REASON,
        )
    return GovernanceVerdict(
        allow=True,
        reason=f"L18 allow: forgetting {record.layer} record {record.record_id!r}",
        policy_id=_POLICY_ALLOW,
    )


__all__ = [
    "GovernanceVerdict",
    "check_forget_permission",
]
