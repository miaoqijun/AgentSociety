#!/usr/bin/env python3
"""Web research CLI script"""

import asyncio
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from workspace .env file
workspace_root = Path(__file__).resolve().parents[4]
env_file = workspace_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Add the workspace root to Python path
import sys

sys.path.insert(0, str(workspace_root / "packages" / "agentsociety2"))


def _import_execute_web_research():
    """Lazy import of agentsociety2.skills.web_research.execute_web_research.

    Kept inside a function so this script's --help and argument parsing
    work even if agentsociety2 is not installed; the import error is only
    raised when the command actually needs to execute the web research.
    """
    try:
        from agentsociety2.skills.web_research import execute_web_research
    except ImportError as exc:
        raise SystemExit(
            "agentsociety2 is not available in the current Python interpreter. "
            "Install it (e.g. `uv sync` from the workspace root) and retry. "
            f"Original error: {exc}"
        )
    return execute_web_research


async def main():
    parser = argparse.ArgumentParser(description="Perform web research")
    parser.add_argument("query", help="Research query")
    parser.add_argument("--llm", help="LLM model name")
    parser.add_argument("--agent", help="Agent configuration name")

    args = parser.parse_args()

    execute_web_research = _import_execute_web_research()
    result = await execute_web_research(
        query=args.query,
        llm=args.llm,
        agent=args.agent,
    )

    if result.get("success"):
        print(result.get("content", "Success"))
        return 0
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
