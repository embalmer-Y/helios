"""Owner: sensory ingress.

Owns:
- source registration
- raw signal normalization
- normalized stimulus batch publication

Does not own:
- salience scoring
- memory retrieval
- action routing
"""

from .contracts import (
    IngestSignalOp,
    PublishStimulusBatchOp,
    RawSignal,
    SensoryIngressAPI,
    SensoryIngressError,
    SensorySource,
    Stimulus,
    StimulusBatch,
)
from .ingress import SensoryIngress
from .internal_monologue import InternalMonologueSource

__all__ = [
    "IngestSignalOp",
    "PublishStimulusBatchOp",
    "RawSignal",
    "SensoryIngress",
    "SensoryIngressAPI",
    "SensoryIngressError",
    "SensorySource",
    "Stimulus",
    "StimulusBatch",
    "InternalMonologueSource",
]