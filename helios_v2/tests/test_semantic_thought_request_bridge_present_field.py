"""R91: focused tests for the composition-side `_present_field_summary_text` helper and the
`SemanticInternalThoughtRequestBridge.temporal_source` plumbing.

The helper is tested directly with minimal frame fixtures (an `08` `ConsciousContentStageResult`
either active with focal content or returned as the `inactive` no-percept sentinel). Owner-neutral:
the helper imports/reads only published `08` state and an optional `TemporalSource`. The bridge
field plumbing (`temporal_source` -> helper) is asserted via construction + signature; the legacy
bridge's None default behavior is asserted by reading the helper's path on a frame missing `08`.
"""

from __future__ import annotations

import pytest

from helios_v2.composition.bridges import (
    FirstVersionInternalThoughtRequestBridge,
    SemanticInternalThoughtRequestBridge,
    _present_field_summary_text,
)
from helios_v2.runtime.contracts import RuntimeFrame
from helios_v2.runtime.stages import ConsciousContentStageResult


# --- direct helper tests ------------------------------------------------------


def _frame_with_focal(focal_summary: str, salient_tokens: tuple[str, ...]) -> RuntimeFrame:
    """Build a frame whose `08` stage published a real focal `ReportableConsciousContent`."""

    from helios_v2.consciousness.contracts import (
        ConsciousContentMaterial,
        ConsciousContentMaterialSet,
        ConsciousState,
        ReportableConsciousContent,
        SupportingContextItem,
    )
    from helios_v2.feeling import InteroceptiveFeelingVector

    affect = InteroceptiveFeelingVector(
        valence=0.4, arousal=0.5, tension=0.5, comfort=0.4,
        fatigue=0.3, pain_like=0.3, social_safety=0.4,
    )
    focal = ReportableConsciousContent(
        content_id="conscious-content:focal:001",
        source_material_id="conscious-material:001",
        source_workspace_candidate_id="workspace-candidate:001",
        source_memory_candidate_id="memory-candidate:001",
        source_feeling_state_id="feeling-state:001",
        content_kind="perceived-stimulus-summary",
        focal_summary=focal_summary,
        affect_trace=affect,
        salient_tokens=salient_tokens,
        tick_id=1,
    )
    state = ConsciousState(
        state_id="conscious-state:001",
        commit_status="committed",
        source_workspace_candidate_set_id="ws-set:001",
        source_working_state_id="working:001",
        focal_content=focal,
        supporting_context=(),
        no_commit_reason=None,
        tick_id=1,
    )
    material = ConsciousContentMaterial(
        material_id="conscious-material:001",
        source_workspace_candidate_id="workspace-candidate:001",
        source_memory_candidate_id="memory-candidate:001",
        source_memory_id="memory:001",
        source_feeling_state_id="feeling-state:001",
        content_kind="perceived-stimulus-summary",
        material_summary="(unused in helper)",
        summary_ref=None,
        context_ref=None,
        salient_tokens=salient_tokens,
        affect_tag=affect,
        forced_consolidation=False,
        workspace_score_hint=0.6,
        priority_hint=0.6,
    )
    material_set = ConsciousContentMaterialSet(
        set_id="ws-set:001",
        source_workspace_candidate_set_id="ws-set:001",
        source_working_state_id="working:001",
        materials=(material,),
        tick_id=1,
    )
    stage_result = ConsciousContentStageResult(
        commit_op=None,
        material_set=material_set,
        state=state,
        publish_state_op=None,
        publish_reportable_content_op=None,
        activated=True,
        inactive_id=None,
    )
    return RuntimeFrame(tick_id=1, stage_results={"reportable_conscious_content": stage_result})


def _frame_inactive() -> RuntimeFrame:
    return RuntimeFrame(
        tick_id=1,
        stage_results={"reportable_conscious_content": ConsciousContentStageResult.inactive(1)},
    )


def _frame_missing() -> RuntimeFrame:
    return RuntimeFrame(tick_id=1, stage_results={})


def _frame_with_stimuli(*pairs: tuple[str, str, str]) -> RuntimeFrame:
    """Build a frame whose `02` published a `SensoryIngressStageResult` carrying the given stimuli.

    Each pair is `(modality, source_name, content)`. `modality="cli"` etc. are external; "body" /
    "interoceptive" / "background" are filtered out by the helper.
    """

    from helios_v2.runtime.stages import SensoryIngressStageResult
    from helios_v2.sensory.contracts import Stimulus, StimulusBatch

    stimuli = tuple(
        Stimulus(
            stimulus_id=f"stim:{i}",
            source_name=src,
            modality=mod,
            content=content,
            channel=None,
            metadata=None,
            provenance_signal_id=f"signal:{i}",
        )
        for i, (mod, src, content) in enumerate(pairs)
    )
    batch = StimulusBatch(batch_id="batch:001", stimuli=stimuli)
    return RuntimeFrame(
        tick_id=1,
        stage_results={
            "sensory_ingress": SensoryIngressStageResult(batch=batch, publish_op=None)
        },
    )


