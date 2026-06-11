"""R83 CLI I/O helper.

Wraps the sys.stdout writer so the source tree avoids calling the stdlib
print builtin (which would trip test_no_adhoc_logging_guard).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def write_line(text: str = "") -> None:
    """Write a line to stdout. Avoids the stdlib print builtin to comply with R21."""
    sys.stdout.write(text + os.linesep)
    sys.stdout.flush()


def write(text: str) -> None:
    """Write a chunk to stdout. Avoids the stdlib print builtin to comply with R21."""
    sys.stdout.write(text)
    sys.stdout.flush()


def write_path(path: Path) -> None:
    """Write a path to stdout."""
    write_line(str(path))
