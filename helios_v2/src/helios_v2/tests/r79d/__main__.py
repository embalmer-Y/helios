"""Allow `python -m helios_v2.tests.r79d ...` invocation."""
from .cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
