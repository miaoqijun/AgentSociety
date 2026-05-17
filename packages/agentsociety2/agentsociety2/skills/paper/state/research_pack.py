"""CRUD for ``state/research_pack.json`` (paper-adapter output)."""

from __future__ import annotations

import json
import re
from typing import Dict, List

from agentsociety2.skills.paper.models import (
    ProvenanceEntry,
    ResearchPack,
    ResearchPackLiterature,
    ResearchPackReferencePool,
)
from agentsociety2.skills.paper.paths import (
    PathLike,
    research_pack_path,
    state_dir,
)


def _normalize_ref_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _literature_identity(entry: ResearchPackLiterature) -> str:
    if entry.cite_key.strip():
        return f"cite:{entry.cite_key.strip().lower()}"
    if entry.doi.strip():
        return f"doi:{entry.doi.strip().lower()}"
    title = _normalize_ref_text(entry.title)
    year = entry.year.strip()
    return f"title:{title}|{year}"


def _merge_literature_pair(
    preferred: ResearchPackLiterature,
    fallback: ResearchPackLiterature,
) -> ResearchPackLiterature:
    merged = preferred.model_copy(deep=True)
    for field in ("cite_key", "title", "authors", "year", "doi", "journal", "bibtex"):
        if not getattr(merged, field) and getattr(fallback, field):
            setattr(merged, field, getattr(fallback, field))
    return merged


def dedupe_literature(
    entries: List[ResearchPackLiterature],
) -> List[ResearchPackLiterature]:
    """Return literature entries deduplicated by cite_key/doi/title-year."""

    deduped: List[ResearchPackLiterature] = []
    by_identity: dict[str, ResearchPackLiterature] = {}
    for entry in entries:
        identity = _literature_identity(entry)
        current = by_identity.get(identity)
        if current is None:
            clone = entry.model_copy(deep=True)
            by_identity[identity] = clone
            deduped.append(clone)
            continue
        merged = _merge_literature_pair(current, entry)
        by_identity[identity] = merged
        current.cite_key = merged.cite_key
        current.title = merged.title
        current.authors = merged.authors
        current.year = merged.year
        current.doi = merged.doi
        current.journal = merged.journal
        current.bibtex = merged.bibtex
    return deduped


def effective_literature(pack: ResearchPack) -> List[ResearchPackLiterature]:
    """Return the effective literature set, honoring reference_pool when present."""

    pool = pack.reference_pool
    if pool is None:
        return dedupe_literature(pack.literature)
    return dedupe_literature([*pool.workspace_refs, *pool.supplemental_refs])


def refresh_reference_pool(
    pack: ResearchPack,
    previous_pack: ResearchPack | None = None,
) -> ResearchPack:
    """Rebuild the incremental reference pool for a freshly scanned research pack."""

    workspace_refs = dedupe_literature(pack.literature)
    workspace_ids = {_literature_identity(entry) for entry in workspace_refs}

    previous_effective = effective_literature(previous_pack) if previous_pack is not None else []
    supplemental_refs = dedupe_literature(
        [
            entry
            for entry in previous_effective
            if _literature_identity(entry) not in workspace_ids
        ]
    )

    updated = pack.model_copy(deep=True)
    updated.reference_pool = ResearchPackReferencePool(
        workspace_refs=workspace_refs,
        supplemental_refs=supplemental_refs,
    )
    updated.literature = effective_literature(updated)
    return updated


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

    normalized = pack.model_copy(deep=True)
    normalized.literature = effective_literature(normalized)
    state_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    path = research_pack_path(workspace_path)
    path.write_text(
        json.dumps(normalized.model_dump(mode="json"), ensure_ascii=False, indent=2),
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
    "exists",
    "effective_literature",
    "load",
    "low_confidence_entries",
    "provenance_map",
    "refresh_reference_pool",
    "save",
    "dedupe_literature",
]
