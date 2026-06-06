"""Temporal pacing and rest-state source owner package.

Produces two real situational facts the `09` thought gate consumes — default-mode-network
availability (rest vs external task) and the spontaneous-thought pacing accumulated from elapsed
rest — replacing the composition-injected constants. Holds no gate/salience/feeling/cognitive
policy and imports no gate, appraisal, feeling, or neuromodulation owner.
"""

from .contracts import (
    TemporalError,
    TemporalPacingSample,
    TemporalSource,
)
from .engine import RestStateTemporalSource

__all__ = [
    "RestStateTemporalSource",
    "TemporalError",
    "TemporalPacingSample",
    "TemporalSource",
]
