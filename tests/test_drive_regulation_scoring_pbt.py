"""Property-based tests for drive-regulation weighted scoring.

# Feature: helios-architecture-enhancement, Property 11: Drive-Regulation Weighted Scoring

**Validates: Requirements 12.2, 12.3**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    floats,
    lists,
    sampled_from,
    composite,
)

from regulation import (
    RegulationEngine,
    ActionCandidate,
    DRIVE_ACTION_RELEVANCE,
    AVAILABLE_ACTIONS,
)


# ═══════════════════════════════════════════════
# Strategies
# ═══════════════════════════════════════════════

# All action types available in the system
ACTION_TYPES = list(AVAILABLE_ACTIONS.keys())

# All known drive names
DRIVE_NAMES = list(DRIVE_ACTION_RELEVANCE.keys()) + ["unknown_drive", ""]

# Strategy for expected_benefit and confidence in valid ranges
benefit_strategy = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
confidence_strategy = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
drive_urgency_strategy = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@composite
def action_candidate_strategy(draw):
    """Generate a random ActionCandidate with valid parameters."""
    action_type = draw(sampled_from(ACTION_TYPES))
    expected_benefit = draw(benefit_strategy)
    confidence = draw(confidence_strategy)
    return ActionCandidate(
        action_type=action_type,
        expected_benefit=expected_benefit,
        confidence=confidence,
        memory_count=5,
        cooldown_ok=True,
        night_safe=True,
    )


# ═══════════════════════════════════════════════
# Property 11: Drive-Regulation Weighted Scoring
# ═══════════════════════════════════════════════


class TestDriveRegulationWeightedScoringProperty:
    """Property 11: For any candidate action evaluation, the final score
    SHALL equal 0.7 × emotional_deviation_score + 0.3 × drive_urgency_score.
    """

    @given(
        candidate=action_candidate_strategy(),
        drive_urgency=drive_urgency_strategy,
        drive_dominant=sampled_from(DRIVE_NAMES),
    )
    @settings(max_examples=300)
    def test_final_score_equals_weighted_combination(self, candidate, drive_urgency, drive_dominant):
        """For any candidate, final_score = 0.7 * emotional_deviation_score + 0.3 * drive_urgency_score.

        **Validates: Requirements 12.2, 12.3**
        """
        engine = RegulationEngine()
        candidates = [candidate]

        engine._score_candidates_with_drives(candidates, drive_urgency, drive_dominant)

        # Compute expected values independently
        emotional_score = candidate.score  # expected_benefit * (0.5 + 0.5 * confidence)
        relevance = DRIVE_ACTION_RELEVANCE.get(drive_dominant, {}).get(candidate.action_type, 0.0)
        drive_score = drive_urgency * relevance
        expected_final = 0.7 * emotional_score + 0.3 * drive_score

        assert abs(candidate.final_score - expected_final) < 1e-9, (
            f"action={candidate.action_type}, drive={drive_dominant}, urgency={drive_urgency:.4f}, "
            f"emotional={emotional_score:.6f}, relevance={relevance}, drive_score={drive_score:.6f}, "
            f"expected_final={expected_final:.9f}, got={candidate.final_score:.9f}"
        )

    @given(
        candidate=action_candidate_strategy(),
        drive_urgency=drive_urgency_strategy,
        drive_dominant=sampled_from(DRIVE_NAMES),
    )
    @settings(max_examples=200)
    def test_emotional_weight_is_seventy_percent(self, candidate, drive_urgency, drive_dominant):
        """The emotional component contributes exactly 70% of its value to final_score.

        **Validates: Requirements 12.3**
        """
        engine = RegulationEngine()
        candidates = [candidate]

        engine._score_candidates_with_drives(candidates, drive_urgency, drive_dominant)

        emotional_score = candidate.score
        relevance = DRIVE_ACTION_RELEVANCE.get(drive_dominant, {}).get(candidate.action_type, 0.0)
        drive_score = drive_urgency * relevance

        # Isolate the emotional contribution
        emotional_contribution = candidate.final_score - 0.3 * drive_score
        expected_emotional_contribution = 0.7 * emotional_score

        assert abs(emotional_contribution - expected_emotional_contribution) < 1e-9, (
            f"Emotional contribution mismatch: expected {expected_emotional_contribution:.9f}, "
            f"got {emotional_contribution:.9f}"
        )

    @given(
        candidate=action_candidate_strategy(),
        drive_urgency=drive_urgency_strategy,
        drive_dominant=sampled_from(DRIVE_NAMES),
    )
    @settings(max_examples=200)
    def test_drive_weight_is_thirty_percent(self, candidate, drive_urgency, drive_dominant):
        """The drive component contributes exactly 30% of its value to final_score.

        **Validates: Requirements 12.2**
        """
        engine = RegulationEngine()
        candidates = [candidate]

        engine._score_candidates_with_drives(candidates, drive_urgency, drive_dominant)

        emotional_score = candidate.score
        relevance = DRIVE_ACTION_RELEVANCE.get(drive_dominant, {}).get(candidate.action_type, 0.0)
        drive_score = drive_urgency * relevance

        # Isolate the drive contribution
        drive_contribution = candidate.final_score - 0.7 * emotional_score
        expected_drive_contribution = 0.3 * drive_score

        assert abs(drive_contribution - expected_drive_contribution) < 1e-9, (
            f"Drive contribution mismatch: expected {expected_drive_contribution:.9f}, "
            f"got {drive_contribution:.9f}"
        )

    @given(
        candidates=lists(action_candidate_strategy(), min_size=2, max_size=10),
        drive_urgency=drive_urgency_strategy,
        drive_dominant=sampled_from(DRIVE_NAMES),
    )
    @settings(max_examples=200)
    def test_formula_holds_for_all_candidates_in_batch(self, candidates, drive_urgency, drive_dominant):
        """The formula holds for every candidate in a batch scored together.

        **Validates: Requirements 12.2, 12.3**
        """
        engine = RegulationEngine()

        engine._score_candidates_with_drives(candidates, drive_urgency, drive_dominant)

        for candidate in candidates:
            emotional_score = candidate.score
            relevance = DRIVE_ACTION_RELEVANCE.get(drive_dominant, {}).get(candidate.action_type, 0.0)
            drive_score = drive_urgency * relevance
            expected_final = 0.7 * emotional_score + 0.3 * drive_score

            assert abs(candidate.final_score - expected_final) < 1e-9, (
                f"Batch scoring failed for action={candidate.action_type}: "
                f"expected {expected_final:.9f}, got {candidate.final_score:.9f}"
            )
