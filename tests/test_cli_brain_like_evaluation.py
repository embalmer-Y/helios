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
    build_default_10min_mixed_cli_scenario,
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


def test_default_10min_mixed_cli_scenario_contains_required_blocks():
    scenario = build_default_10min_mixed_cli_scenario()

    assert scenario.duration_seconds == 600
    assert scenario.interaction_mode == "mixed"
    assert len(scenario.prompt_steps) >= 7
    assert scenario.prompt_steps[0].step_id == "baseline_contact"
    assert scenario.prompt_steps[-1].step_id == "persistence_probe"


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
        assert state["consciousness"]["available"] in {True, False}
        assert state["neurochem"]["available"] in {True, False}
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
        assert report.scenario_id == "cli_brain_like_eval_10min_v1"
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