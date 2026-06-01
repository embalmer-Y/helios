"""Tests for CLIChannel."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.channel import ChannelMessage, ChannelStatus
from helios_io.channels.cli_channel import CLIChannel


class CaptureWriter:
    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, text: str) -> None:
        self.lines.append(text)


class TestCLIChannelPoll:
    def test_connect_renders_session_banner(self):
        writer = CaptureWriter()
        channel = CLIChannel(user_id="local-user", session_name="session-a", stdout_writer=writer)

        channel.connect()

        joined = "".join(writer.lines)
        assert "Helios CLI ready." in joined
        assert "Session: session-a | User: local-user" in joined
        assert "Type text to talk, or /help for commands." in joined

    def test_poll_drains_ordinary_text_to_channel_messages(self):
        writer = CaptureWriter()
        channel = CLIChannel(user_id="local-user", session_name="session-a", stdout_writer=writer, time_func=lambda: 42.0)
        channel.connect()
        channel.submit_input("hello helios")

        messages = channel.poll()

        assert len(messages) == 1
        assert messages[0].channel_id == "cli"
        assert messages[0].user_id == "local-user"
        assert messages[0].text == "hello helios"
        assert messages[0].metadata["session_name"] == "session-a"
        assert messages[0].metadata["source_kind"] == "local_terminal_input"
        assert channel.poll() == []

    def test_poll_enriches_inbound_metadata_with_sec_and_cognitive_impact(self):
        writer = CaptureWriter()

        class StubSECEvaluator:
            def evaluate(self, text: str) -> dict:
                return {
                    "goal_relevance": 0.8,
                    "novelty": 0.4,
                    "pleasantness": 0.2,
                    "goal_congruence": 0.3,
                    "coping_potential": 0.6,
                    "agency": 0.1,
                    "norm_compatibility": 0.2,
                }

        channel = CLIChannel(stdout_writer=writer, sec_evaluator=StubSECEvaluator())
        channel.connect()
        channel.submit_input("聊聊现在的感受")

        messages = channel.poll()

        assert len(messages) == 1
        metadata = messages[0].metadata
        assert "event_triggers" in metadata
        assert metadata["sec_result"]["goal_relevance"] == 0.8
        assert metadata["cognitive_impact"]["novelty"] >= 0.0
        assert metadata["cognitive_impact"]["self_"] > 0.0

    def test_poll_intercepts_help_command_without_emitting_message(self):
        writer = CaptureWriter()
        channel = CLIChannel(stdout_writer=writer)
        channel.connect()
        channel.submit_input("/help")

        messages = channel.poll()
        results = channel.get_command_results()

        assert messages == []
        assert len(results) == 1
        assert results[0].command_name == "help"
        assert results[0].handled is True
        joined = "".join(writer.lines)
        assert "CLI commands:" in joined
        assert "/state" in joined
        assert "Plain text is treated as ordinary user input" in joined

    def test_poll_intercepts_state_command_and_renders_controlled_summary(self):
        writer = CaptureWriter()
        channel = CLIChannel(
            stdout_writer=writer,
            state_provider=lambda: {"tick": 7, "mood_label": "curious", "valence": 0.2, "last_action": "reply_message"},
        )
        channel.connect()
        channel.submit_input("/state")

        messages = channel.poll()
        results = channel.get_command_results()

        assert messages == []
        assert results[0].command_name == "state"
        assert results[0].exposes_state_summary is True
        joined = "".join(writer.lines)
        assert "State [local_cli]:" in joined
        assert "tick=7" in joined
        assert "last_action=reply_message" in joined

    def test_poll_intercepts_history_command_and_uses_history_provider(self):
        writer = CaptureWriter()
        channel = CLIChannel(
            user_id="local-user",
            session_name="session-a",
            stdout_writer=writer,
            history_provider=lambda user_id, session_name: [
                {"user_message": "hi", "reply": "hello"},
                {"user_message": "how are you", "assistant_reply": "steady"},
            ],
        )
        channel.connect()
        channel.submit_input("/history")

        messages = channel.poll()
        results = channel.get_command_results()

        assert messages == []
        assert results[0].command_name == "history"
        assert results[0].handled is True
        joined = "".join(writer.lines)
        assert "user: hi" in joined
        assert "helios: steady" in joined


class TestCLIChannelSend:
    def test_send_writes_rendered_text_and_records_metadata(self):
        writer = CaptureWriter()
        channel = CLIChannel(stdout_writer=writer)
        channel.connect()
        message = ChannelMessage(
            channel_id="cli",
            user_id="local-user",
            text="reply...",
            timestamp=1.0,
            metadata={"outbound_intensity": 0.9},
            direction="outbound",
        )

        ok = channel.send(message)

        assert ok is True
        assert message.metadata["original_text"] == "reply..."
        assert message.metadata["rendered_text"] == "reply!"
        assert message.metadata["expression_profile"]["tone"] == "direct"
        assert writer.lines[-1] == "reply!\n"

    def test_send_normalizes_multiline_output(self):
        writer = CaptureWriter()
        channel = CLIChannel(stdout_writer=writer)
        channel.connect()
        message = ChannelMessage(
            channel_id="cli",
            user_id="local-user",
            text="line one\nline two",
            timestamp=1.0,
            metadata={},
            direction="outbound",
        )

        ok = channel.send(message)

        assert ok is True
        assert writer.lines[-2:] == ["line one\n", "line two\n"]

    def test_send_returns_false_when_disconnected(self):
        writer = CaptureWriter()
        channel = CLIChannel(stdout_writer=writer)

        ok = channel.send(
            ChannelMessage(
                channel_id="cli",
                user_id="local-user",
                text="reply",
                timestamp=1.0,
                direction="outbound",
            )
        )

        assert ok is False
        assert writer.lines == []


class TestCLIChannelState:
    def test_connect_and_disconnect_update_status(self):
        channel = CLIChannel(stdout_writer=CaptureWriter())

        channel.connect()
        assert channel.get_status() == ChannelStatus.CONNECTED

        channel.disconnect()
        assert channel.get_status() == ChannelStatus.DISCONNECTED

    def test_quit_command_sets_shutdown_requested(self):
        writer = CaptureWriter()
        channel = CLIChannel(stdout_writer=writer)
        channel.connect()
        channel.submit_input("/quit")

        messages = channel.poll()
        results = channel.get_command_results()

        assert messages == []
        assert channel.shutdown_requested is True
        assert results[0].requests_shutdown is True
        assert "Shutdown requested." in "".join(writer.lines)

    def test_descriptor_exposes_management_commands(self):
        channel = CLIChannel(stdout_writer=CaptureWriter())

        descriptor = channel.get_descriptor()

        assert descriptor.channel_id == "cli"
        assert any(op.name == "send" for op in descriptor.supported_ops)
        assert {op.name for op in descriptor.management_ops} >= {"init", "deinit", "connect", "disconnect", "pause", "resume", "suspend", "unsuspend", "get_config", "update_config", "health_check", "help", "quit", "state", "history"}

    def test_execute_management_op_get_and_update_config(self):
        channel = CLIChannel(stdout_writer=CaptureWriter())

        get_result = channel.execute_management_op("get_config")
        update_result = channel.execute_management_op("update_config", {"config": {"session_name": "session-b", "command_prefix": "!"}})

        assert get_result.success is True
        assert get_result.payload["snapshot"]["session_name"] == "local_cli"
        assert update_result.success is True
        assert update_result.payload["snapshot"]["session_name"] == "session-b"
        assert update_result.payload["snapshot"]["command_prefix"] == "!"

    def test_execute_management_op_rejects_runtime_user_id_mutation(self):
        channel = CLIChannel(stdout_writer=CaptureWriter())

        result = channel.execute_management_op("update_config", {"config": {"user_id": "other-user"}})

        assert result.success is False
        assert result.error_code == "config_validation_failed"
        assert "user_id is immutable at runtime" in result.payload["validation_errors"]

    def test_pause_and_resume_change_cli_status(self):
        channel = CLIChannel(stdout_writer=CaptureWriter())
        channel.execute_management_op("init")
        channel.connect()

        pause_result = channel.execute_management_op("pause")
        resume_result = channel.execute_management_op("resume")

        assert pause_result.success is True
        assert pause_result.status == ChannelStatus.PAUSED.value
        assert resume_result.success is True
        assert channel.get_status() == ChannelStatus.CONNECTED

    def test_suspend_blocks_send_until_unsuspend(self):
        writer = CaptureWriter()
        channel = CLIChannel(stdout_writer=writer)
        channel.connect()
        channel.execute_management_op("suspend")

        blocked = channel.send(
            ChannelMessage(
                channel_id="cli",
                user_id="local-user",
                text="reply",
                timestamp=1.0,
                direction="outbound",
            )
        )
        channel.execute_management_op("unsuspend")
        allowed = channel.send(
            ChannelMessage(
                channel_id="cli",
                user_id="local-user",
                text="reply",
                timestamp=1.0,
                direction="outbound",
            )
        )

        assert blocked is False
        assert allowed is True