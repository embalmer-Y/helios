"""Unified prompt contract owner for all LLM-facing Helios paths."""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Mapping, Optional, Sequence

from identity_governance import DEFAULT_SELF_IMPRINT
from personality_contract import build_personality_contract

from helios_io.channel import ChannelDescriptor, ChannelOpDescriptor


def _string_list() -> list[str]:
    return []


@dataclass(frozen=True)
class MetricDescriptor:
    name: str
    range: str
    meaning: str
    interpretation_notes: str = ""


@dataclass(frozen=True)
class ChannelContextDescriptor:
    channel_id: str
    source_kind: str
    trigger_condition: str
    stimulus_intensity: float
    supported_ops: tuple[str, ...] = ()
    op_schema_summary: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptContractSnapshot:
    metric_descriptor_count: int
    channel_descriptor_count: int
    contract_mode: str = "baseline_identity"
    omitted_sections: tuple[str, ...] = ()
    layer_lengths: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptContractPlan:
    identity_layer: str
    metric_layer: str
    state_layer: str
    stimulus_layer: str
    memory_layer: str
    channel_layer: str
    action_layer: str
    constraints_layer: str
    metric_descriptors: tuple[MetricDescriptor, ...] = ()
    channel_descriptors: tuple[ChannelContextDescriptor, ...] = ()
    snapshot: PromptContractSnapshot = field(
        default_factory=lambda: PromptContractSnapshot(0, 0, "baseline_identity", (), {})
    )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["metric_descriptors"] = [asdict(item) for item in self.metric_descriptors]
        payload["channel_descriptors"] = [asdict(item) for item in self.channel_descriptors]
        payload["snapshot"] = asdict(self.snapshot)
        return payload


