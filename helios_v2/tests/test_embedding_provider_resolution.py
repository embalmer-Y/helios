"""Requirement 96 - resolver unit tests (composition-side provider selection).

These 10 tests are the network-free contract surface for
`composition.embedding_provider_resolution`. They are referenced by
`docs/requirements/96-real-semantic-embedding/design.md` §5.3 and form the
fail-fast CI gate for the resolver.

The resolver is a small, pure function over an injected `env` mapping; no
network, no LLM, no runtime assembly. The tests use literal env dicts and
verify the frozen `EmbeddingProviderResolution` decision.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from helios_v2.composition import (
    EMBEDDING_MODEL_DIMENSIONS,
    EmbeddingProviderKind,
    EmbeddingProviderResolution,
    HELIOS_EMBEDDING_API_KEY_ENV,
    HELIOS_EMBEDDING_BASE_URL_ENV,
    HELIOS_EMBEDDING_MODEL_ENV,
    resolve_embedding_provider,
)
from helios_v2.composition.embedding_provider_resolution import (
    DEFAULT_EMBEDDING_BASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    OFFLINE_EMBEDDING_BASE_URL,
    OFFLINE_EMBEDDING_KEY_ENV,
    OFFLINE_EMBEDDING_MODEL,
)


def test_resolve_with_key_present_returns_openai_compatible() -> None:
    # HELIOS_EMBEDDING_API_KEY is the single bit of authority: if it is non-blank
    # the resolver picks the real-cloud provider and the canonical model.
    env = {HELIOS_EMBEDDING_API_KEY_ENV: "sk-abc123"}

    resolution = resolve_embedding_provider(env=env)

    assert resolution.kind == "openai_compatible"
    assert resolution.model == "text-embedding-3-small"
    assert resolution.base_url == "https://api.openai.com/v1"
    assert resolution.dimensions == 1536
    assert resolution.api_key_env_var == HELIOS_EMBEDDING_API_KEY_ENV


def test_resolve_with_blank_key_returns_deterministic_hash() -> None:
    # A whitespace-only key is treated as absent: the resolver strips and re-checks,
    # and falls back to the offline-hash path. This is the documented
    # "missing or whitespace-only" failure mode.
    env = {HELIOS_EMBEDDING_API_KEY_ENV: "   "}

    resolution = resolve_embedding_provider(env=env)

    assert resolution.kind == "deterministic_hash"
    assert resolution.model == OFFLINE_EMBEDDING_MODEL
    assert resolution.base_url == OFFLINE_EMBEDDING_BASE_URL
    assert resolution.api_key_env_var == OFFLINE_EMBEDDING_KEY_ENV


def test_resolve_with_no_key_returns_deterministic_hash() -> None:
    # The completely-empty mapping is the R69 baseline: no credential, the
    # R69-equivalent hash path is the active kind. The 1110-test green
    # baseline depends on this branch being preserved byte-for-byte.
    resolution = resolve_embedding_provider(env={})

    assert resolution.kind == "deterministic_hash"
    assert resolution.model == "deterministic-hash"
    assert resolution.base_url == "http://localhost"
    assert resolution.dimensions == 16
    assert resolution.api_key_env_var == "HELIOS_AUTO_EMBEDDING_KEY"


def test_resolve_with_explicit_model_returns_that_model() -> None:
    # An explicit HELIOS_EMBEDDING_MODEL is honored verbatim. The dimensions
    # are looked up in the static map; well-known models resolve to a
    # non-None integer.
    env = {
        HELIOS_EMBEDDING_API_KEY_ENV: "sk-abc123",
        HELIOS_EMBEDDING_MODEL_ENV: "bge-m3",
    }

    resolution = resolve_embedding_provider(env=env)

    assert resolution.kind == "openai_compatible"
    assert resolution.model == "bge-m3"
    assert resolution.dimensions == 1024


def test_resolve_with_unknown_model_returns_dimensions_none() -> None:
    # An unknown model name is not silently coerced to a default. The resolver
    # returns the model verbatim with `dimensions=None`, and the provider is
    # then expected to omit the `dimensions` field from its request. The
    # remote endpoint will reject the model if the name is wrong; the runtime
    # does not silently fall back.
    env = {
        HELIOS_EMBEDDING_API_KEY_ENV: "sk-abc123",
        HELIOS_EMBEDDING_MODEL_ENV: "my-experimental-embedder",
    }

    resolution = resolve_embedding_provider(env=env)

    assert resolution.model == "my-experimental-embedder"
    assert resolution.dimensions is None


def test_resolve_with_explicit_base_url_uses_it() -> None:
    # HELIOS_EMBEDDING_BASE_URL is honored verbatim so an operator can route
    # through a proxy or shengsuanyun-style router without code changes.
    env = {
        HELIOS_EMBEDDING_API_KEY_ENV: "sk-abc123",
        HELIOS_EMBEDDING_BASE_URL_ENV: "https://router.shengsuanyun.com/api/v1",
    }

    resolution = resolve_embedding_provider(env=env)

    assert resolution.base_url == "https://router.shengsuanyun.com/api/v1"


def test_resolve_validates_empty_model() -> None:
    # An explicitly-empty HELIOS_EMBEDDING_MODEL must NOT bypass the
    # no-credential branch. The resolver treats blank model as absent and
    # applies the canonical default; an absent credential still yields hash.
    env = {
        HELIOS_EMBEDDING_API_KEY_ENV: "  ",
        HELIOS_EMBEDDING_MODEL_ENV: "",
    }

    resolution = resolve_embedding_provider(env=env)

    assert resolution.kind == "deterministic_hash"
    assert resolution.model == "deterministic-hash"


def test_embedding_model_dimensions_is_frozen() -> None:
    # The map is a `MappingProxyType`, so any attempt to mutate the
    # module-level dimension catalog is rejected at runtime. This is the
    # single-source-of-truth invariant: no owner may add a new model
    # dimension without editing the module.
    assert isinstance(EMBEDDING_MODEL_DIMENSIONS, MappingProxyType)
    with pytest.raises(TypeError):
        EMBEDDING_MODEL_DIMENSIONS["text-embedding-3-small"] = 0  # type: ignore[index]
    # And the canonical entries are present.
    assert EMBEDDING_MODEL_DIMENSIONS["text-embedding-3-small"] == 1536
    assert EMBEDDING_MODEL_DIMENSIONS["text-embedding-3-large"] == 3072
    assert EMBEDDING_MODEL_DIMENSIONS["deterministic-hash"] == 16


def test_embedding_provider_resolution_validates_empty_fields() -> None:
    # The frozen dataclass's `__post_init__` rejects empty `model`,
    # `base_url`, and `api_key_env_var` strings, and rejects a `kind` that
    # is not in the documented literal set. This is the fail-fast guard for
    # any future caller that hand-builds a resolution without going through
    # the resolver.
    with pytest.raises(ValueError, match="non-empty model"):
        EmbeddingProviderResolution(
            kind="openai_compatible",
            model="",
            base_url="https://api.openai.com/v1",
            dimensions=1536,
            api_key_env_var=HELIOS_EMBEDDING_API_KEY_ENV,
        )
    with pytest.raises(ValueError, match="non-empty base_url"):
        EmbeddingProviderResolution(
            kind="openai_compatible",
            model="text-embedding-3-small",
            base_url="",
            dimensions=1536,
            api_key_env_var=HELIOS_EMBEDDING_API_KEY_ENV,
        )
    with pytest.raises(ValueError, match="non-empty api_key_env_var"):
        EmbeddingProviderResolution(
            kind="openai_compatible",
            model="text-embedding-3-small",
            base_url="https://api.openai.com/v1",
            dimensions=1536,
            api_key_env_var="",
        )
    with pytest.raises(ValueError, match="kind must be"):
        EmbeddingProviderResolution(
            kind="bogus",  # type: ignore[arg-type]
            model="text-embedding-3-small",
            base_url="https://api.openai.com/v1",
            dimensions=1536,
            api_key_env_var=HELIOS_EMBEDDING_API_KEY_ENV,
        )


def test_resolve_uses_str_strip_for_key_check() -> None:
    # The resolver applies `str.strip()` to the api-key value before the
    # truthiness check, so leading/trailing whitespace is silently
    # tolerated. This matches the documented "whitespace-only is absent"
    # contract from design §3.1.
    env = {HELIOS_EMBEDDING_API_KEY_ENV: "  sk-abc123  "}

    resolution = resolve_embedding_provider(env=env)

    assert resolution.kind == "openai_compatible"
    assert resolution.model == DEFAULT_EMBEDDING_MODEL
    assert resolution.base_url == DEFAULT_EMBEDDING_BASE_URL
