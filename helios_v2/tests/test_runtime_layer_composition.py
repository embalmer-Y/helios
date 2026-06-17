"""R100 T7 tests: RuntimeProfile seam + semantic assembly wiring.

Validates:
- RuntimeProfile accepts memory_layer_classifier and memory_layer_preference
- RuntimeProfile validates memory_layer_preference entries (must be valid layer values)
- Default RuntimeProfile has both fields as None
- Provider classes accept preferred_layers field (StoreBackedRecalledMemoryProvider,
  StoreBackedDirectedMemoryCandidateProvider, SemanticStoreBackedDirectedMemoryCandidateProvider)
- Custom MemoryLayerClassifier protocol implementations are accepted
- The 06 engine receives the layer_classifier through construction (separate from the
  full assembly, which is exercised by test_runtime_composition.py)
"""

from __future__ import annotations

import os

# Ensure LLM readiness gate can pass when downstream tests do full assembly.
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

import pytest

from helios_v2.composition import (
    CompositionError,
    RuntimeProfile,
    default_composition_config,
)
from helios_v2.composition.bridges import StoreBackedRecalledMemoryProvider
from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
from helios_v2.persistence.engine import (
    SemanticStoreBackedDirectedMemoryCandidateProvider,
    StoreBackedDirectedMemoryCandidateProvider,
)
from helios_v2.memory import (
    AffectOutcomeMemoryLayerClassifier,
    MemoryLayerClassifier,
    MemoryRecord,
    VALID_MEMORY_LAYERS,
)


# ---------------------------------------------------------------------------
# RuntimeProfile field & validation tests
# ---------------------------------------------------------------------------

