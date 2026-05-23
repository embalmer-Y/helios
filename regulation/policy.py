"""Structured active regulation policy for registry-backed self-regulation proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Mapping, Sequence
from uuid import uuid4

from behavior_registry import RuntimeBehaviorCatalog
from helios_io.action_models import ActionProposal
from neurochem_gate import resolve_neurochem_gate
from personality_projection import resolve_personality_projection
from temporal_gate import resolve_temporal_gate
from utils import clamp

from .constants import DRIVE_ACTION_RELEVANCE


@dataclass
class ActionCandidate:
    """A regulation behavior candidate scored against current needs."""

    action_type: str
    expected_benefit: float
    confidence: float
    memory_count: int
    cooldown_ok: bool
    night_safe: bool
    content_hint: str = ""
    final_score: float = 0.0

    @property
    def score(self) -> float:
        return self.expected_benefit * (0.5 + 0.5 * self.confidence)


@dataclass
class RegulationSignals:
    panksepp: dict[str, float]
    valence: float
    hour_of_day: int
    drive_urgency: float = 0.0
    drive_dominant: str = ""
    dominant_emotions: list[str] = field(default_factory=list)
    recent_execution_outcomes: list[dict[str, object]] = field(default_factory=list)
    personality_projection: object | None = None
    neurochem_gate: object | None = None
    temporal_gate: object | None = None


@dataclass
class RegulationAssessment:
    wants_regulation: bool
    deviations: list[tuple[str, float]] = field(default_factory=list)
    candidates: list[ActionCandidate] = field(default_factory=list)
    selected_action: str = ""
    selected_score: float = 0.0
    drive_dominant: str = ""
    drive_urgency: float = 0.0
    dominant_emotions: list[str] = field(default_factory=list)
    reason_summary: str = ""
    rationale: list[str] = field(default_factory=list)


class RegulationPolicy:
    """Evaluate active self-regulation needs and emit structured proposals."""

    def __init__(
        self,
        *,
        behavior_catalog: RuntimeBehaviorCatalog,
        baseline_valence: float = 0.05,
        baseline_activation: float = 0.15,
        comfort_deviation: float = 0.2,
    ):
        self.behavior_catalog = behavior_catalog
        self.baseline_valence = baseline_valence
        self.baseline_activation = baseline_activation
        self.comfort_deviation = comfort_deviation

    def collect_signals(
        self,
        *,
        panksepp: Mapping[str, float],
        valence: float,
        hour_of_day: int,
        drive_urgency: float = 0.0,
        drive_dominant: str = "",
        dominant_emotions: Sequence[str] | None = None,
        recent_execution_outcomes: Sequence[dict[str, object]] | None = None,
        personality_projection: object | None = None,
        neurochem_gate: object | None = None,
        temporal_gate: object | None = None,
    ) -> RegulationSignals:
        dominant = list(dominant_emotions or [])
        if not dominant and panksepp:
            dominant = [name for name, _score in sorted(panksepp.items(), key=lambda item: -item[1])[:3]]

        return RegulationSignals(
            panksepp={str(name): float(value) for name, value in panksepp.items()},
            valence=float(valence),
            hour_of_day=int(hour_of_day),
            drive_urgency=float(drive_urgency),
            drive_dominant=str(drive_dominant or ""),
            dominant_emotions=dominant,
            recent_execution_outcomes=[dict(item) for item in (recent_execution_outcomes or [])],
            personality_projection=personality_projection,
            neurochem_gate=neurochem_gate,
            temporal_gate=temporal_gate,
        )

    def assess(
        self,
        signals: RegulationSignals,
        *,
        memories: Mapping[str, Mapping[str, Any]],
        last_executed: Mapping[str, float],
    ) -> RegulationAssessment:
        if not signals.panksepp:
            return RegulationAssessment(
                wants_regulation=False,
                drive_dominant=signals.drive_dominant,
                drive_urgency=signals.drive_urgency,
                dominant_emotions=list(signals.dominant_emotions),
                reason_summary="no_affective_state",
            )

        deviations = self.detect_deviations(signals.panksepp, signals.valence)
        if not deviations:
            return RegulationAssessment(
                wants_regulation=False,
                deviations=[],
                drive_dominant=signals.drive_dominant,
                drive_urgency=signals.drive_urgency,
                dominant_emotions=list(signals.dominant_emotions),
                reason_summary="within_comfort_band",
            )

        candidates: list[ActionCandidate] = []
        for sys_name, deviation in deviations:
            candidates.extend(
                self.query_candidates(
                    sys_name,
                    deviation,
                    signals.hour_of_day,
                    memories=memories,
                    last_executed=last_executed,
                )
            )

        if not candidates:
            return RegulationAssessment(
                wants_regulation=False,
                deviations=deviations,
                drive_dominant=signals.drive_dominant,
                drive_urgency=signals.drive_urgency,
                dominant_emotions=list(signals.dominant_emotions),
                reason_summary="no_eligible_candidates",
            )

        self.score_candidates_with_drives(
            candidates,
            signals.drive_urgency,
            signals.drive_dominant,
            neurochem_gate=signals.neurochem_gate,
            temporal_gate=signals.temporal_gate,
        )
        self.apply_recent_feedback(candidates, signals.recent_execution_outcomes)
        candidates.sort(key=lambda candidate: -candidate.final_score)

        best = candidates[0]
        if best.final_score < 0.15:
            return RegulationAssessment(
                wants_regulation=False,
                deviations=deviations,
                candidates=candidates,
                drive_dominant=signals.drive_dominant,
                drive_urgency=signals.drive_urgency,
                dominant_emotions=list(signals.dominant_emotions),
                reason_summary="best_candidate_below_threshold",
                rationale=[f"best={best.action_type}:{best.final_score:.3f}"],
            )

        return RegulationAssessment(
            wants_regulation=True,
            deviations=deviations,
            candidates=candidates,
            selected_action=best.action_type,
            selected_score=best.final_score,
            drive_dominant=signals.drive_dominant,
            drive_urgency=signals.drive_urgency,
            dominant_emotions=list(signals.dominant_emotions),
            reason_summary=f"selected={best.action_type}; score={best.final_score:.3f}",
            rationale=[
                f"deviations={','.join(name for name, _score in deviations[:3])}",
                f"best={best.action_type}:{best.final_score:.3f}",
                f"drive={signals.drive_dominant}:{signals.drive_urgency:.2f}",
            ],
        )

    def build_action_proposal(
        self,
        action_type: str,
        *,
        score: float,
        tick: int = 0,
        timestamp: float | None = None,
        candidate_channels: Sequence[str] | None = None,
        params: Mapping[str, object] | None = None,
        drive_dominant: str = "",
        drive_urgency: float = 0.0,
        dominant_emotions: Sequence[str] | None = None,
        personality_projection: object | None = None,
        neurochem_gate: object | None = None,
        temporal_gate: object | None = None,
        recent_action: str = "",
    ) -> ActionProposal:
        behavior_profile = self.behavior_catalog.get_regulation_behavior(action_type)
        projection = resolve_personality_projection(projection=personality_projection)
        gate = resolve_neurochem_gate(gate=neurochem_gate) if neurochem_gate is not None else None
        time_gate = resolve_temporal_gate(gate=temporal_gate) if temporal_gate is not None else None
        behavior_bias = projection.bias_for_behavior(action_type)
        initiative_component = projection.initiative_bias * 0.12
        neurochem_behavior_bias = gate.bias_for_behavior(action_type) if gate is not None else 0.0
        temporal_behavior_bias = time_gate.bias_for_behavior(action_type) if time_gate is not None else 0.0
        final_score = clamp(score + behavior_bias * 0.22 + initiative_component + neurochem_behavior_bias + temporal_behavior_bias, 0.0, 1.5)

        modalities = ["internal"]
        if action_type.startswith("speak_") or action_type in {"request", "intimate"}:
            modalities = ["text", "speech"]
            if projection.channel_preference("tts") > projection.channel_preference("qq"):
                modalities = ["speech", "text"]

        ranked_channels = projection.rank_channels(list(candidate_channels or []))
        reason = behavior_profile.hint if behavior_profile is not None else action_type
        if dominant_emotions:
            reason = f"{reason}; dominant_emotions={','.join(dominant_emotions[:3])}"
        if abs(behavior_bias) >= 0.03:
            reason = f"{reason}; personality_bias={behavior_bias:+.2f}"
        if abs(neurochem_behavior_bias) >= 0.03:
            reason = f"{reason}; neurochem_bias={neurochem_behavior_bias:+.2f}"
        if abs(temporal_behavior_bias) >= 0.03:
            reason = f"{reason}; temporal_bias={temporal_behavior_bias:+.2f}"

        personality_trace = {
            "behavior_bias": behavior_bias,
            "initiative_bias": projection.initiative_bias,
            "risk_tolerance_bias": projection.risk_tolerance_bias,
            "novelty_bias": projection.novelty_bias,
            "persistence_bias": projection.persistence_bias,
            "expressivity_bias": projection.expressivity_bias,
            "ranked_channels": list(ranked_channels),
            "temporal_gate": dict(time_gate.personality_influence_trace) if time_gate is not None else {},
            "neurochem_gate": dict(gate.personality_influence_trace) if gate is not None else {},
        }

        return ActionProposal(
            proposal_id=f"proposal::regulation::{uuid4().hex}",
            source_type="regulation",
            source_module="regulation_policy",
            intent_type="self_regulation",
            behavior_name=action_type,
            reason_summary=str(reason),
            score_bundle={
                "base": float(score),
                "final": final_score,
                "drive_urgency": float(drive_urgency),
                "personality_behavior_bias": behavior_bias,
                "personality_initiative_bias": projection.initiative_bias,
                "temporal_behavior_bias": temporal_behavior_bias,
                "temporal_exploration_pressure": time_gate.exploration_pressure if time_gate is not None else 0.0,
                "temporal_restorative_pull": time_gate.restorative_pull if time_gate is not None else 0.0,
                "neurochem_behavior_bias": neurochem_behavior_bias,
                "neurochem_initiative_bias": gate.initiative_bias if gate is not None else 0.0,
                "neurochem_caution_bias": gate.caution_bias if gate is not None else 0.0,
            },
            constraints={
                "drive_dominant": drive_dominant,
                "cooldown_seconds": behavior_profile.cooldown_seconds if behavior_profile is not None else 0,
                "night_suppress": behavior_profile.night_suppress if behavior_profile is not None else False,
                "prefer_restoration": time_gate.constrained("prefer_restoration") if time_gate is not None else False,
                "avoid_high_expression": gate.constrained("avoid_high_expression") if gate is not None else False,
            },
            suggested_modalities=modalities,
            candidate_channels=ranked_channels,
            parameters=dict(params or {}),
            provenance={
                "drive_dominant": drive_dominant,
                "drive_urgency": float(drive_urgency),
                "recent_action": recent_action,
                "personality_influence_trace": personality_trace,
                "personality_projection": projection.to_dict(),
                "temporal_gate": time_gate.to_dict() if time_gate is not None else {},
                "neurochem_gate": gate.to_dict() if gate is not None else {},
            },
            created_at_tick=tick,
            created_at_ts=time.time() if timestamp is None else float(timestamp),
        )

    def propose(
        self,
        assessment: RegulationAssessment,
        *,
        tick: int = 0,
        timestamp: float | None = None,
        candidate_channels: Sequence[str] | None = None,
        params: Mapping[str, object] | None = None,
        personality_projection: object | None = None,
        neurochem_gate: object | None = None,
        temporal_gate: object | None = None,
        recent_action: str = "",
    ) -> list[ActionProposal]:
        if not assessment.wants_regulation or not assessment.selected_action:
            return []
        return [
            self.build_action_proposal(
                assessment.selected_action,
                score=assessment.selected_score,
                tick=tick,
                timestamp=timestamp,
                candidate_channels=candidate_channels,
                params=params,
                drive_dominant=assessment.drive_dominant,
                drive_urgency=assessment.drive_urgency,
                dominant_emotions=assessment.dominant_emotions,
                personality_projection=personality_projection,
                neurochem_gate=neurochem_gate,
                temporal_gate=temporal_gate,
                recent_action=recent_action,
            )
        ]

    def detect_deviations(self, panksepp: Mapping[str, float], valence: float) -> list[tuple[str, float]]:
        deviations: list[tuple[str, float]] = []
        for sys_name, activation in panksepp.items():
            deviation = abs(float(activation) - self.baseline_activation)
            if deviation >= self.comfort_deviation:
                urgency = deviation
                if valence < -0.1 and activation > self.baseline_activation:
                    urgency *= 1.3
                deviations.append((str(sys_name), urgency))

        valence_dev = abs(float(valence) - self.baseline_valence)
        if valence_dev > self.comfort_deviation * 1.5 and deviations:
            deviations[0] = (deviations[0][0], deviations[0][1] * 1.2)

        deviations.sort(key=lambda item: -item[1])
        return deviations[:3]

    def query_candidates(
        self,
        sys_name: str,
        deviation: float,
        hour_of_day: int,
        *,
        memories: Mapping[str, Mapping[str, Any]],
        last_executed: Mapping[str, float],
    ) -> list[ActionCandidate]:
        is_night = hour_of_day >= 23 or hour_of_day < 7
        now = time.time()
        candidates: list[ActionCandidate] = []

        for behavior_profile in self.behavior_catalog.list_regulation_behaviors():
            action_type = behavior_profile.action_type
            cooldown_ok = now - float(last_executed.get(action_type, 0.0)) >= behavior_profile.cooldown_seconds
            if not cooldown_ok:
                continue

            night_safe = True
            if is_night and behavior_profile.night_suppress:
                if deviation < 0.5:
                    continue
                night_safe = False

            memory = memories.get(action_type, {}).get(sys_name)
            universal_memory = memories.get(action_type, {}).get("ALL")
            if memory is not None:
                expected_benefit = memory.delta_valence * 0.7 - memory.delta_activation * 0.3
                confidence = min(memory.count / 10.0, 1.0) * memory.success_rating
                mem_count = memory.count
            elif universal_memory is not None:
                expected_benefit = universal_memory.delta_valence * 0.5
                confidence = 0.3
                mem_count = 1
            else:
                expected_benefit = 0.1
                confidence = 0.1
                mem_count = 0

            candidates.append(
                ActionCandidate(
                    action_type=action_type,
                    expected_benefit=expected_benefit,
                    confidence=confidence,
                    memory_count=mem_count,
                    cooldown_ok=cooldown_ok,
                    night_safe=night_safe,
                    content_hint=behavior_profile.hint,
                )
            )

        return candidates

    def score_candidates_with_drives(
        self,
        candidates: Sequence[ActionCandidate],
        drive_urgency: float,
        drive_dominant: str,
        neurochem_gate: object | None = None,
        temporal_gate: object | None = None,
    ) -> None:
        gate = resolve_neurochem_gate(gate=neurochem_gate) if neurochem_gate is not None else None
        time_gate = resolve_temporal_gate(gate=temporal_gate) if temporal_gate is not None else None
        for candidate in candidates:
            emotional_score = candidate.score
            relevance = DRIVE_ACTION_RELEVANCE.get(drive_dominant, {}).get(candidate.action_type, 0.0)
            drive_score = drive_urgency * relevance
            neurochem_score = gate.bias_for_behavior(candidate.action_type) if gate is not None else 0.0
            temporal_score = time_gate.bias_for_behavior(candidate.action_type) if time_gate is not None else 0.0
            if gate is not None and gate.constrained("avoid_high_expression") and candidate.action_type.startswith("speak_"):
                neurochem_score -= 0.08
            if gate is not None and gate.constrained("prefer_exploration") and candidate.action_type in {"browse", "search", "learn", "speak_share"}:
                neurochem_score += 0.05
            if time_gate is not None and time_gate.constrained("prefer_restoration") and candidate.action_type in {"idle", "reflect", "check_system"}:
                temporal_score += 0.05
            if time_gate is not None and time_gate.constrained("avoid_high_expression") and candidate.action_type.startswith("speak_"):
                temporal_score -= 0.06
            candidate.final_score = 0.7 * emotional_score + 0.3 * drive_score + neurochem_score + temporal_score

    @staticmethod
    def apply_recent_feedback(
        candidates: Sequence[ActionCandidate],
        recent_execution_outcomes: Sequence[dict[str, object]],
    ) -> None:
        if not recent_execution_outcomes:
            return

        feedback_adjustments: dict[str, float] = {}
        for outcome in recent_execution_outcomes:
            action_name = str(outcome.get("action") or outcome.get("behavior_name") or "")
            if not action_name or "success" not in outcome:
                continue
            feedback_adjustments[action_name] = 0.03 if bool(outcome.get("success")) else -0.08

        if not feedback_adjustments:
            return

        for candidate in candidates:
            candidate.final_score += feedback_adjustments.get(candidate.action_type, 0.0)


__all__ = [
    "ActionCandidate",
    "RegulationAssessment",
    "RegulationPolicy",
    "RegulationSignals",
]