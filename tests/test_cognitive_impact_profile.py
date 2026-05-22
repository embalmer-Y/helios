"""
Tests for CognitiveImpactProfile dataclass and feed_from_impact method.

Validates: Requirements 27.1, 27.2, 27.3, 27.4, 27.5, 27.6
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognition.phi import CognitiveImpactProfile, AdaptiveAlphaICRI


class TestCognitiveImpactProfile:
    """Tests for CognitiveImpactProfile dataclass."""

    def test_creation_with_valid_values(self):
        """CognitiveImpactProfile stores four dimensions correctly."""
        profile = CognitiveImpactProfile(sensory=0.3, cognitive=0.5, self_=0.6, novelty=0.4)
        assert profile.sensory == 0.3
        assert profile.cognitive == 0.5
        assert profile.self_ == 0.6
        assert profile.novelty == 0.4

    def test_clamping_above_one(self):
        """Values above 1.0 are clamped to 1.0."""
        profile = CognitiveImpactProfile(sensory=1.5, cognitive=2.0, self_=1.1, novelty=3.0)
        assert profile.sensory == 1.0
        assert profile.cognitive == 1.0
        assert profile.self_ == 1.0
        assert profile.novelty == 1.0

    def test_clamping_below_zero(self):
        """Values below 0.0 are clamped to 0.0."""
        profile = CognitiveImpactProfile(sensory=-0.5, cognitive=-1.0, self_=-0.1, novelty=-2.0)
        assert profile.sensory == 0.0
        assert profile.cognitive == 0.0
        assert profile.self_ == 0.0
        assert profile.novelty == 0.0

    def test_default_values(self):
        """Default values are all 0.0."""
        profile = CognitiveImpactProfile()
        assert profile.sensory == 0.0
        assert profile.cognitive == 0.0
        assert profile.self_ == 0.0
        assert profile.novelty == 0.0


class TestFeedFromImpact:
    """Tests for AdaptiveAlphaICRI.feed_from_impact() method."""

    def test_sensory_maps_to_sensory_integration(self):
        """sensory dimension feeds sensory_integration source."""
        icri = AdaptiveAlphaICRI()
        profile = CognitiveImpactProfile(sensory=0.7, cognitive=0.0, self_=0.0, novelty=0.0)
        icri.feed_from_impact(profile)
        assert icri._sources["sensory_integration"] == 0.7

    def test_cognitive_maps_to_dmn_depth(self):
        """cognitive dimension feeds dmn_depth source."""
        icri = AdaptiveAlphaICRI()
        profile = CognitiveImpactProfile(sensory=0.0, cognitive=0.8, self_=0.0, novelty=0.0)
        icri.feed_from_impact(profile)
        assert icri._sources["dmn_depth"] == 0.8

    def test_self_maps_to_self_reflection(self):
        """self_ dimension feeds self_reflection source."""
        icri = AdaptiveAlphaICRI()
        profile = CognitiveImpactProfile(sensory=0.0, cognitive=0.0, self_=0.6, novelty=0.0)
        icri.feed_from_impact(profile)
        assert icri._sources["self_reflection"] == 0.6

    def test_novelty_maps_to_global_ignition(self):
        """novelty dimension feeds global_ignition source."""
        icri = AdaptiveAlphaICRI()
        profile = CognitiveImpactProfile(sensory=0.0, cognitive=0.0, self_=0.0, novelty=0.9)
        icri.feed_from_impact(profile)
        assert icri._sources["global_ignition"] == 0.9

    def test_all_dimensions_fed_simultaneously(self):
        """All four dimensions are fed in a single call."""
        icri = AdaptiveAlphaICRI()
        profile = CognitiveImpactProfile(sensory=0.3, cognitive=0.5, self_=0.6, novelty=0.4)
        icri.feed_from_impact(profile)
        assert icri._sources["sensory_integration"] == 0.3
        assert icri._sources["dmn_depth"] == 0.5
        assert icri._sources["self_reflection"] == 0.6
        assert icri._sources["global_ignition"] == 0.4

    def test_ttls_reset_on_feed(self):
        """Source TTLs are reset to DEFAULT_TTL for all fed sources."""
        icri = AdaptiveAlphaICRI()
        # Simulate TTL decay
        for key in icri._source_ttl:
            icri._source_ttl[key] = 0.0

        profile = CognitiveImpactProfile(sensory=0.3, cognitive=0.5, self_=0.6, novelty=0.4)
        icri.feed_from_impact(profile)

        assert icri._source_ttl["sensory_integration"] == icri.DEFAULT_TTL
        assert icri._source_ttl["dmn_depth"] == icri.DEFAULT_TTL
        assert icri._source_ttl["self_reflection"] == icri.DEFAULT_TTL
        assert icri._source_ttl["global_ignition"] == icri.DEFAULT_TTL

    def test_fallback_approximation_methods_still_work(self):
        """Existing approximation methods work when no CognitiveImpactProfile is available."""
        icri = AdaptiveAlphaICRI()
        # Use existing approximation methods (fallback path)
        icri.feed_dmn_from_thinking("deep", 3)
        icri.feed_self_model_from_personality({"openness": 0.8, "neuroticism": 0.6})
        icri.feed_ignition_from_panksepp({"SEEKING": 0.5, "PLAY": 0.4, "CARE": 0.3})
        icri.feed_sensory(0.4)

        assert icri._sources["dmn_depth"] > 0
        assert icri._sources["self_reflection"] > 0
        assert icri._sources["global_ignition"] > 0
        assert icri._sources["sensory_integration"] == 0.4

    def test_impact_overrides_previous_approximation(self):
        """feed_from_impact overrides values set by approximation methods."""
        icri = AdaptiveAlphaICRI()
        # First use approximation
        icri.feed_dmn_from_thinking("deep", 5)
        old_dmn = icri._sources["dmn_depth"]
        assert old_dmn > 0

        # Then feed from impact - should override
        profile = CognitiveImpactProfile(sensory=0.1, cognitive=0.2, self_=0.3, novelty=0.4)
        icri.feed_from_impact(profile)
        assert icri._sources["dmn_depth"] == 0.2

    def test_aggregate_uses_impact_fed_sources(self):
        """After feed_from_impact, aggregate() uses the fed source values."""
        icri = AdaptiveAlphaICRI()
        profile = CognitiveImpactProfile(sensory=0.8, cognitive=0.7, self_=0.6, novelty=0.5)
        icri.feed_from_impact(profile)
        # Also feed emotional coherence so we have all sources
        icri.feed_emotional({"SEEKING": 0.5, "PLAY": 0.4})

        result = icri.aggregate(max_event_intensity=0.5)
        assert result > 0.0  # ICRI should be non-zero with active sources
