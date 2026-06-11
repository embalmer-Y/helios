"""R83 state-block catalog loader.

Loads the 8-state x 5-variant stimulus catalog from
`r83_states.json` and exposes it as a list of `StateBlock` frozen
dataclasses. The catalog is hand-written (no LLM-generated stimuli)
so the audit is reproducible.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "r83_states.json"

EXPECTED_RESPONSE_TAXONOMY = (
    "positive",
    "negative_plus_arousal",
    "arousal_spike_plus_positive",
    "arousal_spike_neutral_valence",
    "mixed",
    "high_drift",
)


@dataclass(frozen=True)
class StateBlock:
    """One state block in the R83 catalog.

    Attributes:
        id: short identifier (e.g. "praise").
        description: human-readable description.
        lever: the bio-chemistry lever the stimulus is expected to
            pull (free-text, e.g. "oxytocin / dopamine").
        expected_response: one of the EXPECTED_RESPONSE_TAXONOMY
            values. The algorithmic A2 scorer uses this to pick
            the scoring rule.
        variants: 5 textual stimuli, 8-25 chars each.
    """

    id: str
    description: str
    lever: str
    expected_response: str
    variants: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError(f"StateBlock id must be non-empty: {self!r}")
        if len(self.variants) < 1:
            raise ValueError(
                f"StateBlock {self.id!r} must have at least 1 variant; got {len(self.variants)}"
            )
        if self.expected_response not in EXPECTED_RESPONSE_TAXONOMY:
            raise ValueError(
                f"StateBlock {self.id!r} expected_response must be one of "
                f"{EXPECTED_RESPONSE_TAXONOMY}; got {self.expected_response!r}"
            )


def load_state_blocks(catalog_path: Path | None = None) -> list[StateBlock]:
    """Load the 8 state blocks from the catalog JSON.

    Args:
        catalog_path: optional override of the catalog path; defaults
            to the bundled `r83_states.json`.

    Returns:
        list of `StateBlock` (one per state; 5 variants each).
    """
    p = catalog_path or CATALOG_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    blocks: list[StateBlock] = []
    for raw in data["state_blocks"]:
        block = StateBlock(
            id=raw["id"],
            description=raw.get("description", ""),
            lever=raw.get("lever", ""),
            expected_response=raw["expected_response"],
            variants=tuple(raw["variants"]),
        )
        blocks.append(block)
    return blocks


def get_state_block(state_id: str, catalog_path: Path | None = None) -> StateBlock:
    """Find a single state block by id; raise KeyError if missing."""
    for b in load_state_blocks(catalog_path):
        if b.id == state_id:
            return b
    raise KeyError(
        f"State block {state_id!r} not in catalog; "
        f"available: {[b.id for b in load_state_blocks(catalog_path)]}"
    )
