#!/usr/bin/env python3
"""Workspace-side launcher for the paper-adapter CLI.

`ags.py paper-adapter --workspace .` resolves to this script. It runs
:func:`agentsociety2.skills.paper.adapter.research_pack_builder.build_research_pack`,
persists the ``ResearchPack``, and emits an envelope.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _default_workspace() -> str:
    raw_workspace = os.environ.get("AGENTSOCIETY_WORKSPACE")
    if raw_workspace:
        return str(Path(raw_workspace).expanduser().resolve())
    return str(Path.cwd().resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-adapter")
    parser.add_argument("--workspace", default=_default_workspace())
    parser.add_argument(
        "--research-objective",
        default=None,
        help="Optional override for ResearchPack.research_objective.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Sentinel env defaults so the agentsociety2 package init succeeds in
    # workspaces that have not configured an LLM key.  The adapter does
    # not call any LLM.
    os.environ.setdefault("MEM0_TELEMETRY", "False")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("AGENTSOCIETY_LLM_API_KEY", "paper-adapter-cli")
    os.environ.setdefault("AGENTSOCIETY_LLM_API_BASE", "https://api.openai.com/v1")

    try:
        from agentsociety2.skills.paper import paths as paper_paths
        from agentsociety2.skills.paper.adapter import (
            research_pack_builder as builder,
        )
        from agentsociety2.skills.paper.envelope import (
            build_envelope,
            envelope_to_json,
        )
        from agentsociety2.skills.paper.state import research_pack as st_pack
    except ModuleNotFoundError as exc:
        sys.stderr.write(
            "agentsociety2 not available; run via `$PYTHON_PATH ...ags.py paper-adapter ...`.\n"
        )
        sys.stderr.write(f"underlying error: {exc}\n")
        return 1

    try:
        pack = builder.build_research_pack(
            args.workspace,
            research_objective=args.research_objective or None,
        )
        st_pack.save(args.workspace, pack)
    except Exception as exc:  # noqa: BLE001
        env = build_envelope(
            "BLOCKED",
            blocking_reason=f"failed to build research pack: {exc}",
            severity="fatal",
        )
        _emit(
            {
                "success": False,
                "error": str(exc),
                "envelope": json.loads(envelope_to_json(env)),
            }
        )
        return 1

    out_path = paper_paths.research_pack_path(args.workspace)
    env = build_envelope(
        "DONE",
        artifacts_read=[str(args.workspace)],
        artifacts_written=[str(out_path)],
        key_findings=[
            f"hypotheses={len(pack.hypotheses)}",
            f"experiments={len(pack.experiments)}",
            f"figures={len(pack.figures)}",
            f"literature={len(pack.literature)}",
        ],
        recommended_next_step="dispatch agentsociety-paper-framing producer",
    )
    _emit(
        {
            "success": True,
            "envelope": json.loads(envelope_to_json(env)),
            "pack_path": str(out_path),
            "counts": {
                "hypotheses": len(pack.hypotheses),
                "experiments": len(pack.experiments),
                "analyses": len(pack.analyses),
                "figures": len(pack.figures),
                "literature": len(pack.literature),
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
