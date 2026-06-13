"""R82: standard production assembly (persistence-by-default) tests.

Network-free: a ready fake LLM gateway is injected and no embedding credential is set, so the
production embedding gateway falls back to the deterministic-hash provider. Durable SQLite files
are written under a pytest tmp directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from helios_v2.composition import (
    DEFAULT_PRODUCTION_DATA_DIR,
    assemble_production_runtime,
    default_composition_config,
)
from helios_v2.composition.runtime_assembly import _production_embedding_gateway
from helios_v2.embedding import DeterministicHashEmbeddingProvider, OpenAICompatibleEmbeddingProvider
from helios_v2.llm import LlmGateway, LlmProfileRegistry, ProviderCompletion
from helios_v2.persistence import ExperienceStore, SqliteExperienceStoreBackend
from helios_v2.continuity_checkpoint import ContinuityCheckpointStore, SqliteCheckpointBackend


@dataclass
class _FakeThoughtProvider:
    """Network-free provider returning a valid structured thought envelope."""

    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "a production thought for the current cycle",
            "sufficiency": 0.9,
            "wants_to_continue": False,
            "continue_reason": "",
            "proposed_action": {"intends_action": True, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _ready_gateway() -> LlmGateway:
    config = default_composition_config()
    return LlmGateway(
        provider=_FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def test_production_assembly_defaults_persistence_on(tmp_path) -> None:
    handle = assemble_production_runtime(data_dir=str(tmp_path), gateway=_ready_gateway())

    # Durable infrastructure is on by default.
    assert handle.experience_store is not None
    assert handle.continuity_checkpoint is not None

    # The three durable critical dependencies are registered.
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert "experience_store_ready" in spec_names
    assert "embedding_profile_ready" in spec_names
    assert "continuity_checkpoint_ready" in spec_names

    # Starts up and runs offline.
    handle.startup()
    handle.run_ticks(3)
    assert handle.experience_store.count() > 0

    # The SQLite files were created under the data dir.
    assert (tmp_path / "experience_store.sqlite3").exists()
    assert (tmp_path / "continuity_checkpoint.sqlite3").exists()


def test_production_assembly_cross_restart_continuity(tmp_path) -> None:
    data_dir = str(tmp_path)

    # Session A: run ticks against a fresh data dir, then drop the handle.
    handle_a = assemble_production_runtime(data_dir=data_dir, gateway=_ready_gateway())
    handle_a.startup()
    handle_a.run_ticks(4)
    count_after_a = handle_a.experience_store.count()
    assert count_after_a > 0
    del handle_a

    # Independently confirm the durable files hold prior state across a fresh store/checkpoint object.
    store_b = ExperienceStore(
        backend=SqliteExperienceStoreBackend(db_path=str(tmp_path / "experience_store.sqlite3"))
    )
    assert store_b.count() == count_after_a  # experience survived the restart
    ckpt_b = ContinuityCheckpointStore(
        backend=SqliteCheckpointBackend(db_path=str(tmp_path / "continuity_checkpoint.sqlite3"))
    )
    assert ckpt_b.load_latest() is not None  # a prior continuity/affect snapshot survived

    # Session B: a fresh production runtime on the same data dir resumes and keeps accumulating.
    handle_b = assemble_production_runtime(data_dir=data_dir, gateway=_ready_gateway())
    handle_b.startup()
    handle_b.run_ticks(2)
    assert handle_b.experience_store.count() > count_after_a  # continued from the prior session


def test_production_embedding_gateway_offline_uses_hash_provider() -> None:
    # No embedding credential -> network-free deterministic-hash provider.
    gateway = _production_embedding_gateway(env={})
    assert isinstance(gateway.provider, DeterministicHashEmbeddingProvider)


def test_production_embedding_gateway_uses_openai_when_credential_present() -> None:
    # A credential -> real OpenAI-compatible provider, bound to the experience-embedding profile.
    gateway = _production_embedding_gateway(
        env={
            "HELIOS_EMBEDDING_API_KEY": "sk-emb",
            "HELIOS_EMBEDDING_MODEL": "text-embedding-3-large",
            "HELIOS_EMBEDDING_BASE_URL": "https://example.test/v1",
        }
    )
    assert isinstance(gateway.provider, OpenAICompatibleEmbeddingProvider)
    report = gateway.check_static_readiness(("experience-embedding",))
    assert report.entries[0].static_ready


def test_default_production_data_dir_is_data() -> None:
    assert DEFAULT_PRODUCTION_DATA_DIR == "data"
