"""R99 emotion validation probe (tests-only, read-only, offline).

Drives a self-contained production-shaped runtime with a deterministic fake-LLM gateway and measures
four bounded emotional-chain metrics:
  - cortisol_valence_separation: mean cortisol on negative-valence fixture ticks minus
    mean cortisol on positive-valence fixture ticks (mirrors R96/R98 separation convention).
  - thought_content_grounding: fraction of fired ticks whose `11` thought content references
    the current visitor fixture text.
  - memory_recall_relevance: fraction of recall-possible ticks whose `10` retrieval bundle
    contains a store-sourced hit.
  - reply_loop_closure: fraction of negative-valence fixture ticks where the `13` planner
    accepted a reply-type proposal.

It composes these into an `EmotionValidationReport` with bounded metrics that the R89 Turing
harness consumes to upgrade its `bio_responsiveness` axis from drift-only reconstruction to
emotion-probe reconstruction. It asserts nothing and emits no `print`/`logging` (R21
discipline); a consuming test renders/asserts.

This package, like the sibling R88/R89/R90 packages, ensures `tests/` is on `sys.path`.
"""

from __future__ import annotations

import os
import sys

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from .emotion_validation_probe import (  # noqa: E402  (path insertion must precede the import)
    DEFAULT_VISITOR_FIXTURES,
    EmotionValidationConfig,
    EmotionValidationReport,
    FixtureResult,
    VisitorFixture,
    run_emotion_validation_probe,
)

__all__ = [
    "DEFAULT_VISITOR_FIXTURES",
    "EmotionValidationConfig",
    "EmotionValidationReport",
    "FixtureResult",
    "VisitorFixture",
    "run_emotion_validation_probe",
]
