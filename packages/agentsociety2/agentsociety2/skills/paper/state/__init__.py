"""State module - YAML/JSON CRUD over <workspace>/paper/state and artifacts.

Each submodule owns one persisted artifact: it defines load/save plus a
small set of artifact-specific helpers (e.g. ``unsupported_claims`` on
:mod:`claim_ledger`, ``filter_auto_executable`` on :mod:`evidence_backlog`).

The submodules import only :mod:`agentsociety2.skills.paper.paths` and
:mod:`agentsociety2.skills.paper.models`; no LLM or workspace-discovery
logic lives here.
"""

from __future__ import annotations

from agentsociety2.skills.paper.state import (
    claim_ledger,
    evidence_backlog,
    figure_argument,
    human_gates,
    paper_state,
    research_pack,
    reviews,
    runs,
    storyline,
)

__all__ = [
    "claim_ledger",
    "evidence_backlog",
    "figure_argument",
    "human_gates",
    "paper_state",
    "research_pack",
    "reviews",
    "runs",
    "storyline",
]
