"""Shared regulation constants used by the policy and compatibility facade."""

from __future__ import annotations


DRIVE_ACTION_RELEVANCE: dict[str, dict[str, float]] = {
    "curiosity": {
        "browse": 1.0,
        "search": 0.9,
        "learn": 1.0,
        "speak_share": 0.6,
        "reflect": 0.4,
    },
    "social": {
        "speak_care": 1.0,
        "speak_missing": 0.9,
        "speak_play": 0.8,
        "speak_share": 0.7,
        "speak_fear": 0.6,
        "request": 0.5,
    },
    "homeostatic": {
        "reflect": 0.8,
        "check_system": 1.0,
        "idle": 0.7,
    },
    "achievement": {
        "learn": 0.7,
        "search": 0.6,
        "request": 0.5,
        "check_system": 0.4,
    },
    "aesthetic": {
        "speak_share": 0.8,
        "speak_play": 0.7,
        "browse": 0.5,
        "reflect": 0.6,
    },
}


__all__ = ["DRIVE_ACTION_RELEVANCE"]