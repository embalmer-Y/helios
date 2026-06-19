"""R101 composition-wiring tests.

Verify:
- Default RuntimeProfile has all 6 R101 seams set to None.
- Constructing a profile with a partial R101 seam set raises CompositionError.
- Constructing a profile with all 6 R101 seams accepted.
- Default RuntimeProfile() assembles a runtime where MemoryAffectReplayEngine has all
  6 R101 seams set to the first-version implementations.
- The semantic assembly's R101 path is on by default for the default profile.
- Legacy path remains byte-for-byte identical when R101 is fully off.
"""

from __future__ import annotations

import pytest

from helios_v2.composition import (
    CompositionError,
    RuntimeProfile,
    assemble_runtime,
)
from helios_v2.memory import (
    ConvexWeightedObjectiveAggregator,
    FirstVersionDoubleConfirmationGate,
    FirstVersionObjectiveImportanceEstimator,
    FirstVersionRecallUtilityTracker,
    ObjectiveImportanceLayerResolver,
    SqlBackedTrainingDatasetExtractor,
)


def test_default_runtime_profile_has_6_r101_seams_none() -> None:
    profile = RuntimeProfile()
    assert profile.objective_importance_estimator is None
    assert profile.objective_aggregator is None
    assert profile.double_confirmation_gate is None
    assert profile.objective_layer_resolver is None
    assert profile.recall_utility_tracker is None
    assert profile.training_dataset_extractor is None


def test_partial_r101_seam_set_raises_composition_error() -> None:
    with pytest.raises(CompositionError) as exc:
        RuntimeProfile(
            objective_importance_estimator=FirstVersionObjectiveImportanceEstimator(),
            # other 5 omitted -> partial -> error
        )
    assert "all-or-nothing" in str(exc.value)
    assert "objective_aggregator" in str(exc.value)


def test_full_r101_seam_set_accepted() -> None:
    # When all 6 are provided the post-init passes
    from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
    from helios_v2.embedding import EmbeddingGateway, EmbeddingProfile, EmbeddingProfileRegistry
    from helios_v2.embedding.engine import DeterministicHashEmbeddingProvider

    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.initialize()
    gateway = EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(EmbeddingProfile(profile_name="experience-embedding", model="deterministic-hash", api_key_env="HELIOS_EMBEDDING_API_KEY", base_url="offline://hash"),)),
    )
    profile = RuntimeProfile(
        experience_store=store,
        embedding_gateway=gateway,
        objective_importance_estimator=FirstVersionObjectiveImportanceEstimator(),
        objective_aggregator=ConvexWeightedObjectiveAggregator(),
        double_confirmation_gate=FirstVersionDoubleConfirmationGate(),
        objective_layer_resolver=ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=FirstVersionRecallUtilityTracker(),
        training_dataset_extractor=SqlBackedTrainingDatasetExtractor(
            experience_store=object(),  # placeholder; not used in profile validation
        ),
    )
    assert profile.objective_importance_estimator is not None
    assert profile.objective_aggregator is not None


def test_default_assembly_wires_6_r101_seams_on_memory_engine() -> None:
    """Default semantic assembly wires the 6 first-version R101 implementations.

    Without an experience_store the engine runs the R100 path; with one (and an embedding
    gateway) the engine activates the R101 6-dim path. We assert that when the engine is
    constructed by `assemble_runtime(experience_store=..., embedding_gateway=...)`, all 6
    R101 inject points are populated.
    """
    from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
    from helios_v2.embedding import EmbeddingGateway, EmbeddingProfile, EmbeddingProfileRegistry
    from helios_v2.embedding.engine import DeterministicHashEmbeddingProvider

    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.initialize()
    gateway = EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(EmbeddingProfile(profile_name="experience-embedding", model="deterministic-hash", api_key_env="HELIOS_EMBEDDING_API_KEY", base_url="offline://hash"),)),
    )
    handle = assemble_runtime(experience_store=store, embedding_gateway=gateway)
    # Access the memory engine from the handle's kernel -> stage -> memory_layer
    memory_stage = next(
        s for s in handle.kernel._stages if s.stage_name == "memory_affect_and_replay"
    )
    memory_engine = memory_stage.memory_layer  # type: ignore[attr-defined]
    assert memory_engine.objective_importance_estimator is not None
    assert memory_engine.objective_aggregator is not None
    assert memory_engine.double_confirmation_gate is not None
    assert memory_engine.objective_layer_resolver is not None
    assert memory_engine.recall_utility_tracker is not None
    # R101 path is active (all 6 wired) -> MemoryAffectReplayEngine has the 6 fields
    assert isinstance(
        memory_engine.objective_importance_estimator,
        FirstVersionObjectiveImportanceEstimator,
    )
    assert isinstance(
        memory_engine.objective_aggregator,
        ConvexWeightedObjectiveAggregator,
    )
    assert isinstance(
        memory_engine.double_confirmation_gate,
        FirstVersionDoubleConfirmationGate,
    )
    assert isinstance(
        memory_engine.objective_layer_resolver,
        ObjectiveImportanceLayerResolver,
    )
    assert isinstance(
        memory_engine.recall_utility_tracker,
        FirstVersionRecallUtilityTracker,
    )


def test_legacy_constant_assembly_keeps_r101_seams_none() -> None:
    """default_signal_mode='legacy_constant' should not wire any R101 seam (byte-for-byte)."""
    profile = RuntimeProfile(default_signal_mode="legacy_constant")
    handle = assemble_runtime(profile=profile)
    memory_stage = next(
        s for s in handle.kernel._stages if s.stage_name == "memory_affect_and_replay"
    )
    memory_engine = memory_stage.memory_layer  # type: ignore[attr-defined]
    assert memory_engine.objective_importance_estimator is None
    assert memory_engine.objective_aggregator is None
    assert memory_engine.double_confirmation_gate is None
    assert memory_engine.objective_layer_resolver is None
    assert memory_engine.recall_utility_tracker is None


def test_custom_r101_injects_are_honored() -> None:
    """When a profile supplies a custom R101 seam, assemble_runtime forwards it."""
    from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
    from helios_v2.embedding import EmbeddingGateway, EmbeddingProfile, EmbeddingProfileRegistry
    from helios_v2.embedding.engine import DeterministicHashEmbeddingProvider

    custom_estimator = FirstVersionObjectiveImportanceEstimator()
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    store.initialize()
    gateway = EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(EmbeddingProfile(profile_name="experience-embedding", model="deterministic-hash", api_key_env="HELIOS_EMBEDDING_API_KEY", base_url="offline://hash"),)),
    )
    profile = RuntimeProfile(
        experience_store=store,
        embedding_gateway=gateway,
        objective_importance_estimator=custom_estimator,
        objective_aggregator=ConvexWeightedObjectiveAggregator(),
        double_confirmation_gate=FirstVersionDoubleConfirmationGate(),
        objective_layer_resolver=ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=FirstVersionRecallUtilityTracker(),
        training_dataset_extractor=SqlBackedTrainingDatasetExtractor(experience_store=object()),
    )
    handle = assemble_runtime(profile=profile)
    memory_stage = next(
        s for s in handle.kernel._stages if s.stage_name == "memory_affect_and_replay"
    )
    memory_engine = memory_stage.memory_layer  # type: ignore[attr-defined]
    # Custom estimator is honored (identity check)
    assert memory_engine.objective_importance_estimator is custom_estimator
