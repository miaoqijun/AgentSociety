"""CRUD for ``state/research_pack.json`` (paper-adapter output)."""

from __future__ import annotations

import json
from typing import Dict, List

from agentsociety2.skills.paper.models import ProvenanceEntry, ResearchPack
from agentsociety2.skills.paper.paths import (
    PathLike,
    research_pack_path,
    state_dir,
)


def load(workspace_path: PathLike) -> ResearchPack:
    """Load ResearchPack from disk.

    Raises FileNotFoundError if the pack has not been built yet - callers
    should use :func:`exists` to gate on this and route through the adapter.
    """

    path = research_pack_path(workspace_path)
    if not path.exists():
        raise FileNotFoundError(
            f"research_pack.json not found at {path}. Run the paper-adapter first."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ResearchPack.model_validate(raw)


def save(workspace_path: PathLike, pack: ResearchPack) -> None:
    """Persist ``pack`` as JSON."""

    state_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    path = research_pack_path(workspace_path)
    path.write_text(
        json.dumps(pack.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def exists(workspace_path: PathLike) -> bool:
    return research_pack_path(workspace_path).exists()


def provenance_map(pack: ResearchPack) -> Dict[str, ProvenanceEntry]:
    """Return ``{artifact_id: ProvenanceEntry}`` for fast lookup."""

    return {entry.artifact_id: entry for entry in pack.provenance}


def low_confidence_entries(pack: ResearchPack) -> List[ProvenanceEntry]:
    """Return provenance entries flagged as low-confidence."""

    return [entry for entry in pack.provenance if entry.confidence == "low"]


__all__ = [
    "load",
    "save",
    "exists",
    "provenance_map",
    "low_confidence_entries",
]
