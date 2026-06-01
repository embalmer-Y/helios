"""Property-based tests for autobiographical personalization bounds.

Property 14: Autobiographical Memory Inclusion Bound
Validates Requirement 16.2
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from hypothesis import given, strategies as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.response_pipeline import ResponsePipeline


@dataclass
class FakeAutobioMoment:
    narrative: str
    phi: float = 0.5
    significance: float = 0.5


class FakeAutobioStore:
    def __init__(self, narratives):
        self._narratives = narratives

    def query_related(self, **kwargs):
        return [FakeAutobioMoment(narrative=text) for text in self._narratives]


@given(st.lists(st.text(min_size=1, max_size=40), min_size=0, max_size=12))
def test_autobio_context_includes_at_most_three_narratives(narratives):
    pipeline = ResponsePipeline(autobio_store=FakeAutobioStore(narratives))

    context = pipeline._get_autobio_context("topic", "user1", [])

    bullet_lines = [line for line in context.splitlines() if line.startswith("  - ")]
    assert len(bullet_lines) <= 3