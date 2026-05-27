from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class OptionalChannelBootstrapSpec:
    channel_id: str
    factory: object
    payload: dict[str, object]


OptionalChannelBootstrapFactory = Callable[[], OptionalChannelBootstrapSpec]