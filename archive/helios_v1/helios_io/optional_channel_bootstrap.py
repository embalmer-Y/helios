from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

from .channel import ChannelManagementResult, ChannelStatus, InputChannel, OutputChannel
from .channels.cli_channel import build_cli_bootstrap_factory
from .channels.stt_channel import build_stt_bootstrap_factory
from .channels.tts_channel import build_tts_bootstrap_factory
from .channels.vision_channel import build_vision_bootstrap_factory
from .optional_channel_contract import OptionalChannelBootstrapFactory, OptionalChannelBootstrapSpec


DefaultOptionalChannelBootstrapFactoryBuilder = Callable[..., OptionalChannelBootstrapFactory]

_DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS: dict[str, DefaultOptionalChannelBootstrapFactoryBuilder] = {}


@dataclass(frozen=True)
class OptionalChannelBootstrapSummary:
    results: tuple[tuple[OptionalChannelBootstrapSpec, ChannelManagementResult], ...]
    active_channel_ids: tuple[str, ...]
    dormant_channel_ids: tuple[str, ...]
    failed_channel_ids: tuple[str, ...]


@dataclass(frozen=True)
class OptionalChannelRuntimeSnapshot:
    factory_ids: tuple[str, ...]
    spec_ids: tuple[str, ...]
    runtime_active_channel_ids: tuple[str, ...]
    last_bootstrap_summary: OptionalChannelBootstrapSummary | None


class OptionalChannelBootstrapRegistry:
    def __init__(self, factories: dict[str, OptionalChannelBootstrapFactory] | None = None):
        self._factories: dict[str, OptionalChannelBootstrapFactory] = dict(factories or {})
        self._specs: dict[str, OptionalChannelBootstrapSpec] = {}

    def get_specs(self) -> dict[str, OptionalChannelBootstrapSpec]:
        return dict(self._specs)

    def get_factory_ids(self) -> tuple[str, ...]:
        return tuple(self._factories)

    def has_spec(self, channel_id: str) -> bool:
        return str(channel_id) in self._specs

    def rebuild_specs(self) -> dict[str, OptionalChannelBootstrapSpec]:
        specs: dict[str, OptionalChannelBootstrapSpec] = {}
        for channel_id, spec_factory in self._factories.items():
            spec = spec_factory()
            if spec.channel_id != channel_id:
                raise ValueError(
                    f"Optional channel bootstrap factory for {channel_id} produced mismatched spec {spec.channel_id}."
                )
            specs[channel_id] = spec
        self._specs = specs
        return self.get_specs()

    def register_spec(self, spec: OptionalChannelBootstrapSpec) -> None:
        self._specs[spec.channel_id] = spec

    def register_factory(self, channel_id: str, spec_factory: OptionalChannelBootstrapFactory) -> OptionalChannelBootstrapSpec:
        spec = spec_factory()
        if spec.channel_id != channel_id:
            raise ValueError(
                f"Optional channel bootstrap factory for {channel_id} produced mismatched spec {spec.channel_id}."
            )
        self._factories[channel_id] = spec_factory
        self._specs[channel_id] = spec
        return spec

    def deregister_spec(self, channel_id: str) -> OptionalChannelBootstrapSpec | None:
        return self._specs.pop(str(channel_id), None)

    def deregister_factory(self, channel_id: str) -> bool:
        return self._factories.pop(str(channel_id), None) is not None


