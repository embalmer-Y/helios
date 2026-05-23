"""Initialize the SQLite memory backend database."""

from __future__ import annotations

import argparse
from pathlib import Path

from memory import ensure_sqlite_memory_backend


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the Helios SQLite memory backend database.")
    parser.add_argument(
        "--db-path",
        default=str(Path("data") / "memory_backend.sqlite3"),
        help="Path to the SQLite memory backend database.",
    )
    args = parser.parse_args()
    backend = ensure_sqlite_memory_backend(args.db_path)
    print(f"Memory backend initialized at {backend.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())