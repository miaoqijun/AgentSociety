"""CRUD for ``artifacts/figure_argument_map.{md,json}``."""

from __future__ import annotations

import json
from typing import List, Optional

from agentsociety2.skills.paper.models import FigureArgumentMap, FigureSpec
from agentsociety2.skills.paper.paths import (
    PathLike,
    artifacts_dir,
    figure_argument_json_path,
    figure_argument_md_path,
)


def load(workspace_path: PathLike) -> Optional[FigureArgumentMap]:
    path = figure_argument_json_path(workspace_path)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FigureArgumentMap.model_validate(raw)


def save(workspace_path: PathLike, fmap: FigureArgumentMap) -> None:
    artifacts_dir(workspace_path).mkdir(parents=True, exist_ok=True)
    figure_argument_json_path(workspace_path).write_text(
        json.dumps(fmap.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    figure_argument_md_path(workspace_path).write_text(
        render_markdown(fmap),
        encoding="utf-8",
    )


def render_markdown(fmap: FigureArgumentMap) -> str:
    lines: list[str] = ["# Figure-Argument Map", ""]
    if not fmap.figures:
        lines.append("_No figures planned yet._")
        return "\n".join(lines) + "\n"
    for fig in fmap.figures:
        lines.append(f"## {fig.figure_id}: {fig.title or '(untitled)'}")
        lines.append(f"- **status**: {fig.status} | **target section**: {fig.target_section or '-'}")
        if fig.question_answered:
            lines.append(f"- **question answered**: {fig.question_answered}")
        if fig.claim_supported:
            lines.append("- **claims supported**: " + ", ".join(fig.claim_supported))
        if fig.alternative_explanation_addressed:
            lines.append(
                "- **alternative explanations addressed**: "
                + ", ".join(fig.alternative_explanation_addressed)
            )
        if fig.file_path:
            lines.append(f"- **file**: {fig.file_path}")
        if fig.panels:
            lines.append("- **panels**:")
            for idx, panel in enumerate(fig.panels):
                label = chr(ord("a") + idx) if idx < 26 else f"p{idx}"
                lines.append(f"  - **{label}.** {panel}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def panels_missing_for(fmap: FigureArgumentMap, claim_id: str) -> List[FigureSpec]:
    """Return figure specs that *should* support ``claim_id`` but lack panels.

    Useful for the figure-logic reviewer: a figure linked to a claim with
    no concrete panel descriptions is suspect.
    """

    out: list[FigureSpec] = []
    for fig in fmap.figures:
        if claim_id not in fig.claim_supported:
            continue
        if not fig.panels:
            out.append(fig)
    return out


def by_section(fmap: FigureArgumentMap, section: str) -> List[FigureSpec]:
    return [fig for fig in fmap.figures if fig.target_section == section]


def exists(workspace_path: PathLike) -> bool:
    return figure_argument_json_path(workspace_path).exists()


__all__ = [
    "load",
    "save",
    "render_markdown",
    "panels_missing_for",
    "by_section",
    "exists",
]
