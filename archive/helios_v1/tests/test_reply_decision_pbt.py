"""Property-based tests for ResponsePipeline reply decision threshold.

# Feature: helios-architecture-enhancement, Property 6: Reply Decision Threshold

**Validates: Requirements 7.1**
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import floats, fixed_dictionaries, just

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.response_pipeline import ResponsePipeline


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------

# SEC scores are floats in [0, 1] range (standard SEC evaluation output)
sec_score = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


# ------------------------------------------------------------------
# Property 6: Reply Decision Threshold
# ------------------------------------------------------------------


class TestReplyDecisionThreshold:
    """Property 6: For any SEC evaluation result, the ResponsePipeline SHALL
    determine a reply is warranted if and only if
    (goal_relevance + novelty) > 0.3.
    """

    @given(goal_relevance=sec_score, novelty=sec_score)
    @settings(max_examples=200)
    def test_reply_warranted_iff_sum_exceeds_threshold(
        self, goal_relevance: float, novelty: float
    ):
        """should_reply() returns True iff (goal_relevance + novelty) > 0.3"""
        pipeline = ResponsePipeline()
        msg = {"text": "test", "user_id": "user1"}
        sec_result = {"goal_relevance": goal_relevance, "novelty": novelty}

        result = pipeline.should_reply(msg, sec_result)
        expected = (goal_relevance + novelty) > 0.3

        assert result == expected, (
            f"should_reply returned {result} but expected {expected} "
            f"for goal_relevance={goal_relevance}, novelty={novelty}, "
            f"sum={goal_relevance + novelty}"
        )

    @given(goal_relevance=sec_score, novelty=sec_score)
    @settings(max_examples=200)
    def test_reply_true_implies_sum_above_threshold(
        self, goal_relevance: float, novelty: float
    ):
        """If should_reply() returns True, then (goal_relevance + novelty) > 0.3"""
        pipeline = ResponsePipeline()
        msg = {"text": "test", "user_id": "user1"}
        sec_result = {"goal_relevance": goal_relevance, "novelty": novelty}

        if pipeline.should_reply(msg, sec_result):
            assert (goal_relevance + novelty) > 0.3

    @given(goal_relevance=sec_score, novelty=sec_score)
    @settings(max_examples=200)
    def test_reply_false_implies_sum_at_or_below_threshold(
        self, goal_relevance: float, novelty: float
    ):
        """If should_reply() returns False, then (goal_relevance + novelty) <= 0.3"""
        pipeline = ResponsePipeline()
        msg = {"text": "test", "user_id": "user1"}
        sec_result = {"goal_relevance": goal_relevance, "novelty": novelty}

        if not pipeline.should_reply(msg, sec_result):
            assert (goal_relevance + novelty) <= 0.3

    @given(goal_relevance=sec_score, novelty=sec_score)
    @settings(max_examples=200)
    def test_decision_independent_of_message_content(
        self, goal_relevance: float, novelty: float
    ):
        """The reply decision depends only on SEC scores, not message content."""
        pipeline = ResponsePipeline()
        sec_result = {"goal_relevance": goal_relevance, "novelty": novelty}

        result_a = pipeline.should_reply({"text": "hello", "user_id": "u1"}, sec_result)
        result_b = pipeline.should_reply({"text": "goodbye", "user_id": "u2"}, sec_result)

        assert result_a == result_b, (
            f"Decision should be identical for same SEC scores regardless of message content"
        )