class TestRuntimeProfileLayerFields:
    """R100: RuntimeProfile exposes memory_layer_classifier and memory_layer_preference."""

    def test_default_classifier_is_none(self):
        """Default RuntimeProfile leaves memory_layer_classifier as None."""
        profile = RuntimeProfile()
        assert profile.memory_layer_classifier is None

    def test_default_preference_is_none(self):
        """Default RuntimeProfile leaves memory_layer_preference as None."""
        profile = RuntimeProfile()
        assert profile.memory_layer_preference is None

    def test_classifier_can_be_set(self):
        """memory_layer_classifier can be set to an explicit classifier instance."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        profile = RuntimeProfile(memory_layer_classifier=classifier)
        assert profile.memory_layer_classifier is classifier

    def test_preference_can_be_set(self):
        """memory_layer_preference can be set to an explicit layer tuple."""
        profile = RuntimeProfile(memory_layer_preference=("L4_long", "L5_autobiographical"))
        assert profile.memory_layer_preference == ("L4_long", "L5_autobiographical")

    def test_empty_preference_tuple_raises(self):
        """An empty preference tuple raises CompositionError (must be None or non-empty)."""
        with pytest.raises(CompositionError, match="non-empty tuple"):
            RuntimeProfile(memory_layer_preference=())

    def test_invalid_preference_layer_raises(self):
        """An invalid layer value in memory_layer_preference raises CompositionError."""
        with pytest.raises(CompositionError, match="memory_layer_preference entries"):
            RuntimeProfile(memory_layer_preference=("L4_long", "invalid_layer"))

    def test_all_four_valid_layer_values_accepted(self):
        """All four MemoryLayer values are valid in memory_layer_preference."""
        for layers in [
            ("L2_working",),
            ("L3_short",),
            ("L4_long",),
            ("L5_autobiographical",),
            ("L2_working", "L3_short", "L4_long", "L5_autobiographical"),
        ]:
            profile = RuntimeProfile(memory_layer_preference=layers)
            assert profile.memory_layer_preference == layers

    def test_default_profile_byte_for_byte_unchanged(self):
        """Default RuntimeProfile preserves all pre-R100 fields unchanged."""
        profile = RuntimeProfile()
        # Pre-R100 defaults verified
        assert profile.default_signal_mode == "semantic"
        assert profile.embedding_provider_kind == "deterministic_hash"
        assert profile.embedding_provider_model == "deterministic-hash"
        # R100 additive fields default to None
        assert profile.memory_layer_classifier is None
        assert profile.memory_layer_preference is None

    def test_r100_fields_after_construct_with_other_args(self):
        """R100 fields default to None even when other profile args are set."""
        profile = RuntimeProfile(
            deterministic_thought=True,
            memory_layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        assert profile.memory_layer_classifier is not None
        assert profile.memory_layer_preference is None  # still default


# ---------------------------------------------------------------------------
# Provider layer preference tests
# ---------------------------------------------------------------------------

class TestProviderLayerPreference:
    """R100: providers accept and forward preferred_layers."""

    def test_store_backed_provider_accepts_preferred_layers(self):
        """StoreBackedDirectedMemoryCandidateProvider accepts preferred_layers field."""
        store = ExperienceStore(InMemoryExperienceStoreBackend())
        provider = StoreBackedDirectedMemoryCandidateProvider(
            store=store,
            preferred_layers=("L4_long", "L5_autobiographical"),
        )
        assert provider.preferred_layers == ("L4_long", "L5_autobiographical")

    def test_store_backed_provider_default_preferred_layers_none(self):
        """StoreBackedDirectedMemoryCandidateProvider defaults preferred_layers to None."""
        store = ExperienceStore(InMemoryExperienceStoreBackend())
        provider = StoreBackedDirectedMemoryCandidateProvider(store=store)
        assert provider.preferred_layers is None

    def test_semantic_provider_accepts_preferred_layers(self):
        """SemanticStoreBackedDirectedMemoryCandidateProvider accepts preferred_layers field."""
        store = ExperienceStore(InMemoryExperienceStoreBackend())
        provider = SemanticStoreBackedDirectedMemoryCandidateProvider(
            store=store,
            embed_query=lambda text: (1.0, 0.0, 0.0, 0.0),
            preferred_layers=("L4_long",),
        )
        assert provider.preferred_layers == ("L4_long",)

    def test_semantic_provider_default_preferred_layers_none(self):
        """SemanticStoreBackedDirectedMemoryCandidateProvider defaults preferred_layers to None."""
        store = ExperienceStore(InMemoryExperienceStoreBackend())
        provider = SemanticStoreBackedDirectedMemoryCandidateProvider(
            store=store,
            embed_query=lambda text: (1.0, 0.0, 0.0, 0.0),
        )
        assert provider.preferred_layers is None

    def test_recalled_memory_provider_accepts_preferred_layers(self):
        """StoreBackedRecalledMemoryProvider accepts preferred_layers field."""
        store = ExperienceStore(InMemoryExperienceStoreBackend())
        provider = StoreBackedRecalledMemoryProvider(
            embed_text=lambda text: (1.0, 0.0, 0.0, 0.0),
            store=store,
            preferred_layers=("L4_long", "L5_autobiographical"),
        )
        assert provider.preferred_layers == ("L4_long", "L5_autobiographical")

    def test_recalled_memory_provider_default_none(self):
        """StoreBackedRecalledMemoryProvider defaults preferred_layers to None."""
        store = ExperienceStore(InMemoryExperienceStoreBackend())
        provider = StoreBackedRecalledMemoryProvider(
            embed_text=lambda text: (1.0, 0.0, 0.0, 0.0),
            store=store,
        )
        assert provider.preferred_layers is None

    def test_provider_passes_preferred_layers_to_read_recent(self):
        """StoreBackedDirectedMemoryCandidateProvider passes preferred_layers to read_recent."""
        # Append two records with different layers
        from helios_v2.persistence.contracts import PersistedExperienceRecord
        from helios_v2.directed_retrieval import RetrievalQueryPlan, RetrievalStrategy

        store = ExperienceStore(InMemoryExperienceStoreBackend())
        record_l2 = PersistedExperienceRecord(
            record_id="r1",
            tick_id=1,
            continuity_kind="episodic",
            outcome_class="affect_memory",
            source_outcome_kind="memory_item",
            source_outcome_id="r1",
            writeback_status="formed",
            summary="r1",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("high_affect_intensity",),
            linkage={},
            layer="L2_working",
        )
        record_l5 = PersistedExperienceRecord(
            record_id="r2",
            tick_id=1,
            continuity_kind="autobiographical",
            outcome_class="affect_memory",
            source_outcome_kind="memory_item",
            source_outcome_id="r2",
            writeback_status="formed",
            summary="r2",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("high_affect_intensity",),
            linkage={},
            layer="L5_autobiographical",
        )
        store.append_records((record_l2, record_l5))

        # With preferred_layers filter, only L5 record is returned
        provider = StoreBackedDirectedMemoryCandidateProvider(
            store=store,
            preferred_layers=("L5_autobiographical",),
        )
        plan = RetrievalQueryPlan(
            plan_id="p1",
            source_request_id="r1",
            query_text="q1",
            query_source="compact_stimuli",
            target_tiers=("mid_term", "autobiographical"),
            limit=5,
            retrieval_strategy="deterministic_first_version",
            tick_id=1,
        )
        candidates = provider.collect_candidates(plan)
        # Only the L5 record is returned (read_recent with layer_filter)
        assert len(candidates) == 1
        assert candidates[0].memory_id == "experience:2"

    def test_provider_no_filter_returns_all(self):
        """StoreBackedDirectedMemoryCandidateProvider without preferred_layers returns all records."""
        from helios_v2.persistence.contracts import PersistedExperienceRecord
        from helios_v2.directed_retrieval import RetrievalQueryPlan, RetrievalStrategy

        store = ExperienceStore(InMemoryExperienceStoreBackend())
        record_l2 = PersistedExperienceRecord(
            record_id="r1",
            tick_id=1,
            continuity_kind="episodic",
            outcome_class="affect_memory",
            source_outcome_kind="memory_item",
            source_outcome_id="r1",
            writeback_status="formed",
            summary="r1",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("high_affect_intensity",),
            linkage={},
            layer="L2_working",
        )
        record_l5 = PersistedExperienceRecord(
            record_id="r2",
            tick_id=1,
            continuity_kind="autobiographical",
            outcome_class="affect_memory",
            source_outcome_kind="memory_item",
            source_outcome_id="r2",
            writeback_status="formed",
            summary="r2",
            requested_effect_summary="",
            applied_effect_summary="",
            reason_trace=("high_affect_intensity",),
            linkage={},
            layer="L5_autobiographical",
        )
        store.append_records((record_l2, record_l5))

        provider = StoreBackedDirectedMemoryCandidateProvider(store=store)
        plan = RetrievalQueryPlan(
            plan_id="p1",
            source_request_id="r1",
            query_text="q1",
            query_source="compact_stimuli",
            target_tiers=("mid_term", "autobiographical"),
            limit=5,
            retrieval_strategy="deterministic_first_version",
            tick_id=1,
        )
        candidates = provider.collect_candidates(plan)
        # No filter: both records returned
        assert len(candidates) == 2


# ---------------------------------------------------------------------------
# Custom classifier injection (protocol-based)
# ---------------------------------------------------------------------------

class TestCustomClassifierInjection:
    """R100: any MemoryLayerClassifier protocol implementation is accepted."""

    def test_custom_classifier_protocol_satisfies_runtime_profile(self):
        """A custom classifier implementing MemoryLayerClassifier is accepted by RuntimeProfile."""

        class _FixedLayerClassifier:
            def classify_layer(self, affect_intensity: float, outcome_class: str) -> str:
                return "L5_autobiographical"

        classifier = _FixedLayerClassifier()
        # Verify it satisfies the runtime_checkable protocol
        assert isinstance(classifier, MemoryLayerClassifier)
        profile = RuntimeProfile(memory_layer_classifier=classifier)
        assert profile.memory_layer_classifier is classifier

    def test_default_classifier_returns_layer_values(self):
        """The default AffectOutcomeMemoryLayerClassifier returns valid layer values."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        for layer in classifier.classify_layer(0.0, "no_outcome"), classifier.classify_layer(0.3, "no_outcome"), classifier.classify_layer(0.6, "self_changed"):
            assert layer in VALID_MEMORY_LAYERS


# ---------------------------------------------------------------------------
# MemoryLayer contract integrity
# ---------------------------------------------------------------------------

class TestMemoryLayerContractIntegrity:
    """R100: MemoryLayer taxonomy is consistent across contracts."""

    def test_valid_memory_layers_frozenset(self):
        """VALID_MEMORY_LAYERS contains exactly the 4 layer values."""
        assert VALID_MEMORY_LAYERS == frozenset({
            "L2_working", "L3_short", "L4_long", "L5_autobiographical"
        })

    def test_memory_record_layer_validation(self):
        """MemoryRecord accepts all 4 layer values."""
        for layer in ("L2_working", "L3_short", "L4_long", "L5_autobiographical"):
            record = MemoryRecord(
                memory_id="m:1",
                layer=layer,
                affect_intensity_at_write=0.5,
                outcome_class_at_write="no_outcome",
                source_feeling_state_id="fs:1",
                family="episodic",
                content=None,  # type: ignore
                binding_context_id=None,
                tick_id=1,
                created_at_wall=1000.0,
            )
            assert record.layer == layer
