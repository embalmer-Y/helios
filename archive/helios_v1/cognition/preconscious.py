"""Bounded preconscious candidate generation for low-latency internal behaviors."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import time
from typing import Iterable, Optional
from uuid import uuid4

from helios_io.action_models import ActionDecision, ActionProposal, ExecutionFeedback
from helios_io.limb import BehaviorCommand
from memory import MemorySearchHit
from neurochem_gate import resolve_neurochem_gate
from personality_projection import resolve_personality_projection
from temporal_gate import resolve_temporal_gate


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class PreconsciousSignals:
    thought_type: str = ""
    thought_content: str = ""
    thought_generated: bool = False
    icri: float = 0.0
    valence: float = 0.0
    arousal: float = 0.0
    dominant_system: str = ""
    drive_urgency: float = 0.0
    boredom: float = 0.0
    novelty_hunger: float = 0.0
    fatigue_pressure: float = 0.0
    restoration_level: float = 0.0
    dmn_active: bool = False
    memory_hit_count: int = 0
    top_memory_score: float = 0.0
    strongest_stimulus_intensity: float = 0.0
    strongest_stimulus_channel: str = ""
    strongest_stimulus_user_id: str = ""
    personality_projection: object | None = None
    temporal_gate: object | None = None
    neurochem_gate: object | None = None


@dataclass
class PreconsciousAssessment:
    wants_action: bool
    primary_behavior: str = ""
    candidate_behaviors: list[str] = field(default_factory=list)
    score: float = 0.0
    reason_summary: str = ""
    feature_bundle: dict[str, float] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)


class PreconsciousPolicy:
    """Generate low-commitment proposals from thought and replay salience."""

    THOUGHT_BEHAVIOR_MAP = {
        "rumination": "reflect",
        "counterfactual": "reflect",
        "episodic_fragment": "reflect",
        "self_question": "learn",
        "future_projection": "learn",
        "free_association": "browse",
    }

    def __init__(self, *, activation_threshold: float = 0.28, score_cap: float = 0.72):
        self._activation_threshold = activation_threshold
        self._score_cap = score_cap
        self._feedback_history: list[dict[str, object]] = []
        self._rejection_history: list[dict[str, object]] = []
        self._last_observability_snapshot: dict[str, object] = self._build_empty_snapshot()

    def collect_signals(self, *, state, thought=None, memory_hits: Optional[Iterable[MemorySearchHit]] = None) -> PreconsciousSignals:
        hits = list(memory_hits or [])
        top_memory_score = max((float(hit.score) for hit in hits), default=0.0)
        stimuli = list(getattr(state, "current_stimuli", []) or [])
        strongest_stimulus = max(
            stimuli,
            key=lambda item: float(item.get("stimulus_intensity", 0.0) or 0.0),
            default={},
        )
        strongest_payload = dict(strongest_stimulus.get("payload", {}) or {})
        return PreconsciousSignals(
            thought_type=str(getattr(thought, "type", "") or getattr(state, "last_thought_type", "")),
            thought_content=str(getattr(thought, "content", "") or ""),
            thought_generated=bool(thought),
            icri=float(getattr(state, "icri", 0.0) or 0.0),
            valence=float(getattr(state, "valence", 0.0) or 0.0),
            arousal=float(getattr(state, "arousal", 0.0) or 0.0),
            dominant_system=str(getattr(state, "dominant_system", "") or ""),
            drive_urgency=float(getattr(state, "drive_urgency", 0.0) or 0.0),
            boredom=float(getattr(state, "boredom", 0.0) or 0.0),
            novelty_hunger=float(getattr(state, "novelty_hunger", 0.0) or 0.0),
            fatigue_pressure=float(getattr(state, "fatigue_pressure", 0.0) or 0.0),
            restoration_level=float(getattr(state, "restoration_level", 0.0) or 0.0),
            dmn_active=bool(getattr(state, "dmn_active", False)),
            memory_hit_count=len(hits),
            top_memory_score=top_memory_score,
            strongest_stimulus_intensity=float(strongest_stimulus.get("stimulus_intensity", 0.0) or 0.0),
            strongest_stimulus_channel=str(strongest_stimulus.get("source_channel_id", "") or ""),
            strongest_stimulus_user_id=str(strongest_payload.get("user_id", "") or strongest_stimulus.get("user_id", "") or ""),
            personality_projection=getattr(state, "personality_projection", None),
            temporal_gate=getattr(state, "temporal_gate", None),
            neurochem_gate=getattr(state, "neurochem_gate", None),
        )

    def assess(self, signals: PreconsciousSignals) -> PreconsciousAssessment:
        projection = resolve_personality_projection(projection=signals.personality_projection)
        temporal_gate = resolve_temporal_gate(gate=signals.temporal_gate) if signals.temporal_gate is not None else resolve_temporal_gate()
        neurochem_gate = resolve_neurochem_gate(gate=signals.neurochem_gate) if signals.neurochem_gate is not None else resolve_neurochem_gate()

        if not signals.thought_generated and signals.memory_hit_count == 0:
            return PreconsciousAssessment(wants_action=False, reason_summary="no_preconscious_salience")
        if signals.icri < 0.12 or not signals.dmn_active:
            return PreconsciousAssessment(wants_action=False, reason_summary="dmn_or_icri_gate_closed")

        reflection_pressure = _clamp(
            (0.28 if signals.thought_type in {"rumination", "counterfactual", "episodic_fragment"} else 0.0)
            + signals.top_memory_score * 0.10
            + signals.memory_hit_count * 0.04
            + projection.persistence_bias * 0.18,
            0.0,
            1.0,
        )
        exploration_pressure = _clamp(
            (0.22 if signals.thought_type in {"self_question", "future_projection", "free_association"} else 0.0)
            + signals.novelty_hunger * 0.24
            + projection.novelty_bias * 0.18
            + signals.drive_urgency * 0.10
            + temporal_gate.exploration_pressure * 0.18,
            0.0,
            1.0,
        )
        fatigue_penalty = _clamp(
            signals.fatigue_pressure * 0.26
            + temporal_gate.restorative_pull * 0.18
            + neurochem_gate.caution_bias * 0.10,
            0.0,
            0.65,
        )
        base_score = _clamp(
            0.12
            + max(reflection_pressure, exploration_pressure)
            + min(signals.icri, 0.8) * 0.08
            - fatigue_penalty,
            0.0,
            self._score_cap,
        )

        primary_behavior = self._thought_behavior(signals.thought_type)
        if primary_behavior == "browse" and exploration_pressure < 0.42:
            primary_behavior = "reflect"
        if primary_behavior == "learn" and exploration_pressure < reflection_pressure:
            primary_behavior = "reflect"

        if base_score < self._activation_threshold or not primary_behavior:
            return PreconsciousAssessment(
                wants_action=False,
                score=base_score,
                reason_summary="preconscious_score_below_threshold",
                feature_bundle={
                    "reflection_pressure": reflection_pressure,
                    "exploration_pressure": exploration_pressure,
                    "fatigue_penalty": fatigue_penalty,
                    "final": base_score,
                },
            )

        candidates = [primary_behavior]
        if primary_behavior != "reflect" and reflection_pressure >= self._activation_threshold - 0.04:
            candidates.append("reflect")
        if primary_behavior == "reflect" and exploration_pressure >= self._activation_threshold + 0.06:
            candidates.append("learn")
        candidates = list(dict.fromkeys(candidates))

        return PreconsciousAssessment(
            wants_action=True,
            primary_behavior=primary_behavior,
            candidate_behaviors=candidates,
            score=base_score,
            reason_summary="preconscious salience surfaced a low-commitment internal candidate",
            feature_bundle={
                "icri": signals.icri,
                "memory_hit_count": float(signals.memory_hit_count),
                "top_memory_score": signals.top_memory_score,
                "reflection_pressure": reflection_pressure,
                "exploration_pressure": exploration_pressure,
                "fatigue_penalty": fatigue_penalty,
                "personality_novelty_bias": projection.novelty_bias,
                "personality_persistence_bias": projection.persistence_bias,
                "personality_social_initiation_bias": projection.social_initiation_bias,
                "temporal_exploration_pressure": temporal_gate.exploration_pressure,
                "temporal_restorative_pull": temporal_gate.restorative_pull,
                "neurochem_caution_bias": neurochem_gate.caution_bias,
                "final": base_score,
            },
            rationale=[
                f"thought_type={signals.thought_type or 'none'}",
                f"memory_hits={signals.memory_hit_count}",
                f"reflection={reflection_pressure:.2f}",
                f"exploration={exploration_pressure:.2f}",
                f"fatigue_penalty={fatigue_penalty:.2f}",
            ],
        )

    def propose(self, *, state, thought=None, memory_hits: Optional[Iterable[MemorySearchHit]] = None) -> list[ActionProposal]:
        signals = self.collect_signals(state=state, thought=thought, memory_hits=memory_hits)
        projection = resolve_personality_projection(projection=signals.personality_projection)
        assessment = self.assess(signals)
        if not assessment.wants_action:
            self._update_observability_snapshot(signals=signals, assessment=assessment, proposals=[])
            return []

        proposals: list[ActionProposal] = []
        for index, behavior_name in enumerate(assessment.candidate_behaviors):
            final_score = _clamp(assessment.score - index * 0.06, 0.0, self._score_cap)
            proposals.append(
                ActionProposal(
                    proposal_id=f"proposal::preconscious::{uuid4().hex}",
                    source_type="preconscious",
                    source_module="preconscious_policy",
                    origin_type="thought",
                    origin_id=self._build_thought_origin_id(state=state, thought=thought, signals=signals),
                    intent_type="internal_bias",
                    behavior_name=behavior_name,
                    reason_summary=assessment.reason_summary,
                    score_bundle={**assessment.feature_bundle, "final": final_score},
                    constraints={
                        "requires_deliberate_review": True,
                    },
                    suggested_modalities=["internal"],
                    candidate_channels=[],
                    parameters={
                        "tick": int(getattr(state, "tick", 0)),
                        "preconscious_context": {
                            "thought_type": signals.thought_type,
                            "thought_generated": signals.thought_generated,
                        },
                    },
                    provenance={
                        "thought_type": signals.thought_type,
                        "thought_content": signals.thought_content,
                        "rationale": list(assessment.rationale),
                        "personality_projection": projection.to_dict(),
                    },
                    created_at_tick=int(getattr(state, "tick", 0)),
                    created_at_ts=float(getattr(state, "timestamp", time.time())),
                )
            )
        self._update_observability_snapshot(signals=signals, assessment=assessment, proposals=proposals)
        return proposals

    @staticmethod
    def _build_thought_origin_id(*, state, thought, signals: PreconsciousSignals) -> str:
        timestamp = getattr(thought, "timestamp", getattr(state, "timestamp", time.time()))
        return f"thought::{int(getattr(state, 'tick', 0))}::{signals.thought_type or 'unknown'}::{int(float(timestamp) * 1000)}"

    def observe_idle_tick(self, *, state, reason: str = "no_preconscious_thought") -> None:
        self._last_observability_snapshot = {
            **self._build_empty_snapshot(),
            "source_type": "preconscious",
            "owner_role": "secondary_helper",
            "active": False,
            "skip_reason": reason,
            "signals": {
                "thought_type": str(getattr(state, "last_thought_type", "") or ""),
                "thought_generated": False,
                "icri": float(getattr(state, "icri", 0.0) or 0.0),
                "dmn_active": bool(getattr(state, "dmn_active", False)),
            },
            "assessment": {
                "wants_action": False,
                "reason_summary": reason,
                "candidate_behaviors": [],
                "rationale": [],
            },
        }
        self._refresh_history_fields()

    @property
    def feedback_history(self) -> list[dict[str, object]]:
        return list(self._feedback_history)

    @property
    def rejection_history(self) -> list[dict[str, object]]:
        return list(self._rejection_history)

    def get_observability_snapshot(self) -> dict[str, object]:
        return deepcopy(self._last_observability_snapshot)

    def on_execution_feedback(self, command: BehaviorCommand, feedback: ExecutionFeedback) -> None:
        self._feedback_history.append(
            {
                "proposal_id": feedback.proposal_id,
                "decision_id": feedback.decision_id,
                "behavior_name": feedback.behavior_name,
                "success": feedback.success,
                "channel_id": feedback.channel_id,
                "tick": feedback.observed_at_tick,
                "source_type": str(command.provenance.get("source_type", "")),
                "thought_type": str(((command.params or {}).get("preconscious_context") or {}).get("thought_type", "")),
            }
        )
        self._feedback_history = self._feedback_history[-20:]
        self._refresh_history_fields()

    def on_decision_rejected(self, proposal: ActionProposal, decision: ActionDecision) -> None:
        self._rejection_history.append(
            {
                "proposal_id": proposal.proposal_id,
                "behavior_name": proposal.behavior_name,
                "rejection_reason": decision.rejection_reason,
                "source_type": proposal.source_type,
                "thought_type": str((proposal.provenance or {}).get("thought_type", "")),
            }
        )
        self._rejection_history = self._rejection_history[-20:]
        self._refresh_history_fields()

    def _build_empty_snapshot(self) -> dict[str, object]:
        return {
            "source_type": "preconscious",
            "active": False,
            "skip_reason": "",
            "signals": {},
            "assessment": {},
            "proposals": [],
            "latest_feedback": {},
            "latest_rejection": {},
            "recent_feedback": [],
            "recent_rejections": [],
            "feedback_count": 0,
            "rejection_count": 0,
        }

    def _update_observability_snapshot(
        self,
        *,
        signals: PreconsciousSignals,
        assessment: PreconsciousAssessment,
        proposals: list[ActionProposal],
    ) -> None:
        self._last_observability_snapshot = {
            **self._build_empty_snapshot(),
            "source_type": "preconscious",
            "owner_role": "secondary_helper",
            "active": True,
            "skip_reason": "",
            "signals": {
                "thought_type": signals.thought_type,
                "thought_generated": signals.thought_generated,
                "icri": signals.icri,
                "valence": signals.valence,
                "arousal": signals.arousal,
                "dominant_system": signals.dominant_system,
                "memory_hit_count": signals.memory_hit_count,
                "top_memory_score": signals.top_memory_score,
                "drive_urgency": signals.drive_urgency,
                "boredom": signals.boredom,
                "novelty_hunger": signals.novelty_hunger,
                "fatigue_pressure": signals.fatigue_pressure,
                "restoration_level": signals.restoration_level,
                "dmn_active": signals.dmn_active,
            },
            "assessment": {
                "wants_action": assessment.wants_action,
                "primary_behavior": assessment.primary_behavior,
                "candidate_behaviors": list(assessment.candidate_behaviors),
                "score": assessment.score,
                "reason_summary": assessment.reason_summary,
                "feature_bundle": dict(assessment.feature_bundle),
                "rationale": list(assessment.rationale),
            },
            "proposals": [
                {
                    "proposal_id": proposal.proposal_id,
                    "behavior_name": proposal.behavior_name,
                    "intent_type": proposal.intent_type,
                    "final_score": float(proposal.score_bundle.get("final", 0.0)),
                    "constraints": dict(proposal.constraints),
                }
                for proposal in proposals
            ],
        }
        self._refresh_history_fields()

    def _refresh_history_fields(self) -> None:
        self._last_observability_snapshot["latest_feedback"] = dict(self._feedback_history[-1]) if self._feedback_history else {}
        self._last_observability_snapshot["latest_rejection"] = dict(self._rejection_history[-1]) if self._rejection_history else {}
        self._last_observability_snapshot["recent_feedback"] = [dict(item) for item in self._feedback_history[-3:]]
        self._last_observability_snapshot["recent_rejections"] = [dict(item) for item in self._rejection_history[-3:]]
        self._last_observability_snapshot["feedback_count"] = len(self._feedback_history)
        self._last_observability_snapshot["rejection_count"] = len(self._rejection_history)

    @classmethod
    def _thought_behavior(cls, thought_type: str) -> str:
        return cls.THOUGHT_BEHAVIOR_MAP.get(thought_type, "reflect")


__all__ = ["PreconsciousAssessment", "PreconsciousPolicy", "PreconsciousSignals"]