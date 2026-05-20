#!/usr/bin/env python3
"""CLI wrapper for literature full-text helpers."""

from __future__ import annotations

import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(workspace_root / "packages" / "agentsociety2"))

from agentsociety2.skills.literature.full_text import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
