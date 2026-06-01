"""Shared helpers for annotating inbound text messages with SEC and cognitive impact."""

from __future__ import annotations

import logging
from typing import Dict

from ..channel import ChannelMessage

_SEC_KEYS = {
    "novelty",
    "pleasantness",
    "goal_relevance",
    "goal_congruence",
    "coping_potential",
    "agency",
    "norm_compatibility",
}


def clamp_score(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def looks_like_sec_result(result: object) -> bool:
    return isinstance(result, dict) and bool(_SEC_KEYS.intersection(result.keys()))


def sec_to_triggers(sec_result: Dict[str, float]) -> Dict[str, float]:
    novelty = clamp_score(sec_result.get("novelty", 0.0))
    pleasantness = sec_result.get("pleasantness", 0.0)
    goal_relevance = clamp_score(sec_result.get("goal_relevance", 0.0))
    goal_congruence = sec_result.get("goal_congruence", 0.0)
    coping = clamp_score(sec_result.get("coping_potential", 0.5))
    agency = sec_result.get("agency", 0.0)
    norm = sec_result.get("norm_compatibility", 0.0)

    triggers = {
        "SEEKING": clamp_score(0.55 * novelty + 0.45 * goal_relevance + max(goal_congruence, 0.0) * 0.15),
        "CARE": clamp_score(max(pleasantness, 0.0) * 0.55 + goal_relevance * 0.25 + max(norm, 0.0) * 0.20),
        "PLAY": clamp_score(max(pleasantness, 0.0) * 0.45 + novelty * 0.35 + coping * 0.20),
        "PANIC": clamp_score(max(-pleasantness, 0.0) * 0.45 + goal_relevance * 0.35 + (1.0 - coping) * 0.20),
        "FEAR": clamp_score(max(-pleasantness, 0.0) * 0.35 + novelty * 0.35 + (1.0 - coping) * 0.30),
        "RAGE": clamp_score(max(-goal_congruence, 0.0) * 0.45 + max(-pleasantness, 0.0) * 0.25 + max(-agency, 0.0) * 0.30),
    }
    return {key: value for key, value in triggers.items() if value > 0.0}


def triggers_to_sec(triggers: Dict[str, float]) -> Dict[str, float]:
    seeking = clamp_score(triggers.get("SEEKING", 0.0))
    care = clamp_score(triggers.get("CARE", 0.0))
    play = clamp_score(triggers.get("PLAY", 0.0))
    panic = clamp_score(triggers.get("PANIC", 0.0))
    fear = clamp_score(triggers.get("FEAR", 0.0))
    rage = clamp_score(triggers.get("RAGE", 0.0))

    pleasantness = clamp_score(0.6 * care + 0.55 * play - 0.45 * panic - 0.4 * fear - 0.5 * rage, -1.0, 1.0)
    goal_congruence = clamp_score(0.5 * seeking + 0.3 * care - 0.45 * fear - 0.55 * rage - 0.5 * panic, -1.0, 1.0)
    agency = clamp_score(0.2 * seeking - 0.6 * rage - 0.2 * fear, -1.0, 1.0)
    norm = clamp_score(0.35 * care + 0.25 * play - 0.3 * rage, -1.0, 1.0)

    return {
        "novelty": clamp_score(max(seeking, play * 0.7, fear * 0.6)),
        "pleasantness": pleasantness,
        "goal_relevance": clamp_score(max(seeking, care, panic, fear, rage)),
        "goal_congruence": goal_congruence,
        "coping_potential": clamp_score(0.65 - 0.35 * panic - 0.25 * fear + 0.15 * play),
        "agency": agency,
        "norm_compatibility": norm,
    }


def build_cognitive_impact(text: str, sec_result: Dict[str, float], triggers: Dict[str, float]) -> Dict[str, float]:
    novelty = clamp_score(sec_result.get("novelty", 0.0))
    goal_relevance = clamp_score(sec_result.get("goal_relevance", 0.0))
    pleasantness = abs(sec_result.get("pleasantness", 0.0))
    coping = clamp_score(sec_result.get("coping_potential", 0.5))
    urgency = clamp_score(max(triggers.values(), default=0.0))
    text_density = clamp_score(len(text.strip()) / 80.0)

    return {
        "sensory": clamp_score(0.20 + text_density * 0.35 + novelty * 0.45),
        "cognitive": clamp_score(0.15 + goal_relevance * 0.45 + novelty * 0.20 + (1.0 - coping) * 0.20),
        "self_": clamp_score(0.10 + goal_relevance * 0.45 + pleasantness * 0.15 + urgency * 0.30),
        "novelty": clamp_score(max(novelty, urgency * 0.8)),
    }


def evaluate_text_triggers(message: ChannelMessage, sec_evaluator, logger: logging.Logger, owner_name: str) -> Dict[str, float]:
    cached_triggers = dict(message.metadata.get("event_triggers", {}) or {})
    if cached_triggers:
        return cached_triggers
    if sec_evaluator is None or not message.text:
        return {}
    try:
        result = sec_evaluator.evaluate(message.text)
        if looks_like_sec_result(result):
            return sec_to_triggers(result)
        return dict(result or {})
    except Exception as exc:
        logger.warning("%s SEC evaluation failed: %s", owner_name, exc)
        return {}


def annotate_inbound_text_message(message: ChannelMessage, sec_evaluator, logger: logging.Logger, owner_name: str) -> ChannelMessage:
    if not message.text:
        return message

    metadata = dict(message.metadata)
    triggers = dict(metadata.get("event_triggers", {}) or {})
    sec_result = dict(metadata.get("sec_result", {}) or {})

    if sec_evaluator is not None and not triggers:
        try:
            evaluation = sec_evaluator.evaluate(message.text)
        except Exception as exc:
            logger.warning("%s inbound annotation failed: %s", owner_name, exc)
            evaluation = {}

        if looks_like_sec_result(evaluation):
            sec_result = dict(evaluation)
            triggers = sec_to_triggers(sec_result)
        else:
            triggers = dict(evaluation or {})
            sec_result = triggers_to_sec(triggers) if triggers else {}
    elif triggers and not sec_result:
        sec_result = triggers_to_sec(triggers)

    if triggers:
        metadata["event_triggers"] = triggers
    if sec_result:
        metadata["sec_result"] = sec_result
        metadata["cognitive_impact"] = build_cognitive_impact(message.text, sec_result, triggers)

    return ChannelMessage(
        channel_id=message.channel_id,
        user_id=message.user_id,
        text=message.text,
        timestamp=message.timestamp,
        metadata=metadata,
        direction=message.direction,
    )