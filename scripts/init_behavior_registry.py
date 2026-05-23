"""Initialize the SQLite behavior registry database."""

from __future__ import annotations

import argparse
from pathlib import Path

from behavior_registry import ensure_behavior_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize the Helios behavior registry database.")
    parser.add_argument(
        "--db-path",
        default=str(Path("data") / "behavior_registry.sqlite3"),
        help="Path to the SQLite behavior registry database.",
    )
    args = parser.parse_args()
    registry = ensure_behavior_registry(args.db_path)
    print(f"Behavior registry initialized at {registry.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())