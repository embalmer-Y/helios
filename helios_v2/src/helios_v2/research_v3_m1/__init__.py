"""helios_v3 调研 ship package。

M1-T1: AspectState 10 字段向量
M1-T2: 8 维 CDS + Radau stiff solver
"""
from .aspect_state import (
    AspectState,
    LEGAL_RANGES,
    FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY,
    FIXTURE_POSITIVE_VALENCE_LOW_AROUSAL,
    FIXTURE_HIGH_ACTIVATION_HIGH_PRECISION,
)
from .projections import (
    Hormone9D,
    Feeling7D,
    Salience5D,
    project_v2_to_aspect_state,
    project_v2_to_aspect_state_default,
)
from .cds import (
    CoupledDynamicalSystem,
    CDSODEParams,
    PTS_DIMENSION_NAMES,
    DEFAULT_ALPHA,
    DEFAULT_KURAMOTO_SCALE,
)

__all__ = [
    # M1-T1
    "AspectState",
    "LEGAL_RANGES",
    "FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY",
    "FIXTURE_POSITIVE_VALENCE_LOW_AROUSAL",
    "FIXTURE_HIGH_ACTIVATION_HIGH_PRECISION",
    "Hormone9D",
    "Feeling7D",
    "Salience5D",
    "project_v2_to_aspect_state",
    "project_v2_to_aspect_state_default",
    # M1-T2
    "CoupledDynamicalSystem",
    "CDSODEParams",
    "PTS_DIMENSION_NAMES",
    "DEFAULT_ALPHA",
    "DEFAULT_KURAMOTO_SCALE",
]
