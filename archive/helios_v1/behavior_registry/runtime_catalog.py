"""Runtime-facing behavior catalog backed by the SQLite behavior registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable, Iterable

from helios_io.action_models import BehaviorSpec
from helios_io.bootstrap_behavior_specs import build_bootstrap_behavior_specs

from .records import BehaviorSourceRecord
from .sqlite_registry import SQLiteBehaviorRegistry, ensure_behavior_registry


@dataclass(frozen=True)
class RegulationBehaviorProfile:
    """Behavior metadata resolved for the active regulation path."""

    spec: BehaviorSpec
    policy_domains: tuple[str, ...]
    hint: str
    cooldown_seconds: float
    night_suppress: bool

    @property
    def action_type(self) -> str:
        return self.spec.name


class RuntimeBehaviorCatalog:
    """Serve runtime behavior definitions from the registry with bootstrap seeding."""

    DEFAULT_DB_FILENAME = "behavior_registry.sqlite3"

    def __init__(
        self,
        registry: SQLiteBehaviorRegistry,
        *,
        bootstrap_supplier: Callable[[], dict[str, BehaviorSpec]] = build_bootstrap_behavior_specs,
    ):
        self._registry = registry
        self._bootstrap_supplier = bootstrap_supplier
        self._active_cache: dict[str, BehaviorSpec] | None = None

    @classmethod
    def from_db_path(cls, db_path: str | Path) -> RuntimeBehaviorCatalog:
        return cls(ensure_behavior_registry(db_path))

    @property
    def registry(self) -> SQLiteBehaviorRegistry:
        return self._registry

    def refresh(self) -> None:
        self._active_cache = None

    def ensure_bootstrap_behaviors(self) -> int:
        bootstrap_specs = list(self._bootstrap_supplier().values())
        existing_by_name = {
            spec.name: spec
            for spec in self._registry.list_behaviors()
        }
        source_records: list[BehaviorSourceRecord] = []
        for bootstrap_spec in bootstrap_specs:
            existing = existing_by_name.get(bootstrap_spec.name)
            if existing is not None:
                bootstrap_spec.status = existing.status
                bootstrap_spec.review_state = existing.review_state
            source_records.append(
                BehaviorSourceRecord(
                    source_id=f"source::bootstrap::{bootstrap_spec.behavior_id}",
                    behavior_id=bootstrap_spec.behavior_id,
                    source_kind=bootstrap_spec.source_kind,
                    source_summary="Bootstrap behavior imported from helios_io.bootstrap_behavior_specs",
                    captured_at=float(bootstrap_spec.source_detail.get("created_at", 0.0) or 0.0) or time.time(),
                )
            )
        self._registry.import_behaviors(bootstrap_specs)
        self._registry.record_behavior_sources(source_records)
        self.refresh()
        return len(bootstrap_specs)

    def snapshot_by_name(
        self,
        *,
        policy_domain: str = "",
        category: str = "",
        status: str = "active",
        review_state: str = "approved",
    ) -> dict[str, BehaviorSpec]:
        return {
            spec.name: spec
            for spec in self.list_specs(
                policy_domain=policy_domain,
                category=category,
                status=status,
                review_state=review_state,
            )
        }

    def list_specs(
        self,
        *,
        policy_domain: str = "",
        category: str = "",
        status: str = "active",
        review_state: str = "approved",
    ) -> list[BehaviorSpec]:
        if not policy_domain and not category and status == "active" and review_state == "approved":
            return list(self._load_active_cache().values())

        specs = self._registry.list_behaviors(
            category=category,
            status=status,
            review_state=review_state,
        )
        if not policy_domain:
            return specs
        return [spec for spec in specs if policy_domain in self._policy_domains(spec)]

    def get_behavior(
        self,
        behavior_name: str,
        *,
        status: str = "active",
        review_state: str = "approved",
    ) -> BehaviorSpec | None:
        if status == "active" and review_state == "approved":
            return self._load_active_cache().get(behavior_name)

        spec = self._registry.get_behavior(behavior_name)
        if spec is None:
            return None
        if status and spec.status != status:
            return None
        if review_state and spec.review_state != review_state:
            return None
        return spec

    def list_regulation_behaviors(self) -> list[RegulationBehaviorProfile]:
        profiles: list[RegulationBehaviorProfile] = []
        for spec in self.list_specs(policy_domain="regulation_active"):
            profiles.append(self._build_regulation_profile(spec))
        return profiles

    def get_regulation_behavior(self, behavior_name: str) -> RegulationBehaviorProfile | None:
        spec = self.get_behavior(behavior_name)
        if spec is None:
            return None
        domains = self._policy_domains(spec)
        if "regulation_active" not in domains:
            return None
        return self._build_regulation_profile(spec)

    def propose_behavior(
        self,
        spec: BehaviorSpec,
        *,
        source_summary: str = "",
        source_uri: str = "",
        source_kind: str = "llm_proposal",
    ) -> BehaviorSpec:
        proposed = self._registry.propose_behavior(
            spec,
            source_summary=source_summary,
            source_uri=source_uri,
            source_kind=source_kind,
        )
        self.refresh()
        return proposed

    def approve_behavior(
        self,
        behavior_name_or_id: str,
        *,
        approved_by: str = "",
        review_note: str = "",
        status: str = "active",
    ) -> BehaviorSpec | None:
        approved = self._registry.approve_behavior(
            behavior_name_or_id,
            approved_by=approved_by,
            review_note=review_note,
            status=status,
        )
        self.refresh()
        return approved

    def _load_active_cache(self) -> dict[str, BehaviorSpec]:
        if self._active_cache is None:
            self._active_cache = {
                spec.name: spec
                for spec in self._registry.list_behaviors(
                    status="active",
                    review_state="approved",
                )
            }
        return self._active_cache

    @staticmethod
    def _policy_domains(spec: BehaviorSpec) -> tuple[str, ...]:
        raw_domains = spec.applicable_context.get("policy_domains", [])
        if isinstance(raw_domains, str):
            return (raw_domains,)
        return tuple(str(item) for item in raw_domains)

    def _build_regulation_profile(self, spec: BehaviorSpec) -> RegulationBehaviorProfile:
        domains = self._policy_domains(spec)
        bootstrap_profile = spec.source_detail.get("bootstrap_profile", {})
        hint = str(bootstrap_profile.get("hint") or spec.description or spec.display_name)
        return RegulationBehaviorProfile(
            spec=spec,
            policy_domains=domains,
            hint=hint,
            cooldown_seconds=float(spec.cooldown_policy.get("seconds", 0.0) or 0.0),
            night_suppress=bool(spec.cooldown_policy.get("night_suppress", False)),
        )


__all__ = ["RuntimeBehaviorCatalog", "RegulationBehaviorProfile"]