class OptionalChannelBootstrapManager:
    def __init__(
        self,
        *,
        registry: OptionalChannelBootstrapRegistry,
        bootstrap_spec: Callable[[OptionalChannelBootstrapSpec], ChannelManagementResult],
        runtime_channel_active: Callable[[str], bool],
        deregister_runtime_channel: Callable[[str, bool], ChannelManagementResult],
    ):
        self._registry = registry
        self._bootstrap_spec = bootstrap_spec
        self._runtime_channel_active = runtime_channel_active
        self._deregister_runtime_channel = deregister_runtime_channel

    def get_specs(self) -> dict[str, OptionalChannelBootstrapSpec]:
        return self._registry.get_specs()

    def get_factory_ids(self) -> tuple[str, ...]:
        return self._registry.get_factory_ids()

    def is_runtime_active(self, channel_id: str) -> bool:
        return self._runtime_channel_active(str(channel_id))

    def bootstrap_all(self) -> list[tuple[OptionalChannelBootstrapSpec, ChannelManagementResult]]:
        results: list[tuple[OptionalChannelBootstrapSpec, ChannelManagementResult]] = []
        for spec in self._registry.get_specs().values():
            results.append((spec, self._bootstrap_spec(spec)))
        return results

    def register_spec(
        self,
        spec: OptionalChannelBootstrapSpec,
        *,
        bootstrap: bool = True,
    ) -> ChannelManagementResult:
        self._registry.register_spec(spec)
        if not bootstrap:
            return ChannelManagementResult(
                channel_id=spec.channel_id,
                op_name="register_optional_channel_bootstrap_spec",
                success=True,
                status=ChannelStatus.UNINITIALIZED.value,
                message="Optional channel bootstrap spec registered.",
                payload={"runtime_registered": False, "spec_registered": True},
            )
        return self._bootstrap_spec(spec)

    def register_factory(
        self,
        channel_id: str,
        spec_factory: OptionalChannelBootstrapFactory,
        *,
        bootstrap: bool = True,
    ) -> ChannelManagementResult:
        try:
            spec = self._registry.register_factory(channel_id, spec_factory)
        except ValueError as exc:
            return ChannelManagementResult(
                channel_id=channel_id,
                op_name="register_optional_channel_bootstrap_factory",
                success=False,
                status=ChannelStatus.ERROR.value,
                message=str(exc),
                error_code="optional_channel_factory_channel_id_mismatch",
            )
        result = self.register_spec(spec, bootstrap=bootstrap)
        return ChannelManagementResult(
            channel_id=channel_id,
            op_name="register_optional_channel_bootstrap_factory",
            success=result.success,
            status=result.status,
            message=result.message,
            payload={
                "factory_registered": True,
                "spec_registered": self._registry.has_spec(channel_id),
                "runtime_registered": self._runtime_channel_active(channel_id),
            },
            error_code=result.error_code,
        )

    def deregister_spec(
        self,
        channel_id: str,
        *,
        disconnect: bool = True,
    ) -> ChannelManagementResult:
        spec = self._registry.deregister_spec(channel_id)
        if spec is None:
            return ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister_optional_channel_bootstrap_spec",
                success=False,
                status=ChannelStatus.ERROR.value,
                message=f"Optional channel bootstrap spec {channel_id} is not registered.",
                error_code="optional_channel_spec_not_registered",
            )
        if self._runtime_channel_active(channel_id):
            runtime_result = self._deregister_runtime_channel(channel_id, disconnect)
            return ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister_optional_channel_bootstrap_spec",
                success=runtime_result.success,
                status=runtime_result.status,
                message=runtime_result.message,
                payload={"runtime_registered": False, "spec_registered": False},
                error_code=runtime_result.error_code,
            )
        return ChannelManagementResult(
            channel_id=channel_id,
            op_name="deregister_optional_channel_bootstrap_spec",
            success=True,
            status=ChannelStatus.DEINITIALIZED.value,
            message="Optional channel bootstrap spec deregistered.",
            payload={"runtime_registered": False, "spec_registered": False},
        )

    def deregister_factory(
        self,
        channel_id: str,
        *,
        disconnect: bool = True,
    ) -> ChannelManagementResult:
        removed_factory = self._registry.deregister_factory(channel_id)
        if not removed_factory:
            return ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister_optional_channel_bootstrap_factory",
                success=False,
                status=ChannelStatus.ERROR.value,
                message=f"Optional channel bootstrap factory {channel_id} is not registered.",
                error_code="optional_channel_factory_not_registered",
            )
        if self._registry.has_spec(channel_id):
            result = self.deregister_spec(channel_id, disconnect=disconnect)
            return ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister_optional_channel_bootstrap_factory",
                success=result.success,
                status=result.status,
                message=result.message,
                payload={
                    "factory_registered": False,
                    "spec_registered": self._registry.has_spec(channel_id),
                    "runtime_registered": self._runtime_channel_active(channel_id),
                },
                error_code=result.error_code,
            )
        return ChannelManagementResult(
            channel_id=channel_id,
            op_name="deregister_optional_channel_bootstrap_factory",
            success=True,
            status=ChannelStatus.DEINITIALIZED.value,
            message="Optional channel bootstrap factory deregistered.",
            payload={"factory_registered": False, "spec_registered": False, "runtime_registered": False},
        )