def _frame_combined(*pairs, focal_summary=None, salient_tokens=()):
    """Frame with both `02` external stimuli and an `08` focal commitment (when supplied)."""

    from helios_v2.consciousness.contracts import (
        ConsciousContentMaterial,
        ConsciousContentMaterialSet,
        ConsciousState,
        ReportableConsciousContent,
    )
    from helios_v2.feeling import InteroceptiveFeelingVector
    from helios_v2.runtime.stages import SensoryIngressStageResult
    from helios_v2.sensory.contracts import Stimulus, StimulusBatch

    stimuli = tuple(
        Stimulus(
            stimulus_id=f"stim:{i}",
            source_name=src,
            modality=mod,
            content=content,
            channel=None,
            metadata=None,
            provenance_signal_id=f"signal:{i}",
        )
        for i, (mod, src, content) in enumerate(pairs)
    )
    batch = StimulusBatch(batch_id="batch:001", stimuli=stimuli)
    sensory = SensoryIngressStageResult(batch=batch, publish_op=None)
    stage_results: dict[str, object] = {"sensory_ingress": sensory}
    if focal_summary is not None:
        affect = InteroceptiveFeelingVector(
            valence=0.4, arousal=0.5, tension=0.5, comfort=0.4,
            fatigue=0.3, pain_like=0.3, social_safety=0.4,
        )
        focal = ReportableConsciousContent(
            content_id="conscious-content:focal:001",
            source_material_id="conscious-material:001",
            source_workspace_candidate_id="workspace-candidate:001",
            source_memory_candidate_id="memory-candidate:001",
            source_feeling_state_id="feeling-state:001",
            content_kind="perceived-stimulus-summary",
            focal_summary=focal_summary,
            affect_trace=affect,
            salient_tokens=salient_tokens,
            tick_id=1,
        )
        state = ConsciousState(
            state_id="conscious-state:001",
            commit_status="committed",
            source_workspace_candidate_set_id="ws-set:001",
            source_working_state_id="working:001",
            focal_content=focal,
            supporting_context=(),
            no_commit_reason=None,
            tick_id=1,
        )
        material = ConsciousContentMaterial(
            material_id="conscious-material:001",
            source_workspace_candidate_id="workspace-candidate:001",
            source_memory_candidate_id="memory-candidate:001",
            source_memory_id="memory:001",
            source_feeling_state_id="feeling-state:001",
            content_kind="perceived-stimulus-summary",
            material_summary="(unused)",
            summary_ref=None,
            context_ref=None,
            salient_tokens=salient_tokens,
            affect_tag=affect,
            forced_consolidation=False,
            workspace_score_hint=0.6,
            priority_hint=0.6,
        )
        material_set = ConsciousContentMaterialSet(
            set_id="ws-set:001",
            source_workspace_candidate_set_id="ws-set:001",
            source_working_state_id="working:001",
            materials=(material,),
            tick_id=1,
        )
        stage_results["reportable_conscious_content"] = ConsciousContentStageResult(
            commit_op=None,
            material_set=material_set,
            state=state,
            publish_state_op=None,
            publish_reportable_content_op=None,
            activated=True,
            inactive_id=None,
        )
    return RuntimeFrame(tick_id=1, stage_results=stage_results)


class _StubTemporalSource:
    """Minimal stand-in for a TemporalSource — sample() returns a fixed bounded signal."""

    def __init__(self, signal: float = 0.4) -> None:
        self._signal = signal

    def sample(self, external_stimulus_present: bool):  # noqa: ARG002 - bridge passes the flag
        from helios_v2.temporal.contracts import TemporalPacingSample
        return TemporalPacingSample(temporal_signal=self._signal, dmn_available=True)


