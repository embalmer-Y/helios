"""Durable experience store owner package.

Infrastructure owner for durable persistence of the experience-writeback continuity stream
and its re-entry into the directed-retrieval candidate path after a restart. Holds no
cognitive policy and performs no semantic ranking.
"""

from .contracts import (
    ExperienceStoreBackend,
    PersistedExperienceRecord,
    PersistenceError,
    PriorExistenceSnapshot,
    SimilarityHit,
    SimilaritySearchResult,
    UNASSIGNED_SEQUENCE,
)
from .engine import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
    SemanticStoreBackedDirectedMemoryCandidateProvider,
    SqliteExperienceStoreBackend,
    StoreBackedDirectedMemoryCandidateProvider,
    cosine_similarity,
)

__all__ = [
    "ExperienceStore",
    "ExperienceStoreBackend",
    "InMemoryExperienceStoreBackend",
    "PersistedExperienceRecord",
    "PersistenceError",
    "PriorExistenceSnapshot",
    "SemanticStoreBackedDirectedMemoryCandidateProvider",
    "SimilarityHit",
    "SimilaritySearchResult",
    "SqliteExperienceStoreBackend",
    "StoreBackedDirectedMemoryCandidateProvider",
    "UNASSIGNED_SEQUENCE",
    "cosine_similarity",
]
