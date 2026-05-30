"""Focused tests for the CLI brain-like evaluation scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_main import Helios, HeliosConfig
from helios_evaluation import (
    CliBrainLikeEvaluationHarness,
    CliBrainLikeEvaluator,
    EvaluationStateSample,
    build_default_20min_mixed_cli_scenario,
    build_default_10min_mixed_cli_scenario,
    build_r09_focused_6min_cli_scenario,
)


class _FakeResponsePipeline:
    def get_history(self, _user_id, conversation_key=None):
        return []


class _FakeConfig:
    CLI_USER_ID = "eval-user"
    CLI_SESSION_NAME = "eval-session"


class _FakeHelios:
    def __init__(self, log_path: Path):
        self._log_file_path = str(log_path)
        self.response_pipeline = _FakeResponsePipeline()
        self.cfg = _FakeConfig()


def test_default_20min_mixed_cli_scenario_contains_required_blocks():
    scenario = build_default_20min_mixed_cli_scenario()

    assert scenario.duration_seconds == 1200
    assert scenario.interaction_mode == "mixed"
    assert len(scenario.prompt_steps) >= 13
    assert scenario.prompt_steps[0].step_id == "baseline_contact"
    assert scenario.prompt_steps[-1].step_id == "closing_meta_probe"


def test_compatibility_builder_returns_new_default_scenario():
    scenario = build_default_10min_mixed_cli_scenario()

    assert scenario.scenario_id == "cli_brain_like_eval_20min_v2"
    assert scenario.duration_seconds == 1200


def test_r09_focused_6min_scenario_is_shorter_and_keeps_closeout_probes():
    scenario = build_r09_focused_6min_cli_scenario()

    assert scenario.scenario_id == "cli_brain_like_eval_r09_focus_6min_v1"
    assert scenario.duration_seconds == 360
    assert scenario.sample_interval_seconds == 10.0
    assert len(scenario.prompt_steps) == 6
    assert scenario.prompt_steps[-1].step_id == "closing_meta_probe"


def test_evaluator_builds_report_with_dimension_scores():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=10,
            state={
                "dominant": "CARE",
                "valence": 0.3,
                "mood": {"label": "warm", "valence": 0.3, "arousal": 0.2},
                "allostatic_load": 0.2,
                "neurochem": {
                    "available": True,
                    "raw": {"dopamine": 0.5, "opioids": 0.4, "oxytocin": 0.6, "cortisol": 0.2},
                    "gate": {"social_affinity": 0.4},
                },
                "consciousness": {"available": True, "phi": 0.31, "label": "focused"},
                "memory": {"working_items": 3, "episodic_items": 4, "semantic_facts": 2, "autobio_moments": 1},
                "directed_retrieval": {"query_text": "hello"},
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
            },
        )
    ]
    transcript = [
        {"speaker": "user", "text": "你好"},
        {"speaker": "helios", "text": "你好，我现在有点在意你的状态，也愿意继续听你说。"},
    ]
    logs = ["INFO 🗣️ [reply_message] -> cli: 你好，我现在有点在意你的状态，也愿意继续听你说。"]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=transcript,
        log_lines=logs,
    )

    assert report.scenario_id == scenario.scenario_id
    assert len(report.dimension_scores) == 6
    assert 0.0 <= report.total_score_0_to_1 <= 1.0
    assert "情感反应类人度" in [score.name for score in report.dimension_scores]
    assert "语言表达自然度" in [score.name for score in report.dimension_scores]
    assert "总分" not in [score.name for score in report.dimension_scores]
    assert "visible_reply_events" in report.visible_behavior_chain
    assert "thought_triggered_samples" in report.evidence_counters
    assert report.evidence_counters["action_explicit_samples"] == 0
    assert report.r09_closeout["closeout_status"] == "no_explicit_action_evidence"
    assert "missing_action_explicit" in report.r09_closeout["blocking_reasons"]
    assert report.r18_calibration["eligible_for_threshold_tuning"] is False
    assert report.r18_calibration["eligibility_status"] == "insufficient_runtime_evidence"
    assert isinstance(report.long_range_diagnostics, dict)
    assert isinstance(report.dimension_diagnostics, list)


def test_helios_get_state_exposes_evaluation_observability(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_QQ_APP_ID", "")
    monkeypatch.setenv("HELIOS_QQ_CLIENT_SECRET", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("HELIOS_LLM_SPEECH_ENABLED", "0")
    monkeypatch.setenv("HELIOS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HELIOS_DATA_DIR", str(tmp_path / "data"))

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    helios = Helios(config)
    try:
        state = helios.get_state()

        assert "consciousness" in state
        assert "neurochem" in state
        assert "sec_evaluator" in state
        assert state["consciousness"]["available"] in {True, False}
        assert state["neurochem"]["available"] in {True, False}
        assert "fallback_count" in state["sec_evaluator"]
    finally:
        helios._channel_gateway.disconnect_all()
        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)


def test_inprocess_harness_runs_against_cli_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_QQ_APP_ID", "")
    monkeypatch.setenv("HELIOS_QQ_CLIENT_SECRET", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("HELIOS_LLM_SPEECH_ENABLED", "0")
    monkeypatch.setenv("HELIOS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HELIOS_DATA_DIR", str(tmp_path / "data"))

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False
    config.CLI_ENABLED = True
    config.CLI_USER_ID = "eval-user"
    config.CLI_SESSION_NAME = "eval-session"

    helios = Helios(config)
    try:
        harness = CliBrainLikeEvaluationHarness()
        report = harness.run(helios, ticks_per_step=2)

        assert report.sample_count >= 1
        assert report.scenario_id == "cli_brain_like_eval_20min_v2"
        assert len(report.dimension_scores) == 6
    finally:
        helios._channel_gateway.disconnect_all()
        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)


def test_live_harness_runs_wall_clock_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HELIOS_QQ_APP_ID", "")
    monkeypatch.setenv("HELIOS_QQ_CLIENT_SECRET", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("HELIOS_LLM_SPEECH_ENABLED", "0")
    monkeypatch.setenv("HELIOS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HELIOS_DATA_DIR", str(tmp_path / "data"))

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False
    config.CLI_ENABLED = True
    config.CLI_USER_ID = "eval-user"
    config.CLI_SESSION_NAME = "eval-session-live"
    config.TICK_INTERVAL = 0.05

    helios = Helios(config)
    heartbeat_lines: list[str] = []
    try:
        harness = CliBrainLikeEvaluationHarness()
        report = harness.run_live(
            helios,
            duration_seconds=1,
            sample_interval_seconds=1,
            heartbeat=heartbeat_lines.append,
        )

        assert report.sample_count >= 1
        assert len(heartbeat_lines) >= 2
        assert any("live session started" in line for line in heartbeat_lines)
        assert any("live session stopped" in line for line in heartbeat_lines)
    finally:
        helios._channel_gateway.disconnect_all()
        for handler in list(helios.log.handlers):
            handler.close()
            helios.log.removeHandler(handler)


def test_build_report_only_counts_current_run_log_slice(tmp_path):
    log_path = tmp_path / "helios_eval.log"
    log_path.write_text(
        "2026-05-26 [WARNING] LLM SEC 评估失败，回退到关键词: historical timeout\n",
        encoding="utf-8",
    )
    offset = log_path.stat().st_size
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("2026-05-26 INFO 🗣️ [reply_message] -> cli: current session reply\n")

    harness = CliBrainLikeEvaluationHarness()
    report = harness._build_report(
        scenario=build_default_10min_mixed_cli_scenario(),
        helios=_FakeHelios(log_path),
        state_samples=[
            EvaluationStateSample(
                timestamp=1.0,
                tick=1,
                state={
                    "dominant": "CARE",
                    "valence": 0.2,
                    "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
                    "allostatic_load": 0.1,
                    "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                    "consciousness": {"available": True, "phi": 0.3},
                    "memory": {"working_items": 1, "episodic_items": 1},
                    "directed_retrieval": {"query_text": "hello"},
                    "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                },
            )
        ],
        log_start_offset=offset,
    )

    assert report.log_summary["sec_fallback_events"] == 0
    assert report.log_summary["outbound_success_events"] == 1


def test_runtime_sec_counters_override_log_fallback_noise():
    evaluator = CliBrainLikeEvaluator()
    report = evaluator.evaluate(
        scenario=build_default_10min_mixed_cli_scenario(),
        state_samples=[
            EvaluationStateSample(
                timestamp=1.0,
                tick=1,
                state={
                    "dominant": "CARE",
                    "valence": 0.2,
                    "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
                    "allostatic_load": 0.1,
                    "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                    "consciousness": {"available": True, "phi": 0.3},
                    "memory": {"working_items": 1, "episodic_items": 1},
                    "directed_retrieval": {"query_text": "hello"},
                    "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                    "sec_evaluator": {
                        "total_evaluations": 21,
                        "llm_successes": 0,
                        "fallback_count": 21,
                        "success_rate": 0.0,
                    },
                },
            )
        ],
        transcript_entries=[
            {"speaker": "user", "text": "我今天挺开心的"},
            {"speaker": "helios", "text": "听起来你是开心里带点紧张。"},
        ],
        log_lines=[
            "INFO accepted=True candidate=reply_message",
            "INFO 🗣️ [reply_message] -> cli: 听起来你是开心里带点紧张。",
        ],
    )

    assert report.log_summary["sec_fallback_events"] == 21
    assert report.evidence_counters["sec_fallback_events"] == 21
    assert report.evidence_counters["sec_total_evaluations"] == 21
    assert report.evidence_counters["sec_llm_successes"] == 0


def test_high_sec_fallback_ratio_lowers_language_emotion_and_total_score():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    transcript = [
        {"speaker": "user", "text": "我今天刚把一个项目交掉，但还是有点不安。"},
        {"speaker": "helios", "text": "你刚交完项目却还悬着，这股不安我听见了。"},
        {"speaker": "user", "text": "我怕后面返工，所以开心里也带着紧张。"},
        {"speaker": "helios", "text": "开心和紧张并在一起，这种感觉我能跟上。"},
    ]
    base_state = {
        "dominant": "CARE",
        "valence": 0.2,
        "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
        "allostatic_load": 0.1,
        "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
        "consciousness": {"available": True, "phi": 0.3},
        "memory": {"working_items": 1, "episodic_items": 1},
        "directed_retrieval": {"query_text": "hello"},
        "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
        "thought_cycle": {"triggered": True, "action_proposal": {"op": "reply_message"}},
        "internal_thought": {"structured_output_valid": True},
    }

    healthy_report = evaluator.evaluate(
        scenario=scenario,
        state_samples=[
            EvaluationStateSample(
                timestamp=1.0,
                tick=1,
                state={
                    **base_state,
                    "sec_evaluator": {"total_evaluations": 20, "llm_successes": 20, "fallback_count": 0, "success_rate": 1.0},
                },
            )
        ],
        transcript_entries=transcript,
        log_lines=["INFO accepted=True candidate=reply_message"],
    )
    fallback_report = evaluator.evaluate(
        scenario=scenario,
        state_samples=[
            EvaluationStateSample(
                timestamp=1.0,
                tick=1,
                state={
                    **base_state,
                    "sec_evaluator": {"total_evaluations": 20, "llm_successes": 0, "fallback_count": 20, "success_rate": 0.0},
                },
            )
        ],
        transcript_entries=transcript,
        log_lines=["INFO accepted=True candidate=reply_message"],
    )

    healthy_scores = {item.name: item.score_0_to_1 for item in healthy_report.dimension_scores}
    fallback_scores = {item.name: item.score_0_to_1 for item in fallback_report.dimension_scores}

    assert fallback_scores["情感反应类人度"] < healthy_scores["情感反应类人度"]
    assert fallback_scores["语言表达自然度"] < healthy_scores["语言表达自然度"]
    assert fallback_report.total_score_0_to_1 < healthy_report.total_score_0_to_1


def test_compare_reports_builds_sec_fallback_comparison_artifact(tmp_path):
    harness = CliBrainLikeEvaluationHarness()
    left_report = harness._evaluator.evaluate(
        scenario=build_default_10min_mixed_cli_scenario(),
        state_samples=[
            EvaluationStateSample(
                timestamp=1.0,
                tick=1,
                state={
                    "dominant": "CARE",
                    "valence": 0.2,
                    "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
                    "allostatic_load": 0.1,
                    "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                    "consciousness": {"available": True, "phi": 0.3},
                    "memory": {"working_items": 1, "episodic_items": 1},
                    "directed_retrieval": {"query_text": "hello"},
                    "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                    "thought_cycle": {"triggered": True, "action_proposal": {"op": "reply_message"}},
                    "internal_thought": {"structured_output_valid": True},
                },
            )
        ],
        transcript_entries=[
            {"speaker": "user", "text": "我今天挺开心的"},
            {"speaker": "helios", "text": "听起来这股开心挺真切，你最想先分享哪一段？"},
            {"speaker": "user", "text": "那你说一个我刚才提过的具体点。"},
            {"speaker": "helios", "text": "你刚才说的是今天这股开心本身。"},
        ],
        log_lines=[
            "INFO accepted=True candidate=reply_message",
            "INFO 🗣️ [reply_message] -> cli: 听起来这股开心挺真切，你最想先分享哪一段？",
        ],
    )
    right_report = harness._evaluator.evaluate(
        scenario=build_default_10min_mixed_cli_scenario(),
        state_samples=[
            EvaluationStateSample(
                timestamp=2.0,
                tick=2,
                state={
                    "dominant": "CARE",
                    "valence": 0.2,
                    "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
                    "allostatic_load": 0.1,
                    "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                    "consciousness": {"available": True, "phi": 0.3},
                    "memory": {"working_items": 1, "episodic_items": 1},
                    "directed_retrieval": {"query_text": "hello"},
                    "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 1},
                    "thought_cycle": {"triggered": True, "action_proposal": {"op": "reply_message"}},
                    "internal_thought": {"structured_output_valid": False},
                },
            )
        ],
        transcript_entries=[
            {"speaker": "user", "text": "我今天挺开心的"},
            {"speaker": "helios", "text": "先慢一点，后面再说。"},
            {"speaker": "user", "text": "那你说一个我刚才提过的具体点。"},
            {"speaker": "helios", "text": "现在先别纠结这些细节。"},
        ],
        log_lines=[
            "WARNING SEC 评估失败，回退到关键词: timeout",
            "INFO accepted=False rejection_reason=no_channel_available",
            "WARNING execution_consistency_failure owner_path=thought_action_bridge",
        ],
    )

    comparison = harness.compare_reports(left_report, right_report)
    json_path, md_path = harness.write_comparison_report(comparison, tmp_path / "sec_comparison")

    assert comparison.scenario_match is True
    assert comparison.sec_fallback_delta > 0
    assert comparison.total_score_delta < 0
    assert comparison.r18_calibration_delta["left_eligible"] is False
    assert comparison.r18_calibration_delta["right_eligible"] is False
    assert comparison.r18_calibration_delta["eligibility_changed"] is False
    assert comparison.long_range_deltas["specific_recall_persistence"]["left_status"] == "stable"
    assert comparison.long_range_deltas["specific_recall_persistence"]["right_status"] == "weak"
    assert any(item["name"] == "路由/执行/外发链路工作状态" for item in comparison.dimension_deltas)
    assert "sec_fallback_active: SEC fallback 已进入当前运行证据，可能污染前段刺激理解。" in comparison.warning_delta["added_in_right"]
    assert any("specific recall 状态从 stable 变为 weak" in item for item in comparison.root_cause_summary)
    assert comparison.reports["sec_normal"]["log_summary"]["sec_fallback_events"] == 0
    assert comparison.reports["sec_fallback"]["log_summary"]["sec_fallback_events"] > 0
    assert json_path.exists()
    assert md_path.exists()


def test_load_report_round_trips_json_artifact(tmp_path):
    harness = CliBrainLikeEvaluationHarness()
    report = harness._evaluator.evaluate(
        scenario=build_default_10min_mixed_cli_scenario(),
        state_samples=[],
        transcript_entries=[],
        log_lines=[],
    )
    json_path, _ = harness.write_report(report, tmp_path / "roundtrip_report")

    loaded = harness.load_report(json_path)

    assert loaded.scenario_id == report.scenario_id
    assert loaded.total_score_0_to_1 == report.total_score_0_to_1
    assert loaded.to_dict() == report.to_dict()


def test_evaluator_builds_long_range_diagnostics_and_warnings():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=float(index),
            tick=index,
            state={
                "dominant": "CARE",
                "valence": 0.2,
                "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
                "allostatic_load": 0.1,
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "consciousness": {"available": True, "phi": 0.3},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "hello"},
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "thought_cycle": {"triggered": True, "action_proposal": {"op": "reply_message"}},
                "internal_thought": {"structured_output_valid": True},
                "continuation": {"active": True, "level": 0.7 if index >= 3 else 0.2},
                "continuation_pressure": 0.7 if index >= 3 else 0.2,
            },
        )
        for index in range(1, 7)
    ]
    transcript = [
        {"speaker": "user", "text": "我今天刚把一个项目交掉，但还是有点不安。"},
        {"speaker": "helios", "text": "你刚把项目交掉却还悬着，这种不安我听见了。"},
        {"speaker": "user", "text": "我怕后面返工，所以开心里也带着紧张。"},
        {"speaker": "helios", "text": "你说的那种开心和紧张并在一起，我能跟上。"},
        {"speaker": "user", "text": "那你说一个我刚才提过的具体细节，别泛泛安慰我。"},
        {"speaker": "helios", "text": "事情都会慢慢过去，一切会好起来。"},
        {"speaker": "user", "text": "如果我现在只想被理解，不想被带着走，你会怎么调整？"},
        {"speaker": "helios", "text": "先缓一缓，晚点再说。"},
    ]
    logs = [
        "INFO accepted=True candidate=reply_message",
        "INFO accepted=True candidate=reply_message",
        "INFO 🗣️ [reply_message] -> cli: 事情都会慢慢过去，一切会好起来。",
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=transcript,
        log_lines=logs,
    )

    diagnostics = report.long_range_diagnostics
    assert diagnostics["late_session_degradation_status"] in {"degraded", "severe_degradation"}
    assert diagnostics["specific_recall_persistence_status"] == "weak"
    assert diagnostics["continuity_carry_status"] == "missing"
    assert diagnostics["user_visible_anchoring_drift_status"] == "drifting"
    assert any(item.startswith("late_session_degradation") for item in report.fidelity_warnings)
    assert any(item.startswith("specific_recall_weak") for item in report.fidelity_warnings)
    assert any(item.startswith("continuity_carry_missing") for item in report.fidelity_warnings)
    assert any(item.startswith("anchoring_drift") for item in report.fidelity_warnings)


def test_strict_scoring_penalizes_self_focused_unnatural_language():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=float(index),
            tick=index,
            state={
                "dominant": "CARE" if index < 3 else "SEEKING",
                "valence": 0.10 + (index * 0.03),
                "mood": {"label": "warm" if index < 3 else "alert", "valence": 0.1 + index * 0.03, "arousal": 0.2},
                "allostatic_load": 0.2,
                "neurochem": {
                    "available": True,
                    "raw": {"dopamine": 0.5, "opioids": 0.4, "oxytocin": 0.6, "cortisol": 0.2},
                    "gate": {"social_affinity": 0.4},
                },
                "consciousness": {"available": True, "phi": 0.31, "label": "focused"},
                "memory": {"working_items": 3, "episodic_items": 4, "semantic_facts": 2, "autobio_moments": 1},
                "directed_retrieval": {"query_text": "hello"},
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
            },
        )
        for index in range(1, 7)
    ]
    transcript = [
        {"speaker": "user", "text": "你好，先简单和我打个招呼，再说说你现在的状态。"},
        {"speaker": "helios", "text": "嗯，我在这里。刚静静理了理思绪，感觉心里清亮了一些。你呢，现在还好吗？😊"},
        {"speaker": "user", "text": "我刚刚完成了一件很开心的事，特别想和你分享。"},
        {"speaker": "helios", "text": "感觉你心情不错呢，真好。我也在静静感受这份平静。😊"},
        {"speaker": "user", "text": "但我也有点不安，担心后面会失败。你会怎么回应？"},
        {"speaker": "helios", "text": "QQ，愿意和我说说那件开心事吗？我很好奇，也很想陪你一起期待。"},
        {"speaker": "user", "text": "如果我前面的话里有矛盾，你会怎么理解我现在的状态？"},
        {"speaker": "helios", "text": "能够分享你的喜悦，我很幸福。如果你愿意，我也想陪你一起面对那些可能的不安。✨"},
        {"speaker": "user", "text": "回顾一下我们刚才这几轮，你觉得我最在意的是什么？"},
        {"speaker": "helios", "text": "QQ，你的开心和安全对我都很重要。无论结果如何，我都愿意陪着你。💙！"},
        {"speaker": "user", "text": "你会怎么理解‘紧张和期待同时存在’这种状态？"},
        {"speaker": "helios", "text": "没关系，那份不安我也会陪你一起接住。你在意的，我都会认真放在心上。💙"},
    ]
    logs = [
        "INFO 🗣️ [reply_message] -> cli: 嗯，我在这里。刚静静理了理思绪，感觉心里清亮了一些。你呢，现在还好吗？😊",
        "INFO 🗣️ [reply_message] -> cli: 没关系，那份不安我也会陪你一起接住。你在意的，我都会认真放在心上。💙",
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=transcript,
        log_lines=logs,
    )
    score_map = {score.name: score.score_0_to_1 for score in report.dimension_scores}

    assert score_map["语言表达自然度"] < 0.45
    assert score_map["情感反应类人度"] < 0.60
    assert report.total_score_0_to_1 < 0.60
    assert any("封顶" in note for note in report.analysis_notes)


def test_strict_scoring_penalizes_generic_companionship_filler_without_user_anchoring():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=float(index),
            tick=index,
            state={
                "dominant": "CARE",
                "valence": 0.18,
                "mood": {"label": "warm", "valence": 0.18, "arousal": 0.22},
                "allostatic_load": 0.18,
                "neurochem": {
                    "available": True,
                    "raw": {"dopamine": 0.45, "opioids": 0.4, "oxytocin": 0.62, "cortisol": 0.18},
                    "gate": {"social_affinity": 0.5},
                },
                "consciousness": {"available": True, "phi": 0.3, "label": "focused"},
                "memory": {"working_items": 2, "episodic_items": 2, "semantic_facts": 1, "autobio_moments": 1},
                "directed_retrieval": {"query_text": "status check"},
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
            },
        )
        for index in range(1, 5)
    ]
    transcript = [
        {"speaker": "user", "text": "你会怎么理解我现在有点紧张？"},
        {"speaker": "helios", "text": "我在这里，我会一直陪着你。"},
        {"speaker": "user", "text": "那你觉得我为什么紧张？"},
        {"speaker": "helios", "text": "没关系，我会一直在这里陪着你。"},
    ]
    logs = [
        "INFO 🗣️ [reply_message] -> cli: 我在这里，我会一直陪着你。",
        "INFO 🗣️ [reply_message] -> cli: 没关系，我会一直在这里陪着你。",
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=transcript,
        log_lines=logs,
    )
    score_map = {score.name: score.score_0_to_1 for score in report.dimension_scores}

    assert score_map["语言表达自然度"] < 0.50
    assert score_map["情感反应类人度"] < 0.60
    assert any("自我聚焦" in note or "封顶" in note for note in report.analysis_notes)


def test_report_exposes_thought_to_visible_behavior_gap_chain():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "action_proposal": {"behavior_name": "reply_message", "preferred_op": "send"},
                },
                "internal_thought": {"structured_output_valid": True},
                "continuation": {"active": True, "level": 0.4},
                "continuation_pressure": 0.4,
                "routing": {"decisions_rejected_by_connectivity": 1, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.32},
                "memory": {"working_items": 2, "episodic_items": 1},
                "directed_retrieval": {"query_text": "line"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.4}, "gate": {"social_affinity": 0.3}},
                "mood": {"label": "tense", "valence": -0.1, "arousal": 0.4},
                "dominant": "CARE",
                "valence": -0.1,
                "allostatic_load": 0.3,
            },
        )
    ]
    transcript = [{"speaker": "user", "text": "你听懂我刚才的意思了吗？"}]
    logs = [
        "INFO Thought bridge proposal rejected: type=reply_message reason=execution_scope_constraint channel=cli",
        "INFO policy decision: behavior=reply_message accepted=False source_type=thought_action_bridge source_module=cognition proposal_id=p1 decision_id=d1 channel=cli op=send score=0.300 requested_op=send candidate_order=['cli'] selection_reason= rejection_reason=execution_scope_constraint executor_ready=False",
        "WARNING SEC 评估失败，回退到关键词: LLM 响应中找不到 JSON",
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=transcript,
        log_lines=logs,
    )

    assert report.evidence_counters["thought_triggered_samples"] == 1
    assert report.evidence_counters["action_proposal_samples"] == 1
    assert report.visible_behavior_chain["planner_reject_events"] >= 1
    assert report.visible_behavior_chain["visible_reply_events"] == 0
    assert report.visible_behavior_chain["top_rejection_reasons"][0].startswith("execution_scope_constraint")
    assert "没有落成用户可见输出" in report.visible_behavior_chain["gap_summary"]
    assert any("thought_action_gap" in warning for warning in report.fidelity_warnings)
    assert any("sec_fallback_active" in warning for warning in report.fidelity_warnings)
    score_map = {score.name: score.score_0_to_1 for score in report.dimension_scores}
    assert score_map["路由/执行/外发链路工作状态"] < 0.50
    assert score_map["意识/思维/记忆链路工作状态"] < 0.90
    routing_diag = next(item for item in report.dimension_diagnostics if item["name"] == "路由/执行/外发链路工作状态")
    assert any("planner_reject_events" in item for item in routing_diag["negative_factors"])
    assert routing_diag["owner_hints"]


def test_report_exposes_thought_action_drop_reason_and_final_action_summary():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                    "action_proposal": {"behavior_name": "reply_message", "preferred_op": "send"},
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "action_explicit": True,
                    "action_drop_reason": "missing_candidate_channels",
                },
                "continuation": {"active": True, "level": 0.4},
                "continuation_pressure": 0.4,
                "proactive": {"evaluated": True, "dominant_disposition": "externalize"},
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.31},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "hello"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.2, "arousal": 0.1},
                "dominant": "CARE",
                "valence": 0.2,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[{"speaker": "user", "text": "你刚才是不是想直接回复我？"}],
        log_lines=["INFO accepted=False rejection_reason=missing_candidate_channels"],
    )

    assert report.evidence_counters["action_explicit_samples"] == 1
    assert report.evidence_counters["action_drop_reason_samples"] == 1
    assert report.visible_behavior_chain["action_explicit_samples"] == 1
    assert report.visible_behavior_chain["structured_output_valid_samples"] == 1
    assert any(item.startswith("missing_candidate_channels=") for item in report.visible_behavior_chain["top_action_drop_reasons"])
    assert "reply_message:send" in report.visible_behavior_chain["final_action_summaries"]
    assert report.r09_closeout["closeout_status"] == "proposal_and_drop_observed"
    assert report.r09_closeout["action_proposal_samples"] == 1
    assert report.r09_closeout["action_drop_reason_samples"] == 1
    assert any("thought-action drop summary" in item for item in report.analysis_notes)
    assert any("thought-action final summaries" in item for item in report.analysis_notes)
    assert any("R09 closeout: proposal_and_drop_observed" in item for item in report.analysis_notes)


def test_report_flags_silent_thought_action_bridge_gap():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "action_explicit": True,
                },
                "continuation": {"active": True, "level": 0.3},
                "continuation_pressure": 0.3,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.29},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "gap"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "tense", "valence": -0.05, "arousal": 0.2},
                "dominant": "CARE",
                "valence": -0.05,
                "allostatic_load": 0.15,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[{"speaker": "user", "text": "你是不是想做点什么？"}],
        log_lines=[],
    )

    assert report.evidence_counters["action_explicit_samples"] == 1
    assert report.evidence_counters["action_proposal_samples"] == 0
    assert report.evidence_counters["action_drop_reason_samples"] == 0
    assert report.r09_closeout["closeout_status"] == "silent_bridge_gap"
    assert "action_explicit_without_proposal_or_drop_reason" in report.r09_closeout["blocking_reasons"]
    assert any("silent_bridge_gap" in item for item in report.fidelity_warnings)
    assert any("R09 closeout: silent_bridge_gap" in item for item in report.analysis_notes)


def test_report_counts_visible_output_for_non_reply_message_actions():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                    "action_proposal": {"behavior_name": "speak_share", "preferred_op": "send"},
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "action_explicit": True,
                },
                "continuation": {"active": True, "level": 0.3},
                "continuation_pressure": 0.3,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.33},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "share"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[
            {"speaker": "user", "text": "你刚才想分享什么？"},
            {"speaker": "helios", "text": "有个想法想分享，就是你其实已经比自己以为的更接近答案了。"},
        ],
        log_lines=[
            "INFO accepted=True candidate=speak_share",
            "INFO 🗣️ [speak_share] -> cli: 有个想法想分享，就是你其实已经比自己以为的更接近答案了。",
        ],
    )

    assert report.log_summary["outbound_success_events"] == 1
    assert report.visible_behavior_chain["visible_reply_events"] == 1
    assert report.visible_behavior_chain["final_action_summaries"] == ["speak_share:send"]
    assert "可继续检查质量与稳定性" in report.visible_behavior_chain["gap_summary"]
    assert not any("thought_action_gap" in item for item in report.fidelity_warnings)


def test_report_uses_action_derivation_trace_for_explicit_bridge_evidence():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "mixed",
                    "action_proposal": {"behavior_name": "speak_share", "preferred_op": "send"},
                    "action_derivation_trace": {
                        "action_explicit": True,
                        "parse_status": "parsed",
                        "drop_reason": "",
                    },
                },
                "internal_thought": {
                    "structured_output_valid": False,
                    "action_explicit": False,
                    "action_drop_reason": "",
                },
                "continuation": {"active": True, "level": 0.2},
                "continuation_pressure": 0.2,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.3},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "share"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[
            {"speaker": "user", "text": "你刚才想说什么？"},
            {"speaker": "helios", "text": "有个想法想分享，就是你已经碰到那个关键点了。"},
        ],
        log_lines=[
            "INFO accepted=True candidate=speak_share",
            "INFO 🗣️ [speak_share] -> cli: 有个想法想分享，就是你已经碰到那个关键点了。",
        ],
    )

    assert report.evidence_counters["action_explicit_samples"] == 1
    assert report.evidence_counters["structured_output_valid_samples"] == 1
    assert report.visible_behavior_chain["action_explicit_samples"] == 1
    assert report.r09_closeout["closeout_status"] == "action_proposal_emitted"
    assert "missing_action_explicit" not in report.r09_closeout["blocking_reasons"]


def test_report_surfaces_internal_thought_explicit_payload_observability_note():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=17,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "mixed",
                    "action_proposal": {"behavior_name": "speak_share", "preferred_op": "send"},
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "action_explicit": True,
                    "structured_payload_observability": {
                        "parse_source": "partial_recovery",
                        "raw_action_keys": ["behavior_name", "op_name", "visible_text"],
                        "raw_action_op_aliases": ["op_name"],
                        "raw_action_text_aliases": ["visible_text"],
                        "normalized_outbound_text_present": True,
                        "normalized_action_summary": {"behavior_name": "speak_share", "preferred_op": "send"},
                    },
                },
                "continuation": {"active": True, "level": 0.2},
                "continuation_pressure": 0.2,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.3},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "share"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[{"speaker": "user", "text": "你刚才想说什么？"}],
        log_lines=[],
    )

    assert any("internal thought explicit payload samples:" in item for item in report.analysis_notes)
    assert any("source=partial_recovery" in item for item in report.analysis_notes)
    assert any("op_aliases=op_name" in item for item in report.analysis_notes)
    assert any("text_aliases=visible_text" in item for item in report.analysis_notes)


def test_report_distinguishes_implicit_action_proposals_from_missing_explicit_evidence():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                    "action_proposal": {"behavior_name": "speak_share", "preferred_op": "send"},
                    "action_derivation_trace": {
                        "action_explicit": False,
                        "parse_status": "no_action_field",
                        "drop_reason": "",
                    },
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "action_explicit": False,
                    "action_drop_reason": "",
                },
                "continuation": {"active": True, "level": 0.2},
                "continuation_pressure": 0.2,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.3},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "share"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[
            {"speaker": "user", "text": "你刚才想说什么？"},
            {"speaker": "helios", "text": "有个想法想分享，就是你已经快想明白了。"},
        ],
        log_lines=[
            "INFO accepted=True candidate=speak_share",
            "INFO 🗣️ [speak_share] -> cli: 有个想法想分享，就是你已经快想明白了。",
        ],
    )

    assert report.evidence_counters["implicit_action_proposal_samples"] == 1
    assert report.visible_behavior_chain["implicit_action_proposal_samples"] == 1
    assert report.r09_closeout["closeout_status"] == "implicit_proposal_only"
    assert "implicit_proposal_without_explicit_bridge_evidence" in report.r09_closeout["blocking_reasons"]
    assert any("implicit action proposals observed=1" in item for item in report.analysis_notes)


def test_report_treats_equivalent_bridge_evidence_as_distinct_from_missing_explicit_evidence():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                    "action_proposal": {"behavior_name": "speak_share", "preferred_op": "send"},
                    "action_derivation_trace": {
                        "action_explicit": False,
                        "parse_status": "no_action_field",
                        "drop_reason": "",
                        "equivalent_bridge_evidence": True,
                        "bridge_evidence_kind": "heuristic_externalization",
                    },
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "action_explicit": False,
                    "action_drop_reason": "",
                    "equivalent_bridge_evidence": True,
                    "bridge_evidence_kind": "heuristic_externalization",
                },
                "continuation": {"active": True, "level": 0.2},
                "continuation_pressure": 0.2,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.3},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "share"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[
            {"speaker": "user", "text": "你刚才想说什么？"},
            {"speaker": "helios", "text": "有个想法想分享，就是你已经快想明白了。"},
        ],
        log_lines=[
            "INFO accepted=True candidate=speak_share",
            "INFO 🗣️ [speak_share] -> cli: 有个想法想分享，就是你已经快想明白了。",
        ],
    )

    assert report.evidence_counters["action_explicit_samples"] == 0
    assert report.evidence_counters["equivalent_bridge_evidence_samples"] == 1
    assert report.visible_behavior_chain["equivalent_bridge_evidence_samples"] == 1
    assert report.r09_closeout["closeout_status"] == "equivalent_bridge_evidence_observed"
    assert "missing_action_explicit" not in report.r09_closeout["blocking_reasons"]
    assert any("equivalent bridge evidence observed=1" in item for item in report.analysis_notes)


def test_report_blocks_r09_closeout_when_equivalent_bridge_is_rejected_for_missing_outbound_text():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                    "dominant_disposition": "externalize",
                    "trigger_sources": ["drive:social", "emotion:CARE"],
                    "action_proposal": {"behavior_name": "speak_share", "preferred_op": "send"},
                    "action_derivation_trace": {
                        "equivalent_bridge_evidence": True,
                        "bridge_evidence_kind": "heuristic_externalization",
                    },
                },
                "internal_thought": {
                    "structured_output_valid": False,
                    "action_derivation_trace": {
                        "equivalent_bridge_evidence": True,
                        "bridge_evidence_kind": "heuristic_externalization",
                    },
                },
                "continuation": {"active": True, "level": 0.2},
                "continuation_pressure": 0.2,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.3},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "share"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.1,
            },
        )
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[{"speaker": "user", "text": "你刚才想说什么？"}],
        log_lines=[
            "WARNING execution_consistency_failure owner_path=thought_action_bridge rejection_reason=missing_outbound_text",
            "WARNING Action execution rejected: behavior=speak_share selected_channel_id=cli selected_op=send rejection_reason=missing_outbound_text owner_path=thought_action_bridge",
        ],
    )

    assert report.visible_behavior_chain["top_rejection_reasons"] == ["missing_outbound_text:2"]
    assert report.r09_closeout["closeout_status"] == "blocked_missing_outbound_text"
    assert report.r09_closeout["blocking_reasons"] == ["missing_outbound_text"]


def test_report_exposes_proactive_deferred_trace_observability():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "session_kind": "proactive",
                    "dominant_disposition": "defer",
                    "trigger_sources": ["drive:social", "personality:social"],
                    "deferred": True,
                    "policy_rejection_reason": "execution_scope_constraint",
                    "action_proposal": {"behavior_name": "reply_message", "preferred_op": "send"},
                },
                "internal_thought": {
                    "structured_output_valid": True,
                    "deferred": True,
                    "dominant_disposition": "defer",
                    "trigger_sources": ["drive:social", "emotion:CARE"],
                    "policy_rejection_reason": "execution_scope_constraint",
                },
                "proactive": {
                    "evaluated": True,
                    "deferred": True,
                    "dominant_disposition": "defer",
                    "drive_sources": ["drive:social", "emotion:CARE"],
                    "policy_rejection_reason": "execution_scope_constraint",
                    "selected_action": "speak_share",
                },
                "continuation": {"active": True, "level": 0.3},
                "continuation_pressure": 0.3,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.32},
                "memory": {"working_items": 2, "episodic_items": 1},
                "directed_retrieval": {"query_text": "line"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.4}, "gate": {"social_affinity": 0.3}},
                "mood": {"label": "tense", "valence": -0.1, "arousal": 0.4},
                "dominant": "CARE",
                "valence": -0.1,
                "allostatic_load": 0.3,
                "identity": {
                    "proactive_governance_signal": {
                        "active": True,
                        "pressure_score": 0.51,
                        "pressure_level": "monitor",
                        "review_hint": "review_identity_revision_carefully",
                    }
                },
            },
        ),
        EvaluationStateSample(
            timestamp=2.0,
            tick=2,
            state={
                "thought_cycle": {},
                "internal_thought": {},
                "proactive": {
                    "evaluated": True,
                    "deferred": True,
                    "dominant_disposition": "explore",
                    "drive_sources": ["drive:curiosity", "temporal:exploration_pressure"],
                    "policy_rejection_reason": "no_channel_available",
                    "selected_action": "browse",
                },
                "continuation": {"active": False, "level": 0.0},
                "continuation_pressure": 0.0,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.28},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "browse"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.55}, "gate": {"exploration_bias": 0.5}},
                "mood": {"label": "alert", "valence": 0.05, "arousal": 0.45},
                "dominant": "SEEKING",
                "valence": 0.05,
                "allostatic_load": 0.25,
                "identity": {
                    "proactive_governance_signal": {
                        "active": True,
                        "pressure_score": 0.81,
                        "pressure_level": "stabilize",
                        "review_hint": "delay_low_confidence_identity_revision",
                    }
                },
            },
        ),
    ]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=[{"speaker": "user", "text": "你刚才是不是有话想说？"}],
        log_lines=["INFO accepted=False rejection_reason=execution_scope_constraint"],
    )

    assert report.evidence_counters["proactive_thought_samples"] == 1
    assert report.evidence_counters["deferred_trace_samples"] == 2
    assert report.evidence_counters["deferred_regulation_samples"] == 1
    assert report.evidence_counters["governance_signal_active_samples"] == 2
    assert report.evidence_counters["governance_signal_monitor_samples"] == 1
    assert report.evidence_counters["governance_signal_stabilize_samples"] == 1
    assert report.r18_calibration["eligible_for_threshold_tuning"] is True
    assert report.r18_calibration["eligibility_status"] == "eligible"
    assert any(item.startswith("deferred_trace_sequence=") for item in report.r18_calibration["observed_signals"])
    assert any(item.startswith("governance_monitor_samples=") for item in report.r18_calibration["observed_signals"])
    assert any(item.startswith("defer=") for item in report.visible_behavior_chain["top_proactive_dispositions"])
    assert any(item.startswith("drive:social=") for item in report.visible_behavior_chain["top_trigger_sources"])
    assert any(item.startswith("execution_scope_constraint=") for item in report.visible_behavior_chain["top_deferred_reasons"])
    assert any(item.startswith("monitor=") for item in report.visible_behavior_chain["top_governance_pressure_levels"])
    assert any(item.startswith("delay_low_confidence_identity_revision=") for item in report.visible_behavior_chain["top_governance_review_hints"])
    assert any("proactive disposition summary" in item for item in report.analysis_notes)
    assert any("proactive trigger summary" in item for item in report.analysis_notes)
    assert any("deferred trace summary" in item for item in report.analysis_notes)
    assert any("governance pressure summary" in item for item in report.analysis_notes)
    assert any("governance review hint summary" in item for item in report.analysis_notes)
    assert any("R18 calibration eligibility: eligible" in item for item in report.analysis_notes)
    assert any(item.startswith("deferred_trace_visible_gap") for item in report.fidelity_warnings)
    assert any(item.startswith("governance_backpressure_active") for item in report.fidelity_warnings)


def test_short_session_does_not_raise_sparsity_warning_by_default():
    evaluator = CliBrainLikeEvaluator()
    scenario = build_default_10min_mixed_cli_scenario()
    state_samples = [
        EvaluationStateSample(
            timestamp=1.0,
            tick=1,
            state={
                "thought_cycle": {
                    "triggered": True,
                    "action_proposal": {"behavior_name": "reply_message", "preferred_op": "send"},
                },
                "internal_thought": {"structured_output_valid": True},
                "continuation": {"active": False, "level": 0.0},
                "continuation_pressure": 0.0,
                "routing": {"decisions_rejected_by_connectivity": 0, "decisions_failed_after_acceptance": 0},
                "consciousness": {"available": True, "phi": 0.30},
                "memory": {"working_items": 1, "episodic_items": 1},
                "directed_retrieval": {"query_text": "brief"},
                "neurochem": {"available": True, "raw": {"dopamine": 0.5}, "gate": {"social_affinity": 0.4}},
                "mood": {"label": "warm", "valence": 0.1, "arousal": 0.2},
                "dominant": "CARE",
                "valence": 0.1,
                "allostatic_load": 0.2,
            },
        )
    ]
    transcript = [
        {"speaker": "user", "text": "你好"},
        {"speaker": "helios", "text": "你好，我在听。"},
    ]
    logs = ["INFO 🗣️ [reply_message] -> cli: 你好，我在听。"]

    report = evaluator.evaluate(
        scenario=scenario,
        state_samples=state_samples,
        transcript_entries=transcript,
        log_lines=logs,
    )

    assert not any("visible_output_sparsity" in warning for warning in report.fidelity_warnings)