"""Composition owner capability bundles.

This module holds opt-in capability bundles for `assemble_runtime`. The
`AggressiveRadicalPromptProfile` bundle (R79-B) activates the v3
embodied-prompt path (R79-A) end-to-end without altering the default v1
assembly.

Fail-fast: every bundle raises `CompositionError` at `__post_init__` on
construction-time invariant violations. There is no silent fallback to the
v1 path; the caller must fix the bundle or omit it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .runtime_assembly import CompositionError

PromptPathMode = Literal["aggressive-radical-v3"]
"""Allowed prompt-path mode literals for the v3 aggressive-radical bundle.

Today the bundle is the only one — R79-A's v3 path. Future owners (R80+
R82) may extend this literal to add v4 / v5 path names; the type alias
keeps the public surface a single import.
"""


@dataclass(frozen=True)
class AggressiveRadicalPromptProfile:
    """Opt-in capability bundle for the v3 aggressive-radical embodied-prompt path.

    Owner: composition (capability bundle; not a cognitive owner).

    Purpose:
        Activate the `AggressiveRadicalEmbodiedPromptPath` (R79-A) end-to-end
        and inject the channel catalog the v3 contract advertises to the
        LLM. When the bundle is omitted from `assemble_runtime`, the
        default first-version path is used and the v3 contract is dormant.

    Failure semantics:
        `__post_init__` raises `CompositionError` on:
        - empty `ready_channels` (the v3 contract asks the LLM to pick a
          channel; an empty catalog leaves the LLM with no speaking surface
          and is treated as a configuration error, not a silent v1
          fallback).
        - a non-string entry in `ready_channels` (the catalog is a set of
          driver ids, never a typed metadata object).
        - a duplicate entry in `ready_channels` (the catalog is a set,
          not a multiset; duplicates are a caller bug).

    Notes:
        `prompt_path_mode` is a literal rather than a free string so a
        future v4 / v5 path can be added only by extending the `Literal`
        alias, never by silently accepting an unknown string.
    """

    prompt_path_mode: PromptPathMode = "aggressive-radical-v3"
    ready_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.ready_channels:
            raise CompositionError(
                "AggressiveRadicalPromptProfile.ready_channels must declare at least "
                "one channel; an empty list leaves the v3 path with no speaking "
                "surface (fail-fast; no silent v1 fallback)."
            )
        seen: set[str] = set()
        for channel in self.ready_channels:
            if not isinstance(channel, str) or not channel:
                raise CompositionError(
                    "AggressiveRadicalPromptProfile.ready_channels entry must be a "
                    f"non-empty string, got {channel!r}."
                )
            if channel in seen:
                raise CompositionError(
                    "AggressiveRadicalPromptProfile.ready_channels contains duplicate "
                    f"channel {channel!r} (channels are a set, not a multiset)."
                )
            seen.add(channel)