def test_present_field_text_projects_focal_summary_and_tokens() -> None:
    frame = _frame_with_focal(
        focal_summary="苏蕊 just shared pre-defense anxiety",
        salient_tokens=("苏蕊", "答辩", "焦虑"),
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    assert text.startswith("focal: 苏蕊 just shared pre-defense anxiety")
    assert "tokens: 苏蕊, 答辩, 焦虑" in text


def test_present_field_text_appends_pacing_when_temporal_source_wired() -> None:
    frame = _frame_with_focal("focal A", salient_tokens=())
    text = _present_field_summary_text(frame, temporal_source=_StubTemporalSource(signal=0.4))
    assert text is not None
    assert text.endswith("pacing: 0.4")
    # No tokens clause when salient_tokens is empty.
    assert "tokens:" not in text


def test_present_field_text_omits_pacing_when_no_source() -> None:
    frame = _frame_with_focal("focal A", salient_tokens=())
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    assert "pacing" not in text


def test_present_field_text_emits_honest_absent_marker_when_inactive() -> None:
    frame = _frame_inactive()
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    # Honest absence — never a fabricated speaker.
    assert text.startswith("no focal content this cycle")
    assert "operator named" not in text
    assert "just said" not in text


def test_present_field_text_returns_none_when_08_stage_missing() -> None:
    text = _present_field_summary_text(_frame_missing(), temporal_source=None)
    assert text is None


# --- R91 correction (post-empirical-smoke): real `02` stimuli must reach present-field ----------


def test_present_field_text_projects_real_external_stimulus_content() -> None:
    """The most important R91 fact: the operator's actual words must reach the LLM.

    Empirical smoke (helios_v2/logs/prerun/emotion_r91_smoke_llm.jsonl) showed `08.focal_summary`
    is a generic descriptor that does not carry the raw operator text. The operator's text lives
    in `02 sensory_ingress`'s `Stimulus.content`, and R91 projects it from there directly.
    """

    frame = _frame_with_stimuli(
        ("cli", "operator:小林", "你好，我叫小林，今天有点想找个人说说话。"),
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    assert 'operator:小林 said: "你好，我叫小林，今天有点想找个人说说话。"' in text


def test_present_field_text_filters_internal_modalities() -> None:
    """Interoceptive/body/background stimuli must NOT appear as a speaker in present-field."""

    frame = _frame_with_stimuli(
        ("interoceptive", "compute_pressure", "cpu 0.45"),
        ("body", "heartbeat", "(internal)"),
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    # No external speaker -> no stimuli clause; no 08 -> no focal clause; no temporal -> nothing.
    assert text is None


def test_present_field_text_caps_to_three_stimuli() -> None:
    pairs = tuple(("cli", f"speaker_{i}", f"line {i}") for i in range(6))
    frame = _frame_with_stimuli(*pairs)
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    # Only the first three are rendered.
    assert "speaker_0" in text and "speaker_1" in text and "speaker_2" in text
    assert "speaker_3" not in text


def test_present_field_text_truncates_overlong_stimulus_content() -> None:
    long_content = "a" * 500
    frame = _frame_with_stimuli(("cli", "operator", long_content))
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    # Per-stimulus cap with explicit ellipsis suffix.
    assert "…" in text
    assert text.count("a") < 500


def test_present_field_text_combines_stimulus_focal_pacing() -> None:
    """The realistic case: real `02` stimulus + `08` focal commitment + temporal pacing combined."""

    frame = _frame_combined(
        ("cli", "operator:阿哲", "我准备了三年的项目今天拿到投资了！"),
        focal_summary="ignited focal: a high-arousal social signal",
        salient_tokens=("阿哲", "投资", "成功"),
    )
    text = _present_field_summary_text(frame, temporal_source=_StubTemporalSource(signal=0.2))
    assert text is not None
    # Stimulus first (the operator's text), then focal commitment, then pacing.
    assert text.index("阿哲") < text.index("focal:")
    assert text.index("focal:") < text.index("pacing:")
    assert "tokens: 阿哲, 投资, 成功" in text


def test_present_field_text_only_focal_when_no_external_stimulus() -> None:
    """Internal-only or empty `02` tick: no stimuli clause, but `08` commitment still appears."""

    frame = _frame_combined(
        ("interoceptive", "compute_pressure", "cpu 0.6"),
        focal_summary="quiet idle",
        salient_tokens=(),
    )
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    assert "said:" not in text  # no fabricated speaker
    assert text.startswith("focal: quiet idle")


def test_present_field_text_caps_tokens_to_8() -> None:
    tokens = tuple(f"t{i}" for i in range(20))
    frame = _frame_with_focal("focal A", salient_tokens=tokens)
    text = _present_field_summary_text(frame, temporal_source=None)
    assert text is not None
    # Only the first 8 tokens are joined.
    assert "tokens: t0, t1, t2, t3, t4, t5, t6, t7" in text
    assert "t8" not in text


# --- bridge plumbing ----------------------------------------------------------


def test_semantic_bridge_accepts_optional_temporal_source() -> None:
    # Default: no temporal source.
    b1 = SemanticInternalThoughtRequestBridge()
    assert b1.temporal_source is None
    # Wired source.
    src = _StubTemporalSource()
    b2 = SemanticInternalThoughtRequestBridge(temporal_source=src)
    assert b2.temporal_source is src


def test_first_version_bridge_unchanged_no_temporal_field() -> None:
    # The legacy bridge stays simple; no temporal_source field, no present_field plumbing.
    bridge = FirstVersionInternalThoughtRequestBridge()
    assert not hasattr(bridge, "temporal_source")
