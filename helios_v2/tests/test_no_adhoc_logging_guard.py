"""Repository guard: the R21 observability owner is the single logging mechanism.

This test enforces plan C for unified logging. Any module under `helios_v2/src` that
introduces `import logging`, a logger acquisition, or a `print(` call fails this guard.
The only legal logging mechanism in Helios v2 is the `helios_v2.observability` owner,
which itself uses neither `logging` nor `print`.
"""

from __future__ import annotations

import re
from pathlib import Path

# Source root scanned by the guard.
_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "helios_v2"

# Forbidden patterns. The observability owner emits structured events; it does not use
# the stdlib logging module or print, so no module under src is exempt.
_FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("import logging", re.compile(r"^\s*import\s+logging\b", re.MULTILINE)),
    ("from logging import", re.compile(r"^\s*from\s+logging\b", re.MULTILINE)),
    ("getLogger", re.compile(r"\bgetLogger\s*\(")),
    ("print(", re.compile(r"(?<![\w.])print\s*\(")),
)


def _iter_source_files() -> list[Path]:
    return [
        path
        for path in _SRC_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def test_src_tree_has_no_adhoc_logging_or_print() -> None:
    source_files = _iter_source_files()
    assert source_files, "Expected to find Python source files under helios_v2/src"

    violations: list[str] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for label, pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(text):
                violations.append(f"{path}: forbidden pattern '{label}'")

    assert not violations, (
        "Ad-hoc logging is forbidden; the R21 observability owner is the single logging "
        "mechanism. Violations:\n" + "\n".join(violations)
    )
