"""
Tests for drive-regulation weighted scoring (Task 9.2).

Verifies that RegulationEngine computes final action scores using:
  final_score = 0.7 × emotional_deviation_score + 0.3 × drive_urgency_score

Requirements: 12.2, 12.3
"""

import pytest
from regulation import (
    RegulationEngine,
    ActionCandidate,
    DRIVE_ACTION_RELEVANCE,
)


class TestDriveRegulationScoring:
    """Tests for the weighted scoring formula combining emotion and drives."""

    def test_final_score_formula_with_drives(self):
        """Final score = 0.7 * emotional + 0.3 * (urgency * relevance)."""
        engine = RegulationEngine()

        candidate = ActionCandidate(
            action_type="browse",
            expected_benefit=0.4,
            confidence=0.6,
            memory_count=5,
            cooldown_ok=True,
            night_safe=True,
        )
        candidates = [candidate]

        # Curiosity drive with browse action (relevance = 1.0)
        engine._score_candidates_with_drives(candidates, drive_urgency=0.8, drive_dominant="curiosity")

        emotional_score = candidate.score  # 0.4 * (0.5 + 0.5*0.6) = 0.32
        relevance = DRIVE_ACTION_RELEVANCE["curiosity"]["browse"]  # 1.0
        drive_score = 0.8 * relevance  # 0.8
        expected_final = 0.7 * emotional_score + 0.3 * drive_score

        assert abs(candidate.final_score - expected_final) < 1e-9

    def test_zero_drive_urgency_means_pure_emotional(self):
        """When drive_urgency=0, final_score = 0.7 * emotional + 0.3 * 0."""
        engine = RegulationEngine()

        candidate = ActionCandidate(
            action_type="speak_care",
            expected_benefit=0.5,
            confidence=0.8,
            memory_count=10,
            cooldown_ok=True,
            night_safe=True,
        )
        candidates = [candidate]

        engine._score_candidates_with_drives(candidates, drive_urgency=0.0, drive_dominant="social")

        expected = 0.7 * candidate.score + 0.3 * 0.0
        assert abs(candidate.final_score - expected) < 1e-9

    def test_unknown_drive_gives_zero_relevance(self):
        """When drive_dominant is unknown, all relevance is 0."""
        engine = RegulationEngine()

        candidate = ActionCandidate(
            action_type="browse",
            expected_benefit=0.5,
            confidence=0.8,
            memory_count=10,
            cooldown_ok=True,
            night_safe=True,
        )
        candidates = [candidate]

        engine._score_candidates_with_drives(candidates, drive_urgency=0.9, drive_dominant="unknown_drive")

        # No relevance mapping, so drive_score = 0.9 * 0 = 0
        expected = 0.7 * candidate.score + 0.3 * 0.0
        assert abs(candidate.final_score - expected) < 1e-9

    def test_unrelated_action_gets_no_drive_boost(self):
        """Action not in the drive's relevance map gets 0 drive boost."""
        engine = RegulationEngine()

        # speak_complain is NOT in curiosity relevance map
        candidate = ActionCandidate(
            action_type="speak_complain",
            expected_benefit=0.3,
            confidence=0.5,
            memory_count=3,
            cooldown_ok=True,
            night_safe=True,
        )
        candidates = [candidate]

        engine._score_candidates_with_drives(candidates, drive_urgency=1.0, drive_dominant="curiosity")

        # speak_complain not relevant to curiosity → relevance = 0
        expected = 0.7 * candidate.score + 0.3 * 0.0
        assert abs(candidate.final_score - expected) < 1e-9

    def test_drive_influences_action_ranking(self):
        """Higher drive relevance should boost an action's ranking."""
        engine = RegulationEngine()

        # Two candidates with same emotional score
        browse = ActionCandidate(
            action_type="browse",
            expected_benefit=0.3,
            confidence=0.5,
            memory_count=5,
            cooldown_ok=True,
            night_safe=True,
        )
        speak_care = ActionCandidate(
            action_type="speak_care",
            expected_benefit=0.3,
            confidence=0.5,
            memory_count=5,
            cooldown_ok=True,
            night_safe=True,
        )
        candidates = [browse, speak_care]

        # With curiosity drive, browse (relevance=1.0) should outscore speak_care (relevance=0)
        engine._score_candidates_with_drives(candidates, drive_urgency=0.8, drive_dominant="curiosity")

        assert browse.final_score > speak_care.final_score

    def test_tick_accepts_drive_parameters(self):
        """RegulationEngine.tick() accepts drive_urgency and drive_dominant kwargs."""
        engine = RegulationEngine()
        panksepp = {"PANIC": 0.8, "SEEKING": 0.6, "FEAR": 0.5}
        valence = -0.4

        # Should not raise
        result = engine.tick(
            panksepp=panksepp,
            valence=valence,
            hour_of_day=14,
            drive_urgency=0.7,
            drive_dominant="social",
        )
        # Result can be None or an action string
        assert result is None or isinstance(result, str)

    def test_tick_backward_compatible_without_drives(self):
        """RegulationEngine.tick() still works without drive parameters."""
        engine = RegulationEngine()
        panksepp = {"PANIC": 0.8, "SEEKING": 0.6}
        valence = -0.4

        # Should not raise
        result = engine.tick(panksepp=panksepp, valence=valence, hour_of_day=14)
        assert result is None or isinstance(result, str)

    def test_weight_proportions_are_correct(self):
        """Emotional weight is 70% and drive weight is 30%."""
        engine = RegulationEngine()

        candidate = ActionCandidate(
            action_type="learn",
            expected_benefit=1.0,
            confidence=1.0,
            memory_count=10,
            cooldown_ok=True,
            night_safe=True,
        )
        candidates = [candidate]

        # learn has relevance 1.0 for curiosity
        engine._score_candidates_with_drives(candidates, drive_urgency=1.0, drive_dominant="curiosity")

        emotional_score = candidate.score  # 1.0 * (0.5 + 0.5*1.0) = 1.0
        # final = 0.7 * 1.0 + 0.3 * (1.0 * 1.0) = 0.7 + 0.3 = 1.0
        assert abs(candidate.final_score - 1.0) < 1e-9
