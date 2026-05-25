"""CLIChannel adapts local terminal I/O into the channel abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import queue
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional

from ..channel import BidirectionalChannel, ChannelDescriptor, ChannelMessage, ChannelOpDescriptor, ChannelStatus
from ..expression_modulation import modulate_outbound_expression
from .inbound_text_annotation import annotate_inbound_text_message, evaluate_text_triggers

log = logging.getLogger("helios.helios_io.channels.cli_channel")


def _stdout_writer(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


@dataclass(frozen=True)
class CLICommandResult:
    command_name: str
    handled: bool
    rendered_lines: List[str] = field(default_factory=list)
    requests_shutdown: bool = False
    exposes_state_summary: bool = False
    history_scope: str = ""
    error_message: str = ""


class CLIChannel(BidirectionalChannel):
    CHANNEL_ID = "cli"

    def __init__(
        self,
        *,
        channel_id: str = CHANNEL_ID,
        user_id: str = "local_operator",
        session_name: str = "local_cli",
        enabled: bool = True,
        command_prefix: str = "/",
        enable_commands: bool = True,
        stdout_writer: Optional[Callable[[str], None]] = None,
        input_stream=None,
        time_func: Optional[Callable[[], float]] = None,
        state_provider: Optional[Callable[[], Mapping[str, Any] | Any]] = None,
        history_provider: Optional[Callable[[str, str], Any]] = None,
        sec_evaluator: object | None = None,
        banner_enabled: bool = True,
    ):
        self._channel_id = str(channel_id or self.CHANNEL_ID)
        self._user_id = str(user_id or "local_operator")
        self._session_name = str(session_name or "local_cli")
        self.is_available = bool(enabled)
        self._command_prefix = str(command_prefix or "/")
        self._enable_commands = bool(enable_commands)
        self._stdout_writer = stdout_writer or _stdout_writer
        self._input_stream = input_stream
        self._time = time_func or time.time
        self._state_provider = state_provider
        self._history_provider = history_provider
        self._sec_evaluator = sec_evaluator
        self._banner_enabled = bool(banner_enabled)
        self._queue: queue.Queue[str] = queue.Queue()
        self._command_results: List[CLICommandResult] = []
        self._status = ChannelStatus.DISCONNECTED
        self._shutdown_requested = False
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._render_lock = threading.Lock()

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def get_status(self) -> ChannelStatus:
        return self._status

    def get_descriptor(self) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=self.channel_id,
            display_name="Terminal CLI Channel",
            input_types=["text_message", "management_command"],
            output_types=["text_message", "management_output"],
            input_formats=["terminal:stdin"],
            output_formats=["terminal:stdout"],
            capabilities=["poll", "send", "text_input", "text_output", "local_session", "management_commands"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="poll",
                    direction="input",
                    description="Poll queued terminal input lines and normalize ordinary text into ChannelMessage objects.",
                    output_schema={"messages": "list[ChannelMessage]"},
                ),
                ChannelOpDescriptor(
                    name="send",
                    direction="output",
                    description="Render an outbound Helios text message to the terminal stdout sink.",
                    input_schema={"message": "ChannelMessage(text, user_id, metadata[normalized_intensity|outbound_intensity])"},
                    output_schema={"success": "bool"},
                ),
            ],
            management_ops=[
                ChannelOpDescriptor("connect", "management", "Activate the local CLI channel."),
                ChannelOpDescriptor("disconnect", "management", "Disconnect the local CLI channel."),
                ChannelOpDescriptor("help", "management", "Show supported CLI commands."),
                ChannelOpDescriptor("quit", "management", "Request orderly shutdown from the CLI."),
                ChannelOpDescriptor("state", "management", "Render a controlled local state summary."),
                ChannelOpDescriptor("history", "management", "Render recent conversation history for the local session."),
            ],
            startup_requirements=["optional stdin stream for background reader", "startup-configured user_id/session_name"],
            shutdown_requirements=["reader thread stop signal", "local CLI status transition"],
            health_signals=["get_status", "shutdown_requested", "queued_input_count"],
            ack_schema={"success": "bool", "delivery": "best_effort"},
            limitations=["Current CLI support is text-only.", "Management commands are local and do not enter the cognitive stimulus path."],
        )

    def submit_input(self, text: str) -> None:
        self._queue.put(str(text or ""))

    def poll(self) -> List[ChannelMessage]:
        messages: List[ChannelMessage] = []
        while True:
            try:
                raw_text = self._queue.get_nowait()
            except queue.Empty:
                break
            line = str(raw_text or "").strip()
            if not line:
                continue
            if self._enable_commands and line.startswith(self._command_prefix):
                self._command_results.append(self._handle_command(line))
                continue
            messages.append(self._annotate_inbound_message(
                ChannelMessage(
                    channel_id=self.channel_id,
                    user_id=self._user_id,
                    text=line,
                    timestamp=self._time(),
                    metadata={
                        "source_kind": "local_terminal_input",
                        "trigger_condition": "cli_text_input",
                        "session_name": self._session_name,
                        "conversation_key": self._session_name,
                    },
                    direction="inbound",
                )
            ))
        return messages

    def send(self, message: ChannelMessage) -> bool:
        if not self.is_connected():
            return False

        metadata = dict(message.metadata)
        modulation = modulate_outbound_expression(message.text, metadata)
        rendered_text = str(modulation.rendered_text or message.text)
        message.metadata["original_text"] = message.text
        message.metadata["rendered_text"] = rendered_text
        message.metadata["expression_profile"] = modulation.to_metadata()
        try:
            self._write_lines(self._split_render_lines(rendered_text))
            return True
        except Exception as exc:
            log.warning("CLIChannel send failed: %s", exc)
            return False

    def is_connected(self) -> bool:
        return self._status == ChannelStatus.CONNECTED

    def connect(self) -> None:
        if not self.is_available:
            self._status = ChannelStatus.DISCONNECTED
            return
        if self.is_connected():
            return
        self._stop_event.clear()
        self._shutdown_requested = False
        self._status = ChannelStatus.CONNECTED
        if self._banner_enabled:
            self._write_lines(self._render_banner())
        if self._input_stream is not None and self._reader_thread is None:
            self._reader_thread = threading.Thread(target=self._reader_loop, name="helios-cli-reader", daemon=True)
            self._reader_thread.start()

    def disconnect(self) -> None:
        self._stop_event.set()
        self._status = ChannelStatus.DISCONNECTED
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=0.1)
            if not self._reader_thread.is_alive():
                self._reader_thread = None

    def get_command_results(self) -> List[CLICommandResult]:
        return list(self._command_results)

    def clear_command_results(self) -> None:
        self._command_results.clear()

    def _reader_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                line = self._input_stream.readline()
                if line == "":
                    self._status = ChannelStatus.DISCONNECTED if self._stop_event.is_set() else ChannelStatus.ERROR
                    break
                self.submit_input(line.rstrip("\r\n"))
        except Exception as exc:
            log.warning("CLIChannel reader failed: %s", exc)
            self._status = ChannelStatus.ERROR

    def evaluate_message(self, message: ChannelMessage, state=None) -> Dict[str, float]:
        return evaluate_text_triggers(message, self._sec_evaluator, log, "CLIChannel")

    def _handle_command(self, line: str) -> CLICommandResult:
        body = line[len(self._command_prefix):].strip()
        if not body:
            return self._emit_command_result(
                CLICommandResult(
                    command_name="",
                    handled=False,
                    rendered_lines=["Unknown command. Use /help for available commands."],
                    error_message="missing_command_name",
                )
            )

        parts = body.split()
        command_name = parts[0].lower()
        args = parts[1:]
        if command_name == "help":
            return self._emit_command_result(
                CLICommandResult(
                    command_name="help",
                    handled=True,
                    rendered_lines=self._render_help_lines(),
                )
            )
        if command_name == "quit":
            self._shutdown_requested = True
            return self._emit_command_result(
                CLICommandResult(
                    command_name="quit",
                    handled=True,
                    rendered_lines=["Shutdown requested."],
                    requests_shutdown=True,
                )
            )
        if command_name == "state":
            return self._emit_command_result(
                CLICommandResult(
                    command_name="state",
                    handled=True,
                    rendered_lines=self._render_state_summary(),
                    exposes_state_summary=True,
                )
            )
        if command_name == "history":
            scope = args[0] if args else self._session_name
            return self._emit_command_result(
                CLICommandResult(
                    command_name="history",
                    handled=True,
                    rendered_lines=self._render_history_summary(),
                    history_scope=scope,
                )
            )
        return self._emit_command_result(
            CLICommandResult(
                command_name=command_name,
                handled=False,
                rendered_lines=[f"Unknown command: /{command_name}"],
                error_message="unknown_command",
            )
        )

    def _emit_command_result(self, result: CLICommandResult) -> CLICommandResult:
        try:
            self._write_lines(result.rendered_lines)
        except Exception as exc:
            log.warning("CLIChannel command render failed: %s", exc)
        return result

    def _annotate_inbound_message(self, message: ChannelMessage) -> ChannelMessage:
        return annotate_inbound_text_message(message, self._sec_evaluator, log, "CLIChannel")

    def _render_state_summary(self) -> List[str]:
        if self._state_provider is None:
            return ["State summary unavailable."]
        try:
            state = self._state_provider()
        except Exception as exc:
            log.warning("CLIChannel state provider failed: %s", exc)
            return ["State summary unavailable."]
        if isinstance(state, Mapping):
            parts = []
            for key in ("tick", "mood_label", "dominant_system", "valence", "arousal", "last_action"):
                if key in state:
                    parts.append(f"{key}={state[key]}")
            return [f"State [{self._session_name}]: " + (", ".join(parts) if parts else "available")]
        return [f"State: {state}"]

    def _render_history_summary(self) -> List[str]:
        if self._history_provider is None:
            return ["History unavailable."]
        try:
            history = self._history_provider(self._user_id, self._session_name)
        except Exception as exc:
            log.warning("CLIChannel history provider failed: %s", exc)
            return ["History unavailable."]
        if not history:
            return ["History: empty"]
        rendered = ["History:"]
        for item in list(history)[-5:]:
            if isinstance(item, Mapping):
                user_message = str(item.get("user_message", "") or "")
                reply = str(item.get("reply", "") or item.get("assistant_reply", "") or "")
            else:
                user_message = str(getattr(item, "user_message", "") or "")
                reply = str(getattr(item, "assistant_reply", "") or getattr(item, "reply", "") or "")
            rendered.append(f"- user: {user_message}")
            if reply:
                rendered.append(f"  helios: {reply}")
        return rendered

    def _render_banner(self) -> List[str]:
        return [
            "Helios CLI ready.",
            f"Session: {self._session_name} | User: {self._user_id}",
            f"Type text to talk, or {self._command_prefix}help for commands.",
        ]

    def _render_help_lines(self) -> List[str]:
        prefix = self._command_prefix
        return [
            "CLI commands:",
            f"- {prefix}help    Show this help summary.",
            f"- {prefix}state   Show a controlled runtime state summary.",
            f"- {prefix}history Show recent exchange history for this session.",
            f"- {prefix}quit    Request orderly shutdown.",
            "Plain text is treated as ordinary user input and enters the tick-driven channel path.",
        ]

    def _write_lines(self, lines: List[str]) -> None:
        with self._render_lock:
            for line in lines:
                self._stdout_writer(f"{str(line).rstrip(chr(10)).rstrip(chr(13))}\n")

    @staticmethod
    def _split_render_lines(text: str) -> List[str]:
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        parts = normalized.split("\n")
        return parts if parts else [""]