"""R95 followup: regression guard that the engine and planner do not
hardcode specific op-name strings.

The R95 spirit: the channel subsystem is the SOLE source of truth for op
names. The engine and the planner must not name ops; they read driver
self-descriptions (the `ChannelOpSpec` from each driver's descriptor) and
let upstream contract validation enforce the contract.

This test file fails (clearly) if `engine.py` or `planner_bridge/engine.py`
ever re-introduces a literal op-name string outside of an explanatory
comment. The shim layer (composition/bridges.py) is allowed to carry
`_FIRST_VERSION_SYNTHETIC_CLI_OPS` because the shim is the explicit first-
version channel-state policy; production paths (semantic assembly with
real `frame.channel_state`) do not depend on the shim's literal.

Forbidden literals (any of):
- `reply_message` (cli's reply op)
- `send_message` (qq's send op, voice's send op)
- `speak_text` (voice's speak op)
- `fs_read` / `fs_write` (fs_sandbox ops)

These names are owned by the channel drivers (`channel/drivers/cli.py`,
etc.). The engine and the planner should only read them as opaque strings
returned by driver self-description.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INTERNAL_THOUGHT_ENGINE = (
    REPO_ROOT / "src" / "helios_v2" / "internal_thought" / "engine.py"
)
PLANNER_BRIDGE_ENGINE = (
    REPO_ROOT / "src" / "helios_v2" / "planner_bridge" / "engine.py"
)
ACTION_EXTERNALIZATION_ENGINE = (
    REPO_ROOT / "src" / "helios_v2" / "action_externalization" / "engine.py"
)

FORBIDDEN_OP_LITERALS: tuple[str, ...] = (
    "reply_message",
    "send_message",
    "speak_text",
    "fs_read",
    "fs_write",
)

# R95 followup C1: composition/bridges.py may carry
# `_FIRST_VERSION_SYNTHETIC_CLI_OPS` (the shim's declared policy). Other
# literals in composition/bridges.py are tested separately (the shim is
# the SOLE allowed exception).


def _strip_triple_quoted_strings(text: str) -> str:
    return re.sub(r'"""[\s\S]*?"""', "", text)


def _strip_line_comments(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text)


def _extract_code_lines(path: Path) -> list[tuple[int, str]]:
    """Return (line_number, line) for non-comment, non-docstring lines."""
    text = path.read_text(encoding="utf-8")
    text = _strip_triple_quoted_strings(text)
    text = _strip_line_comments(text)
    lines: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            lines.append((line_no, line))
    return lines


def _assert_no_op_name_literal(path: Path, literal: str) -> None:
    """Fail if `path` contains `literal` as a quoted string in code (not comment)."""
    quoted_variants = (f'"{literal}"', f"'{literal}'")
    for line_no, line in _extract_code_lines(path):
        for variant in quoted_variants:
            if variant in line:
                raise AssertionError(
                    f"R95 followup: {path.name} contains forbidden op-name "
                    f"literal {variant!r} in code at line {line_no}. The "
                    f"{path.parent.name} engine must not name ops; the "
                    f"channel driver subsystem is the SOLE source of truth. "
                    f"Line: {line.strip()}"
                )


def test_internal_thought_engine_does_not_hardcode_op_names() -> None:
    """R95 followup (C3): the engine's offline default derives from
    `request.prompt_contract_summary['available_channel_ops']`; no
    op-name literal lives in the engine code."""
    for literal in FORBIDDEN_OP_LITERALS:
        _assert_no_op_name_literal(INTERNAL_THOUGHT_ENGINE, literal)


def test_planner_bridge_engine_does_not_hardcode_op_names() -> None:
    """R95 followup (C4): the planner's `_missing_required_input` fallback
    is REMOVED. The planner no longer carries a hardcoded set of outbound
    op names; it reads the op's `required_params` from the driver's spec.
    No op-name literal lives in the planner code."""
    for literal in FORBIDDEN_OP_LITERALS:
        _assert_no_op_name_literal(PLANNER_BRIDGE_ENGINE, literal)


def test_action_externalization_engine_does_not_hardcode_op_names() -> None:
    """R95 followup (C3 adjacent): the action-externalization engine
    normalizes the LLM's `tool_op` (or the offline `behavior_name`) into
    a `requested_op` for the planner. The engine should treat the op
    name as opaque — the planner keys off the op spec. No op-name
    literal lives in the action-externalization engine code."""
    for literal in FORBIDDEN_OP_LITERALS:
        _assert_no_op_name_literal(ACTION_EXTERNALIZATION_ENGINE, literal)