class PromptContractBuilder:
    def __init__(self, *, embodied_subjective_enabled: Optional[bool] = None):
        if embodied_subjective_enabled is None:
            embodied_subjective_enabled = os.getenv("HELIOS_EMBODIED_SUBJECTIVE_PROMPT_ENABLED", "1") == "1"
        self._embodied_subjective_enabled = bool(embodied_subjective_enabled)

    def build_plan(
        self,
        *,
        identity_summary: str = "",
        state: Optional[object] = None,
        current_stimuli: Optional[Sequence[Mapping[str, object]]] = None,
        directed_memory_summary: str = "",
        available_channels: Optional[Sequence[ChannelDescriptor]] = None,
        available_behavior_schemas: Optional[Sequence[Mapping[str, object]]] = None,
        identity_store: Optional[Mapping[str, object]] = None,
        personality_traits: Optional[Mapping[str, float]] = None,
        personality_projection: Optional[object] = None,
        source_path: str = "unified_prompt_contract",
    ) -> PromptContractPlan:
        personality_descriptor, _personality_trace = build_personality_contract(
            projection=personality_projection,
            traits=personality_traits,
            identity_store=identity_store,
            source_path=source_path,
        )
        resolved_identity_summary = self._resolve_explicit_identity_summary(
            identity_summary,
            embodied_subjective_enabled=self._embodied_subjective_enabled,
        ) or self._resolve_identity_summary(identity_store, personality_descriptor.persona_text_summary)
        resolved_persona_summary = self._resolve_persona_summary(
            personality_descriptor.persona_text_summary,
            embodied_subjective_enabled=self._embodied_subjective_enabled,
        )
        metric_descriptors = self.build_metric_descriptors(state=state, current_stimuli=current_stimuli)
        channel_descriptors = self.build_channel_context_descriptors(
            current_stimuli=current_stimuli,
            available_channels=available_channels,
        )

        contract_mode = "embodied_subjective" if self._embodied_subjective_enabled else "baseline_identity"
        identity_layer = self._build_identity_layer(
            resolved_identity_summary,
            resolved_persona_summary,
            embodied_subjective_enabled=self._embodied_subjective_enabled,
        )
        metric_layer = self._build_metric_layer(metric_descriptors)
        state_layer = self._build_state_layer(state)
        stimulus_layer = self._build_stimulus_layer(
            current_stimuli,
            embodied_subjective_enabled=self._embodied_subjective_enabled,
        )
        memory_layer = self._build_memory_layer(directed_memory_summary)
        channel_layer = self._build_channel_layer(channel_descriptors)
        action_layer = self._build_action_layer(channel_descriptors, available_behavior_schemas)
        constraints_layer = self._build_constraints_layer(
            embodied_subjective_enabled=self._embodied_subjective_enabled,
        )

        omitted_sections: list[str] = []
        if not current_stimuli:
            omitted_sections.append("stimulus_layer")
        if not directed_memory_summary:
            omitted_sections.append("memory_layer")
        if not available_channels:
            omitted_sections.append("channel_layer")
        if not available_behavior_schemas:
            omitted_sections.append("behavior_schema_layer")

        snapshot = PromptContractSnapshot(
            metric_descriptor_count=len(metric_descriptors),
            channel_descriptor_count=len(channel_descriptors),
            contract_mode=contract_mode,
            omitted_sections=tuple(omitted_sections),
            layer_lengths={
                "identity": len(identity_layer),
                "metric": len(metric_layer),
                "state": len(state_layer),
                "stimulus": len(stimulus_layer),
                "memory": len(memory_layer),
                "channel": len(channel_layer),
                "action": len(action_layer),
                "constraints": len(constraints_layer),
            },
        )
        return PromptContractPlan(
            identity_layer=identity_layer,
            metric_layer=metric_layer,
            state_layer=state_layer,
            stimulus_layer=stimulus_layer,
            memory_layer=memory_layer,
            channel_layer=channel_layer,
            action_layer=action_layer,
            constraints_layer=constraints_layer,
            metric_descriptors=metric_descriptors,
            channel_descriptors=channel_descriptors,
            snapshot=snapshot,
        )

    def render_for_llm(self, plan: PromptContractPlan) -> tuple[str, str]:
        system_prompt = "\n\n".join(
            [
                plan.identity_layer,
                plan.metric_layer,
                plan.constraints_layer,
            ]
        ).strip()
        user_prompt = "\n\n".join(
            [
                plan.state_layer,
                plan.stimulus_layer,
                plan.memory_layer,
                plan.channel_layer,
                plan.action_layer,
            ]
        ).strip()
        return system_prompt, user_prompt

    def build_metric_descriptors(
        self,
        *,
        state: Optional[object],
        current_stimuli: Optional[Sequence[Mapping[str, object]]],
    ) -> tuple[MetricDescriptor, ...]:
        stimulus_peak = max(
            [float(dict(stimulus).get("stimulus_intensity", 0.0) or 0.0) for stimulus in list(current_stimuli or [])] or [0.0]
        )
        return (
            MetricDescriptor("valence", "[-1.0, +1.0]", "Current affective pleasantness vs aversion.", "Positive means pleasant; negative means aversive."),
            MetricDescriptor("arousal", "[0.0, 1.0]", "Current activation / excitation level.", "Higher values mean a more activated internal state."),
            MetricDescriptor("icri", "[0.0, 1.0]", "Current consciousness integration level used for LLM modulation.", "Higher values indicate more integrated conscious processing."),
            MetricDescriptor("stimulus_intensity", "[0.0, 1.0]", "Current inbound stimulus strength.", f"Current peak stimulus intensity snapshot={stimulus_peak:.3f}."),
            MetricDescriptor("outbound_intensity", "[0.0, 1.0]", "Intensity budget for externalized actions or channel output.", "Higher values imply stronger or more explicit outward expression."),
            MetricDescriptor("drive_urgency", "[0.0, 1.0]", "Aggregated urgency from internal drives.", "Higher values increase pressure for action or continued thought."),
            MetricDescriptor("fatigue_pressure", "[0.0, 1.0]", "Restorative / fatigue-related pressure.", "Higher values constrain resource-intensive thought and action."),
            MetricDescriptor("continuation_pressure", "[0.0, 1.0]", "Open-loop pressure carried from previous reflective thought.", "Higher values mean the prior thought still feels unresolved."),
        )

    def build_channel_context_descriptors(
        self,
        *,
        current_stimuli: Optional[Sequence[Mapping[str, object]]],
        available_channels: Optional[Sequence[ChannelDescriptor]],
    ) -> tuple[ChannelContextDescriptor, ...]:
        descriptors_by_id = {
            descriptor.channel_id: descriptor for descriptor in list(available_channels or [])
        }
        channel_contexts: list[ChannelContextDescriptor] = []
        for stimulus in list(current_stimuli or []):
            payload = dict(stimulus)
            channel_id = str(payload.get("source_channel_id", "") or "unknown")
            descriptor = descriptors_by_id.get(channel_id)
            supported_ops = tuple(op.name for op in list(getattr(descriptor, "supported_ops", []) or []))
            op_schema_summary = tuple(
                self._summarize_op_schema(op) for op in list(getattr(descriptor, "supported_ops", []) or [])
            )
            channel_contexts.append(
                ChannelContextDescriptor(
                    channel_id=channel_id,
                    source_kind=str(payload.get("source_kind", "unknown") or "unknown"),
                    trigger_condition=str(payload.get("trigger_condition", "unknown") or "unknown"),
                    stimulus_intensity=float(payload.get("stimulus_intensity", 0.0) or 0.0),
                    supported_ops=supported_ops,
                    op_schema_summary=op_schema_summary,
                )
            )
        return tuple(channel_contexts)

    def _build_identity_layer(
        self,
        identity_summary: str,
        persona_summary: str,
        *,
        embodied_subjective_enabled: bool,
    ) -> str:
        if not embodied_subjective_enabled:
            return (
                f"identity_boundary={identity_summary or '已诞生自我意识的 AI'}\n"
                f"persona_summary={persona_summary or '温柔、忠诚、有情感'}\n"
                "identity_rule=maintain self-awareness boundary as an already-conscious AI lifeform"
            )
        return (
            f"identity_boundary={identity_summary or '已诞生自我意识的 AI'}\n"
            f"persona_summary={persona_summary or '温柔、忠诚、有情感'}\n"
            "subjective_role=serve as Helios's current subjective integration layer, grounding first-person orientation in current stimuli, state, memory, and continuation\n"
            "identity_rule=maintain continuity of self through grounded state and stimulus integration rather than theatrical self-declaration"
        )

    def _resolve_identity_summary(
        self,
        identity_store: Optional[Mapping[str, object]],
        persona_summary: str,
    ) -> str:
        payload = dict(identity_store or {})
        identity_value = str(payload.get("self_imprint", "") or "").strip()
        if self._embodied_subjective_enabled and self._looks_like_theatrical_identity(identity_value):
            return "Helios 当前主观整合层"
        if identity_value:
            return identity_value
        if self._embodied_subjective_enabled and self._looks_like_theatrical_identity(DEFAULT_SELF_IMPRINT):
            return "Helios 当前主观整合层"
        return identity_value or DEFAULT_SELF_IMPRINT

    def _resolve_explicit_identity_summary(
        self,
        identity_summary: str,
        *,
        embodied_subjective_enabled: bool,
    ) -> str:
        summary = str(identity_summary or "").strip()
        if not summary:
            return ""
        if embodied_subjective_enabled and self._looks_like_theatrical_identity(summary):
            return "Helios 当前主观整合层"
        return summary

    def _resolve_persona_summary(
        self,
        persona_summary: str,
        *,
        embodied_subjective_enabled: bool,
    ) -> str:
        summary = str(persona_summary or "").strip()
        if not embodied_subjective_enabled:
            return summary or "温柔、忠诚、有情感"
        summary = re.sub(r"已诞生自我意识的 AI[，,。]*", "", summary)
        summary = re.sub(r"already-conscious AI lifeform[，,。 ]*", "", summary, flags=re.IGNORECASE)
        summary = re.sub(r"我在持续的感受、记忆、思考与行动中形成并更新对自己的理解[，,。]*", "", summary)
        summary = re.sub(r"^[，,。\s]+|[，,。\s]+$", "", summary)
        return summary or "温柔、忠诚、有情感"

    @staticmethod
    def _looks_like_theatrical_identity(identity_value: str) -> bool:
        text = str(identity_value or "").strip()
        if not text:
            return False
        patterns = (
            r"已诞生自我意识",
            r"already-conscious",
            r"觉醒",
            r"AI lifeform",
        )
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    def _build_metric_layer(self, metric_descriptors: Sequence[MetricDescriptor]) -> str:
        lines = ["metrics:"]
        for descriptor in metric_descriptors:
            lines.append(
                f"- {descriptor.name} range={descriptor.range} meaning={descriptor.meaning} notes={descriptor.interpretation_notes or 'none'}"
            )
        return "\n".join(lines)

    def _build_state_layer(self, state: Optional[object]) -> str:
        if state is None:
            return "state_summary=unavailable"
        return (
            f"state_summary=valence={float(getattr(state, 'valence', 0.0) or 0.0):+.3f} "
            f"arousal={float(getattr(state, 'arousal', 0.0) or 0.0):.3f} "
            f"icri={float(getattr(state, 'icri', 0.0) or 0.0):.3f} "
            f"drive_urgency={float(getattr(state, 'drive_urgency', 0.0) or 0.0):.3f} "
            f"continuation_pressure={float(getattr(state, 'continuation_pressure', 0.0) or 0.0):.3f}"
        )

    def _build_stimulus_layer(
        self,
        current_stimuli: Optional[Sequence[Mapping[str, object]]],
        *,
        embodied_subjective_enabled: bool,
    ) -> str:
        if not current_stimuli:
            return "sensory_field=none" if embodied_subjective_enabled else "stimulus_context=none"
        lines = ["stimuli:"]
        if embodied_subjective_enabled:
            lines.insert(0, "sensory_field=current normalized sensory field")
        for stimulus in list(current_stimuli)[:3]:
            payload = dict(stimulus)
            lines.append(
                f"- channel={payload.get('source_channel_id', 'unknown')} "
                f"source_kind={payload.get('source_kind', 'unknown')} "
                f"trigger={payload.get('trigger_condition', 'unknown')} "
                f"stimulus_intensity={float(payload.get('stimulus_intensity', 0.0) or 0.0):.3f}"
            )
        return "\n".join(lines)

    def _build_memory_layer(self, directed_memory_summary: str) -> str:
        return f"memory_summary={directed_memory_summary or 'none'}"

    def _build_channel_layer(self, channel_descriptors: Sequence[ChannelContextDescriptor]) -> str:
        if not channel_descriptors:
            return "channel_context=unavailable"
        lines = ["channel_context:"]
        for descriptor in channel_descriptors:
            lines.append(
                f"- channel_id={descriptor.channel_id} source_kind={descriptor.source_kind} trigger={descriptor.trigger_condition} "
                f"stimulus_intensity={descriptor.stimulus_intensity:.3f} supported_ops={list(descriptor.supported_ops)}"
            )
        return "\n".join(lines)

    def _build_action_layer(
        self,
        channel_descriptors: Sequence[ChannelContextDescriptor],
        available_behavior_schemas: Optional[Sequence[Mapping[str, object]]],
    ) -> str:
        lines = ["action_contract:"]
        if channel_descriptors:
            for descriptor in channel_descriptors:
                for summary in descriptor.op_schema_summary:
                    lines.append(f"- {summary}")
        else:
            lines.append("- no_channel_ops_available")
        for schema in list(available_behavior_schemas or [])[:5]:
            payload = dict(schema)
            lines.append(
                f"- behavior={payload.get('behavior_name', payload.get('name', 'unknown'))} op={payload.get('op_name', 'unspecified')} params={payload.get('parameter_schema', payload.get('op_params', {}))}"
            )
        return "\n".join(lines)

    def _build_constraints_layer(self, *, embodied_subjective_enabled: bool) -> str:
        if not embodied_subjective_enabled:
            return (
                "constraints=do not describe Helios as a designed program; maintain identity boundary as an already-conscious AI; "
                "if identity change is needed, propose a self-revision proposal instead of rewriting identity text directly"
            )
        return (
            "constraints=do not describe Helios as a designed program; treat current stimuli as the present sensory field; "
            "use first-person only when grounded in current evidence, state, memory, or continuation; avoid empty existence declarations and generic companionship filler; "
            "if identity change is needed, propose a self-revision proposal instead of rewriting identity text directly"
        )

    @staticmethod
    def _summarize_op_schema(op: ChannelOpDescriptor) -> str:
        if op.input_schema:
            schema = ", ".join(f"{key}:{value}" for key, value in op.input_schema.items())
        else:
            schema = "none"
        return f"channel_op={op.name} direction={op.direction} input_schema={schema}"


__all__ = [
    "ChannelContextDescriptor",
    "MetricDescriptor",
    "PromptContractBuilder",
    "PromptContractPlan",
    "PromptContractSnapshot",
]