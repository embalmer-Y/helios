"""Embedding provider resolution (composition-side glue).

Owner: composition.

Purpose:
    The single place that reads the embedding-related environment variables and decides
    whether the active embedding provider is the real OpenAI-compatible cloud (when
    `HELIOS_EMBEDDING_API_KEY` is set) or the explicit-honest deterministic-hash
    placeholder (the R69 baseline, when the key is absent). This is the R96 owner-
    confirmed decision: **option A — OpenAI-compatible cloud** is the active default
    whenever the runtime environment declares the necessary credential; the hash
    placeholder is a hard, explicit, recorded fallback (not silent degradation).

Failure semantics:
    `resolve_embedding_provider` never raises for valid env inputs. Whitespace-only
    `HELIOS_EMBEDDING_API_KEY` is treated as absent (the resolution rules apply
    `str.strip()`). An empty injected `env` mapping is treated as "no env vars"
    (the same as a real `os.environ` empty mapping). The `EmbeddingProviderResolution`
    `__post_init__` validates the resolved fields at construction and raises
    `ValueError` on an empty model / base_url / api_key_env_var (defensive).

Notes:
    This module holds *no* cognitive policy. It is pure data + env reads + a static
    model-dimensions map. The `34` embedding owner receives a constructed
    `EmbeddingProfile` and an already-resolved provider; the embedding owner never
    reads the env directly. The cognitive owners never see the env-var names.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from helios_v2.embedding import (
    DeterministicHashEmbeddingProvider,
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    OpenAICompatibleEmbeddingProvider,
)


# Public Literal type for the resolved provider kind. The two values are the only legal
# outcomes of `resolve_embedding_provider`.
EmbeddingProviderKind = Literal["openai_compatible", "deterministic_hash"]


# Static map from well-known model names to their declared vector dimensions. This is the
# ONLY place dimension knowledge lives for the auto-provisioned path. A model not in the
# map returns `dimensions=None` (the R34 `OpenAICompatibleEmbeddingProvider` already
# handles a `None` `dimensions` by omitting the field from the request, preserving the
# provider's documented behavior).
#
# The "deterministic-hash" entry is explicit so the resolver can return its dimension
# for the hash path too (the R69 provider uses 16 by default; the test suite
# `DeterministicHashEmbeddingProvider` is constructed with `dimensions=16`).
EMBEDDING_MODEL_DIMENSIONS: Mapping[str, int] = MappingProxyType(
    {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        "bge-m3": 1024,
        "bge-large-zh-v1.5": 1024,
        "bge-base-zh-v1.5": 768,
        "bge-small-zh-v1.5": 512,
        "deterministic-hash": 16,
    }
)


# Env-var names. The resolver is the SINGLE source of truth for these names; the LLM
# module, the embedding owner, and the composition root all read them through this module
# (R82's `_production_embedding_gateway` and the R69 auto-provisioning block in
# `assemble_runtime` both call into this resolver). Cognitive owners never see these names.
#
# Project convention: the `.env` file at the repo root (e.g. `D:\Software\project\helios\.env`)
# holds the real values; entry-point scripts under `helios_v2/scripts/` call
# `load_dotenv()` (or the project's own `_load_dotenv_into_environ` helper) to populate
# `os.environ` before invoking `assemble_runtime` / `assemble_production_runtime`. The
# library code under `helios_v2/src/` reads `os.environ` indirectly through the `env`
# parameter that this resolver accepts (so tests can inject a `dict` and stay
# network-free without mutating the real environment).
HELIOS_EMBEDDING_API_KEY_ENV = "HELIOS_EMBEDDING_API_KEY"
HELIOS_EMBEDDING_BASE_URL_ENV = "HELIOS_EMBEDDING_BASE_URL"
HELIOS_EMBEDDING_MODEL_ENV = "HELIOS_EMBEDDING_MODEL"

# Defaults applied when the corresponding env var is unset or empty after `str.strip()`.
DEFAULT_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# The R69/R82 hash-fallback profile's env stub name and the literal stub value it
# carries. The hash provider does not need a real api key; the stub key keeps
# `EmbeddingGateway.check_static_readiness` reporting `static_ready=True` for the
# offline assembly. Preserved byte-for-byte from R69 + R82 so the existing 1110-test
# baseline still passes.
OFFLINE_EMBEDDING_KEY_ENV = "HELIOS_AUTO_EMBEDDING_KEY"
OFFLINE_EMBEDDING_KEY_STUB_VALUE = "auto-provisioned"  # R69 default
# R82 used "production-offline" in `_production_embedding_gateway`. Both values are valid
# (the hash provider ignores them); the R69 path is the default and the R82 path
# overrides the stub value to "production-offline" to self-document the assembly origin.
# `build_embedding_gateway` accepts an optional `offline_stub_value` parameter to honor
# both call sites without duplicating the provider-construction logic.
OFFLINE_EMBEDDING_KEY_STUB_VALUE_R82 = "production-offline"
OFFLINE_EMBEDDING_BASE_URL = "http://localhost"
OFFLINE_EMBEDDING_MODEL = "deterministic-hash"


@dataclass(frozen=True)
class EmbeddingProviderResolution:
    """Owner: composition.

    Purpose:
        The frozen decision produced by `resolve_embedding_provider`. The composition
        root consumes this to pick a concrete `EmbeddingProfile` and `EmbeddingProvider`
        and to record the active kind on the resolved `RuntimeProfile`.

    Failure semantics:
        Construction raises `ValueError` on an empty `model` / `base_url` /
        `api_key_env_var` and on a `kind` outside `EmbeddingProviderKind`. The dataclass
        is frozen; the fields are read-only after construction.

    Notes:
        `dimensions` is the resolved declared vector length for the active model, or
        `None` if the model is not in `EMBEDDING_MODEL_DIMENSIONS`. The embedding
        owner decides what to do with `None` (it omits the field from the provider
        request, per R34 §3.1). The `api_key_env_var` is the env-var name the gateway
        uses to look up the api key; the resolver does not return the api key value
        itself (the gateway's `env` mapping is the single read point).
    """

    kind: EmbeddingProviderKind
    model: str
    base_url: str
    dimensions: int | None
    api_key_env_var: str

    def __post_init__(self) -> None:
        if self.kind not in ("openai_compatible", "deterministic_hash"):
            raise ValueError(
                f"EmbeddingProviderResolution kind must be 'openai_compatible' or "
                f"'deterministic_hash', got '{self.kind}'"
            )
        if not self.model:
            raise ValueError("EmbeddingProviderResolution must declare a non-empty model")
        if not self.base_url:
            raise ValueError(
                "EmbeddingProviderResolution must declare a non-empty base_url"
            )
        if not self.api_key_env_var:
            raise ValueError(
                "EmbeddingProviderResolution must declare a non-empty api_key_env_var"
            )


def _env_str(env: Mapping[str, str], name: str) -> str:
    """Read `name` from `env`; return empty string when missing. Never raises."""
    return env.get(name, "")


def resolve_embedding_provider(env: Mapping[str, str]) -> EmbeddingProviderResolution:
    """Owner: composition. The single place that reads the embedding env vars.

    Purpose:
        Decide whether the assembled runtime should use the real OpenAI-compatible
        cloud embedding provider (when `HELIOS_EMBEDDING_API_KEY` is set and non-blank)
        or the R69 deterministic-hash placeholder provider (when the key is absent
        or blank). Returns a frozen `EmbeddingProviderResolution` carrying the
        resolved provider kind, model name, base URL, declared dimensions (from the
        `EMBEDDING_MODEL_DIMENSIONS` map; `None` if unknown), and the env-var name the
        gateway should use to read the api key.

    Inputs:
        `env` - a string mapping (typically `os.environ`; tests inject a `dict`).

    Returns:
        An `EmbeddingProviderResolution`. When `HELIOS_EMBEDDING_API_KEY` (after
        `str.strip()`) is non-empty:
            - `kind == "openai_compatible"`
            - `model` is `HELIOS_EMBEDDING_MODEL` (default `"text-embedding-3-small"`)
            - `base_url` is `HELIOS_EMBEDDING_BASE_URL` (default
              `"https://api.openai.com/v1"`)
            - `dimensions` is the `EMBEDDING_MODEL_DIMENSIONS` lookup (or `None` for
              unknown models)
            - `api_key_env_var == "HELIOS_EMBEDDING_API_KEY"`
        Otherwise:
            - `kind == "deterministic_hash"`
            - `model == "deterministic-hash"`
            - `base_url == "http://localhost"`
            - `dimensions == 16`
            - `api_key_env_var == "HELIOS_AUTO_EMBEDDING_KEY"`

    Raises:
        Never. Whitespace-only `HELIOS_EMBEDDING_API_KEY` is treated as absent. The
        returned `EmbeddingProviderResolution` validates its own fields in
        `__post_init__`; the function itself never raises for valid env inputs.

    Notes:
        Composition is the only module that reads these env-var names. The embedding
        owner receives the resolved `EmbeddingProfile` and a constructed provider; it
        never sees `HELIOS_EMBEDDING_*`. This keeps the env-var surface narrow and
        testable.
    """

    api_key_raw = _env_str(env, HELIOS_EMBEDDING_API_KEY_ENV)
    api_key_present = bool(api_key_raw.strip())

    if not api_key_present:
        return EmbeddingProviderResolution(
            kind="deterministic_hash",
            model=OFFLINE_EMBEDDING_MODEL,
            base_url=OFFLINE_EMBEDDING_BASE_URL,
            dimensions=EMBEDDING_MODEL_DIMENSIONS.get(OFFLINE_EMBEDDING_MODEL),
            api_key_env_var=OFFLINE_EMBEDDING_KEY_ENV,
        )

    # Real-cloud path. The api-key env-var name is preserved verbatim so the gateway
    # reads the same variable the resolver just inspected.
    model_raw = _env_str(env, HELIOS_EMBEDDING_MODEL_ENV).strip()
    model = model_raw if model_raw else DEFAULT_EMBEDDING_MODEL
    base_url_raw = _env_str(env, HELIOS_EMBEDDING_BASE_URL_ENV).strip()
    base_url = base_url_raw if base_url_raw else DEFAULT_EMBEDDING_BASE_URL
    return EmbeddingProviderResolution(
        kind="openai_compatible",
        model=model,
        base_url=base_url,
        dimensions=EMBEDDING_MODEL_DIMENSIONS.get(model),
        api_key_env_var=HELIOS_EMBEDDING_API_KEY_ENV,
    )


def build_embedding_gateway(
    resolution: EmbeddingProviderResolution,
    profile_name: str,
    env: "Mapping[str, str] | None" = None,
    offline_stub_value: str = OFFLINE_EMBEDDING_KEY_STUB_VALUE,
) -> EmbeddingGateway:
    """Owner: composition. The single place that builds a usable `EmbeddingGateway` from a
    resolved embedding-provider decision.

    Purpose:
        Convert the structured `EmbeddingProviderResolution` into a fully wired
        `EmbeddingGateway` bound to `profile_name`, ready for the R69 auto-provisioning
        block, the R82 `_production_embedding_gateway` path, and any future caller
        (e.g. tests or scripts that need a one-shot gateway).

    Inputs:
        `resolution` - the decision produced by `resolve_embedding_provider`.
        `profile_name` - the embedding profile name (must match the assembly's
            `embedding_profile_name`; default `"experience-embedding"`).
        `env` - the environment mapping to hand to the gateway (the gateway reads the
            api key from this). `None` means "use a fresh `os.environ` snapshot" (the
            existing R34 / R82 / R69 pattern).
        `offline_stub_value` - the literal value injected into the gateway's `env` for
            the `OFFLINE_EMBEDDING_KEY_ENV` stub key. R69's `assemble_runtime` auto-
            provisioning uses `"auto-provisioned"` (the default); R82's
            `_production_embedding_gateway` uses `"production-offline"` to self-document
            the production assembly origin. The hash provider ignores the value; only
            the literal in the gateway's `env` mapping differs (for traceability).

    Returns:
        A fully wired `EmbeddingGateway` whose bound profile is statically ready
        (`HELIOS_EMBEDDING_API_KEY` non-empty for the real-cloud path; the
        `HELIOS_AUTO_EMBEDDING_KEY` stub for the hash path). The `EmbeddingError`
        fail-fast invariants from R34 §3.1 are preserved byte-for-byte (gateway
        fail-fast on missing key, missing profile, or empty input text).

    Raises:
        None. The construction is fail-fast only on profile/key shape violations,
        which the gateway validates at first `embed()` call (per R34).

    Notes:
        This helper is the only function in this module that imports from
        `helios_v2.embedding`. Keeping the gateway construction here means R82's
        `_production_embedding_gateway` and the R69 auto-provisioning block in
        `assemble_runtime` both build the gateway through the same code path; no
        duplication, no drift.
    """

    resolved_env = dict(env) if env is not None else dict(os.environ)
    if resolution.kind == "openai_compatible":
        profile = EmbeddingProfile(
            profile_name=profile_name,
            model=resolution.model,
            api_key_env=resolution.api_key_env_var,
            base_url=resolution.base_url,
            dimensions=resolution.dimensions,
        )
        return EmbeddingGateway(
            provider=OpenAICompatibleEmbeddingProvider(),
            registry=EmbeddingProfileRegistry(profiles=(profile,)),
            env=resolved_env,
        )
    # Offline / hash-fallback path. R69-equivalent: the stub key keeps static readiness
    # green without a real api key (the hash provider ignores it).
    profile = EmbeddingProfile(
        profile_name=profile_name,
        model=resolution.model,
        api_key_env=resolution.api_key_env_var,
        base_url=resolution.base_url,
    )
    return EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={resolution.api_key_env_var: offline_stub_value},
    )


__all__ = [
    "DEFAULT_EMBEDDING_BASE_URL",
    "DEFAULT_EMBEDDING_MODEL",
    "EMBEDDING_MODEL_DIMENSIONS",
    "EmbeddingProviderKind",
    "EmbeddingProviderResolution",
    "HELIOS_EMBEDDING_API_KEY_ENV",
    "HELIOS_EMBEDDING_BASE_URL_ENV",
    "HELIOS_EMBEDDING_MODEL_ENV",
    "OFFLINE_EMBEDDING_BASE_URL",
    "OFFLINE_EMBEDDING_KEY_ENV",
    "OFFLINE_EMBEDDING_KEY_STUB_VALUE",
    "OFFLINE_EMBEDDING_KEY_STUB_VALUE_R82",
    "OFFLINE_EMBEDDING_MODEL",
    "build_embedding_gateway",
    "resolve_embedding_provider",
]
