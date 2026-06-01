from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import helios_main


def test_main_applies_explicit_cli_args(monkeypatch):
    captured: dict[str, object] = {}

    class FakeHelios:
        def __init__(self, config):
            captured["config"] = config

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "helios_main.py",
            "--interval",
            "0.2",
            "--cli",
            "--cli-user-id",
            "operator-a",
            "--cli-session-name",
            "shell-a",
        ],
    )
    monkeypatch.setattr(helios_main, "Helios", FakeHelios)

    helios_main.main()

    config = captured["config"]
    assert config.TICK_INTERVAL == 0.2
    assert config.CLI_ENABLED is True
    assert config.CLI_USER_ID == "operator-a"
    assert config.CLI_SESSION_NAME == "shell-a"
    assert captured["started"] is True


def test_main_can_disable_cli_explicitly(monkeypatch):
    captured: dict[str, object] = {}

    class FakeHelios:
        def __init__(self, config):
            captured["config"] = config

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(sys, "argv", ["helios_main.py", "--no-cli"])
    monkeypatch.setattr(helios_main, "Helios", FakeHelios)

    helios_main.main()

    config = captured["config"]
    assert config.CLI_ENABLED is False
    assert captured["started"] is True