class OptionalChannelRuntime:
    def __init__(
        self,
        *,
        manager: OptionalChannelBootstrapManager,
        register_runtime_channel: Callable[[InputChannel | OutputChannel], ChannelManagementResult],
    ):
        self._manager = manager
        self._register_runtime_channel = register_runtime_channel
        self._last_bootstrap_summary: OptionalChannelBootstrapSummary | None = None

    def _invalidate_bootstrap_summary(self) -> None:
        self._last_bootstrap_summary = None

    def get_specs(self) -> dict[str, OptionalChannelBootstrapSpec]:
        return self._manager.get_specs()

    def get_factory_ids(self) -> tuple[str, ...]:
        return self._manager.get_factory_ids()

    def is_runtime_active(self, channel_id: str) -> bool:
        return self._manager.is_runtime_active(channel_id)

    def get_last_bootstrap_summary(self) -> OptionalChannelBootstrapSummary | None:
        return self._last_bootstrap_summary

    def get_runtime_snapshot(self) -> OptionalChannelRuntimeSnapshot:
        specs = self._manager.get_specs()
        spec_ids = tuple(specs)
        runtime_active_channel_ids = tuple(
            channel_id for channel_id in spec_ids if self._manager.is_runtime_active(channel_id)
        )
        return OptionalChannelRuntimeSnapshot(
            factory_ids=self._manager.get_factory_ids(),
            spec_ids=spec_ids,
            runtime_active_channel_ids=runtime_active_channel_ids,
            last_bootstrap_summary=self._last_bootstrap_summary,
        )

    def bootstrap_all(self) -> list[tuple[OptionalChannelBootstrapSpec, ChannelManagementResult]]:
        return self._manager.bootstrap_all()

    def bootstrap_defaults(self, *, logger: logging.Logger | None = None) -> OptionalChannelBootstrapSummary:
        results = tuple(self._manager.bootstrap_all())
        active_channel_ids: list[str] = []
        dormant_channel_ids: list[str] = []
        failed_channel_ids: list[str] = []

        for spec, result in results:
            if bool(result.payload.get("runtime_registered", False)):
                active_channel_ids.append(spec.channel_id)
            else:
                dormant_channel_ids.append(spec.channel_id)
            if not result.success:
                failed_channel_ids.append(spec.channel_id)
                if logger is not None:
                    logger.warning("Optional channel %s connect failed during bootstrap: %s", spec.channel_id, result.message)

        summary = OptionalChannelBootstrapSummary(
            results=results,
            active_channel_ids=tuple(active_channel_ids),
            dormant_channel_ids=tuple(dormant_channel_ids),
            failed_channel_ids=tuple(failed_channel_ids),
        )
        self._last_bootstrap_summary = summary

        if logger is not None:
            logger.debug(
                "Active optional channels: %s",
                ", ".join(summary.active_channel_ids) if summary.active_channel_ids else "none",
            )
            logger.debug(
                "Dormant optional channels: %s",
                ", ".join(summary.dormant_channel_ids) if summary.dormant_channel_ids else "none",
            )

        return summary

    def register_spec(
        self,
        spec: OptionalChannelBootstrapSpec,
        *,
        bootstrap: bool = True,
    ) -> ChannelManagementResult:
        self._invalidate_bootstrap_summary()
        return self._manager.register_spec(spec, bootstrap=bootstrap)

    def register_factory(
        self,
        channel_id: str,
        spec_factory: OptionalChannelBootstrapFactory,
        *,
        bootstrap: bool = True,
    ) -> ChannelManagementResult:
        self._invalidate_bootstrap_summary()
        return self._manager.register_factory(channel_id, spec_factory, bootstrap=bootstrap)

    def deregister_spec(
        self,
        channel_id: str,
        *,
        disconnect: bool = True,
    ) -> ChannelManagementResult:
        self._invalidate_bootstrap_summary()
        return self._manager.deregister_spec(channel_id, disconnect=disconnect)

    def deregister_factory(
        self,
        channel_id: str,
        *,
        disconnect: bool = True,
    ) -> ChannelManagementResult:
        self._invalidate_bootstrap_summary()
        return self._manager.deregister_factory(channel_id, disconnect=disconnect)

    def bootstrap_spec(self, spec: OptionalChannelBootstrapSpec) -> ChannelManagementResult:
        channel = spec.factory(**dict(spec.payload))
        if not bool(getattr(channel, "is_available", False)):
            return ChannelManagementResult(
                channel_id=spec.channel_id,
                op_name="bootstrap_optional_channel_spec",
                success=True,
                status=ChannelStatus.DISCONNECTED.value,
                message="Optional channel spec registered but channel is dormant.",
                payload={"runtime_registered": False, "spec_registered": True},
            )
        runtime_result = self._register_runtime_channel(channel)
        return ChannelManagementResult(
            channel_id=spec.channel_id,
            op_name="bootstrap_optional_channel_spec",
            success=runtime_result.success,
            status=runtime_result.status,
            message=runtime_result.message,
            payload={"runtime_registered": runtime_result.success, "spec_registered": True},
            error_code=runtime_result.error_code,
        )


