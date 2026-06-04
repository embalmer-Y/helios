"""Embedding inference gateway owner package.

Backend-neutral capability owner that turns text into a vector through a named profile and
reports readiness, mirroring the `25` LLM inference gateway. Holds no cognitive policy and
never interprets an embedding vector.
"""

from .contracts import (
    EmbeddingError,
    EmbeddingGatewayAPI,
    EmbeddingProfile,
    EmbeddingProfileReadiness,
    EmbeddingProvider,
    EmbeddingReadinessReport,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingUsage,
    ProviderEmbedding,
)
from .engine import (
    EmbeddingGateway,
    EmbeddingProfileRegistry,
    OpenAICompatibleEmbeddingProvider,
)

__all__ = [
    "EmbeddingError",
    "EmbeddingGateway",
    "EmbeddingGatewayAPI",
    "EmbeddingProfile",
    "EmbeddingProfileReadiness",
    "EmbeddingProfileRegistry",
    "EmbeddingProvider",
    "EmbeddingReadinessReport",
    "EmbeddingRequest",
    "EmbeddingResult",
    "EmbeddingUsage",
    "OpenAICompatibleEmbeddingProvider",
    "ProviderEmbedding",
]
