"""Owner: runtime composition root.

First-version critical-dependency declaration and provider for the runnable runtime.

This module ships a minimal, explicit dependency surface so the composition root can
exercise the existing fail-fast startup gate (`runtime.dependencies`). It does not
invent capabilities: it declares the baseline capabilities the first-version runtime
actually relies on and reports availability for exactly those.

Owns:
- the default critical-dependency spec set for the first-version runnable runtime
- a first-version dependency provider that reports availability for declared capabilities

Does not own:
- any cognitive runtime decision or owner state
- the startup gate itself (owned by `runtime.dependencies`)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from helios_v2.channel import ChannelSubsystemAPI
from helios_v2.embedding import EmbeddingGatewayAPI
from helios_v2.llm import LlmGatewayAPI
from helios_v2.persistence import ExperienceStore, PersistenceError
from helios_v2.continuity_checkpoint import CheckpointError, ContinuityCheckpointStore
from helios_v2.runtime import RuntimeDependencySpec
from helios_v2.runtime.contracts import RuntimeDependencyProvider, RuntimeDependencyStatus

# Stable capability name for the deterministic first-version cognition chain. The
# baseline runtime depends on this single declared capability being present.
RUNTIME_COGNITION_BASELINE = "runtime_cognition_baseline"

# Stable capability name for bound LLM profile static readiness. A runtime that binds at
# least one LLM consumer adds this critical dependency; static readiness is checked
# network-free through the `25` gateway so the startup gate fails fast on a missing key.
LLM_PROFILES_READY = "llm_profiles_ready"

# Stable capability name for bound channel-driver static readiness. A runtime that binds
# at least one critical channel driver adds this critical dependency; static readiness is
# checked network-free through the `30` subsystem so the startup gate fails fast on a
# missing driver credential. This mechanism ships unbound: the baseline runtime declares
# no critical driver, so it does not add this spec and is unaffected (the CLI driver in
# `31` declares no credential and never trips the gate).
CHANNEL_DRIVERS_READY = "channel_drivers_ready"

# Stable capability name for durable experience-store readiness. A runtime assembled with
# persistence enabled (`33`) adds this critical dependency; readiness is the backend's
# ability to initialize (create/open its durable file), checked at startup so an
# un-initializable or unwritable store fails fast rather than running non-persistently.
# The default (non-persistent) runtime does not add this spec and is unaffected.
EXPERIENCE_STORE_READY = "experience_store_ready"

# Stable capability name for bound embedding-profile static readiness. A runtime assembled
# with semantic memory enabled (`34`) adds this critical dependency; static readiness is
# checked network-free through the `34` embedding gateway so the startup gate fails fast on a
# missing key. The default and recency-only persistent runtimes do not add it and are
# unaffected. There is no degraded recency fallback when semantic memory is enabled.
EMBEDDING_PROFILE_READY = "embedding_profile_ready"

# Stable capability name for durable runtime-continuity checkpoint readiness. A runtime
# assembled with checkpointing enabled (`42`) adds this critical dependency; readiness is the
# checkpoint backend's ability to initialize (create/open its durable file), checked at startup
# so an un-initializable or unwritable checkpoint store fails fast rather than running without a
# resumable continuity checkpoint. The default (non-checkpointing) runtime does not add this
# spec and is unaffected.
CONTINUITY_CHECKPOINT_READY = "continuity_checkpoint_ready"


def default_critical_dependency_specs() -> list[RuntimeDependencySpec]:
    """Owner: composition.

    Purpose:
        Return the default critical-dependency spec set for the first-version runtime.

    Inputs:
        None.

    Returns:
        A list with one required spec for the deterministic baseline cognition chain.

    Raises:
        None.

    Notes:
        Later requirements that add real capabilities (LLM, persistent memory, channel
        transport) extend this set; they must not weaken the fail-fast gate.
    """

    return [
        RuntimeDependencySpec(
            name=RUNTIME_COGNITION_BASELINE,
            required=True,
            description="Deterministic first-version cognition chain availability.",
        )
    ]


def llm_critical_dependency_spec() -> RuntimeDependencySpec:
    """Owner: composition.

    Purpose:
        Return the critical-dependency spec for bound LLM profile static readiness.

    Inputs:
        None.

    Returns:
        A required spec for the `llm_profiles_ready` capability.

    Notes:
        This spec is added to the default set only when the assembled runtime binds at
        least one LLM consumer. A runtime that binds no LLM consumer does not add it and is
        unaffected.
    """

    return RuntimeDependencySpec(
        name=LLM_PROFILES_READY,
        required=True,
        description="Bound LLM profile static readiness (profile registered and api key set).",
    )


def channel_critical_dependency_spec() -> RuntimeDependencySpec:
    """Owner: composition.

    Purpose:
        Return the critical-dependency spec for bound channel-driver static readiness.

    Inputs:
        None.

    Returns:
        A required spec for the `channel_drivers_ready` capability.

    Notes:
        This spec is added to the default set only when the assembled runtime binds at
        least one critical channel driver. The baseline runtime and the CLI driver (`31`,
        which declares no credential) do not add it, so they are unaffected. The binding is
        deferred to the requirement that wires a real critical driver into composition; this
        slice ships the mechanism only.
    """

    return RuntimeDependencySpec(
        name=CHANNEL_DRIVERS_READY,
        required=True,
        description="Bound channel driver static readiness (driver registered and credential present).",
    )


def experience_store_critical_dependency_spec() -> RuntimeDependencySpec:
    """Owner: composition.

    Purpose:
        Return the critical-dependency spec for durable experience-store readiness.

    Inputs:
        None.

    Returns:
        A required spec for the `experience_store_ready` capability.

    Notes:
        This spec is added to the default set only when the assembled runtime enables
        persistence (`33`). The default (non-persistent) runtime does not add it and is
        unaffected. There is no degraded non-persistent path when persistence is enabled.
    """

    return RuntimeDependencySpec(
        name=EXPERIENCE_STORE_READY,
        required=True,
        description="Durable experience-store readiness (backend initializes and is writable).",
    )


def embedding_profile_critical_dependency_spec() -> RuntimeDependencySpec:
    """Owner: composition.

    Purpose:
        Return the critical-dependency spec for bound embedding-profile static readiness.

    Inputs:
        None.

    Returns:
        A required spec for the `embedding_profile_ready` capability.

    Notes:
        This spec is added to the default set only when the assembled runtime enables semantic
        memory (`34`). The default and recency-only persistent runtimes do not add it and are
        unaffected. There is no degraded recency fallback when semantic memory is enabled.
    """

    return RuntimeDependencySpec(
        name=EMBEDDING_PROFILE_READY,
        required=True,
        description="Bound embedding profile static readiness (profile registered and api key set).",
    )


def continuity_checkpoint_critical_dependency_spec() -> RuntimeDependencySpec:
    """Owner: composition.

    Purpose:
        Return the critical-dependency spec for durable runtime-continuity checkpoint readiness.

    Inputs:
        None.

    Returns:
        A required spec for the `continuity_checkpoint_ready` capability.

    Notes:
        This spec is added to the default set only when the assembled runtime enables
        checkpointing (`42`). The default (non-checkpointing) runtime does not add it and is
        unaffected. There is no degraded non-checkpointing path once checkpointing is enabled.
    """

    return RuntimeDependencySpec(
        name=CONTINUITY_CHECKPOINT_READY,
        required=True,
        description="Durable runtime-continuity checkpoint readiness (backend initializes and is writable).",
    )


@dataclass
class FirstVersionDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for the first-version runnable runtime.

    Failure semantics:
        Reports unavailable for any capability not in the declared available set, so the
        existing startup gate fails fast on an undeclared or missing critical dependency.
    """

    available_capabilities: frozenset[str] = field(
        default_factory=lambda: frozenset({RUNTIME_COGNITION_BASELINE})
    )

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus` reporting availability for the named capability.

        Raises:
            None.

        Notes:
            Availability is membership in the explicit `available_capabilities` set. An
            unknown name is reported unavailable rather than silently treated as present.
        """

        available = name in self.available_capabilities
        detail = "available" if available else "not declared available in first-version runtime"
        return RuntimeDependencyStatus(name=name, available=available, detail=detail)


@dataclass
class LlmReadinessDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for a runtime that binds LLM consumers. It
        delegates the `LLM_PROFILES_READY` capability to the `25` gateway's network-free
        static readiness check for the bound profile names, and delegates every other
        capability to a wrapped baseline provider.

    Failure semantics:
        Reports `LLM_PROFILES_READY` unavailable when any bound profile is not statically
        ready (unknown profile or unset api key), so the existing startup gate fails fast.
        Performs no network call.

    Notes:
        This is owner-neutral assembly glue. It holds no cognitive policy; it only routes a
        capability name to the gateway's readiness query. The live probe is never invoked
        here, keeping the startup gate deterministic and network-free.
    """

    gateway: LlmGatewayAPI
    bound_profile_names: tuple[str, ...]
    baseline_provider: RuntimeDependencyProvider = field(default_factory=FirstVersionDependencyProvider)

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus`. For `LLM_PROFILES_READY` the status reflects the
            gateway's static readiness for all bound profiles; other names defer to the
            wrapped baseline provider.

        Raises:
            None.
        """

        if name == LLM_PROFILES_READY:
            report = self.gateway.check_static_readiness(self.bound_profile_names)
            if report.all_static_ready():
                return RuntimeDependencyStatus(
                    name=name,
                    available=True,
                    detail="all bound LLM profiles are statically ready",
                )
            unready = tuple(
                entry.profile_name for entry in report.entries if not entry.static_ready
            )
            return RuntimeDependencyStatus(
                name=name,
                available=False,
                detail=f"bound LLM profiles not statically ready: {', '.join(unready) or 'none-bound'}",
            )
        return self.baseline_provider.get_dependency_status(name)


@dataclass
class ChannelReadinessDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for a runtime that binds critical channel
        drivers. It delegates the `CHANNEL_DRIVERS_READY` capability to the `30` subsystem's
        network-free static readiness check for the bound driver ids, and delegates every
        other capability to a wrapped baseline provider.

    Failure semantics:
        Reports `CHANNEL_DRIVERS_READY` unavailable when any bound driver is not statically
        ready (unregistered or missing credential), so the existing startup gate fails fast.
        Performs no network call.

    Notes:
        This is owner-neutral assembly glue. It holds no cognitive policy; it only routes a
        capability name to the subsystem's readiness query. It ships unbound: it is wired in
        only when the assembled runtime binds at least one critical channel driver.
    """

    subsystem: ChannelSubsystemAPI
    bound_driver_ids: tuple[str, ...]
    baseline_provider: RuntimeDependencyProvider = field(default_factory=FirstVersionDependencyProvider)

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus`. For `CHANNEL_DRIVERS_READY` the status reflects the
            subsystem's static readiness for all bound drivers; other names defer to the
            wrapped baseline provider.

        Raises:
            None.
        """

        if name == CHANNEL_DRIVERS_READY:
            report = self.subsystem.check_static_readiness(self.bound_driver_ids)
            if report.all_ready():
                return RuntimeDependencyStatus(
                    name=name,
                    available=True,
                    detail="all bound channel drivers are statically ready",
                )
            unready = tuple(entry.driver_id for entry in report.entries if not entry.ready)
            return RuntimeDependencyStatus(
                name=name,
                available=False,
                detail=f"bound channel drivers not statically ready: {', '.join(unready) or 'none-bound'}",
            )
        return self.baseline_provider.get_dependency_status(name)


@dataclass
class ExperienceStoreReadinessDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for a runtime assembled with persistence
        enabled. It delegates the `EXPERIENCE_STORE_READY` capability to the `33` store's
        ability to initialize its durable backend, and delegates every other capability to a
        wrapped baseline provider.

    Failure semantics:
        Reports `EXPERIENCE_STORE_READY` unavailable when the store backend cannot initialize
        (for example an unwritable path), so the existing startup gate fails fast. There is no
        degraded non-persistent path.

    Notes:
        This is owner-neutral assembly glue. It holds no cognitive policy; it only routes a
        capability name to the store's `initialize`. `initialize` is idempotent, so probing
        readiness here does not double-create the backend.
    """

    store: ExperienceStore
    baseline_provider: RuntimeDependencyProvider = field(default_factory=FirstVersionDependencyProvider)

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus`. For `EXPERIENCE_STORE_READY` the status reflects
            whether the durable backend initializes successfully; other names defer to the
            wrapped baseline provider.

        Raises:
            None. A backend initialization failure is captured into an unavailable status,
            not raised, so the startup gate (not this provider) performs the fail-fast.
        """

        if name == EXPERIENCE_STORE_READY:
            try:
                self.store.initialize()
            except PersistenceError as error:
                return RuntimeDependencyStatus(
                    name=name,
                    available=False,
                    detail=f"experience store backend not ready: {error}",
                )
            return RuntimeDependencyStatus(
                name=name,
                available=True,
                detail="experience store backend initialized and writable",
            )
        return self.baseline_provider.get_dependency_status(name)


@dataclass
class EmbeddingReadinessDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for a runtime assembled with semantic memory
        enabled. It delegates the `EMBEDDING_PROFILE_READY` capability to the `34` embedding
        gateway's network-free static readiness check for the bound profile names, and
        delegates every other capability to a wrapped baseline provider.

    Failure semantics:
        Reports `EMBEDDING_PROFILE_READY` unavailable when any bound profile is not statically
        ready (unknown profile or unset api key), so the existing startup gate fails fast.
        Performs no network call.

    Notes:
        Owner-neutral assembly glue. It holds no cognitive policy; it only routes a capability
        name to the gateway's readiness query. The live probe is never invoked here, keeping
        the startup gate deterministic and network-free.
    """

    gateway: EmbeddingGatewayAPI
    bound_profile_names: tuple[str, ...]
    baseline_provider: RuntimeDependencyProvider = field(default_factory=FirstVersionDependencyProvider)

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus`. For `EMBEDDING_PROFILE_READY` the status reflects the
            gateway's static readiness for all bound profiles; other names defer to the
            wrapped baseline provider.

        Raises:
            None.
        """

        if name == EMBEDDING_PROFILE_READY:
            report = self.gateway.check_static_readiness(self.bound_profile_names)
            if report.all_static_ready():
                return RuntimeDependencyStatus(
                    name=name,
                    available=True,
                    detail="all bound embedding profiles are statically ready",
                )
            unready = tuple(
                entry.profile_name for entry in report.entries if not entry.static_ready
            )
            return RuntimeDependencyStatus(
                name=name,
                available=False,
                detail=f"bound embedding profiles not statically ready: {', '.join(unready) or 'none-bound'}",
            )
        return self.baseline_provider.get_dependency_status(name)


@dataclass
class ContinuityCheckpointReadinessDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for a runtime assembled with checkpointing
        enabled. It delegates the `CONTINUITY_CHECKPOINT_READY` capability to the `42` checkpoint
        store's ability to initialize its durable backend, and delegates every other capability
        to a wrapped baseline provider.

    Failure semantics:
        Reports `CONTINUITY_CHECKPOINT_READY` unavailable when the checkpoint backend cannot
        initialize (for example an unwritable path), so the existing startup gate fails fast.
        There is no degraded non-checkpointing path.

    Notes:
        Owner-neutral assembly glue. It holds no cognitive policy; it only routes a capability
        name to the store's `initialize`. `initialize` is idempotent, so probing readiness here
        does not double-create the backend.
    """

    store: ContinuityCheckpointStore
    baseline_provider: RuntimeDependencyProvider = field(default_factory=FirstVersionDependencyProvider)

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus`. For `CONTINUITY_CHECKPOINT_READY` the status reflects
            whether the durable checkpoint backend initializes successfully; other names defer to
            the wrapped baseline provider.

        Raises:
            None. A backend initialization failure is captured into an unavailable status, not
            raised, so the startup gate (not this provider) performs the fail-fast.
        """

        if name == CONTINUITY_CHECKPOINT_READY:
            try:
                self.store.initialize()
            except CheckpointError as error:
                return RuntimeDependencyStatus(
                    name=name,
                    available=False,
                    detail=f"continuity checkpoint backend not ready: {error}",
                )
            return RuntimeDependencyStatus(
                name=name,
                available=True,
                detail="continuity checkpoint backend initialized and writable",
            )
        return self.baseline_provider.get_dependency_status(name)
