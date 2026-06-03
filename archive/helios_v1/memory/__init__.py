"""Memory package compatibility surface for Phase 4 restructuring."""

from .autobiographical import AutobiographicalMoment, AutobiographicalStore, Chapter
from .backend import AutobiographicalBackend, DirectoryMemoryBackend, JsonlAutobiographicalBackend, MemoryBackend
from .emotional_memory import EmotionalEpisode, EmotionalEpisodicMemory
from .memory_compressor import CompressedSummary, MemoryCompressor
from .retrieval import (
    DirectedMemoryBundle,
    MemorySearchHit,
    MemorySearchQuery,
    MemoryScope,
    MemoryStrategy,
    NullVectorMemoryProvider,
    PublicMemoryTier,
    PublicMemoryTierSnapshot,
    RetrievalQueryPlan,
    RetrievalSECResult,
    RetrievalSelectionTrace,
    VectorMemoryProvider,
)
from .seed_memory_importer import SeedMemoryImporter, SeedMoment
from .sqlite_backend import SQLiteMemoryBackend, ensure_sqlite_memory_backend
from .memory_system import (
    AutobiographicalMemory,
    EpisodicMemory,
    MemoryConsolidator,
    MemoryItem,
    MemoryRetriever,
    MemorySystem,
    SemanticMemory,
    WorkingMemory,
)

__all__ = [
    "AutobiographicalMoment",
    "AutobiographicalStore",
    "AutobiographicalBackend",
    "Chapter",
    "DirectoryMemoryBackend",
    "EmotionalEpisode",
    "EmotionalEpisodicMemory",
    "JsonlAutobiographicalBackend",
    "CompressedSummary",
    "DirectedMemoryBundle",
    "MemorySearchHit",
    "MemorySearchQuery",
    "MemoryScope",
    "MemoryStrategy",
    "MemoryBackend",
    "NullVectorMemoryProvider",
    "PublicMemoryTier",
    "PublicMemoryTierSnapshot",
    "RetrievalQueryPlan",
    "RetrievalSECResult",
    "RetrievalSelectionTrace",
    "SQLiteMemoryBackend",
    "AutobiographicalMemory",
    "EpisodicMemory",
    "MemoryCompressor",
    "MemoryConsolidator",
    "MemoryItem",
    "MemoryRetriever",
    "MemorySystem",
    "SeedMemoryImporter",
    "SeedMoment",
    "SemanticMemory",
    "VectorMemoryProvider",
    "WorkingMemory",
    "ensure_sqlite_memory_backend",
]