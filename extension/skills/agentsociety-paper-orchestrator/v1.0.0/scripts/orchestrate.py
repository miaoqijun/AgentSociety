#!/usr/bin/env python3
"""Workspace-side launcher for the paper-orchestrator CLI.

`ags.py paper-orchestrator <subcommand> ...` resolves to this script,
which delegates to
:func:`agentsociety2.skills.paper.cli.generate_paper.main`.

The Python CLI handles env sentinel defaults internally so this script
stays as small as possible.
"""

from __future__ import annotations

import sys


def main() -> int:
    # Lazy-import: ``main()`` itself sets sentinel ``AGENTSOCIETY_LLM_*``
    # values before triggering the agentsociety2 package init cascade.
    try:
        from agentsociety2.skills.paper.cli.generate_paper import main as cli_main
    except ModuleNotFoundError as exc:
        sys.stderr.write(
            "agentsociety2 is not available in the current Python interpreter. "
            "Run via the workspace launcher: "
            "`$PYTHON_PATH .agentsociety/bin/ags.py paper-orchestrator ...`.\n"
        )
        sys.stderr.write(f"underlying error: {exc}\n")
        return 1
    return int(cli_main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