def register_default_optional_channel_bootstrap_factory_builder(
    channel_id: str,
    builder: DefaultOptionalChannelBootstrapFactoryBuilder,
) -> None:
    _DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS[str(channel_id)] = builder


def deregister_default_optional_channel_bootstrap_factory_builder(channel_id: str) -> bool:
    return _DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS.pop(str(channel_id), None) is not None


def get_default_optional_channel_bootstrap_factory_builders() -> dict[str, DefaultOptionalChannelBootstrapFactoryBuilder]:
    return dict(_DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS)


def get_default_optional_channel_bootstrap_factory_builder_ids() -> tuple[str, ...]:
    return tuple(_DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS)


def _build_default_tts_factory(**kwargs) -> OptionalChannelBootstrapFactory:
    return build_tts_bootstrap_factory(cfg=kwargs["cfg"])


def _build_default_cli_factory(**kwargs) -> OptionalChannelBootstrapFactory:
    return build_cli_bootstrap_factory(
        cfg=kwargs["cfg"],
        state_provider=kwargs["state_provider"],
        history_provider=kwargs["history_provider"],
        sec_evaluator=kwargs["sec_evaluator"],
        input_stream=kwargs["cli_input_stream"],
    )


def _build_default_stt_factory(**kwargs) -> OptionalChannelBootstrapFactory:
    return build_stt_bootstrap_factory(
        cfg=kwargs["cfg"],
        sec_evaluator=kwargs["sec_evaluator"],
    )


def _build_default_vision_factory(**kwargs) -> OptionalChannelBootstrapFactory:
    return build_vision_bootstrap_factory(cfg=kwargs["cfg"])


def build_default_optional_channel_bootstrap_factories(
    *,
    cfg: object,
    state_provider: Callable[[], object],
    history_provider: Callable[[str, str], object],
    sec_evaluator: object,
    selected_channel_ids: Sequence[str] | None = None,
) -> dict[str, OptionalChannelBootstrapFactory]:
    cli_input_stream = None
    if bool(getattr(cfg, "CLI_ENABLED", False)) and bool(getattr(sys.stdin, "isatty", lambda: False)()):
        cli_input_stream = sys.stdin

    channel_ids = tuple(selected_channel_ids) if selected_channel_ids is not None else get_default_optional_channel_bootstrap_factory_builder_ids()
    unknown_channel_ids = [channel_id for channel_id in channel_ids if channel_id not in _DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS]
    if unknown_channel_ids:
        raise ValueError(
            "Unknown default optional channel bootstrap builders: " + ", ".join(sorted(unknown_channel_ids))
        )

    factories: dict[str, OptionalChannelBootstrapFactory] = {}
    for channel_id in channel_ids:
        builder = _DEFAULT_OPTIONAL_CHANNEL_BOOTSTRAP_FACTORY_BUILDERS[channel_id]
        factories[channel_id] = builder(
            cfg=cfg,
            state_provider=state_provider,
            history_provider=history_provider,
            sec_evaluator=sec_evaluator,
            cli_input_stream=cli_input_stream,
        )
    return factories


