"""Write ``<workspace>/paper/paper_meta.yaml`` from JSON args.

This module is *not* itself interactive.  The
``agentsociety-paper-orchestrator`` plugin skill instructs Claude to
conduct the intake interview per ``stages/intake.md``, collect
title / authors / affils / availability URLs / target journal as a JSON
blob, and pass it to :func:`write_meta_from_json` via the CLI.

The interview pattern mirrors ``agentsociety-create-agent`` -- non-LLM
code only validates and persists the structured result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml

from agentsociety2.skills.paper.models import (
    Affiliation,
    Author,
    PaperMeta,
)
from agentsociety2.skills.paper.paths import paper_meta_path, paper_root


def _coerce_authors(raw: Any) -> list[Author]:
    if not isinstance(raw, list):
        raise ValueError("paper_meta.authors must be a list")
    out: list[Author] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each author must be a JSON object")
        author = Author(
            name=str(entry.get("name", "")).strip(),
            affils=[int(x) for x in (entry.get("affils") or [])],
            email=(str(entry["email"]).strip() if entry.get("email") else None),
            corresponding=bool(entry.get("corresponding", False)),
        )
        if not author.name:
            raise ValueError("author.name cannot be empty")
        out.append(author)
    if not out:
        raise ValueError("at least one author is required")
    return out


def _coerce_affils(raw: Any) -> list[Affiliation]:
    if not isinstance(raw, list):
        raise ValueError("paper_meta.affils must be a list")
    out: list[Affiliation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each affil must be a JSON object")
        aff = Affiliation(id=int(entry["id"]), name=str(entry["name"]).strip())
        if not aff.name:
            raise ValueError("affil.name cannot be empty")
        out.append(aff)
    if not out:
        raise ValueError("at least one affiliation is required")
    return out


def build_meta_from_dict(payload: Dict[str, Any]) -> PaperMeta:
    """Validate ``payload`` and return a :class:`PaperMeta` instance."""

    title = str(payload.get("title", "")).strip()
    if not title:
        raise ValueError("paper_meta.title is required")

    authors = _coerce_authors(payload.get("authors"))
    affils = _coerce_affils(payload.get("affils"))

    affil_ids = {a.id for a in affils}
    for author in authors:
        for ref in author.affils:
            if ref not in affil_ids:
                raise ValueError(
                    f"author '{author.name}' references unknown affil id {ref}"
                )

    if not any(a.corresponding for a in authors):
        # Convention: mark the last author corresponding when none flagged
        authors[-1].corresponding = True

    return PaperMeta(
        title=title,
        authors=authors,
        affils=affils,
        data_availability_url=(payload.get("data_availability_url") or None),
        code_availability_url=(payload.get("code_availability_url") or None),
        target_journal=(payload.get("target_journal") or None),
    )


def write_meta_from_json(
    workspace_path: Path | str,
    *,
    payload: Dict[str, Any] | str,
) -> Path:
    """Write ``paper_meta.yaml`` to ``<workspace>/paper/``.

    ``payload`` may be a pre-decoded ``dict`` or a JSON string.  Returns
    the path to the written file.
    """

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("payload must decode to a JSON object")

    meta = build_meta_from_dict(payload)
    out_dir = paper_root(workspace_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = paper_meta_path(workspace_path)
    out_path.write_text(
        yaml.safe_dump(
            meta.model_dump(mode="json", exclude_none=True),
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return out_path


def load_meta(workspace_path: Path | str) -> PaperMeta:
    """Load ``paper_meta.yaml``; raises ``FileNotFoundError`` if absent."""

    path = paper_meta_path(workspace_path)
    if not path.exists():
        raise FileNotFoundError(
            f"paper_meta.yaml not found at {path}; run `paper-orchestrator init-meta` first."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PaperMeta.model_validate(raw)


__all__ = [
    "build_meta_from_dict",
    "write_meta_from_json",
    "load_meta",
]
