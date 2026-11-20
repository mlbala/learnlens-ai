"""python -m app.guardrails_harness"""

from __future__ import annotations

import sys

from app.guardrails_harness.cli import main

if __name__ == "__main__":
    sys.exit(main())