def build_default_optional_channel_bootstrap_registry(
    *,
    cfg: object,
    state_provider: Callable[[], object],
    history_provider: Callable[[str, str], object],
    sec_evaluator: object,
    selected_channel_ids: Sequence[str] | None = None,
) -> OptionalChannelBootstrapRegistry:
    registry = OptionalChannelBootstrapRegistry(
        build_default_optional_channel_bootstrap_factories(
            cfg=cfg,
            state_provider=state_provider,
            history_provider=history_provider,
            sec_evaluator=sec_evaluator,
            selected_channel_ids=selected_channel_ids,
        )
    )
    registry.rebuild_specs()
    return registry


def build_default_optional_channel_bootstrap_manager(
    *,
    cfg: object,
    state_provider: Callable[[], object],
    history_provider: Callable[[str, str], object],
    sec_evaluator: object,
    selected_channel_ids: Sequence[str] | None = None,
    bootstrap_spec: Callable[[OptionalChannelBootstrapSpec], ChannelManagementResult],
    runtime_channel_active: Callable[[str], bool],
    deregister_runtime_channel: Callable[[str, bool], ChannelManagementResult],
) -> OptionalChannelBootstrapManager:
    return OptionalChannelBootstrapManager(
        registry=build_default_optional_channel_bootstrap_registry(
            cfg=cfg,
            state_provider=state_provider,
            history_provider=history_provider,
            sec_evaluator=sec_evaluator,
            selected_channel_ids=selected_channel_ids,
        ),
        bootstrap_spec=bootstrap_spec,
        runtime_channel_active=runtime_channel_active,
        deregister_runtime_channel=deregister_runtime_channel,
    )


def build_default_optional_channel_runtime(
    *,
    cfg: object,
    state_provider: Callable[[], object],
    history_provider: Callable[[str, str], object],
    sec_evaluator: object,
    selected_channel_ids: Sequence[str] | None = None,
    register_runtime_channel: Callable[[InputChannel | OutputChannel], ChannelManagementResult],
    runtime_channel_active: Callable[[str], bool],
    deregister_runtime_channel: Callable[[str, bool], ChannelManagementResult],
    bootstrap_logger: logging.Logger | None = None,
    auto_bootstrap: bool = True,
) -> OptionalChannelRuntime:
    runtime = OptionalChannelRuntime(
        manager=OptionalChannelBootstrapManager(
            registry=build_default_optional_channel_bootstrap_registry(
                cfg=cfg,
                state_provider=state_provider,
                history_provider=history_provider,
                sec_evaluator=sec_evaluator,
                selected_channel_ids=selected_channel_ids,
            ),
            bootstrap_spec=lambda spec: runtime.bootstrap_spec(spec),
            runtime_channel_active=runtime_channel_active,
            deregister_runtime_channel=deregister_runtime_channel,
        ),
        register_runtime_channel=register_runtime_channel,
    )
    if auto_bootstrap:
        runtime.bootstrap_defaults(logger=bootstrap_logger)
    return runtime


register_default_optional_channel_bootstrap_factory_builder("tts", _build_default_tts_factory)
register_default_optional_channel_bootstrap_factory_builder("cli", _build_default_cli_factory)
register_default_optional_channel_bootstrap_factory_builder("stt", _build_default_stt_factory)
register_default_optional_channel_bootstrap_factory_builder("vision", _build_default_vision_factory)